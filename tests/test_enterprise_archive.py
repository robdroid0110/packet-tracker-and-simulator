import json
import tempfile
import unittest
from copy import deepcopy
from pathlib import Path
from netsim.model import NetworkLab,LabError
from netsim.enterprise_training import action,view
from netsim.enterprise_archive import progress,report
from test_enterprise_assessment import start,until,payload
import test_physical_special_notes_http as isolated

SMALL={"departments":2,"hosts_per_department":1}
OTHER={"departments":3,"hosts_per_department":1}

def restart(lab,cfg=SMALL):
    v=view(lab)
    action(lab,{"action":"restart","mode":"assessment","config":cfg,"run_id":v["run_id"],"step":v["step"]})

def retention(lab,value):
    action(lab,{"action":"set_retention","limit":value,"expected_limit":lab.enterprise_archive["limit"]})

class ArchiveTests(unittest.TestCase):
    def test_comparison_retention_and_persistence(self):
        lab=NetworkLab();start(lab,SMALL)
        first=until(lab,"completed",False)
        restart(lab);second=until(lab,"completed")
        restart(lab,OTHER);third=until(lab,"completed")
        p=progress(lab);self.assertEqual(p["retained"],3)
        g=next(g for g in p["groups"] if g["config"]==SMALL)
        self.assertEqual((g["first"],g["latest"],g["best"],g["change"]),(55,100,100,45))
        self.assertEqual(len(p["groups"]),2)
        self.assertEqual(next(c["change"] for c in g["criteria"] if c["id"]=="evidence_supported_root_cause"),15)
        self.assertEqual(report(lab,first["run_id"])["report"],first["report"])
        self.assertIsNotNone(p["attempts"][0]["completed_at"])
        retention(lab,2);p=progress(lab)
        self.assertEqual((p["retained"],p["evicted"],p["limit"]),(2,1,2))
        with self.assertRaises(LabError):report(lab,first["run_id"])
        self.assertEqual(report(lab,second["run_id"])["report"],second["report"])
        with tempfile.TemporaryDirectory() as d:
            path=Path(d)/"lab.json";lab.save(str(path));restored=NetworkLab();restored.load(str(path))
            self.assertEqual(progress(restored),p)
            self.assertEqual(report(restored,third["run_id"]),report(lab,third["run_id"]))
            raw=json.loads(path.read_text());raw["enterprise_archive"]["entries"][0]["run"]["observations"]["fault"]["component"]["outcome"]="success"
            path.write_text(json.dumps(raw))
            with self.assertRaises(LabError):NetworkLab().load(str(path))
        restart(lab);self.assertEqual(progress(lab),p)
        retention(lab,1);self.assertEqual(progress(lab)["retained"],1)
        retention(lab,24);self.assertEqual(progress(lab)["retained"],1)
        until(lab,"completed")
        self.assertEqual([r["sequence"] for r in progress(lab)["attempts"]],[3,4])

    def test_invalid_retention_is_atomic(self):
        lab=NetworkLab();before=lab.to_dict()
        for value in (True,0,25,"12",1.5):
            with self.assertRaises(LabError):retention(lab,value)
            self.assertEqual(lab.to_dict(),before)
        with self.assertRaises(LabError):action(lab,{"action":"set_retention","limit":2,"expected_limit":1})
        self.assertEqual(lab.to_dict(),before)

    def test_migrate_completed_and_ignore_incomplete_legacy(self):
        lab=NetworkLab();start(lab,SMALL);v=until(lab,"completed")
        raw=lab.to_dict();raw.pop("enterprise_archive")
        with tempfile.TemporaryDirectory() as d:
            path=Path(d)/"lab.json";path.write_text(json.dumps(raw));restored=NetworkLab();restored.load(str(path))
            self.assertEqual(progress(restored)["retained"],1)
            self.assertIsNone(progress(restored)["attempts"][0]["completed_at"])
            self.assertEqual(report(restored,v["run_id"])["report"],v["report"])
            raw=restored.to_dict();raw["enterprise_archive"]["entries"]=[]
            path.write_text(json.dumps(raw))
            with self.assertRaises(LabError):NetworkLab().load(str(path))
        restart(lab);self.assertEqual(progress(lab)["retained"],1)
        legacy=NetworkLab();action(legacy,{"action":"start","config":SMALL});until(legacy,"completed")
        self.assertEqual(progress(legacy)["retained"],0)

class ArchiveHTTPTests(unittest.TestCase):
    setUpClass=isolated.PhysicalSpecialNotesHTTPTests.__dict__["setUpClass"]
    tearDownClass=isolated.PhysicalSpecialNotesHTTPTests.__dict__["tearDownClass"]
    setUp=isolated.PhysicalSpecialNotesHTTPTests.setUp
    request=isolated.PhysicalSpecialNotesHTTPTests.request

    def test_api_history_read_only_and_undo(self):
        base="/api/cyber-range/enterprise"
        status,data=self.request(base+"/action",{"action":"start","config":SMALL,"mode":"assessment"})
        self.assertEqual(status,200,data);v=data["enterprise"]
        while v["next_action"]:
            status,data=self.request(base+"/action",payload(v));self.assertEqual(status,200,data);v=data["enterprise"]
        url=base+"/report?run_id="+v["run_id"]
        before=self.app.STATE.read_bytes()
        self.assertEqual(self.request(url)[1]["report"],v["report"])
        self.assertEqual(self.request(base+"/archive")[1]["retained"],1)
        self.assertEqual(self.app.STATE.read_bytes(),before)
        self.assertEqual(self.request(url+"&run_id=x")[0],400)
        self.assertEqual(self.request(base+"/archive?foo=x")[0],400)
        self.assertEqual(self.request(base+"/action",{"action":"set_retention","limit":1,"expected_limit":12})[0],200)
        self.assertEqual(self.request(base+"/archive")[1]["limit"],1)
        self.request("/api/command",{"command":"undo"})
        self.assertEqual(self.request(base+"/archive")[1]["limit"],12)
        self.request("/api/command",{"command":"undo"})
        self.assertEqual(self.request(url)[0],400)
        self.request("/api/command",{"command":"redo"})
        self.assertEqual(self.request(url)[1]["report"],v["report"])
        self.assertEqual(self.request("/api/cyber-range/exercises")[1]["progress"]["retained"],0)

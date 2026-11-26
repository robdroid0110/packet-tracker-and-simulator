import json
import tempfile
import unittest
from copy import deepcopy
from pathlib import Path
from netsim.model import NetworkLab, LabError
from netsim.exercise_runner import action, view, archived_report, ARCHIVE_LIMIT
from netsim.exercise_library import TEMPLATES
import test_physical_special_notes_http as isolated

def body(v,op,**kw):
    return {"action":op,**({} if op=="start" else {"run_id":v["run_id"],"step":v["step"]}),**kw}

def fields(v,correct=True):
    r=v["report"];c=r["observations"];op=v["next_action"]
    if op=="acknowledge":return {"event_id":v["primary_failure_event_id"]}
    if op=="assess":
        refs={role:c[p][k]["id"] for role,p,k in [
            ("baseline_icmp","baseline","icmp"),("baseline_http","baseline","http"),
            ("fault_icmp","fault","icmp"),("fault_http","fault","http"),("component_state","fault","component")]}
        return {"diagnosis":TEMPLATES[r["template"]]["diagnosis"] if correct else "insufficient_evidence",
                "references":refs,"note":"Reviewed modeled evidence."}
    if op=="verify_recovery":
        latest=c[v["verification_phase"]]
        return {"icmp_event_id":latest["icmp"]["id"],"http_event_id":latest["http"]["id"]}
    return {}

def finish(lab,correct=True):
    while (v:=view(lab))["next_action"]:
        action(lab,body(v,v["next_action"],**fields(v,correct)))
    return view(lab)

class LibraryTests(unittest.TestCase):
    def test_all_templates_and_sampled_recovery(self):
        for template in TEMPLATES:
            with self.subTest(template=template):
                lab=NetworkLab();lab.add_device("pc","Existing")
                before=lab.to_dict()
                action(lab,{"action":"start","template":template})
                v=finish(lab);r=v["report"];c=r["observations"]
                self.assertEqual(r["score"]["points"],100)
                self.assertEqual(c["fault"]["icmp"]["outcome"],"success" if template=="http-availability" else "failure")
                self.assertEqual(c["fault"]["http"]["outcome"],"failure")
                self.assertEqual(c["fault"]["component"]["source"],TEMPLATES[template]["component"])
                self.assertEqual(len(r["incidents"]["cases"]),1)
                case=r["incidents"]["cases"][0]
                self.assertEqual(case["status"],"resolved")
                self.assertEqual(case["evidence"][0]["protocol"],"HTTP" if template=="http-availability" else "ICMP")
                self.assertEqual(r["monitoring"]["span_simulated_seconds"],10)
                self.assertEqual(len(r["monitoring"]["samples"]),3)
                self.assertTrue(r["monitoring"]["passed"])
                self.assertEqual(archived_report(lab,v["run_id"])["report"],r)
                after=lab.to_dict();after["exercise_runner"]=None;after["exercise_archive"]=before["exercise_archive"]
                self.assertEqual(before,after)

    def test_progress_archive_and_persistence(self):
        lab=NetworkLab()
        action(lab,{"action":"start","template":"http-availability"})
        first=finish(lab,False);self.assertEqual(first["report"]["score"]["points"],80)
        action(lab,body(first,"restart"));second=finish(lab)
        group=second["progress"]["by_template"][0]
        self.assertEqual((group["completed"],group["first"],group["latest"],group["best"],group["change"]),(2,80,100,100,20))
        action(lab,body(second,"restart",template="server-interface-availability"))
        third=view(lab)
        self.assertEqual(third["progress"]["retained"],2)
        self.assertEqual(third["attempt"],3)
        self.assertEqual(archived_report(lab,first["run_id"])["report"],first["report"])
        with tempfile.TemporaryDirectory() as d:
            p=Path(d)/"lab.json";lab.save(str(p));restored=NetworkLab();restored.load(str(p))
            self.assertEqual(view(restored),third)
            raw=json.loads(p.read_text());raw["exercise_archive"]["runs"][0]["observations"]["fault"]["http"]["outcome"]="success"
            p.write_text(json.dumps(raw))
            with self.assertRaises(LabError):NetworkLab().load(str(p))

    def test_recovery_guards_and_legacy_migration(self):
        lab=NetworkLab();action(lab,{"action":"start","template":"interface-availability"})
        while (v:=view(lab))["status"]!="restored": action(lab,body(v,v["next_action"],**fields(v)))
        before=deepcopy(lab.exercise_runner)
        with self.assertRaises(LabError):action(lab,body(v,"complete"))
        self.assertEqual(before,lab.exercise_runner)
        action(lab,body(v,"monitor_recovery"));v=view(lab)
        c=v["report"]["observations"]
        with self.assertRaises(LabError):action(lab,body(v,"verify_recovery",icmp_event_id=c["recovery"]["icmp"]["id"],http_event_id=c["recovery"]["http"]["id"]))
        self.assertEqual(view(lab),v)
        finish(lab)
        # A legacy v1 completed save is archived on load without regrading.
        legacy=NetworkLab();action(legacy,{"action":"start"})
        from test_exercise_runner import assessment
        while (v:=view(legacy))["next_action"]:
            op=v["next_action"];c=(v["report"] or {}).get("observations",{});kw={}
            if op=="acknowledge":kw={"event_id":c["fault"]["icmp"]["id"]}
            if op=="assess":kw=assessment(c)
            if op=="verify_recovery":kw={"icmp_event_id":c["recovery"]["icmp"]["id"],"http_event_id":c["recovery"]["http"]["id"]}
            action(legacy,body(v,op,**kw))
        raw=legacy.to_dict();raw.pop("exercise_archive")
        with tempfile.TemporaryDirectory() as d:
            p=Path(d)/"lab.json";p.write_text(json.dumps(raw));restored=NetworkLab();restored.load(str(p))
            self.assertEqual(view(restored)["report"],v["report"])
            self.assertEqual(view(restored)["progress"]["retained"],1)

    def test_archive_retention(self):
        lab=NetworkLab();action(lab,{"action":"start","template":"http-availability"})
        first=finish(lab)
        for _ in range(ARCHIVE_LIMIT):
            action(lab,body(view(lab),"restart"));finish(lab)
        p=view(lab)["progress"]
        self.assertEqual((p["retained"],p["evicted"]),(ARCHIVE_LIMIT,1))
        with self.assertRaises(LabError):archived_report(lab,first["run_id"])

class LibraryHTTPTests(unittest.TestCase):
    setUpClass=isolated.PhysicalSpecialNotesHTTPTests.__dict__["setUpClass"]
    tearDownClass=isolated.PhysicalSpecialNotesHTTPTests.__dict__["tearDownClass"]
    setUp=isolated.PhysicalSpecialNotesHTTPTests.setUp
    request=isolated.PhysicalSpecialNotesHTTPTests.request

    def test_archive_endpoint_and_undo(self):
        base="/api/cyber-range/exercises"
        status,data=self.request(base+"/action",{"action":"start","template":"http-availability"})
        self.assertEqual(status,200,data);v=data["exercise"]
        while v["next_action"]:
            op=v["next_action"];status,data=self.request(base+"/action",body(v,op,**fields(v)))
            self.assertEqual(status,200,data);v=data["exercise"]
        url=base+"/report?run_id="+v["run_id"]
        before=self.app.STATE.read_bytes()
        self.assertEqual(self.request(url)[1]["report"],v["report"])
        self.assertEqual(before,self.app.STATE.read_bytes())
        self.assertEqual(self.request(url+"&run_id=x")[0],400)
        self.request("/api/command",{"command":"undo"})
        self.assertEqual(self.request(url)[0],400)
        self.request("/api/command",{"command":"redo"})
        self.assertEqual(self.request(url)[1]["report"],v["report"])

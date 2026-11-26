import json
import tempfile
import unittest
from copy import deepcopy
from pathlib import Path
from netsim.model import NetworkLab, LabError
from netsim.enterprise_training import action,view
import test_physical_special_notes_http as isolated

CFG={"departments":3,"hosts_per_department":2}

def payload(v,op=None,correct=True):
    op=op or v["next_action"];c=v["report"]["observations"]
    b={"action":op,"run_id":v["run_id"],"step":v["step"]}
    if op=="acknowledge":b["event_id"]=c["fault"]["component"]["id"]
    if op=="assess":
        f=c["fault"]["clients"];base=c["baseline"]["clients"]
        b.update(diagnosis="dns_interface_down" if correct else "app_service_down",
                 root_refs={"component":c["fault"]["component"]["id"],"dns":f[0]["dns"]["id"],"direct_http":f[0]["direct_http"]["event"]["id"]},
                 impact_clients=[x["client"] for x in f],impact_departments=sorted({x["department"] for x in f}),
                 impact_refs={x["client"]:{"baseline":y["named_http"]["event"]["id"],"fault":x["named_http"]["event"]["id"]} for x,y in zip(f,base)},
                 note="Reviewed availability evidence.",note_event_id=c["fault"]["component"]["id"])
        if not correct:
            omitted=b["impact_clients"].pop();del b["impact_refs"][omitted]
            b["impact_departments"].pop()
    if op=="resolve":
        z=c["recovery_10s"]
        b.update(dependency_event_id=z["component"]["id"],recovery_refs={x["client"]:{"dns":x["dns"]["id"],"http":x["named_http"]["event"]["id"]} for x in z["clients"]})
    return b

def start(lab,cfg=CFG):
    action(lab,{"action":"start","config":cfg,"mode":"assessment"})

def until(lab,stage,correct=True):
    while (v:=view(lab))["status"]!=stage:
        if not v["next_action"]:raise AssertionError(stage)
        action(lab,payload(v,correct=correct))
    return v

class AnalystTests(unittest.TestCase):
    def test_complete_workflow_and_isolation(self):
        lab=NetworkLab();lab.add_device("pc","Existing");before=lab.to_dict();start(lab)
        v=until(lab,"completed");r=v["report"];p=r["parent_incident"]
        self.assertEqual(r["analyst"]["score"]["points"],100)
        self.assertTrue(p["acknowledged"] and p["analyst_resolved"])
        self.assertEqual((p["status"],p["verified_clients"]),("closed",6))
        after=lab.to_dict();after["enterprise_training"]=None;after["enterprise_archive"]=before["enterprise_archive"];self.assertEqual(after,before)

    def test_incorrect_diagnosis_and_partial_impact_graded(self):
        lab=NetworkLab();start(lab,{"departments":2,"hosts_per_department":1})
        r=until(lab,"completed",False)["report"]
        self.assertEqual(r["analyst"]["score"]["points"],55)
        self.assertEqual(r["parent_incident"]["status"],"closed")
        c={x["id"]:x["met"] for x in r["analyst"]["score"]["criteria"]}
        self.assertFalse(c["evidence_supported_root_cause"])
        self.assertFalse(c["per_client_impact_evidence"])

    def test_guards_and_atomicity(self):
        lab=NetworkLab();start(lab,{"departments":2,"hosts_per_department":1})
        v=until(lab,"fault_observed")
        bad=payload(v);bad["event_id"]=True
        with self.assertRaises(LabError):action(lab,bad)
        v=until(lab,"acknowledged")
        good=payload(v)
        for field,value in (("note"," "),("note_event_id",999999),("impact_clients",["external"]),("impact_departments",["IT","IT"])):
            bad=deepcopy(good);bad[field]=value;before=lab.to_dict()
            with self.assertRaises(LabError):action(lab,bad)
            self.assertEqual(lab.to_dict(),before)
        v=until(lab,"restored")
        with self.assertRaises(LabError):action(lab,{"action":"complete","run_id":v["run_id"],"step":v["step"]})
        v=until(lab,"recovery_verified");good=payload(v)
        for change in ("omit","stale","wrong_client","dependency"):
            bad=deepcopy(good);key=next(iter(bad["recovery_refs"]))
            if change=="omit":del bad["recovery_refs"][key]
            if change=="stale":bad["recovery_refs"][key]["dns"]=v["report"]["observations"]["recovery"]["clients"][0]["dns"]["id"]
            if change=="wrong_client":bad["recovery_refs"][key]=list(bad["recovery_refs"].values())[-1]
            if change=="dependency":bad["dependency_event_id"]=True
            before=lab.to_dict()
            with self.assertRaises(LabError):action(lab,bad)
            self.assertEqual(lab.to_dict(),before)
        action(lab,good)
        with self.assertRaises(LabError):action(lab,good)

    def test_persistence_and_legacy(self):
        lab=NetworkLab();start(lab,{"departments":2,"hosts_per_department":1})
        with tempfile.TemporaryDirectory() as d:
            p=Path(d)/"lab.json"
            while True:
                v=view(lab);lab.save(str(p));restored=NetworkLab();restored.load(str(p));self.assertEqual(view(restored),v)
                if not v["next_action"]:break
                action(lab,payload(v))
            raw=json.loads(p.read_text());raw["enterprise_training"]["steps"][-1]["recovery_refs"]={}
            p.write_text(json.dumps(raw))
            with self.assertRaises(LabError):NetworkLab().load(str(p))
        legacy=NetworkLab();action(legacy,{"action":"start","config":{"departments":2,"hosts_per_department":1}})
        self.assertEqual(view(legacy)["report"]["version"],1)

class AnalystHTTPTests(unittest.TestCase):
    setUpClass=isolated.PhysicalSpecialNotesHTTPTests.__dict__["setUpClass"]
    tearDownClass=isolated.PhysicalSpecialNotesHTTPTests.__dict__["tearDownClass"]
    setUp=isolated.PhysicalSpecialNotesHTTPTests.setUp
    request=isolated.PhysicalSpecialNotesHTTPTests.request

    def test_api_resolution_and_undo(self):
        base="/api/cyber-range/enterprise"
        status,data=self.request(base+"/action",{"action":"start","mode":"assessment","config":{"departments":2,"hosts_per_department":1}})
        self.assertEqual(status,200,data);v=data["enterprise"]
        while v["next_action"]:
            status,data=self.request(base+"/action",payload(v));self.assertEqual(status,200,data);v=data["enterprise"]
        self.assertEqual(v["report"]["analyst"]["score"]["points"],100)
        before=self.app.STATE.read_bytes();self.assertEqual(self.request(base)[1],v);self.assertEqual(self.app.STATE.read_bytes(),before)
        self.request("/api/command",{"command":"undo"})
        self.assertEqual(self.request(base)[1]["status"],"recovery_verified")
        self.request("/api/command",{"command":"redo"});self.assertEqual(self.request(base)[1],v)

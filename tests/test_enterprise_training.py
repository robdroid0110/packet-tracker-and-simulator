import json
import tempfile
import unittest
from copy import deepcopy
from pathlib import Path
from netsim.model import NetworkLab, LabError
from netsim.enterprise_training import action, view
import test_physical_special_notes_http as isolated

def request(v,op,**kw):
    return {"action":op,**({} if op=="start" else {"run_id":v["run_id"],"step":v["step"]}),**kw}

def finish(lab):
    while (v:=view(lab))["next_action"]:
        action(lab,request(v,v["next_action"]))
    return view(lab)

class EnterpriseTests(unittest.TestCase):
    def test_all_configurations_and_dependency_impact(self):
        for departments in (2,3):
            for hosts in (1,2):
                with self.subTest(departments=departments,hosts=hosts):
                    lab=NetworkLab();lab.add_device("pc","Existing")
                    before=lab.to_dict()
                    cfg={"departments":departments,"hosts_per_department":hosts}
                    action(lab,{"action":"start","config":cfg})
                    r=finish(lab)["report"]
                    count=departments*hosts
                    self.assertTrue(r["complete"])
                    self.assertEqual(len(r["inventory"]["segments"]),departments+1)
                    self.assertEqual(r["topology"]["devices"],1+departments+1+count+2)
                    self.assertEqual(r["topology"]["links"],r["topology"]["devices"]-1)
                    self.assertEqual(r["impact"]["affected_count"],count)
                    self.assertEqual(len(r["impact"]["affected_departments"]),departments)
                    self.assertTrue(r["impact"]["app_ip_controls_healthy"])
                    self.assertEqual(r["impact"]["affected_clients"],r["impact"]["recovered_clients"])
                    self.assertEqual(r["impact"]["dependency_fault_event_id"],r["observations"]["fault"]["component"]["id"])
                    self.assertEqual(r["impact"]["dependency_recovery_event_id"],r["observations"]["recovery"]["component"]["id"])
                    self.assertEqual(len(r["incidents"]["cases"]),count)
                    for phase,c in r["observations"].items():
                        expected="failure" if phase=="fault" else "success"
                        self.assertEqual(c["component"]["outcome"],expected)
                        for x in c["clients"]:
                            self.assertEqual(x["dns"]["outcome"],expected)
                            self.assertEqual(x["named_http"]["event"]["outcome"],expected)
                            self.assertEqual(x["named_http"]["http_status"],None if phase=="fault" else 200)
                            self.assertEqual(x["direct_http"]["http_status"],200)
                            self.assertEqual(x["app_icmp"]["outcome"],"success")
                    self.assertEqual(r["monitoring"]["span_simulated_seconds"],10)
                    self.assertTrue(r["monitoring"]["passed"])
                    after=lab.to_dict();after["enterprise_training"]=None
                    self.assertEqual(before,after)
                    if count==6:
                        self.assertGreater(r["soc"]["retention"]["dropped"],0)
                        ids={e["id"] for e in r["soc"]["logs"]}
                        self.assertTrue(any(e["baseline_id"] not in ids for e in r["impact"]["evidence"]))
                        self.assertEqual(len(r["impact"]["evidence"]),6)

    def test_configuration_validation_and_stale_actions(self):
        lab=NetworkLab()
        for cfg in (None,{},{"departments":True,"hosts_per_department":1},
                    {"departments":4,"hosts_per_department":1},{"departments":2,"hosts_per_department":3},
                    {"departments":2,"hosts_per_department":1,"target":"external.example"}):
            before=lab.to_dict()
            with self.assertRaises(LabError):action(lab,{"action":"start","config":cfg})
            self.assertEqual(before,lab.to_dict())
        cfg={"departments":2,"hosts_per_department":1};action(lab,{"action":"start","config":cfg})
        v=view(lab)
        for body in (request(v,"complete"),request(v,"inject_fault",target="external.example"),{**request(v,"inject_fault"),"step":True}):
            before=lab.to_dict()
            with self.assertRaises(LabError):action(lab,body)
            self.assertEqual(before,lab.to_dict())
        action(lab,request(v,"restart",config={"departments":3,"hosts_per_department":1}))
        with self.assertRaises(LabError):action(lab,request(v,"inject_fault"))
        self.assertEqual(view(lab)["report"]["config"]["departments"],3)

    def test_persistence_evidence_validation_and_legacy(self):
        lab=NetworkLab();action(lab,{"action":"start","config":{"departments":2,"hosts_per_department":1}})
        with tempfile.TemporaryDirectory() as d:
            p=Path(d)/"lab.json"
            while True:
                v=view(lab);lab.save(str(p));restored=NetworkLab();restored.load(str(p))
                self.assertEqual(view(restored),v)
                if not v["next_action"]:break
                action(lab,request(v,v["next_action"]))
            raw=json.loads(p.read_text())
            forged=deepcopy(raw);forged["enterprise_training"]["observations"]["fault"]["clients"][0]["named_http"]["event"]["outcome"]="success"
            p.write_text(json.dumps(forged))
            with self.assertRaises(LabError):NetworkLab().load(str(p))
            raw.pop("enterprise_training");p.write_text(json.dumps(raw));restored.load(str(p))
            self.assertEqual(view(restored)["status"],"idle")

class EnterpriseHTTPTests(unittest.TestCase):
    setUpClass=isolated.PhysicalSpecialNotesHTTPTests.__dict__["setUpClass"]
    tearDownClass=isolated.PhysicalSpecialNotesHTTPTests.__dict__["tearDownClass"]
    setUp=isolated.PhysicalSpecialNotesHTTPTests.setUp
    request=isolated.PhysicalSpecialNotesHTTPTests.request

    def test_api_lifecycle_and_undo(self):
        base="/api/cyber-range/enterprise"
        self.request("/api/command",{"command":"add pc Existing"})
        self.assertEqual(self.request(base+"/schema")[0],200)
        self.assertIn("enterprise_action",self.request("/api/capabilities")[1]["agent_endpoints"])
        self.assertEqual(self.request(base+"?target=external")[0],400)
        status,data=self.request(base+"/action",{"action":"start","config":{"departments":2,"hosts_per_department":1}})
        self.assertEqual(status,200,data);v=data["enterprise"]
        while v["next_action"]:
            status,data=self.request(base+"/action",request(v,v["next_action"]))
            self.assertEqual(status,200,data);v=data["enterprise"]
        before=self.app.STATE.read_bytes()
        self.assertEqual(v,self.request(base)[1])
        self.assertEqual(before,self.app.STATE.read_bytes())
        self.assertEqual(set(self.request("/api/state")[1]["devices"]),{"Existing"})
        self.request("/api/command",{"command":"undo"})
        self.assertEqual(self.request(base)[1]["status"],"recovery_verified")
        self.request("/api/command",{"command":"redo"})
        self.assertEqual(self.request(base)[1],v)

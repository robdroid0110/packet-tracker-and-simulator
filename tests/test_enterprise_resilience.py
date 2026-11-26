import json,tempfile,unittest
from copy import deepcopy
from pathlib import Path
from netsim.model import NetworkLab,LabError
from netsim.enterprise_training import action,view
from netsim.enterprise_archive import progress,report
from netsim.enterprise_resilience import monitoring
import test_physical_special_notes_http as isolated

CFG={"departments":2,"hosts_per_department":1}
def payload(v,correct=True):
    op=v["next_action"];c=v["report"]["observations"];b={"action":op,"run_id":v["run_id"],"step":v["step"]}
    if op=="assess":
        f,p,r=[c[k]["clients"][0] for k in ("failover","partial","relapse")]
        b.update(diagnosis="redundancy_degraded" if correct else "app_outage",
                 references={"primary_failure":f["attempts"]["primary"]["id"],"secondary_success":f["attempts"]["secondary"]["id"],"failover_portal":f["portal"]["event"]["id"],"partial_portal":p["portal"]["event"]["id"],"partial_secondary_failure":p["attempts"]["secondary"]["id"],"relapse_portal_failure":r["portal"]["event"]["id"],"healthy_app_control":r["direct"]["event"]["id"]},
                 affected_clients=[x["client"] for x in c["relapse"]["clients"]] if correct else [],
                 note="Observed intermittent DNS redundancy loss.",note_event_id=c["relapse"]["components"]["primary"]["id"])
        if not correct:b["references"]["partial_secondary_failure"]=p["attempts"]["primary"]["id"]
    if op=="resolve":
        z=c["recovery_10s"];b.update(resolver_refs={k:e["id"] for k,e in z["components"].items()},client_refs={x["client"]:{"primary":x["attempts"]["primary"]["id"],"secondary":x["attempts"]["secondary"]["id"],"portal":x["portal"]["event"]["id"]} for x in z["clients"]})
    return b
def start(lab,cfg=CFG):action(lab,{"action":"start","mode":"resilience","config":cfg})
def until(lab,stage,correct=True):
    while (v:=view(lab))["status"]!=stage:
        if not v["next_action"]:raise AssertionError(stage)
        action(lab,payload(v,correct))
    return v
class ResilienceTests(unittest.TestCase):
    def test_all_configurations(self):
        for d,h in ((2,1),(2,2),(3,1),(3,2)):
            with self.subTest(d=d,h=h):
                lab=NetworkLab();lab.add_device("pc","Existing");before=lab.to_dict();start(lab,{"departments":d,"hosts_per_department":h})
                v=until(lab,"completed");r=v["report"]
                self.assertEqual(r["analyst"]["score"]["points"],100)
                self.assertEqual(r["parent_incident"]["status"],"closed")
                self.assertEqual(len(r["parent_incident"]["affected_clients"]),d*h)
                self.assertEqual(r["topology"]["devices"],1+d+1+d*h+3)
                for phase,expected in (("baseline","primary"),("failover","secondary"),("interruption",None),("partial","primary"),("relapse",None),("restored","primary"),("recovery_5s","primary"),("recovery_10s","primary")):
                    rows=r["observations"][phase]["clients"]
                    self.assertEqual(len(rows),d*h)
                    self.assertTrue(all(x["selected"]==expected and x["direct"]["http_status"]==200 and (x["portal"]["http_status"]==200)==bool(expected) for x in rows))
                m=r["monitoring"];self.assertTrue(m["passed"] and m["partial_recovery_detected"] and m["relapse_detected"]);self.assertGreaterEqual(m["span_simulated_seconds"],10)
                self.assertEqual(report(lab,v["run_id"])["report"],r)
                after=lab.to_dict();after["enterprise_training"]=None;after["enterprise_archive"]=before["enterprise_archive"];self.assertEqual(after,before)
    def test_guards_and_wrong_assessment(self):
        lab=NetworkLab();start(lab)
        v=until(lab,"unstable_recovery");self.assertFalse(v["report"]["monitoring"]["passed"]);self.assertFalse(v["report"]["parent_incident"]["closure_ready"])
        before=lab.to_dict()
        with self.assertRaises(LabError):action(lab,{"action":"resolve","run_id":v["run_id"],"step":v["step"]})
        self.assertEqual(before,lab.to_dict())
        v=until(lab,"recovery_verified");bad=payload(v);bad["references"]["primary_failure"]=True
        with self.assertRaises(LabError):action(lab,bad)
        action(lab,payload(v,False));v=view(lab);self.assertEqual(v["report"]["analyst"]["score"]["points"],50)
        good=payload(v)
        for variant in ("missing","stale","wrong_client","resolver"):
            bad=deepcopy(good);name=next(iter(bad["client_refs"]))
            if variant=="missing":del bad["client_refs"][name]
            if variant=="stale":bad["client_refs"][name]["primary"]=v["report"]["observations"]["restored"]["clients"][0]["attempts"]["primary"]["id"]
            if variant=="wrong_client":bad["client_refs"][name]=list(bad["client_refs"].values())[-1]
            if variant=="resolver":bad["resolver_refs"]["secondary"]=True
            before=lab.to_dict()
            with self.assertRaises(LabError):action(lab,bad)
            self.assertEqual(before,lab.to_dict())
        action(lab,good);self.assertEqual(view(lab)["report"]["analyst"]["score"]["points"],55)
    def test_monitoring_rejects_partial_or_incomplete(self):
        lab=NetworkLab();start(lab);v=until(lab,"recovery_verified");c=v["report"]["observations"]
        for mode in ("missing","duplicate","failed","short","resolver","reused","portal_failure","middle_short"):
            x=deepcopy(c)
            if mode=="missing":x["recovery_10s"]["clients"].pop()
            if mode=="duplicate":x["recovery_10s"]["clients"][-1]=x["recovery_10s"]["clients"][0]
            if mode=="failed":x["recovery_10s"]["clients"][0]["attempts"]["secondary"]["outcome"]="failure"
            if mode=="short":x["recovery_10s"]["sim_time"]=x["restored"]["sim_time"]
            if mode=="resolver":x["recovery_10s"]["components"]["secondary"]["outcome"]="failure"
            if mode=="reused":x["recovery_10s"]["clients"][0]["attempts"]["secondary"]["id"]=x["recovery_5s"]["clients"][0]["attempts"]["secondary"]["id"]
            if mode=="portal_failure":x["recovery_10s"]["clients"][0]["portal"]["event"]["outcome"]="failure"
            if mode=="middle_short":x["recovery_5s"]["sim_time"]=x["restored"]["sim_time"]
            self.assertFalse(monitoring(x)["passed"],mode)
    def test_persistence_and_archive_separation(self):
        from test_enterprise_assessment import start as start_v2,until as until_v2
        lab=NetworkLab();start_v2(lab,CFG);old=until_v2(lab,"completed")
        action(lab,{"action":"restart","mode":"resilience","config":CFG,"run_id":old["run_id"],"step":old["step"]})
        with tempfile.TemporaryDirectory() as d:
            p=Path(d)/"lab.json"
            while True:
                v=view(lab);lab.save(str(p));restored=NetworkLab();restored.load(str(p));self.assertEqual(view(restored),v)
                if not v["next_action"]:break
                action(lab,payload(v))
            self.assertEqual(len(progress(restored)["groups"]),2)
            self.assertEqual(report(restored,old["run_id"])["report"],old["report"])
            raw=json.loads(p.read_text());raw["enterprise_training"]["observations"]["relapse"]["clients"][0]["selected"]="secondary"
            p.write_text(json.dumps(raw))
            with self.assertRaises(LabError):NetworkLab().load(str(p))
class ResilienceHTTPTests(unittest.TestCase):
    setUpClass=isolated.PhysicalSpecialNotesHTTPTests.__dict__["setUpClass"]
    tearDownClass=isolated.PhysicalSpecialNotesHTTPTests.__dict__["tearDownClass"]
    setUp=isolated.PhysicalSpecialNotesHTTPTests.setUp
    request=isolated.PhysicalSpecialNotesHTTPTests.request
    def test_api_undo_and_archive(self):
        base="/api/cyber-range/enterprise"
        status,data=self.request(base+"/action",{"action":"start","mode":"resilience","config":CFG})
        self.assertEqual(status,200,data);v=data["enterprise"]
        while v["next_action"]:
            status,data=self.request(base+"/action",payload(v));self.assertEqual(status,200,data);v=data["enterprise"]
        self.assertEqual(v["report"]["analyst"]["score"]["points"],100)
        url=base+"/report?run_id="+v["run_id"];self.assertEqual(self.request(url)[1]["report"],v["report"])
        self.request("/api/command",{"command":"undo"});self.assertEqual(self.request(url)[0],400)
        self.request("/api/command",{"command":"redo"});self.assertEqual(self.request(url)[1]["report"],v["report"])

"""Exercise runner lifecycle, independent modeled evidence and grading."""
import json
import tempfile
import unittest
from copy import deepcopy
from pathlib import Path
from netsim.model import NetworkLab, LabError
from netsim.cli import CommandProcessor
from netsim.exercise_runner import action, view, FLOW
import test_physical_special_notes_http as isolated

def assessment(checks, correct=True):
    refs={"baseline_icmp":checks["baseline"]["icmp"]["id"],
          "baseline_http":checks["baseline"]["http"]["id"],
          "failure_icmp":checks["fault"]["icmp"]["id"],
          "failure_http":checks["fault"]["http"]["id"],
          "interface_state":checks["fault"]["interface"]["id"]}
    if not correct:
        refs["interface_state"]=checks["baseline"]["interface"]["id"]
        refs["failure_http"]=checks["baseline"]["http"]["id"]
    return {"diagnosis":"client_interface_down" if correct else "application_only",
            "references":refs,"note":"Reviewed the modeled health observations."}

def context(v, op, **fields):
    return {"action":op,**({} if op=="start" else {"run_id":v["run_id"],"step":v["step"]}),**fields}

class ExerciseTests(unittest.TestCase):
    def setUp(self):
        self.lab=NetworkLab()
        self.lab.add_device("pc","Unrelated")
        self.before=self.lab.to_dict()

    def act(self,op,**fields):
        return action(self.lab,context(view(self.lab),op,**fields))

    def report(self):
        return view(self.lab)["report"]

    def until(self, stage, correct=True):
        while view(self.lab)["status"]!=stage:
            v=view(self.lab);op=v["next_action"]
            if not op:self.fail("no next action")
            checks=(v["report"] or {}).get("observations",{})
            extra={}
            if op=="acknowledge":extra={"event_id":checks["fault"]["icmp"]["id"]}
            if op=="assess":extra=assessment(checks,correct)
            if op=="verify_recovery":extra={"icmp_event_id":checks["recovery"]["icmp"]["id"],
                                           "http_event_id":checks["recovery"]["http"]["id"]}
            self.act(op,**extra)

    def test_baseline_fault_recovery_and_isolation(self):
        self.until("completed")
        report=self.report()
        self.assertTrue(report["complete"])
        self.assertEqual(report["history"],["start",*FLOW])
        self.assertEqual(report["sandbox"]["path"],["CLIENT","ACCESS","APP"])
        self.assertEqual(report["score"]["points"],100)
        self.assertEqual(report["incidents"]["cases"][0]["status"],"resolved")
        for phase,expected in (("baseline","success"),("fault","failure"),("recovery","success")):
            c=report["observations"][phase]
            for kind in ("interface","icmp","http"):
                self.assertEqual(c[kind]["outcome"],expected)
                self.assertIn(c[kind],report["soc"]["logs"])
            self.assertEqual(c["http_status"],200 if expected=="success" else None)
        self.assertEqual(report["observations"]["fault"]["interface"]["reason"],"modeled_interface_down")
        after=self.lab.to_dict();after["exercise_runner"]=None;after["exercise_archive"]=deepcopy(self.before["exercise_archive"])
        self.assertEqual(after,self.before)

    def test_wrong_evidence_and_diagnosis_are_penalized(self):
        self.until("completed",correct=False)
        score=self.report()["score"]
        self.assertEqual(score["points"],45)
        criteria={c["id"]:c["met"] for c in score["criteria"]}
        self.assertFalse(criteria["evidence_backed_diagnosis"])
        self.assertFalse(criteria["connectivity_and_http_failure_evidence"])
        self.assertTrue(criteria["verified_connectivity_and_http_recovery"])

    def test_recovery_requires_both_current_checks_and_correct_diagnosis_needs_evidence(self):
        self.until("acknowledged")
        checks=self.report()["observations"]
        fields=assessment(checks)
        fields["references"]["interface_state"]=checks["baseline"]["interface"]["id"]
        self.act("assess",**fields)
        self.assertFalse(next(c for c in self.report()["score"]["criteria"] if c["id"]=="evidence_backed_diagnosis")["met"])
        self.act("restore")
        checks=self.report()["observations"]
        before=deepcopy(self.lab.exercise_runner)
        for bad in ({"icmp_event_id":checks["baseline"]["icmp"]["id"],"http_event_id":checks["recovery"]["http"]["id"]},
                    {"icmp_event_id":checks["recovery"]["icmp"]["id"],"http_event_id":checks["fault"]["http"]["id"]}):
            with self.assertRaises(LabError):self.act("verify_recovery",**bad)
            self.assertEqual(self.lab.exercise_runner,before)
        with self.assertRaises(LabError):self.act("complete")
        self.until("completed")
        self.assertEqual(self.report()["score"]["points"],65)

    def test_restart_and_stale_requests(self):
        self.until("fault_observed")
        old=view(self.lab)
        self.act("restart")
        new=view(self.lab)
        self.assertEqual(new["attempt"],2)
        self.assertNotEqual(new["run_id"],old["run_id"])
        self.assertEqual(new["status"],"baseline_verified")
        self.assertFalse(new["report"]["incidents"]["cases"])
        self.assertNotIn("fault",new["report"]["observations"])
        for body in (context(old,"acknowledge",event_id=old["report"]["observations"]["fault"]["icmp"]["id"]),
                     {"action":"start"}, {**context(new,"inject_fault"),"target":"external.example"},
                     {**context(new,"inject_fault"),"step":True}):
            before=deepcopy(self.lab.exercise_runner)
            with self.assertRaises(LabError):action(self.lab,body)
            self.assertEqual(before,self.lab.exercise_runner)
        self.until("completed")
        self.act("restart")
        self.assertEqual(view(self.lab)["attempt"],3)

    def test_save_reload_each_stage_and_reject_tampered_evidence(self):
        with tempfile.TemporaryDirectory() as directory:
            path=Path(directory)/"lab.json"
            for stage in ("baseline_verified","fault_observed","acknowledged","assessed","restored","recovery_verified","completed"):
                self.until(stage)
                self.lab.save(str(path))
                restored=NetworkLab();restored.load(str(path))
                self.assertEqual(view(restored),view(self.lab))
                self.lab=restored
            raw=json.loads(path.read_text())
            forged=deepcopy(raw);forged["exercise_runner"]["observations"]["fault"]["http"]["outcome"]="success"
            path.write_text(json.dumps(forged))
            with self.assertRaises(LabError):NetworkLab().load(str(path))
            forged=deepcopy(raw);forged["exercise_runner"]["steps"][0]["action"]="complete"
            path.write_text(json.dumps(forged))
            with self.assertRaises(LabError):NetworkLab().load(str(path))
            raw.pop("exercise_runner");path.write_text(json.dumps(raw));restored.load(str(path))
            self.assertEqual(view(restored)["status"],"idle")

    def test_invalid_assessment_and_reset_undo(self):
        self.until("acknowledged")
        checks=self.report()["observations"]
        for value in (True,99999,-1,"1"):
            fields=assessment(checks);fields["references"]["baseline_icmp"]=value
            before=deepcopy(self.lab.exercise_runner)
            with self.assertRaises(LabError):self.act("assess",**fields)
            self.assertEqual(self.lab.exercise_runner,before)
        cp=CommandProcessor(self.lab);previous=view(self.lab)
        cp.execute("reset");self.assertEqual(view(self.lab)["status"],"idle")
        cp.execute("undo");self.assertEqual(view(self.lab),previous)

class ExerciseHTTPTests(unittest.TestCase):
    setUpClass=isolated.PhysicalSpecialNotesHTTPTests.__dict__["setUpClass"]
    tearDownClass=isolated.PhysicalSpecialNotesHTTPTests.__dict__["tearDownClass"]
    setUp=isolated.PhysicalSpecialNotesHTTPTests.setUp
    request=isolated.PhysicalSpecialNotesHTTPTests.request

    def test_http_lifecycle_read_only_report_and_autosave(self):
        self.request("/api/command",{"command":"add pc Existing"})
        base="/api/cyber-range/exercises"
        self.assertEqual(self.request(base+"/schema")[0],200)
        self.assertIn("exercise_action",self.request("/api/capabilities")[1]["agent_endpoints"])
        self.assertEqual(self.request(base+"?target=external")[0],400)
        v=self.request(base)[1]
        def act(op,**fields):
            nonlocal v
            status,result=self.request(base+"/action",context(v,op,**fields))
            self.assertEqual(status,200,result);v=result["exercise"]
        act("start");act("inject_fault")
        checks=v["report"]["observations"]
        act("acknowledge",event_id=checks["fault"]["icmp"]["id"])
        act("assess",**assessment(checks))
        act("restore")
        checks=v["report"]["observations"]
        act("verify_recovery",icmp_event_id=checks["recovery"]["icmp"]["id"],http_event_id=checks["recovery"]["http"]["id"])
        act("complete")
        self.assertEqual(v["report"]["score"]["points"],100)
        before=self.app.STATE.read_bytes()
        self.assertEqual(v,self.request(base)[1])
        self.assertEqual(before,self.app.STATE.read_bytes())
        self.assertEqual(set(self.request("/api/state")[1]["devices"]),{"Existing"})
        loaded=NetworkLab();loaded.load(str(self.app.STATE));self.assertEqual(view(loaded),v)
        self.request("/api/command",{"command":"undo"})
        self.assertEqual(self.request(base)[1]["status"],"recovery_verified")
        self.request("/api/command",{"command":"redo"})
        self.assertEqual(self.request(base)[1],v)

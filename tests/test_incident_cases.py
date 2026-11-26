import json
import tempfile
import unittest
from pathlib import Path
from netsim.model import NetworkLab, LabError
from netsim.cli import CommandProcessor
from netsim.incident_cases import action, view, MAX_EVIDENCE, MAX_CASES, MAX_NOTES
from netsim.simulation import action as simulate
from netsim.defensive_soc import LIMIT, view as soc_view
import test_physical_special_notes_http as isolated

class IncidentTests(unittest.TestCase):
    def setUp(self):
        self.lab=NetworkLab();self.cp=CommandProcessor(self.lab)
        for cmd in ("add pc A","add pc B","connect A eth0 B eth0",
                    "ip A eth0 192.0.2.1/24","ip B eth0 192.0.2.2/24"):
            self.assertFalse(self.cp.execute(cmd).startswith("ERROR:"))

    def probe(self, address="192.0.2.2"):
        return self.lab.ping_detailed("A",address)

    def case(self,index=0):
        return view(self.lab)["cases"][index]

    def act(self,op,event_id=None,**extra):
        body={"action":op,"case_id":self.case()["id"],**extra}
        if event_id is not None:body["event_id"]=event_id
        return action(self.lab,body)

    def fail_probe(self):
        self.cp.execute("down A eth0")
        self.assertFalse(self.probe()["reachable"])
        return self.case()["evidence"][-1]["id"]

    def recover(self):
        self.cp.execute("up A eth0")
        self.assertTrue(self.probe()["reachable"])
        return self.case()["evidence"][-1]["id"]

    def test_complete_benign_exercise_and_score(self):
        self.assertTrue(self.probe()["reachable"])
        self.assertFalse(view(self.lab)["cases"])
        failure=self.fail_probe()
        self.assertEqual(self.case()["status"],"open")
        self.assertEqual(self.case()["score"]["points"],0)
        self.act("acknowledge",failure)
        self.assertEqual(self.case()["score"]["points"],20)
        alert=soc_view(self.lab)["alerts"][-1]
        self.assertEqual(alert["case_id"],self.case()["id"])
        self.assertTrue(alert["acknowledged"])
        self.act("add_note",failure,note="Source interface was unavailable; check its state.")
        self.assertEqual(self.case()["score"]["points"],45)
        with self.assertRaises(LabError):self.act("verify_recovery",failure)
        recovery=self.recover()
        self.assertEqual(self.case()["status"],"investigating")
        self.act("verify_recovery",recovery)
        self.assertEqual(self.case()["score"]["points"],80)
        self.act("resolve")
        self.assertEqual(self.case()["score"]["points"],100)
        self.assertEqual(self.case()["status"],"resolved")
        with self.assertRaises(LabError):self.act("add_note",failure,note="late note")
        self.fail_probe()
        self.assertEqual(len(view(self.lab)["cases"]),2)
        self.assertEqual(self.case(1)["status"],"open")

    def test_correlation_and_new_failure_invalidates_recovery(self):
        first=self.fail_probe()
        self.probe()
        second=self.case()["evidence"][-1]["id"]
        self.assertGreater(second,first)
        self.assertEqual(len(view(self.lab)["cases"]),1)
        self.probe("192.0.2.99")
        self.assertEqual(len(view(self.lab)["cases"]),2)
        with self.assertRaises(LabError):self.act("acknowledge",first)
        self.act("acknowledge",second)
        self.act("add_note",second,note="Repeated failure observed.")
        recovery=self.recover();self.act("verify_recovery",recovery)
        third=self.fail_probe()
        self.assertGreater(third,recovery)
        self.assertEqual(self.case()["status"],"investigating")
        self.assertIsNone(self.case()["recovery_event_id"])
        self.assertIsNone(self.case()["ack_event_id"])
        self.assertFalse(soc_view(self.lab)["alerts"][-1]["acknowledged"])
        self.assertEqual(self.case()["score"]["points"],0)
        with self.assertRaises(LabError):self.act("verify_recovery",recovery)
        with self.assertRaises(LabError):self.act("resolve")

    def test_retention_and_roundtrip_preserves_cited_evidence(self):
        first=self.fail_probe()
        self.act("add_note",first,note="Initial observation.")
        for _ in range(LIMIT+3): self.probe()
        c=self.case()
        self.assertEqual(len(c["evidence"]),MAX_EVIDENCE)
        self.assertGreater(c["omitted"],0)
        self.assertEqual(c["evidence"][0]["id"],first)
        self.assertNotIn(first,[e["id"] for e in self.lab.defensive_soc["logs"]])
        self.act("acknowledge",c["evidence"][-1]["id"])
        with tempfile.TemporaryDirectory() as directory:
            path=Path(directory)/"lab.json";self.lab.save(str(path))
            restored=NetworkLab();restored.load(str(path));self.assertEqual(view(restored),view(self.lab))
            raw=json.loads(path.read_text())
            raw["incident_cases"]["cases"][0]["evidence"][-1]["source"]="forged"
            path.write_text(json.dumps(raw))
            with self.assertRaises(LabError):NetworkLab().load(str(path))
            raw.pop("incident_cases");path.write_text(json.dumps(raw));restored.load(str(path))
            self.assertFalse(view(restored)["cases"])

    def test_note_limits_and_invalid_actions_atomic(self):
        first=self.fail_probe()
        for body in ({"action":"acknowledge","case_id":self.case()["id"],"event_id":True},
                     {"action":"add_note","case_id":self.case()["id"],"event_id":first,"note":"\n"},
                     {"action":"resolve","case_id":self.case()["id"],"unexpected":True}):
            before=self.lab.to_dict()
            with self.assertRaises(LabError):action(self.lab,body)
            self.assertEqual(before,self.lab.to_dict())
        self.act("add_note",first,note="first")
        self.act("add_note",first,note="updated")
        self.assertEqual(self.case()["notes"],[{"event_id":first,"text":"updated"}])
        self.act("remove_note",first)
        self.assertFalse(self.case()["notes"])
        for i in range(MAX_NOTES):
            self.probe()
            self.act("add_note",self.case()["evidence"][-1]["id"],note="Observation "+str(i))
        self.probe(); latest=self.case()["evidence"][-1]["id"]
        with self.assertRaises(LabError):self.act("add_note",latest,note="Extra")
        self.act("remove_note",self.case()["notes"][0]["event_id"])
        self.act("add_note",latest,note="Current failure")
        self.assertEqual(len(self.case()["notes"]),MAX_NOTES)

    def test_scheduled_probe_and_policy_only(self):
        simulate(self.lab,{"action":"mode","mode":"simulation"})
        self.cp.execute("down A eth0")
        self.assertEqual(self.probe()["status"],"queued")
        self.assertFalse(view(self.lab)["cases"])
        while simulate(self.lab,{"action":"step"}):pass
        before=view(self.lab)
        self.assertEqual(len(before["cases"]),1)
        simulate(self.lab,{"action":"back"});simulate(self.lab,{"action":"step"})
        self.assertEqual(before,view(self.lab))
        self.cp.execute("up A eth0")
        self.probe()
        while simulate(self.lab,{"action":"step"}):pass
        self.act("verify_recovery",self.case()["evidence"][-1]["id"])
        self.assertEqual(self.case()["status"],"recovered")
        lab=NetworkLab();lab.load(str(Path(__file__).resolve().parents[1]/"labs/audit/campus.json"))
        lab.add_acl_rule("R1","SOC-TEST","deny","icmp","any","any")
        lab.set_access_group("R1","g0/0.10","SOC-TEST","in")
        lab.ping_detailed("PC1","172.16.3.20")
        self.assertFalse(view(lab)["cases"])

    def test_case_capacity_is_bounded(self):
        for i in range(MAX_CASES+2):self.probe("198.51.100."+str(i+1))
        self.assertEqual(len(view(self.lab)["cases"]),MAX_CASES)
        self.assertEqual(view(self.lab)["skipped"],2)

class IncidentHTTPTests(unittest.TestCase):
    setUpClass=isolated.PhysicalSpecialNotesHTTPTests.__dict__["setUpClass"]
    tearDownClass=isolated.PhysicalSpecialNotesHTTPTests.__dict__["tearDownClass"]
    setUp=isolated.PhysicalSpecialNotesHTTPTests.setUp
    request=isolated.PhysicalSpecialNotesHTTPTests.request

    def test_http_case_lifecycle_and_autosave(self):
        for cmd in ("add pc A","add pc B","connect A eth0 B eth0","ip A eth0 192.0.2.1/24","ip B eth0 192.0.2.2/24","down A eth0","ping A 192.0.2.2"):
            self.request("/api/command",{"command":cmd})
        base="/api/cyber-range/incidents"
        self.assertEqual(self.request(base+"/schema")[0],200)
        self.assertIn("incident_action",self.request("/api/capabilities")[1]["agent_endpoints"])
        case=self.request(base)[1]["cases"][0];cid=case["id"];eid=case["evidence"][0]["id"]
        def act(op,event_id=None,**extra):
            body={"action":op,"case_id":cid,**extra}
            if event_id is not None:body["event_id"]=event_id
            return self.request(base+"/action",body)
        before=self.app.STATE.read_bytes()
        self.assertEqual(act("resolve")[0],400)
        self.assertEqual(before,self.app.STATE.read_bytes())
        self.assertEqual(act("acknowledge",eid)[0],200)
        self.assertEqual(act("add_note",eid,note="Interface unavailable.")[0],200)
        self.request("/api/command",{"command":"up A eth0"})
        self.request("/api/v1/connectivity/ping",{"source":"A","destination_ip":"192.0.2.2"})
        last=self.request(base)[1]["cases"][0]["evidence"][-1]["id"]
        self.assertEqual(act("verify_recovery",last)[0],200)
        status,result=act("resolve")
        self.assertEqual(status,200,result)
        self.assertEqual(result["incidents"]["cases"][0]["score"]["points"],100)
        loaded=NetworkLab();loaded.load(str(self.app.STATE))
        self.assertEqual(view(loaded),result["incidents"])
        self.request("/api/command",{"command":"undo"})
        self.assertEqual(self.request(base)[1]["cases"][0]["status"],"recovered")
        self.request("/api/command",{"command":"redo"})
        self.assertEqual(self.request(base)[1]["cases"][0]["status"],"resolved")

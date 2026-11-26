import json
import tempfile
import unittest
from copy import deepcopy
from pathlib import Path
from netsim.model import NetworkLab, LabError
from netsim.cli import CommandProcessor
from netsim.simulation import action
from netsim.defensive_soc import LIMIT, view
import test_physical_special_notes_http as isolated

class DefensiveSOCTests(unittest.TestCase):
    def setUp(self):
        self.lab=NetworkLab()
        self.cp=CommandProcessor(self.lab)
        for cmd in ("add pc A","add pc B","connect A eth0 B eth0",
                    "ip A eth0 192.0.2.1/24","ip B eth0 192.0.2.2/24"):
            self.assertFalse(self.cp.execute(cmd).startswith("ERROR:"))

    def test_benign_probe_success_failure_and_recovery(self):
        self.assertTrue(self.lab.ping_detailed("A","192.0.2.2")["reachable"])
        self.assertEqual(view(self.lab)["alerts"],[])
        self.cp.execute("down A eth0")
        self.assertFalse(self.lab.ping_detailed("A","192.0.2.2")["reachable"])
        self.cp.execute("up A eth0")
        self.assertTrue(self.lab.ping_detailed("A","192.0.2.2")["reachable"])
        data=view(self.lab)
        self.assertEqual([e["outcome"] for e in data["logs"]],["success","failure","success"])
        self.assertEqual(len(data["alerts"]),1)
        self.assertEqual(data["alerts"][0]["event_id"],data["logs"][1]["id"])
        self.assertEqual(data["evidence_type"],"modeled_synthetic")

    def test_queued_capture_and_playback_no_duplicate(self):
        action(self.lab,{"action":"mode","mode":"simulation"})
        result=self.lab.ping_detailed("A","192.0.2.2")
        self.assertEqual(result["status"],"queued")
        self.assertFalse(view(self.lab)["logs"])
        action(self.lab,{"action":"step"})
        self.assertTrue(view(self.lab)["logs"])
        while action(self.lab,{"action":"step"}): pass
        before=view(self.lab)
        self.assertEqual(len([e for e in before["logs"] if e["kind"]=="scheduled"]),1)
        action(self.lab,{"action":"back"});action(self.lab,{"action":"step"})
        self.assertEqual(before,view(self.lab))
        self.assertFalse(before["alerts"])

    def test_failed_scheduled_operation_alert_once(self):
        action(self.lab,{"action":"mode","mode":"simulation"})
        self.cp.execute("down A eth0")
        self.lab.ping_detailed("A","192.0.2.2")
        while action(self.lab,{"action":"step"}): pass
        data=view(self.lab)
        self.assertEqual(len(data["alerts"]),1)
        self.assertEqual(len(view(self.lab,kind="scheduled")["logs"]),1)
        self.assertEqual(data["alerts"][0]["severity"],"warning")

    def test_policy_denial_is_not_an_attack_and_ipv6_is_labelled(self):
        lab=NetworkLab()
        lab.load(str(Path(__file__).resolve().parents[1]/"labs/audit/campus.json"))
        lab.add_acl_rule("R1","SOC-TEST","deny","icmp","any","any")
        lab.set_access_group("R1","g0/0.10","SOC-TEST","in")
        self.assertFalse(lab.ping_detailed("PC1","172.16.3.20")["reachable"])
        for mode in ("realtime","simulation"):
            if mode=="simulation":
                action(lab,{"action":"mode","mode":mode})
                lab.ping_detailed("PC1","172.16.3.20")
                while action(lab,{"action":"step"}): pass
            alert=view(lab)["alerts"][-1]
            self.assertEqual(alert["category"],"policy_observation")
            self.assertEqual(alert["severity"],"info")
            self.assertIn("not proof",alert["interpretation"])
        self.lab.devices["A"].interfaces["eth0"].ipv6="2001:db8::1/64"
        self.lab.devices["B"].interfaces["eth0"].ipv6="2001:db8::2/64"
        self.assertTrue(self.lab.ping_detailed("A","2001:db8::2")["reachable"])
        self.assertEqual(view(self.lab,kind="connectivity")["logs"][-1]["protocol"],"ICMPv6")
        self.assertFalse(view(self.lab)["alerts"])

    def test_retention_persistence_legacy_and_reset(self):
        for _ in range(LIMIT+3):
            self.lab.ping_detailed("A","192.0.2.2")
        data=view(self.lab)
        self.assertEqual(data["retention"],{"limit":LIMIT,"dropped":3,"retained":LIMIT})
        self.assertEqual(data["logs"][0]["id"],4)
        with tempfile.TemporaryDirectory() as directory:
            path=Path(directory)/"lab.json"
            self.lab.save(str(path));restored=NetworkLab();restored.load(str(path))
            self.assertEqual(view(restored),data)
            raw=json.loads(path.read_text());raw["defensive_soc"]["logs"][0]["id"]=False
            path.write_text(json.dumps(raw))
            with self.assertRaises(LabError): NetworkLab().load(str(path))
            raw.pop("defensive_soc");path.write_text(json.dumps(raw));restored.load(str(path))
            self.assertFalse(view(restored)["logs"])
        self.cp.execute("reset")
        self.assertFalse(view(self.lab)["logs"])
        self.cp.execute("undo")
        self.assertEqual(view(self.lab),data)

    def test_packet_trace_reset_keeps_soc_ids(self):
        self.lab._packet_event("HTTP","A","B","private example text",False)
        self.cp.execute("power-cycle")
        self.lab._packet_event("HTTP","A","B","another example",True)
        data=view(self.lab)
        self.assertEqual([e["id"] for e in data["logs"]],[1,2])
        self.assertEqual([e["packet_seq"] for e in data["logs"]],[1,1])
        self.assertNotIn("private example text",json.dumps(data))
        self.assertFalse(data["alerts"])

class DefensiveSOCHTTPTests(unittest.TestCase):
    setUpClass=isolated.PhysicalSpecialNotesHTTPTests.__dict__["setUpClass"]
    tearDownClass=isolated.PhysicalSpecialNotesHTTPTests.__dict__["tearDownClass"]
    setUp=isolated.PhysicalSpecialNotesHTTPTests.setUp
    request=isolated.PhysicalSpecialNotesHTTPTests.request

    def test_api_read_only_and_shared_engine(self):
        for cmd in ("add pc A","add pc B","connect A eth0 B eth0","ip A eth0 192.0.2.1/24","ip B eth0 192.0.2.2/24"):
            self.assertTrue(self.request("/api/command",{"command":cmd})[1]["ok"])
        self.assertEqual(self.request("/api/cyber-range/soc/schema")[0],200)
        self.assertIn("defensive_soc",self.request("/api/capabilities")[1]["agent_endpoints"])
        self.request("/api/v1/connectivity/ping",{"source":"A","destination_ip":"192.0.2.2"})
        self.request("/api/command",{"command":"down A eth0"})
        self.request("/api/command",{"command":"ping A 192.0.2.2"})
        before=self.app.STATE.read_bytes()
        status,result=self.request("/api/cyber-range/soc?outcome=failure")
        self.assertEqual(status,200,result)
        self.assertEqual(len(result["logs"]),1);self.assertEqual(len(result["alerts"]),1)
        for query in ("kind=nope","outcome=","kind=packet&kind=scheduled","target=external"):
            self.assertEqual(self.request("/api/cyber-range/soc?"+query)[0],400)
        self.assertEqual(before,self.app.STATE.read_bytes())

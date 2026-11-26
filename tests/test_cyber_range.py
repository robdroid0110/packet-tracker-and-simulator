import base64
import json
import tempfile
import unittest
from pathlib import Path
from netsim.cyber_range import generate, schema
from netsim.model import NetworkLab, LabError
import test_physical_special_notes_http as isolated

class CyberRangeTests(unittest.TestCase):
    def test_all_supported_sizes_roundtrip_and_connectivity(self):
        for departments in range(1,4):
            for hosts in range(1,5):
                result = generate({"departments":departments,"hosts_per_department":hosts})
                self.assertEqual(len(result["lab"]["devices"]), 1+departments+1+departments*hosts+2)
                self.assertEqual(len(result["lab"]["links"]), len(result["lab"]["devices"])-1)
                with tempfile.TemporaryDirectory() as directory:
                    path=Path(directory)/"lab.json"
                    path.write_text(json.dumps(result["lab"]))
                    lab=NetworkLab(); lab.load(str(path))
                    check=result["case"]["baseline_check"]
                    ok, detail=lab.ping(check["source"],check["destination_ip"])
                    self.assertTrue(ok, detail)
                for event in result["case"]["events"]:
                    self.assertIn(event["device"],result["lab"]["devices"])
                    self.assertTrue(event["synthetic"])

    def test_deterministic_and_invalid_input(self):
        for scenario in schema()["templates"]:
            self.assertEqual(generate({"scenario":scenario})["case"],generate({"scenario":scenario})["case"])
        for invalid in ({"departments":True},{"departments":4},{"hosts_per_department":0},
                        {"scenario":[]},{"external_target":"example.com"}):
            with self.assertRaises(LabError): generate(invalid)

class CyberRangeHTTPTests(unittest.TestCase):
    setUpClass = isolated.PhysicalSpecialNotesHTTPTests.__dict__["setUpClass"]
    tearDownClass = isolated.PhysicalSpecialNotesHTTPTests.__dict__["tearDownClass"]
    setUp = isolated.PhysicalSpecialNotesHTTPTests.setUp
    request = isolated.PhysicalSpecialNotesHTTPTests.request

    def test_generation_is_non_destructive_and_discoverable(self):
        self.request("/api/command",{"command":"add pc Existing"})
        before=self.app.STATE.read_bytes()
        state=self.request("/api/state")[1]
        self.assertEqual(self.request("/api/cyber-range/schema")[0],200)
        self.assertIn("cyber_range_generate",self.request("/api/capabilities")[1]["agent_endpoints"])
        status,result=self.request("/api/cyber-range/generate",{"scenario":"service-outage"})
        self.assertEqual(status,200,result)
        self.assertEqual(result["case"]["evidence_type"],"synthetic_fixture")
        self.assertNotIn("Existing",result["lab"]["devices"])
        self.assertEqual(self.request("/api/cyber-range/generate",{"departments":0})[0],400)
        self.assertEqual(state,self.request("/api/state")[1])
        self.assertEqual(before,self.app.STATE.read_bytes())
        payload={"filename":"cyber-range-topology.json",
                 "data":base64.b64encode(json.dumps(result["lab"]).encode()).decode()}
        status,preview=self.request("/api/lab/import",payload)
        self.assertEqual(status,200,preview)
        self.assertEqual(preview["devices"],len(result["lab"]["devices"]))
        self.assertEqual(before,self.app.STATE.read_bytes())
        status,opened=self.request("/api/lab/import",{**payload,"commit":True})
        self.assertEqual(status,200,opened)
        self.assertIn("APP-SERVER",opened["state"]["devices"])
        self.assertTrue(opened["safety_backup"])

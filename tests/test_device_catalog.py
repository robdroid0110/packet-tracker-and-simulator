import json
import tempfile
import unittest
from pathlib import Path

from netsim.cli import CommandProcessor
from netsim.device_catalog import CATALOG, MODELS
from netsim.model import NetworkLab


class DeviceCatalogTests(unittest.TestCase):
    def test_packet_tracer_9_documented_catalog_is_exposed(self):
        self.assertGreaterEqual(len(MODELS), 150)
        for mid in ("isr4331", "2960-24tt", "wlc-3504", "asa-5506", "pc-pt", "copper-patch-panel", "garage-door", "mcu-pt", "temperature-sensor"):
            self.assertIn(mid, MODELS)
        groups = {(g["category"], g["subtype"]) for g in CATALOG["groups"]}
        for item in (("end", "Home"), ("end", "Smart City"), ("end", "Industrial"), ("end", "Power Grid"), ("components", "Boards"), ("components", "Actuators"), ("components", "Sensors")):
            self.assertIn(item, groups)

    def test_add_model_uses_existing_engine_when_available(self):
        lab = NetworkLab(); cp = CommandProcessor(lab)
        self.assertFalse(cp.execute("add-model isr4331 R1").startswith("ERROR:"))
        self.assertEqual(lab.devices["R1"].kind, "router")
        self.assertEqual(lab.devices["R1"].model, "isr4331")
        self.assertIn("g0/0", lab.devices["R1"].interfaces)

    def test_wlc_exposes_a_specialized_engine_without_claiming_router_ios(self):
        lab = NetworkLab(); cp = CommandProcessor(lab)
        self.assertFalse(cp.execute("add-model wlc-3504 WLC1").startswith("ERROR:"))
        self.assertEqual(lab.devices["WLC1"].kind, "generic")
        self.assertEqual(MODELS["wlc-3504"]["support"], "engine-simplified")

    def test_model_identity_survives_save_load(self):
        lab = NetworkLab(); cp = CommandProcessor(lab)
        cp.execute("add-model 2960-24tt SW1")
        with tempfile.TemporaryDirectory() as td:
            path = Path(td) / "lab.json"
            lab.save(str(path))
            other = NetworkLab(); other.load(str(path))
        self.assertEqual(other.devices["SW1"].model, "2960-24tt")
        self.assertEqual(other.devices["SW1"].kind, "switch")

    def test_catalog_is_json_serializable(self):
        json.dumps(CATALOG)


if __name__ == "__main__":
    unittest.main()

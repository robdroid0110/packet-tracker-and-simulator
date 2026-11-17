import json
import tempfile
import unittest
from pathlib import Path

from netsim.cli import CommandProcessor
from netsim.model import LabError, NetworkLab


class PhysicalConnectivityTests(unittest.TestCase):
    def test_pc_server_straight_through_down_cross_over_up(self):
        lab = NetworkLab()
        lab.add_device("pc", "PC1")
        lab.add_device("server", "S1")
        lab.set_ip("PC1", "eth0", "192.168.1.1/24")
        lab.set_ip("S1", "eth0", "192.168.1.2/24")
        lab.connect("PC1", "eth0", "S1", "eth0", "copper-straight")
        self.assertFalse(lab.to_dict()["links"][0]["up"])
        self.assertFalse(lab.ping("PC1", "192.168.1.2")[0])
        lab.disconnect("PC1", "eth0")
        lab.connect("PC1", "eth0", "S1", "eth0", "copper-cross")
        self.assertTrue(lab.to_dict()["links"][0]["up"])
        self.assertTrue(lab.ping("PC1", "192.168.1.2")[0])

    def test_switch_pc_straight_crossover_down(self):
        lab = NetworkLab()
        for kind, name in [("switch", "SW1"), ("pc", "PC1")]:
            lab.add_device(kind, name)
        lab.connect("SW1", "fa0/1", "PC1", "eth0", "copper-cross")
        self.assertFalse(lab.link_operational(lab.links[0]))
        lab.disconnect("PC1", "eth0")
        lab.connect("SW1", "fa0/1", "PC1", "eth0", "copper-straight")
        self.assertTrue(lab.link_operational(lab.links[0]))

    def test_power_cycle_preserves_config_drops_carrier(self):
        lab = NetworkLab()
        lab.add_device("switch", "SW1")
        lab.add_device("pc", "PC1")
        lab.add_device("pc", "PC2")
        lab.connect("SW1", "fa0/1", "PC1", "eth0")
        lab.connect("SW1", "fa0/2", "PC2", "eth0")
        lab.set_ip("PC1", "eth0", "10.1.1.1/24")
        lab.set_ip("PC2", "eth0", "10.1.1.2/24")
        self.assertTrue(lab.ping("PC1", "10.1.1.2")[0])
        self.assertTrue(lab.devices["SW1"].mac_table)
        lab.set_power("SW1", False)
        self.assertFalse(lab.devices["SW1"].mac_table)
        self.assertFalse(lab.to_dict()["links"][0]["up"])
        self.assertFalse(lab.ping("PC1", "10.1.1.2")[0])
        lab.set_power("SW1", True)
        self.assertTrue(lab.ping("PC1", "10.1.1.2")[0])
        self.assertEqual(lab.devices["PC1"].interfaces["eth0"].ip, "10.1.1.1/24")

    def test_cable_is_persisted_and_old_state_loads(self):
        lab = NetworkLab()
        for kind, name in [("pc", "PC1"), ("pc", "PC2")]:
            lab.add_device(kind, name)
        lab.connect("PC1", "eth0", "PC2", "eth0", "copper-cross")
        lab.set_power("PC2", False)
        data = lab.to_dict()
        self.assertEqual(data["links"][0]["cable"], "copper-cross")
        self.assertEqual(data["devices"]["PC2"]["powered"], False)
        with tempfile.TemporaryDirectory() as td:
            path = Path(td) / "lab.json"
            lab.save(str(path))
            clone = NetworkLab()
            clone.load(str(path))
            self.assertEqual(clone.links[0].cable, "copper-cross")
            self.assertFalse(clone.devices["PC2"].powered)
            legacy = json.loads(path.read_text())
            legacy["links"][0].pop("cable")
            legacy["links"][0].pop("up", None)
            legacy["links"][0].pop("status", None)
            legacy["devices"]["PC2"].pop("powered")
            path.write_text(json.dumps(legacy))
            clone.load(str(path))
            self.assertEqual(clone.links[0].cable, "auto")
            self.assertTrue(clone.devices["PC2"].powered)

    def test_agents_and_invalid_media(self):
        lab = NetworkLab()
        cp = CommandProcessor(lab)
        cp.execute("add pc PC1")
        cp.execute("add server SRV1")
        self.assertEqual(cp.execute("connect PC1 eth0 SRV1 eth0 copper-cross"), "link created")
        self.assertIn("copper-cross up", cp.execute("show links"))
        self.assertIn("powered off", cp.execute("power SRV1 off"))
        self.assertIn("copper-cross down", cp.execute("show links"))
        self.assertTrue(cp.execute("power SRV1 toggle").startswith("ERROR:"))
        self.assertIn("link removed", cp.execute("disconnect PC1 eth0"))
        self.assertIn("unsupported cable", cp.execute("connect PC1 eth0 SRV1 eth0 fiber-sm"))
        with self.assertRaisesRegex(LabError, "unsupported cable"):
            lab.connect("PC1", "eth0", "SRV1", "eth0", "usb")


if __name__ == "__main__":
    unittest.main()

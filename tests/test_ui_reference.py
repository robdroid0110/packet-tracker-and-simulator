import unittest

from netsim.cli import CommandProcessor
from netsim.model import LabError, NetworkLab


class HelpDrivenConfigTests(unittest.TestCase):
    def test_global_display_name_rename_keeps_links_and_address(self):
        lab = NetworkLab()
        lab.add_device("pc", "PC1")
        lab.add_device("switch", "SW1")
        lab.connect("PC1", "eth0", "SW1", "fa0/1")
        lab.set_ip("PC1", "eth0", "192.168.1.10/24")
        lab.rename_device("PC1", "OfficePC")
        self.assertNotIn("PC1", lab.devices)
        self.assertEqual(lab.devices["OfficePC"].interfaces["eth0"].ip, "192.168.1.10/24")
        self.assertEqual(lab.links[0].a_device, "OfficePC")

    def test_agent_rename_command_and_ios_session_follow_name(self):
        lab = NetworkLab()
        processor = CommandProcessor(lab)
        self.assertEqual(processor.execute("add router R1"), "added router R1")
        processor.execute("ios R1 enable")
        self.assertIn("renamed", processor.execute("rename R1 Core1"))
        self.assertNotIn("R1", lab.devices)
        self.assertIn("Core1", lab.devices)
        self.assertIn("Core1", processor.ios_sessions)
        self.assertEqual(processor.ios_sessions["Core1"].device, "Core1")

    def test_rename_rejects_existing_or_malformed_names(self):
        lab = NetworkLab()
        lab.add_device("pc", "PC1")
        lab.add_device("pc", "PC2")
        with self.assertRaises(LabError):
            lab.rename_device("PC1", "PC2")
        with self.assertRaises(LabError):
            lab.rename_device("PC1", "../outside")
        self.assertIn("PC1", lab.devices)
        self.assertIn("PC2", lab.devices)


if __name__ == "__main__":
    unittest.main()

"""Mode-aware IOS Tab completion regression tests; no saved labs required."""
import unittest
from copy import deepcopy

from netsim.model import NetworkLab
from netsim.ios import IOSSession
from netsim.ios_completion import complete


class IosTabCompletionTests(unittest.TestCase):
    def setUp(self):
        self.lab = NetworkLab()
        self.lab.add_device("router", "R1")
        self.lab.add_device("switch", "SW1")
        self.router = IOSSession(self.lab, "R1")
        self.switch = IOSSession(self.lab, "SW1")

    def tab(self, session, text, cursor=None):
        return complete(session, text, cursor)

    def test_unique_exec_command(self):
        result = self.tab(self.router, "sh")
        self.assertEqual(result["replacement"], "show")
        self.assertEqual(result["candidates"], ["show"])
        self.assertEqual(result["start"], 0)
        self.assertEqual(result["end"], 2)

    def test_multiword_show_command(self):
        self.assertEqual(self.tab(self.router, "show ip int")["replacement"], "interface")
        self.assertEqual(self.tab(self.router, "show ip interface br")["replacement"], "brief")

    def test_privileged_commands_only_in_privileged_mode(self):
        self.assertEqual(self.tab(self.router, "conf")["candidates"], [])
        self.router.execute("enable")
        self.assertEqual(self.router.mode, "priv")
        self.assertEqual(self.tab(self.router, "conf")["replacement"], "configure")
        self.assertEqual(self.tab(self.router, "conf t")["replacement"], "terminal")

    def test_config_interface_from_actual_hardware(self):
        self.router.execute("enable")
        self.router.execute("configure terminal")
        self.assertEqual(self.router.mode, "config")
        self.assertEqual(self.tab(self.router, "int")["replacement"], "interface")
        ifaces = sorted(self.lab.devices["R1"].interfaces)
        target = next(name for name in ifaces if name.startswith("g"))
        answer = self.tab(self.router, "int " + target[:-1])
        self.assertIn(target, answer["candidates"])
        unknown = self.tab(self.router, "interface imaginary")
        self.assertFalse(unknown["candidates"])

    def test_full_interface_aliases_are_suggested(self):
        self.router.execute("enable")
        self.router.execute("configure terminal")
        result = self.tab(self.router, "interface GigabitEthernet0/0")
        self.assertIn("GigabitEthernet0/0", result["candidates"])
        self.assertEqual(self.tab(self.router, "interface GigabitEth")["replacement"], "GigabitEthernet0/")

    def test_mode_aware_shutdown_and_switchport(self):
        self.switch.execute("enable")
        self.switch.execute("configure terminal")
        names = list(self.lab.devices["SW1"].interfaces)
        self.switch.execute("interface " + names[0])
        self.assertEqual(self.switch.mode, "interface")
        self.assertEqual(self.tab(self.switch, "shut")["replacement"], "shutdown")
        self.assertEqual(self.tab(self.switch, "no sh")["replacement"], "shutdown")
        self.assertEqual(self.tab(self.switch, "switchport mode tr")["replacement"], "trunk")
        self.assertEqual(self.tab(self.switch, "switchport access vl")["replacement"], "vlan")
        self.assertEqual(self.tab(self.switch, "show")["candidates"], [])
        self.assertEqual(self.tab(self.switch, "do show ip int")["replacement"], "interface")

    def test_multiple_candidates_do_not_guess(self):
        result = self.tab(self.router, "show ip ")
        self.assertGreater(len(result["candidates"]), 2)
        self.assertFalse(result["changed"])
        self.assertEqual(result["replacement"], "")

    def test_cursor_replacement_bounds(self):
        result = self.tab(self.router, "show ip intX trailing", cursor=11)
        self.assertEqual(result["start"], 8)
        self.assertEqual(result["end"], 12)
        self.assertEqual(result["replacement"], "interface")

    def test_no_completion_for_password_prompt(self):
        self.lab.devices["R1"].config["enable_secret"] = "private-password"
        self.router.awaiting_enable = True
        result = self.tab(self.router, "pri")
        self.assertEqual(result["candidates"], [])
        self.assertNotIn("private-password", str(result))

    def test_no_lab_mutation(self):
        before = deepcopy(self.lab.to_dict())
        self.router.execute("enable")
        self.tab(self.router, "show ip int")
        self.tab(self.router, "show interfaces g0/")
        self.assertEqual(self.lab.to_dict(), before)

    def test_rejects_invalid_inputs(self):
        for text, cursor in [("x\nx", None), ("a" * 2049, None),
                             ("test", -1), ("test", 6), ("test", True)]:
            with self.subTest(text=text[:12], cursor=cursor):
                with self.assertRaises(ValueError):
                    self.tab(self.router, text, cursor)


if __name__ == "__main__":
    unittest.main()

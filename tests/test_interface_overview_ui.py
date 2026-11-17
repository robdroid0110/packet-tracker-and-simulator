"""Interface Overview UI contract: checks presence without confusing UI with simulation parity."""
from pathlib import Path
import shutil
import subprocess
import unittest

ROOT = Path(__file__).resolve().parents[1]
HTML = (ROOT / "web/index.html").read_text()
JS = (ROOT / "web/interface-overview.js").read_text()
CSS = (ROOT / "web/interface-overview.css").read_text()

class InterfaceOverviewUITests(unittest.TestCase):
    def test_ui_layer_is_loaded_after_core_and_preferences(self):
        self.assertIn('href="/interface-overview.css"', HTML)
        self.assertIn('src="/interface-overview.js"', HTML)
        self.assertLess(HTML.index('src="/physical-links.js"'), HTML.index('src="/interface-overview.js"'))

    def test_eight_documented_menus_and_tools(self):
        for menu in ("File", "Edit", "Options", "View", "Tools", "Extensions", "Window", "Help"):
            self.assertIn(menu + ":", JS)
        for tool in ("Inspect", "Resize Shape", "Place Note", "Drawing Palette", "Add Simple PDU", "Add Complex PDU"):
            self.assertIn(tool, JS)

    def test_physical_and_logical_workspace_controls(self):
        for landmark in ("Intercity", "Home City", "Corporate Office", "Main Wiring Closet",
                         "New City", "New Building", "New Closet", "Working Closet",
                         "New Cluster", "Viewport", "Set Tiled Background"):
            self.assertIn(landmark, JS)

    def test_scenarios_are_local_ui_not_fake_network_traffic(self):
        for feature in ("openPduEditor", "renderPduWindow", "scenarioNames", "ptPduWindow", "setDetached"):
            self.assertIn(feature, JS)
        self.assertIn("Simple ICMP PDUs are backed by simulated network reachability", JS)
        self.assertIn("Only ICMP PDU transmission is implemented", JS)
        self.assertIn("#ptPduWindow", CSS)

    def test_ucpw_can_be_collapsed_or_detached(self):
        self.assertIn("pt-ucpw-hidden", JS)
        self.assertIn("pt-ucpw-hidden", CSS)
        self.assertIn("pdu-undocked", CSS)
        self.assertIn("Toggle PDU List Window", HTML)

    def test_javascript_syntax(self):
        node = shutil.which("node")
        if node is None:
            self.skipTest("Node.js not available for JavaScript parser check")
        subprocess.run([node, "--check", str(ROOT / "web/interface-overview.js")], check=True,
                       capture_output=True, text=True)

if __name__ == "__main__":
    unittest.main()

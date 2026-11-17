"""Release-specific checks for original assets and self-contained help."""
import unittest
from pathlib import Path

from netsim.original_icons import icon_svg
from netsim.capabilities import PRODUCT

ROOT = Path(__file__).resolve().parents[1]

class ReleaseIndependenceTests(unittest.TestCase):
    def test_original_icons_are_rendered_for_all_ui_categories(self):
        for category in ('toolbar/new.svg', 'device/router.svg', 'componentbox/switch.svg',
                         'desktop/browser.svg', 'physical-devices/rack.svg'):
            svg = icon_svg(category).decode('utf-8')
            self.assertTrue(svg.startswith('<svg '))
            self.assertIn('viewBox="0 0 64 64"', svg)
            self.assertNotIn('<script', svg)

    def test_branding_is_consistent(self):
        self.assertEqual(PRODUCT, "Packet Tracker and Simulator")
        html = (ROOT / "web/index.html").read_text()
        self.assertIn('<title>Packet Tracker and Simulator</title>', html)

    def test_self_contained_help_exists(self):
        page = (ROOT / "web/help/index.html").read_text()
        self.assertIn('Packet Tracker and Simulator — Help', page)
        self.assertIn('Keyboard shortcuts', page)

    def test_frontend_has_no_external_simulator_asset_dependency(self):
        for entry in (ROOT / 'web').glob('*.js'):
            self.assertNotIn('/vendor/packettracer/', entry.read_text())
            self.assertNotIn("'/reference/", entry.read_text())

    def test_release_metadata(self):
        for file in ('LICENSE', 'CONTRIBUTING.md', 'SECURITY.md', 'THIRD_PARTY_NOTICES.md'):
            self.assertTrue((ROOT / file).is_file(), file)

if __name__ == '__main__':
    unittest.main()

"""Validate the isolated lookup experiment against forwarding behavior."""
import tempfile
from pathlib import Path
import unittest

from netsim.model import NetworkLab
from tools.probe_ping_index import run


ROOT = Path(__file__).resolve().parents[1]


class ScopedLookupProofTests(unittest.TestCase):
    def test_optimized_and_unmodified_ping_match_on_connected_and_failed_paths(self):
        lab = NetworkLab()
        lab.load(str(ROOT / 'labs/audit/campus.json'))
        with tempfile.TemporaryDirectory(prefix='pt-proof-test-') as folder:
            fixture = Path(folder) / 'lab.json'
            for down in (False, True):
                if down:
                    lab.set_interface_state('R1', 'g0/1', False)
                    lab.set_interface_state('R1', 'g0/2', False)
                lab.save(str(fixture))
                _, _, expected, expected_tables = run(fixture, 'baseline')
                self.assertEqual(expected[0], not down)
                for variant in ('index', 'stp', 'both'):
                    _, _, actual, tables = run(fixture, variant)
                    self.assertEqual(actual, expected, (down, variant))
                    self.assertEqual(tables, expected_tables, (down, variant))

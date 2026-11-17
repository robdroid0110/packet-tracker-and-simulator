"""Exercise original mixed labs through a real, isolated HTTP server."""
import json
from pathlib import Path
import tempfile
import unittest

from tools.audit_networks import run


class SystemAuditTests(unittest.TestCase):
    def test_network_services_recovery_and_agent_errors(self):
        with tempfile.TemporaryDirectory() as folder:
            output = Path(folder)
            report = run(output)
            self.assertEqual(report['findings'], [])
            self.assertEqual([(p['devices'], p['links']) for p in report['projects']],
                             [(16, 17), (11, 10), (10, 9)])
            campus = json.loads((output / 'campus.json').read_text())
            for number in range(1, 7):
                self.assertEqual(campus['devices'][f'PC{number}']['dns_server'],
                                 '172.16.3.10')

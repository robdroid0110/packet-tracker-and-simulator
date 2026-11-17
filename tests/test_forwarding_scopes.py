"""Behavioral regressions for isolated forwarding evaluations."""
from concurrent.futures import ThreadPoolExecutor
from contextlib import nullcontext
from copy import deepcopy
import json
from pathlib import Path
import subprocess
import sys
import tempfile
import time
import unittest
from unittest.mock import patch
from urllib.request import Request, urlopen

from netsim.model import LabError, NetworkLab
from netsim.cli import CommandProcessor
from netsim.simulation import action

ROOT = Path(__file__).resolve().parents[1]


def load(name):
    lab = NetworkLab()
    lab.load(str(ROOT / 'labs' / 'audit' / (name + '.json')))
    return lab


class ForwardingScopeTests(unittest.TestCase):
    def assert_equivalent(self, old, new, operation):
        # Disable the new scoped reuse to compare with the previous algorithm.
        with patch.object(NetworkLab, '_forwarding_scope', lambda self: nullcontext()):
            expected = operation(old)
        actual = operation(new)
        self.assertEqual(actual, expected)
        self.assertEqual(new.to_dict(), old.to_dict())
        return actual

    def test_campus_topology_vlan_stp_acl_and_link_changes(self):
        old = load('campus')
        new = deepcopy(old)
        ping_pc = lambda lab: lab.ping('PC1', '10.10.10.101')
        ping_web = lambda lab: lab.ping('PC1', '172.16.3.20')

        for operation in (ping_pc, ping_web, lambda lab: lab.traceroute('PC1', '172.16.3.20')):
            self.assertTrue(self.assert_equivalent(old, new, operation)[0])
        for lab in (old, new):
            lab.set_interface_state('SW1', 'g0/1', False)
            lab.set_stp_priority('SW3', 4096)
        self.assertTrue(self.assert_equivalent(old, new, ping_pc)[0])
        for lab in (old, new):
            lab.set_switchport_access('SW2', 'fa0/1', 20)
        self.assertFalse(self.assert_equivalent(old, new, ping_pc)[0])
        for lab in (old, new):
            lab.set_switchport_access('SW2', 'fa0/1', 10)
        self.assertTrue(self.assert_equivalent(old, new, ping_pc)[0])
        for lab in (old, new):
            lab.disconnect('PC2', 'eth0')
        self.assertFalse(self.assert_equivalent(old, new, ping_pc)[0])
        for lab in (old, new):
            lab.connect('PC2', 'eth0', 'SW2', 'fa0/1')
        self.assertTrue(self.assert_equivalent(old, new, ping_pc)[0])
        for lab in (old, new):
            lab.set_power('PC2', False)
        self.assertFalse(self.assert_equivalent(old, new, ping_pc)[0])
        for lab in (old, new):
            lab.set_power('PC2', True)
        self.assertTrue(self.assert_equivalent(old, new, ping_pc)[0])
        for lab in (old, new):
            lab.add_acl_rule('R1', 'DENY', 'deny', 'icmp', 'any', 'any')
            lab.set_access_group('R1', 'g0/0.10', 'DENY', 'in')
        self.assertFalse(self.assert_equivalent(old, new, ping_web)[0])
        for lab in (old, new):
            lab.set_access_group('R1', 'g0/0.10', None, 'in')
        self.assertTrue(self.assert_equivalent(old, new, ping_web)[0])

    def test_nat_ipv6_and_simulation_state_match(self):
        old = load('branch')
        new = deepcopy(old)
        self.assertTrue(self.assert_equivalent(old, new, lambda lab: lab.ping('Branch1', '203.0.113.10'))[0])
        self.assertTrue(new.devices['EDGE'].nat_sessions)
        old = load('campus')
        new = deepcopy(old)
        for lab in (old, new):
            lab.devices['PC1'].interfaces['eth0'].ipv6 = '2001:db8::1/64'
            lab.devices['PC2'].interfaces['eth0'].ipv6 = '2001:db8::2/64'
        ping = lambda lab: lab.ping('PC1', '2001:db8::2')
        self.assertTrue(self.assert_equivalent(old, new, ping)[0])
        for lab in (old, new):
            lab.set_interface_state('PC2', 'eth0', False)
        self.assertFalse(self.assert_equivalent(old, new, ping)[0])
        for lab in (old, new):
            lab.set_interface_state('PC2', 'eth0', True)
            action(lab, {'action': 'mode', 'mode': 'simulation'})
            action(lab, {'action': 'pdu_add', 'id': 'regression-pdu', 'source': 'PC1', 'destination': 'WEB'})
        while True:
            event = self.assert_equivalent(old, new, lambda lab: action(lab, {'action': 'step'}))
            if event is None:
                break
        self.assertEqual(next(iter(new.simulation['pdus'].values()))['status'], 'Successful')

    def test_exceptions_nested_labs_and_save_load_do_not_leak_topology(self):
        one = load('campus')
        two = deepcopy(one)
        with self.assertRaises(LabError):
            one.ping('missing', '10.10.10.101')
        with one._forwarding_scope():
            self.assertTrue(one.ping('PC1', '10.10.10.101')[0])
            two.disconnect('PC2', 'eth0')
            self.assertFalse(two.ping('PC1', '10.10.10.101')[0])
            self.assertTrue(one.ping('PC1', '10.10.10.101')[0])
        one.disconnect('PC2', 'eth0')
        self.assertFalse(one.ping('PC1', '10.10.10.101')[0])
        with tempfile.TemporaryDirectory(prefix='pt-forwarding-save-') as tmp:
            path = Path(tmp) / 'lab.json'
            one.save(str(path))
            restored = NetworkLab()
            restored.load(str(path))
            self.assertFalse(restored.ping('PC1', '10.10.10.101')[0])
            restored.connect('PC2', 'eth0', 'SW2', 'fa0/1')
            self.assertTrue(restored.ping('PC1', '10.10.10.101')[0])

    def test_undo_and_redo_restore_forwarding(self):
        lab = load('campus')
        cli = CommandProcessor(lab)
        self.assertTrue(lab.ping('PC1', '10.10.10.101')[0])
        self.assertFalse(cli.execute('disconnect PC2 eth0').startswith('ERROR:'))
        self.assertFalse(lab.ping('PC1', '10.10.10.101')[0])
        self.assertEqual(cli.execute('undo'), 'Undo completed')
        self.assertTrue(lab.ping('PC1', '10.10.10.101')[0])
        self.assertEqual(cli.execute('redo'), 'Redo completed')
        self.assertFalse(lab.ping('PC1', '10.10.10.101')[0])

    def test_concurrent_agent_requests_observe_their_own_topology(self):
        with tempfile.TemporaryDirectory(prefix='pt-forwarding-http-') as tmp:
            folder = Path(tmp)
            lab = NetworkLab()
            for name in ('A', 'B'):
                lab.add_device('pc', name)
            lab.connect('A', 'eth0', 'B', 'eth0')
            lab.set_ip('A', 'eth0', '192.0.2.1/24')
            lab.set_ip('B', 'eth0', '192.0.2.2/24')
            lab.save(str(folder / 'state.json'))
            ready = folder / 'ready.json'
            server = subprocess.Popen([sys.executable, str(ROOT / 'desktop.py'), '--server', '--port', '0',
                                       '--state', str(folder / 'state.json'), '--ready-file', str(ready)],
                                      cwd=ROOT, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
            try:
                for _ in range(300):
                    if ready.exists():
                        break
                    if server.poll() is not None:
                        self.fail('isolated server exited')
                    time.sleep(.02)
                self.assertTrue(ready.exists())
                url = 'http://127.0.0.1:' + str(json.loads(ready.read_text())['port']) + '/api/command'
                def command(text):
                    req = Request(url, data=json.dumps({'command': text}).encode(),
                                  headers={'Content-Type': 'application/json'})
                    with urlopen(req, timeout=20) as response:
                        return json.load(response)
                def check(result):
                    self.assertTrue(result['ok'])
                    up = result['state']['devices']['B']['interfaces']['eth0']['admin_up']
                    self.assertEqual('PING success' in result['output'], up)
                check(command('ping A 192.0.2.2'))
                command('down B eth0')
                check(command('ping A 192.0.2.2'))
                commands = ['up B eth0', 'ping A 192.0.2.2', 'down B eth0', 'ping A 192.0.2.2'] * 8
                with ThreadPoolExecutor(max_workers=6) as pool:
                    for text, result in zip(commands, pool.map(command, commands)):
                        if text.startswith('ping '):
                            check(result)
                        else:
                            self.assertTrue(result['ok'])
            finally:
                server.terminate()
                server.wait(timeout=10)


if __name__ == '__main__':
    unittest.main()

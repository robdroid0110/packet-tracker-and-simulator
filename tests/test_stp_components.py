import unittest
from netsim.model import NetworkLab
from netsim.cli import CommandProcessor
from netsim.ios import IOSSession


class IndependentSpanningTrees(unittest.TestCase):
    def test_disconnected_lans_forward_and_report_their_own_roots(self):
        lab = NetworkLab()
        for name in ('A1', 'A2', 'B1', 'B2'):
            lab.add_device('switch', name)
        lab.devices['A1'].stp_priority = 0
        lab.devices['B1'].stp_priority = 4096
        for a, b in (('A1', 'A2'), ('B1', 'B2')):
            lab.connect(a, 'g0/1', b, 'g0/1')
        for i, switch in ((1, 'B1'), (2, 'B2')):
            name = f'Host{i}'
            lab.add_device('pc', name)
            lab.connect(name, 'eth0', switch, 'fa0/1')
            lab.set_ip(name, 'eth0', f'192.168.10.{i}/24')
        tree = lab.spanning_tree(1)
        self.assertEqual(tree['component_roots']['B2'], 'B1')
        self.assertEqual(tree['ports']['B2:g0/1']['state'], 'forwarding')
        self.assertTrue(lab.ping('Host1', '192.168.10.2')[0])
        self.assertIn('Root: B1', CommandProcessor(lab).execute('show stp B2'))
        self.assertIn('Root ID    Bridge B1', IOSSession(lab, 'B2').execute('show spanning-tree'))
        lab.connect('A2', 'g0/2', 'B1', 'g0/2')
        self.assertEqual(lab.spanning_tree(1)['component_roots']['B2'], 'A1')
        lab.disconnect('A2', 'g0/2')
        self.assertEqual(lab.spanning_tree(1)['component_roots']['B2'], 'B1')
        self.assertTrue(lab.ping('Host1', '192.168.10.2')[0])

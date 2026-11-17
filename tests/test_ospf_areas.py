"""Area-aware OSPF behavior, compatibility and control surfaces."""
import json
import tempfile
import unittest
from pathlib import Path

from netsim.cli import CommandProcessor
from netsim.device_config import action, restore, snapshot
from netsim.ios import IOSSession
from netsim.lab_import import import_running_config
from netsim.model import LabError, NetworkLab


class OSPFAreaTests(unittest.TestCase):
    def pair(self):
        lab = NetworkLab()
        for kind, name in [('router', 'R1'), ('router', 'R2'), ('pc', 'PC')]:
            lab.add_device(kind, name)
        lab.connect('R1', 'g0/0', 'R2', 'g0/0')
        lab.connect('R2', 'g0/1', 'PC', 'eth0')
        for name, interface, address in [('R1', 'g0/0', '10.0.0.1/30'), ('R2', 'g0/0', '10.0.0.2/30'),
                                         ('R2', 'g0/1', '192.168.2.1/24'), ('PC', 'eth0', '192.168.2.2/24')]:
            lab.set_ip(name, interface, address)
        lab.set_gateway('PC', '192.168.2.1')
        return lab

    def ospf_routes(self, lab, name):
        return {r.network: r.next_hop for r in lab.devices[name].routes if r.source == 'ospf'}

    def test_matching_networks_areas_advertisement_and_link_state(self):
        lab = self.pair()
        lab.enable_ospf('R1', '198.51.100.0/24', 0)
        lab.enable_ospf('R2', '203.0.113.0/24', 0)
        self.assertEqual(lab.ospf_status('R1')['neighbors'], [])
        self.assertEqual(self.ospf_routes(lab, 'R1'), {})
        lab.enable_ospf('R1', '10.0.0.0/30', 1)
        lab.enable_ospf('R2', '10.0.0.0/30', 2)
        self.assertEqual(lab.ospf_status('R1')['neighbors'], [])
        lab.enable_ospf('R2', '10.0.0.0/30', '0.0.0.1')
        self.assertEqual(lab.ospf_status('R1')['neighbors'][0]['area'], 1)
        self.assertNotIn('192.168.2.0/24', self.ospf_routes(lab, 'R1'))
        lab.enable_ospf('R2', '192.168.2.0/24', 1)
        self.assertEqual(self.ospf_routes(lab, 'R1')['192.168.2.0/24'], '10.0.0.2')
        self.assertTrue(lab.ping('R1', '192.168.2.2')[0])
        lab.set_interface_state('R2', 'g0/0', False)
        self.assertEqual(lab.ospf_status('R1')['neighbors'], [])
        self.assertNotIn('192.168.2.0/24', self.ospf_routes(lab, 'R1'))
        lab.set_interface_state('R2', 'g0/0', True)
        self.assertIn('192.168.2.0/24', self.ospf_routes(lab, 'R1'))
        lab.remove_ospf_network('R2', '192.168.2.0/24', 1)
        self.assertNotIn('192.168.2.0/24', self.ospf_routes(lab, 'R1'))

    def test_multiarea_requires_backbone_on_abr(self):
        lab = NetworkLab()
        for kind, name in [('router', 'R1'), ('router', 'ABR'), ('router', 'R3'),
                           ('pc', 'P1'), ('pc', 'P3'), ('pc', 'Backbone')]:
            lab.add_device(kind, name)
        for a, ap, b, bp in [('R1', 'g0/0', 'ABR', 'g0/0'), ('ABR', 'g0/1', 'R3', 'g0/0'),
                             ('R1', 'g0/1', 'P1', 'eth0'), ('R3', 'g0/1', 'P3', 'eth0'),
                             ('ABR', 'g0/2', 'Backbone', 'eth0')]:
            lab.connect(a, ap, b, bp)
        for n, port, ip in [('R1', 'g0/0', '10.0.0.1/30'), ('ABR', 'g0/0', '10.0.0.2/30'),
                            ('ABR', 'g0/1', '10.0.0.5/30'), ('R3', 'g0/0', '10.0.0.6/30'),
                            ('R1', 'g0/1', '10.1.0.1/24'), ('P1', 'eth0', '10.1.0.2/24'),
                            ('R3', 'g0/1', '10.3.0.1/24'), ('P3', 'eth0', '10.3.0.2/24'),
                            ('ABR', 'g0/2', '172.16.0.1/24')]:
            lab.set_ip(n, port, ip)
        lab.set_gateway('P1', '10.1.0.1')
        lab.set_gateway('P3', '10.3.0.1')
        for n, network, area in [('R1', '10.0.0.0/30', 1), ('R1', '10.1.0.0/24', 1),
                                 ('ABR', '10.0.0.0/30', 1), ('ABR', '10.0.0.4/30', 2),
                                 ('R3', '10.0.0.4/30', 2), ('R3', '10.3.0.0/24', 2)]:
            lab.enable_ospf(n, network, area)
        self.assertNotIn('10.3.0.0/24', self.ospf_routes(lab, 'R1'))
        self.assertFalse(lab.ping('P1', '10.3.0.2')[0])
        lab.enable_ospf('ABR', '172.16.0.0/24', 0)
        self.assertEqual(self.ospf_routes(lab, 'R1')['10.3.0.0/24'], '10.0.0.2')
        self.assertTrue(lab.ping('P1', '10.3.0.2')[0])
        lab.set_interface_state('ABR', 'g0/2', False)
        self.assertNotIn('10.3.0.0/24', self.ospf_routes(lab, 'R1'))

    def test_topology_edits_refresh_routes_and_neighbors(self):
        lab = NetworkLab()
        for kind, name in [('router', 'R1'), ('router', 'R2'),
                           ('switch', 'SW'), ('pc', 'LAN')]:
            lab.add_device(kind, name)
        for name, port, ip in [('R1', 'g0/0', '10.0.0.1/30'),
                               ('R2', 'g0/0', '10.0.0.2/30'),
                               ('R2', 'g0/1', '192.168.2.1/24')]:
            lab.set_ip(name, port, ip)
        for name in ('R1', 'R2'):
            lab.enable_ospf(name, '10.0.0.0/30', 3)
        lab.enable_ospf('R2', '192.168.2.0/24', 3)
        lab.connect('R2', 'g0/1', 'LAN', 'eth0')
        lab.connect('R1', 'g0/0', 'SW', 'fa0/1')
        lab.connect('R2', 'g0/0', 'SW', 'fa0/2')
        self.assertIn('192.168.2.0/24', self.ospf_routes(lab, 'R1'))
        lab.set_switchport_access('SW', 'fa0/1', 10)
        self.assertEqual(lab.ospf_status('R1')['neighbors'], [])
        self.assertNotIn('192.168.2.0/24', self.ospf_routes(lab, 'R1'))
        lab.set_switchport_access('SW', 'fa0/2', 10)
        self.assertIn('192.168.2.0/24', self.ospf_routes(lab, 'R1'))
        lab.disconnect('SW', 'fa0/2')
        self.assertNotIn('192.168.2.0/24', self.ospf_routes(lab, 'R1'))
        lab.connect('R2', 'g0/0', 'SW', 'fa0/2')
        self.assertIn('192.168.2.0/24', self.ospf_routes(lab, 'R1'))
        lab.remove_device('SW')
        self.assertNotIn('192.168.2.0/24', self.ospf_routes(lab, 'R1'))

    def test_next_hop_uses_the_interface_in_the_selected_area(self):
        lab = self.pair()
        lab.connect('R1', 'g0/1', 'R2', 'g0/2')
        lab.set_ip('R1', 'g0/1', '10.0.0.5/30')
        lab.set_ip('R2', 'g0/2', '10.0.0.6/30')
        for name, network, area in [('R1', '10.0.0.0/30', 0),
                                    ('R2', '10.0.0.0/30', 0),
                                    ('R1', '10.0.0.4/30', 1),
                                    ('R2', '10.0.0.4/30', 1),
                                    ('R2', '192.168.2.0/24', 1)]:
            lab.enable_ospf(name, network, area)
        self.assertEqual(self.ospf_routes(lab, 'R1')['192.168.2.0/24'], '10.0.0.6')
        self.assertTrue(lab.ping('R1', '192.168.2.2')[0])
        lab.set_interface_state('R1', 'g0/1', False)
        self.assertEqual(self.ospf_routes(lab, 'R1')['192.168.2.0/24'], '10.0.0.2')
        self.assertTrue(lab.ping('R1', '192.168.2.2')[0])
        lab.set_interface_state('R1', 'g0/1', True)
        self.assertEqual(self.ospf_routes(lab, 'R1')['192.168.2.0/24'], '10.0.0.6')

    def test_deleting_and_restoring_trunk_vlan_withdraws_routes(self):
        lab = NetworkLab()
        for kind, name in [('router', 'R1'), ('router', 'R2'),
                           ('switch', 'SW'), ('pc', 'LAN')]:
            lab.add_device(kind, name)
        lab.connect('R1', 'g0/0', 'SW', 'fa0/1')
        lab.connect('R2', 'g0/0', 'SW', 'fa0/2')
        lab.connect('R2', 'g0/1', 'LAN', 'eth0')
        lab.set_switchport_trunk('SW', 'fa0/1', [10])
        lab.set_switchport_trunk('SW', 'fa0/2', [10])
        lab.add_subinterface('R1', 'g0/0', 10, '10.0.0.1/30')
        lab.add_subinterface('R2', 'g0/0', 10, '10.0.0.2/30')
        lab.set_ip('R2', 'g0/1', '192.168.2.1/24')
        lab.enable_ospf('R1', '10.0.0.0/30', 3)
        lab.enable_ospf('R2', '10.0.0.0/30', 3)
        lab.enable_ospf('R2', '192.168.2.0/24', 3)
        self.assertIn('192.168.2.0/24', self.ospf_routes(lab, 'R1'))
        action(lab, {'device': 'SW', 'action': 'vlan_delete', 'vlan': 10})
        self.assertEqual(lab.ospf_status('R1')['neighbors'], [])
        self.assertNotIn('192.168.2.0/24', self.ospf_routes(lab, 'R1'))
        lab.add_vlan('SW', 10)
        self.assertIn('192.168.2.0/24', self.ospf_routes(lab, 'R1'))

    def test_nonbackbone_area_does_not_bridge_a_partitioned_backbone(self):
        lab = NetworkLab()
        for kind, name in [('router', 'S'), ('router', 'A'), ('router', 'B'),
                           ('router', 'T'), ('pc', 'LAN')]:
            lab.add_device(kind, name)
        for a, ap, b, bp in [('S', 'g0/0', 'A', 'g0/0'),
                             ('A', 'g0/1', 'B', 'g0/0'),
                             ('B', 'g0/1', 'T', 'g0/0'),
                             ('T', 'g0/1', 'LAN', 'eth0')]:
            lab.connect(a, ap, b, bp)
        for name, port, address in [('S', 'g0/0', '10.0.0.1/30'),
                                    ('A', 'g0/0', '10.0.0.2/30'),
                                    ('A', 'g0/1', '10.0.0.5/30'),
                                    ('B', 'g0/0', '10.0.0.6/30'),
                                    ('B', 'g0/1', '10.0.0.9/30'),
                                    ('T', 'g0/0', '10.0.0.10/30'),
                                    ('T', 'g0/1', '192.168.10.1/24')]:
            lab.set_ip(name, port, address)
        for name, network, area in [('S', '10.0.0.0/30', 0),
                                    ('A', '10.0.0.0/30', 0),
                                    ('A', '10.0.0.4/30', 1),
                                    ('B', '10.0.0.4/30', 1),
                                    ('B', '10.0.0.8/30', 0),
                                    ('T', '10.0.0.8/30', 0),
                                    ('T', '192.168.10.0/24', 0)]:
            lab.enable_ospf(name, network, area)
        self.assertNotIn('192.168.10.0/24', self.ospf_routes(lab, 'S'))
        lab.connect('A', 'g0/2', 'B', 'g0/2')
        lab.set_ip('A', 'g0/2', '10.0.0.13/30')
        lab.set_ip('B', 'g0/2', '10.0.0.14/30')
        lab.enable_ospf('A', '10.0.0.12/30', 0)
        lab.enable_ospf('B', '10.0.0.12/30', 0)
        self.assertIn('192.168.10.0/24', self.ospf_routes(lab, 'S'))
        lab.set_interface_state('A', 'g0/2', False)
        self.assertNotIn('192.168.10.0/24', self.ospf_routes(lab, 'S'))

    def test_ios_area_process_no_network_and_running_config(self):
        lab = self.pair()
        session = IOSSession(lab, 'R2')
        for command in ('enable', 'configure terminal', 'router ospf 42'):
            self.assertFalse(session.execute(command).startswith('%'))
        self.assertFalse(lab.devices['R2'].ospf_auto)
        self.assertFalse(session.execute('network 10.0.0.0 0.0.0.3 area 0.0.0.1').startswith('%'))
        self.assertFalse(session.execute('network 192.168.2.0 0.0.0.255 area 1').startswith('%'))
        self.assertTrue(session.execute('network 10.0.0.0 0.0.0.3 area 4294967296').startswith('%'))
        session.execute('end')
        running = session.execute('show running-config')
        self.assertIn('router ospf 42', running)
        self.assertIn('network 10.0.0.0 0.0.0.3 area 1', running)
        session.execute('configure terminal')
        self.assertTrue(session.execute('router ospf 43').startswith('%'))
        session.execute('router ospf 42')
        self.assertTrue(session.execute('no network 10.0.0.0 0.0.0.3 area 0').startswith('%'))
        self.assertFalse(session.execute('no network 10.0.0.0 0.0.0.3 area 1').startswith('%'))
        self.assertEqual(lab.devices['R2'].ospf_networks, ['192.168.2.0/24'])
        session.execute('exit')
        self.assertFalse(session.execute('no router ospf 42').startswith('%'))
        self.assertFalse(lab.devices['R2'].ospf_enabled)
        self.assertEqual(lab.devices['R2'].ospf_networks, [])

    def test_save_load_legacy_and_startup_snapshot(self):
        lab = self.pair()
        lab.enable_ospf('R1')
        lab.enable_ospf('R2', '10.0.0.0/30', 7, process_id=5)
        saved = snapshot(lab, lab.devices['R2'])
        with tempfile.TemporaryDirectory() as folder:
            path = Path(folder) / 'lab.json'
            lab.save(str(path))
            loaded = NetworkLab()
            loaded.load(str(path))
            self.assertTrue(loaded.devices['R1'].ospf_auto)
            self.assertEqual(loaded.devices['R2'].ospf_areas['10.0.0.0/30'], 7)
            self.assertEqual(loaded.devices['R2'].ospf_process_id, 5)
            raw = json.loads(path.read_text())
            for device in raw['devices'].values():
                for key in ('ospf_auto', 'ospf_areas', 'ospf_process_id'):
                    device.pop(key, None)
            path.write_text(json.dumps(raw))
            legacy = NetworkLab()
            legacy.load(str(path))
            self.assertTrue(legacy.devices['R1'].ospf_auto)
            self.assertEqual(legacy.devices['R2'].ospf_areas['10.0.0.0/30'], 0)
            self.assertFalse(legacy.devices['R2'].ospf_auto)
        lab.enable_ospf('R2', '192.168.2.0/24', 9)
        restore(lab, lab.devices['R2'], saved)
        self.assertEqual(lab.devices['R2'].ospf_areas, {'10.0.0.0/30': 7})
        legacy_snapshot = dict(saved)
        for key in ('ospf_auto', 'ospf_areas', 'ospf_process_id'):
            legacy_snapshot.pop(key)
        restore(lab, lab.devices['R2'], legacy_snapshot)
        self.assertEqual(lab.devices['R2'].ospf_areas, {'10.0.0.0/30': 0})

    def test_agent_commands_are_undoable_and_invalid_input_is_atomic(self):
        lab = self.pair()
        cli = CommandProcessor(lab)
        self.assertIn('enabled', cli.execute('ospf R1 enable 10.0.0.0/30 area 7'))
        state = json.loads(cli.execute('show ospf R1'))
        self.assertEqual(state['networks'], [{'network': '10.0.0.0/30', 'area': 7}])
        before = lab.to_dict()
        self.assertTrue(cli.execute('ospf R1 enable 0.0.0.0/0 area -1').startswith('ERROR:'))
        self.assertEqual(lab.to_dict(), before)
        cli.execute('undo')
        self.assertFalse(lab.devices['R1'].ospf_enabled)
        cli.execute('redo')
        self.assertEqual(lab.devices['R1'].ospf_areas['10.0.0.0/30'], 7)
        cli.execute('ospf R1 disable')
        self.assertFalse(lab.devices['R1'].ospf_enabled)
        self.assertEqual(lab.devices['R1'].ospf_areas['10.0.0.0/30'], 7)
        cli.execute('ospf R1 enable')
        self.assertFalse(lab.devices['R1'].ospf_auto)
        cli.execute('ospf R1 auto')
        self.assertTrue(lab.devices['R1'].ospf_auto)
        cli.execute('ospf R1 remove 10.0.0.0/30')
        self.assertEqual(lab.devices['R1'].ospf_networks, [])

    def test_import_preserves_area_and_process(self):
        lab = self.pair()
        warnings = []
        import_running_config(lab, lab.devices['R2'], [
            'router ospf 77', 'network 10.0.0.0 0.0.0.3 area 3', '!'], warnings)
        self.assertEqual(warnings, [])
        self.assertEqual(lab.devices['R2'].ospf_process_id, 77)
        self.assertEqual(lab.devices['R2'].ospf_areas, {'10.0.0.0/30': 3})

    def test_longest_matching_network_and_validation(self):
        lab = self.pair()
        lab.enable_ospf('R1', '10.0.0.0/8', 2)
        lab.enable_ospf('R1', '10.0.0.0/30', 3)
        self.assertEqual(lab.ospf_status('R1')['interfaces'][0]['area'], 3)
        before = lab.to_dict()
        with self.assertRaises(LabError): lab.enable_ospf('R1', '10.0.0.0/30', True)
        self.assertEqual(lab.to_dict(), before)

    def test_disabled_process_configuration_cannot_be_moved_to_another_id(self):
        lab = self.pair()
        lab.enable_ospf('R1', '10.0.0.0/30', 3, process_id=42)
        lab.disable_ospf('R1')
        before = lab.to_dict()
        with self.assertRaises(LabError):
            lab.enable_ospf('R1', automatic=False, process_id=43)
        self.assertEqual(lab.to_dict(), before)


if __name__ == '__main__': unittest.main()

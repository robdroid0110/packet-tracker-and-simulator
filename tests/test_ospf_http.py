"""Verify area-aware OSPF through the actual shared HTTP backend."""
import unittest
import test_physical_special_notes_http as isolated


class OSPFHTTPTests(unittest.TestCase):
    setUpClass = isolated.PhysicalSpecialNotesHTTPTests.__dict__['setUpClass']
    tearDownClass = isolated.PhysicalSpecialNotesHTTPTests.__dict__['tearDownClass']
    setUp = isolated.PhysicalSpecialNotesHTTPTests.setUp
    request = isolated.PhysicalSpecialNotesHTTPTests.request

    def command(self, command, expected=True):
        status, data = self.request('/api/command', {'command': command})
        self.assertEqual(status, 200, data)
        self.assertEqual(data['ok'], expected, data)
        return data

    def test_agent_configure_inspect_undo_and_invalid_device(self):
        for command in ('add router R1', 'add router R2', 'add pc LAN',
                        'connect R1 g0/0 R2 g0/0', 'connect R2 g0/1 LAN eth0',
                        'ip R1 g0/0 10.0.0.1/30', 'ip R2 g0/0 10.0.0.2/30',
                        'ip R2 g0/1 192.168.2.1/24', 'ip LAN eth0 192.168.2.2/24',
                        'gateway LAN 192.168.2.1', 'ospf R1 enable 10.0.0.0/30 area 5',
                        'ospf R2 enable 10.0.0.0/30 area 6',
                        'ospf R2 enable 192.168.2.0/24 area 6'):
            self.command(command)
        status, result = self.request('/api/ospf?device=R1')
        self.assertEqual(status, 200)
        self.assertEqual(result['neighbors'], [])
        self.command('ospf R2 enable 10.0.0.0/30 area 5')
        self.command('ospf R2 enable 192.168.2.0/24 area 5')
        _, result = self.request('/api/ospf?device=R1')
        self.assertEqual(result['neighbors'][0]['device'], 'R2')
        self.assertEqual(result['neighbors'][0]['area'], 5)
        self.assertIn('PING success', self.command('ping R1 192.168.2.2')['output'])
        self.command('ospf R2 remove 10.0.0.0/30')
        self.assertEqual(self.request('/api/ospf?device=R1')[1]['neighbors'], [])
        self.command('undo')
        self.assertEqual(self.request('/api/ospf?device=R1')[1]['neighbors'][0]['area'], 5)
        self.command('ospf R1 enable 0.0.0.0/0 area invalid', expected=False)
        self.assertEqual(self.request('/api/ospf?device=missing')[0], 400)
        self.assertEqual(self.request('/api/ospf')[0], 400)

import unittest
from netsim.model import NetworkLab
from netsim.cli import CommandProcessor
from netsim.capabilities import registry

class AgentControlTests(unittest.TestCase):
    def test_registry_exposes_device_specific_surface(self):
        reg = registry(NetworkLab())
        self.assertEqual(reg['product'], 'Packet Tracker and Simulator')
        self.assertEqual(reg['device_types']['pc']['tabs'], ['Physical','Config','Desktop','Programming','Attributes'])
        self.assertIn('switch.etherchannel', reg['device_types']['switch']['actions'])
        self.assertEqual(reg['agent_endpoints']['ospf_status'], 'GET /api/ospf?device=NAME')
        self.assertIn('router.ospf', reg['device_types']['router']['actions'])
        self.assertEqual(reg['device_types']['pc']['desktop_tools']['Command Prompt'], 'implemented')
        self.assertEqual(reg['device_types']['pc']['desktop_tools']['VPN'], 'implemented-simplified')

    def test_capability_command_discovers_instance_kind(self):
        lab = NetworkLab(); proc = CommandProcessor(lab)
        proc.execute('add router EDGE')
        out = proc.execute('capabilities EDGE')
        self.assertIn('EDGE -> Router (router)', out)
        self.assertIn('router.static_route', out)
        self.assertIn('device.ios_cli', out)

if __name__ == '__main__':
    unittest.main()

import unittest
from netsim.cli import CommandProcessor
from netsim.model import Interface, NetworkLab

class AutomaticConnectionTests(unittest.TestCase):
 def setUp(self):
  self.lab=NetworkLab(); self.cmd=CommandProcessor(self.lab)
  self.lab.add_device('switch','SW'); self.lab.add_device('pc','PC1'); self.lab.add_device('pc','PC2')
 def test_command_chooses_free_ports_and_supports_undo(self):
  first=self.cmd.execute('auto-connect PC1 SW')
  second=self.cmd.execute('auto-connect PC2 SW')
  self.assertIn('PC1:eth0',first);self.assertIn('PC2:eth0',second)
  self.assertEqual([l.b_if for l in self.lab.links],['fa0/1','fa0/2'])
  self.assertTrue(all(self.lab.link_operational(l) for l in self.lab.links))
  self.assertTrue(all(l.cable=='copper-straight' for l in self.lab.links))
  self.assertEqual(self.cmd.execute('undo'),'Undo completed');self.assertEqual(len(self.lab.links),1)
 def test_no_compatible_ports_does_not_change_lab(self):
  self.lab.devices['PC1'].interfaces={'console':Interface('console',media='console')}
  result=self.cmd.execute('auto-connect PC1 SW')
  self.assertIn('no free compatible',result);self.assertEqual(len(self.lab.links),0)
 def test_full_device_and_self_connection_fail(self):
  self.cmd.execute('auto-connect PC1 SW')
  self.assertIn('no free compatible',self.cmd.execute('auto-connect PC1 PC2'))
  self.assertIn('itself',self.cmd.execute('auto-connect SW SW'))
  self.assertEqual(len(self.lab.links),1)
 def test_uses_matching_fiber_when_copper_unavailable(self):
  self.lab.devices['PC1'].interfaces={'f1':Interface('f1',media='fiber-mm')}
  self.lab.devices['PC2'].interfaces={'f2':Interface('f2',media='fiber-mm')}
  self.assertIn('fiber-mm',self.cmd.execute('auto-connect PC1 PC2'))
  self.assertEqual(self.lab.links[0].cable,'fiber-mm')
 def test_crossover_for_direct_hosts_and_routers(self):
  link=self.lab.auto_connect('PC1','PC2')
  self.assertEqual(link.cable,'copper-cross');self.assertTrue(self.lab.link_operational(link))
  self.lab.add_device('router','R1');self.lab.add_device('router','R2')
  link=self.lab.auto_connect('R1','R2')
  self.assertEqual(link.cable,'copper-cross');self.assertTrue(self.lab.link_operational(link))
 def test_prefers_compatible_speed_and_active_ports(self):
  self.lab.devices['SW'].interfaces['fa0/1'].speed='10'
  self.lab.devices['PC1'].interfaces['eth0'].speed='100'
  link=self.lab.auto_connect('PC1','SW')
  self.assertNotEqual(link.b_if,'fa0/1');self.assertTrue(self.lab.link_operational(link))
 def test_ip_phone_switch_and_pc_ports_bridge_traffic(self):
  self.lab.add_device('generic','Phone',model='7960')
  first=self.lab.auto_connect('Phone','SW');second=self.lab.auto_connect('PC1','Phone')
  self.assertEqual(first.a_if,'eth0');self.assertEqual(second.b_if,'pc')
  self.assertEqual(first.cable,'copper-straight');self.assertEqual(second.cable,'copper-straight')
  self.lab.set_ip('PC1','eth0','10.0.0.1/24');self.lab.set_ip('PC2','eth0','10.0.0.2/24')
  self.lab.auto_connect('PC2','SW')
  self.assertTrue(self.lab.ping('PC1','10.0.0.2')[0])
 def test_analog_phone_and_power_unit_have_no_fabricated_ethernet(self):
  self.lab.add_device('generic','Analog',model='analog-phone-pt')
  self.lab.add_device('generic','Power',model='power-distribution-device')
  self.assertNotIn('eth0',self.lab.devices['Analog'].interfaces)
  self.assertNotIn('eth0',self.lab.devices['Power'].interfaces)
  self.assertIn('no free compatible',self.cmd.execute('auto-connect Analog SW'))
  self.assertIn('no free compatible',self.cmd.execute('auto-connect Power SW'))

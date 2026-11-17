"""End-to-end family configuration: IPv6, wireless controllers and WAN access."""
import unittest
from netsim.model import NetworkLab,LabError
from netsim.cli import CommandProcessor
from netsim.device_config import action
from netsim.simulation import action as simulate

class FamilyTests(unittest.TestCase):
 def setUp(self):self.lab=NetworkLab();self.cp=CommandProcessor(self.lab)
 def cmd(self,line):
  result=self.cp.execute(line);self.assertFalse(result.startswith('ERROR:'),result);return result
 def act(self,device,**body):return action(self.lab,{'device':device,**body})
 def nodes(self):
  for line in ('add pc A','add server S','add switch SW','connect A eth0 SW fa0/1','connect S eth0 SW fa0/2','ip A eth0 192.0.2.1/24','ip S eth0 192.0.2.2/24'):self.cmd(line)
 def test_ipv6_router_and_slaac(self):
  for line in ('add pc A','add pc B','add router R','connect A eth0 R g0/0','connect B eth0 R g0/1'):self.cmd(line)
  self.act('R',action='global',ipv6_routing=True)
  self.act('R',action='interface',interface='g0/0',ipv6='2001:db8:1::1/64')
  self.act('R',action='interface',interface='g0/1',ipv6='2001:db8:2::1/64')
  self.act('A',action='ipv6_autoconfigure',interface='eth0');address=self.act('B',action='ipv6_autoconfigure',interface='eth0')
  self.assertIn('success',self.cmd('ping A '+address.split('/')[0]))
  self.cmd('down R g0/1');self.assertNotIn('success',self.cmd('ping A '+address.split('/')[0]))
 def test_dhcpv6_lease_gateway_dns_and_link_local(self):
  self.nodes()
  self.act('S',action='interface',interface='eth0',ipv6='2001:db8::1/64',ipv6_link_local='fe80::1234')
  self.act('S',action='dhcpv6_pool',name='LAN6',prefix='2001:db8::/64',gateway='2001:db8::1',dns_server='2001:db8::53')
  lease=self.act('A',action='ipv6_dhcp',interface='eth0');self.assertEqual(lease['address'],'2001:db8::2/64')
  self.assertEqual(self.act('A',action='ipv6_dhcp',interface='eth0')['address'],lease['address'])
  self.assertEqual(self.lab.devices['A'].config['ipv6_dns_server'],'2001:db8::53');self.assertIn('success',self.cmd('ping A 2001:db8::1'))
  self.assertIn('success',self.cmd('ping A fe80::1234'))
  self.cmd('down S eth0')
  with self.assertRaises(LabError):self.act('A',action='ipv6_dhcp',interface='eth0')
 def test_wlc_wlan_push_and_authenticated_client(self):
  self.nodes();self.cmd('add-model WLC-3504 WLC');self.cmd('add-model AccessPoint-PT AP')
  for cmd in ('connect WLC eth0 SW fa0/3','connect AP eth0 SW fa0/4','ip WLC eth0 192.0.2.3/24','ip AP eth0 192.0.2.4/24','physical place AP building0','physical place A building0','physical device-position A 100 100','physical device-position AP 100 100'):self.cmd(cmd)
  self.act('WLC',action='wlc_wlan',ssid='Managed',security='wpa2-psk',key='password1')
  self.act('WLC',action='wlc_group',name='Office',aps=['AP'],wlans=['Managed'])
  self.cmd('disconnect A eth0');self.act('A',action='associate',ssid='Managed',security='wpa2-psk',key='password1',ip='192.0.2.5/24')
  self.assertIn('success',self.cmd('ping A 192.0.2.2'))
 def test_patch_panel_is_a_paired_passive_path(self):
  for cmd in ('add pc A','add pc B','add-model "Copper Wall Mount" Wall','connect A eth0 Wall front1','connect B eth0 Wall back1','ip A eth0 192.0.2.1/24','ip B eth0 192.0.2.2/24'):self.cmd(cmd)
  self.assertIn('success',self.cmd('ping A 192.0.2.2'))
  self.cmd('disconnect B eth0');self.cmd('connect B eth0 Wall back2')
  self.assertNotIn('success',self.cmd('ping A 192.0.2.2'))
 def test_pppoe_auth_and_address_allocation(self):
  self.nodes();self.act('S',action='service',service='pppoe',enabled=True,prefix='10.254.0.0/24',gateway='10.254.0.1')
  self.act('S',action='service_user',service='pppoe',username='student',password='pw')
  with self.assertRaises(LabError):self.act('A',action='pppoe',username='student',password='wrong')
  result=self.act('A',action='pppoe',username='student',password='pw');self.assertTrue(result['connected'])
  self.assertIn('success',self.cmd('ping A 10.254.0.1'))
  self.act('A',action='pppoe',operation='disconnect');self.assertEqual(self.lab.devices['A'].interfaces['eth0'].ip,'192.0.2.1/24')
 def test_vpn_auth_split_route_and_underlay_drop(self):
  self.nodes();self.cmd('add pc Private');self.cmd('add router Edge')
  for cmd in ('connect Edge g0/0 SW fa0/3','connect Edge g0/1 Private eth0','ip Edge g0/0 192.0.2.254/24','ip Edge g0/1 10.10.0.1/24','ip Private eth0 10.10.0.2/24','gateway Private 10.10.0.1'):self.cmd(cmd)
  self.act('Edge',action='service',service='vpn',enabled=True,group='Lab',key='shared',network='10.10.0.0/24')
  self.act('Edge',action='service_user',service='vpn',username='student',password='pw')
  connected=self.act('A',action='vpn',server='Edge',username='student',password='pw',group='Lab',key='shared',network='10.10.0.0/24')
  self.assertTrue(connected['connected']);self.assertIn('success',self.cmd('ping A 10.10.0.2'))
  self.cmd('down A eth0');self.assertNotIn('success',self.cmd('ping A 10.10.0.2'))
 def test_simulation_deferred_transfer_and_ping(self):
  self.nodes();self.act('S',action='service',service='tftp',enabled=True);self.act('S',action='file_write',file='example.txt',content='contents')
  simulate(self.lab,{'action':'mode','mode':'simulation'})
  queued=self.act('A',action='transfer',server='S',protocol='tftp',operation='get',file='example.txt')
  self.assertIn('queued',queued);self.assertNotIn('example.txt',self.lab.devices['A'].config.get('files',{}))
  for _ in range(20):
   if not simulate(self.lab,{'action':'step'}):break
  self.assertEqual(self.lab.devices['A'].config['files']['example.txt'],'contents')
  self.assertIn('queued',self.cmd('ping A 192.0.2.2'))

if __name__=='__main__':unittest.main()

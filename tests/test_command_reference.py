"""Behavioural contracts for the command-reference expansion."""
import copy,unittest
from netsim.model import NetworkLab
from netsim.cli import CommandProcessor
from netsim.ios import IOSSession
from netsim.device_config import action

class ReferenceTests(unittest.TestCase):
 def setUp(self):
  self.lab=NetworkLab();self.cp=CommandProcessor(self.lab)
  for c in ('add router R','add pc A','connect R g0/0 A eth0','ip R g0/0 192.0.2.1/24'):self.assertFalse(self.cp.execute(c).startswith('ERROR:'))
  self.ios=IOSSession(self.lab,'R');self.runios('enable','configure terminal')
 def runios(self,*commands):
  result=''
  for command in commands:
   result=self.ios.execute(command);self.assertFalse(result.startswith('%'),result)
  return result
 def test_named_acl_port_matching(self):
  self.runios('ip access-list extended WEB','10 deny tcp any any eq www','20 permit ip any any','exit','interface GigabitEthernet0/0','ip access-group WEB in','ip address 192.0.2.1 255.255.255.0','end')
  self.cp.execute('ip A eth0 192.0.2.2/24')
  self.assertFalse(self.lab._transit('A','192.0.2.1','tcp',destination_port=80)[0]);self.assertTrue(self.lab._transit('A','192.0.2.1','tcp',destination_port=443)[0])
 def test_dhcp_pool_issues_real_lease(self):
  self.runios('ip dhcp pool LAN','network 192.0.2.0 255.255.255.0','default-router 192.0.2.1','dns-server 192.0.2.53','exit','end')
  self.assertIn('192.0.2.',self.lab.dhcp_request('A','eth0'));self.assertEqual(self.lab.devices['A'].default_gateway,'192.0.2.1');self.assertIn('LAN',self.runios('show ip dhcp binding'))
 def test_bad_command_rolls_back_and_do_keeps_mode(self):
  self.runios('ip dhcp pool LAN','network 192.0.2.0 255.255.255.0')
  before=copy.deepcopy(self.lab.to_dict());self.assertTrue(self.ios.execute('default-router 198.51.100.1').startswith('%'));self.assertEqual(before,self.lab.to_dict());self.assertEqual(self.ios.mode,'dhcp')
  self.assertIn('Interface',self.runios('do show ip interface brief'));self.assertEqual(self.ios.mode,'dhcp')
 def test_interface_controls_and_clear(self):
  self.runios('interface GigabitEthernet0/0','mtu 1400','tx-ring-limit 30','mac-address 0200.0000.0011','mdix auto','description hello','no description','end')
  port=self.lab.devices['R'].interfaces['g0/0'];self.assertEqual(port.mtu,1400);self.assertEqual(port.mac,'02:00:00:00:00:11');self.assertTrue(port.auto_mdix)
  self.lab.devices['R'].arp_table['192.0.2.2']='02:00:00:00:00:22';self.runios('clear arp-cache');self.assertFalse(self.lab.devices['R'].arp_table)
 def test_mode_context_survives_remote_calls(self):
  for command in ('enable','configure terminal','ip access-list extended SAVED','10 permit ip any any'):
   from netsim.device_config import terminal_session
   output=terminal_session(self.lab,'A','R','console:test',command);self.assertFalse(output.startswith('%'),output)
  self.assertIn('SAVED',self.lab.devices['R'].acls)
 def test_reference_index_is_explicitly_partial(self):
  from netsim.command_reference import view
  index=view();self.assertEqual(len(index['profiles']),65);self.assertEqual(index['profiles'][0]['section'],74);self.assertEqual(index['profiles'][-1]['section'],138)
  self.assertIn('not an implementation claim',index['notice']);self.assertEqual(view('PC1.0')['profile'],'PC1.0')
 def test_host_options_and_interactive_ftp(self):
  def host(text):return action(self.lab,{'device':'A','action':'host_command','command':text})
  host('ipconfig 192.0.2.2 255.255.255.0 192.0.2.1');self.assertEqual(self.lab.devices['A'].interfaces['eth0'].ip,'192.0.2.2/24')
  self.cp.execute('add server S');self.cp.execute('disconnect R g0/0');self.cp.execute('connect S eth0 A eth0');self.cp.execute('ip S eth0 192.0.2.3/24')
  for body in ({'action':'service','service':'ftp','enabled':True},{'action':'service_user','service':'ftp','username':'student','password':'pw'},{'action':'file_write','file':'test.txt','content':'Transferred via interactive FTP'}):action(self.lab,{'device':'S',**body})
  self.assertEqual(host('ftp S'),'Username:');self.assertEqual(host('student'),'Password:');self.assertIn('Authenticated',host('pw'));self.assertIn('test.txt',host('dir'));self.assertEqual(host('get test.txt'),'Transferred via interactive FTP');host('quit')
  host('arp -d');host('ipconfig /release');self.assertIsNone(self.lab.devices['A'].interfaces['eth0'].ip)
 def test_unsupported_protocol_is_rejected_without_mutation(self):
  before=copy.deepcopy(self.lab.to_dict());self.assertTrue(self.ios.execute('router bgp 65000').startswith('%'));self.assertEqual(self.lab.to_dict(),before)
 def test_running_text_preserves_acl_ports_and_dhcp(self):
  from netsim.device_config import merge_text
  self.runios('ip access-list extended WEB','10 deny tcp any any eq www','20 permit ip any any','exit','ip dhcp pool LAN','network 192.0.2.0 255.255.255.0','default-router 192.0.2.1','exit','end')
  text=self.ios._running_config();self.assertIn('eq 80',text)
  other=NetworkLab();other.add_device('router','R');merge_text(other,'R',text)
  self.assertEqual(other.devices['R'].acls['WEB'][0].destination_port['first'],80);self.assertIn('LAN',other.devices['R'].dhcp_pools)
 def test_rommon_environment_and_network_recovery(self):
  self.cp.execute('add server S');self.cp.execute('disconnect R g0/0');self.cp.execute('connect R g0/0 S eth0');self.cp.execute('ip S eth0 192.0.2.2/24')
  action(self.lab,{'device':'S','action':'service','service':'tftp','enabled':True});action(self.lab,{'device':'S','action':'file_write','file':'recovery.bin','content':'Packet Tracker and Simulator simulated IOS recovery'})
  action(self.lab,{'device':'R','action':'boot_image','file':'missing.bin'});action(self.lab,{'device':'R','action':'boot'});self.assertEqual(self.lab.devices['R'].config['boot_state'],'rommon')
  self.runios('set IP_ADDRESS 192.0.2.1','set IP_SUBNET_MASK 255.255.255.0','set TFTP_SERVER 192.0.2.2','set TFTP_FILE recovery.bin','tftpdnld','boot flash:recovery.bin')
  self.assertEqual(self.lab.devices['R'].config['boot_state'],'running')

if __name__=='__main__':unittest.main()

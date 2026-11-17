"""Cross-feature contracts for sections 33–73, always on isolated model state."""
import copy,json,tempfile,unittest
from pathlib import Path
from netsim.model import NetworkLab,LabError
from netsim.cli import CommandProcessor
from netsim.device_config import action
from netsim.simulation import action as simulation
from netsim.industrial_switching import rep_status

class Contracts(unittest.TestCase):
 def setUp(self):self.lab=NetworkLab();self.cp=CommandProcessor(self.lab)
 def cmds(self,*lines):
  for line in lines:
   result=self.cp.execute(line);self.assertFalse(result.startswith('ERROR:'),result)
 def act(self,device,**b):return action(self.lab,dict(device=device,**b))
 def roundtrip(self):
  with tempfile.TemporaryDirectory() as tmp:
   path=Path(tmp)/'lab.json';self.lab.save(str(path));other=NetworkLab();other.load(str(path));self.assertEqual(other.to_dict(),self.lab.to_dict())
 def test_nondefault_scenario_survives_reboot_and_load(self):
  self.cmds('add router R','add pc A','connect R g0/0 A eth0','ip R g0/0 192.0.2.1/24','ip A eth0 192.0.2.2/24')
  sid=simulation(self.lab,{'action':'scenario_add','name':'Saved scenario'})
  simulation(self.lab,{'action':'scenario_select','id':sid})
  simulation(self.lab,{'action':'pdu_add','source':'R','destination':'A','start':100})
  self.act('R',action='save_startup');self.act('R',action='interface',interface='g0/0',ip='192.0.2.99/24')
  self.act('R',action='power',enabled=False);self.act('R',action='power',enabled=True)
  self.assertEqual(self.lab.devices['R'].interfaces['g0/0'].ip,'192.0.2.1/24');self.roundtrip()
 def test_tcp_destination_acl_is_enforced_on_next_hop(self):
  self.cmds('add pc A','add router R','add server S','connect A eth0 R g0/0','connect R g0/1 S eth0','ip A eth0 192.0.2.2/24','ip R g0/0 192.0.2.1/24','ip R g0/1 198.51.100.1/24','ip S eth0 198.51.100.2/24','gateway A 192.0.2.1','gateway S 198.51.100.1')
  self.act('R',action='acl_rule',name='WEB',policy='deny',protocol='tcp',source='any',destination='any',destination_port=80)
  self.act('R',action='acl_rule',name='WEB',policy='permit',protocol='ip',source='any',destination='any')
  self.act('R',action='access_group',interface='g0/1',name='WEB',direction='out')
  self.assertFalse(self.lab._transit('A','198.51.100.2','tcp',destination_port=80)[0])
  self.assertTrue(self.lab._transit('A','198.51.100.2','tcp',destination_port=443)[0]);self.roundtrip()
 def test_svi_routes_between_access_vlans_and_changes_ports(self):
  self.cmds('add pc A','add pc B','add switch SW','connect A eth0 SW fa0/1','connect B eth0 SW fa0/2','ip A eth0 192.0.2.2/24','ip B eth0 198.51.100.2/24','gateway A 192.0.2.1','gateway B 198.51.100.1')
  self.lab.set_switchport_access('SW','fa0/1',10);self.lab.set_switchport_access('SW','fa0/2',20)
  self.act('SW',action='svi',vlan=10,ip='192.0.2.1/24');self.act('SW',action='svi',vlan=20,ip='198.51.100.1/24')
  self.assertTrue(self.lab.ping('A','198.51.100.2')[0])
  self.lab.set_switchport_trunk('SW','fa0/3',[10,20]);self.assertIn('fa0/3.20',self.lab.devices['SW'].interfaces)
  self.lab.set_switchport_trunk('SW','fa0/3',[10]);self.assertNotIn('fa0/3.20',self.lab.devices['SW'].interfaces)
  self.lab.set_switchport_access('SW','fa0/3',20);self.assertNotIn('fa0/3.10',self.lab.devices['SW'].interfaces);self.roundtrip()
 def test_l2nat_bidirectional_translation_and_counter(self):
  self.cmds('add pc A','add pc B','add switch SW','connect A eth0 SW fa0/1','connect B eth0 SW fa0/2','ip A eth0 10.0.0.1/24','ip B eth0 192.0.2.2/24')
  self.act('SW',action='l2nat',direction='inside',original='10.0.0.1',translated='192.0.2.1')
  self.act('SW',action='l2nat',direction='outside',original='192.0.2.2',translated='10.0.0.2')
  self.assertTrue(self.lab.ping('A','10.0.0.2')[0]);self.assertTrue(self.lab.ping('B','192.0.2.1')[0])
  self.assertGreater(self.lab.devices['SW'].config['l2nat']['translated_packets'],0)
 def test_rep_ring_unblocks_after_carrier_failure(self):
  self.cmds('add switch A','add switch B','add switch C','connect A fa0/1 B fa0/1','connect B fa0/2 C fa0/1','connect C fa0/2 A fa0/2')
  for node in ('A','B','C'):
   for port in ('fa0/1','fa0/2'):self.act(node,action='rep',interface=port,segment=1)
  self.assertEqual(len(rep_status(self.lab,1)),1)
  self.cmds('down A fa0/1');self.assertEqual(rep_status(self.lab,1),set())
 def test_network_management_login_and_apply(self):
  self.cmds('add pc A','add-model WRT300N W','connect A eth0 W eth0','ip A eth0 192.0.2.2/24','ip W eth0 192.0.2.1/24')
  self.act('W',action='service',service='http',enabled=True)
  with self.assertRaises(LabError):self.act('A',action='management_login',server='W',username='admin',password='wrong')
  login=self.act('A',action='management_login',server='W',username='admin',password='admin')
  self.act('A',action='management_apply',token=login['token'],settings={'action':'global','hostname':'Managed'})
  self.assertEqual(self.lab.devices['W'].config['hostname'],'Managed')
  self.cmds('down A eth0')
  with self.assertRaises(LabError):self.act('A',action='management_apply',token=login['token'],settings={'action':'global','hostname':'Blocked'})
 def test_modem_call_authentication_and_disconnect(self):
  self.cmds('add pc A','add router R','add-model Cloud-PT C')
  for name in ('A','R','C'):self.act(name,action='power',enabled=False)
  for name in ('A','R'):self.act(name,action='add_port',port='modem0',media='modem')
  self.act('C',action='add_port',port='modem1',media='modem')
  for name in ('A','R','C'):self.act(name,action='power',enabled=True)
  self.cmds('connect A modem0 C modem0 phone','connect R modem0 C modem1 phone','ip A modem0 192.0.2.1/24','ip R modem0 192.0.2.2/24')
  self.act('C',action='cloud_port',interface='modem1',phone_number='5551000')
  self.act('R',action='local_user',username='student',password='pw')
  self.assertFalse(self.lab.ping('A','192.0.2.2')[0])
  with self.assertRaises(LabError):self.act('A',action='dialup',number='5551000',username='student',password='bad')
  self.assertTrue(self.act('A',action='dialup',number='5551000',username='student',password='pw')['connected'])
  self.assertTrue(self.lab.ping('A','192.0.2.2')[0]);self.roundtrip()
  self.act('A',action='dialup',operation='disconnect');self.assertFalse(self.lab.ping('A','192.0.2.2')[0])
 def test_ipv6_ping_waits_for_capture(self):
  self.cmds('add pc A','add pc B','connect A eth0 B eth0')
  for node,address in (('A','2001:db8::1/64'),('B','2001:db8::2/64')):self.act(node,action='interface',interface='eth0',ipv6=address)
  simulation(self.lab,{'action':'mode','mode':'simulation'})
  self.assertIn('queued',self.lab.ping('A','2001:db8::2')[1]);self.assertNotIn('ndp',self.lab.devices['A'].config)
  while simulation(self.lab,{'action':'step'}):pass
  self.assertIn('ndp',self.lab.devices['A'].config);self.assertTrue(next(iter(self.lab.simulation['pdus'].values()))['result']['ok']);self.roundtrip()
 def test_home_port_forward_and_dmz_use_real_forwarding(self):
  self.cmds('add pc A','add router R','add server S','connect A eth0 R g0/0','connect R g0/1 S eth0','ip A eth0 192.0.2.2/24','ip R g0/0 192.0.2.1/24','ip R g0/1 10.0.0.1/24','ip S eth0 10.0.0.2/24','gateway S 10.0.0.1','nat-role R g0/0 outside','nat-role R g0/1 inside','http-page S / "<h1>Private server</h1>"')
  self.act('R',action='port_forward',name='web',protocol='tcp',external_port=8080,internal_port=80,ip='10.0.0.2')
  self.assertEqual(self.lab.http_request('A','http://192.0.2.1:8080/')['server'],'S')
  self.act('R',action='port_forward',name='web',delete=True)
  with self.assertRaises(LabError):self.lab.http_request('A','http://192.0.2.1:8080/')
  self.act('R',action='dmz',enabled=True,ip='10.0.0.2');self.assertEqual(self.lab.http_request('A','http://192.0.2.1/')['server'],'S');self.roundtrip()
 def test_host_prompt_shares_network_and_files(self):
  self.cmds('add pc A','add server S','connect A eth0 S eth0','ip A eth0 192.0.2.1/24','ip S eth0 192.0.2.2/24')
  self.assertIn('success',self.act('A',action='host_command',command='ping 192.0.2.2'))
  self.act('A',action='file_write',file='note.txt',content='host prompt');self.assertIn('note.txt',self.act('A',action='host_command',command='dir'))
  self.act('S',action='service',service='ftp',enabled=True);self.act('S',action='service_user',service='ftp',username='student',password='pw',permissions=['write','list'])
  self.act('A',action='host_command',command='ftp S student pw put note.txt');self.assertEqual(self.lab.devices['S'].config['files']['note.txt'],'host prompt')
  simulation(self.lab,{'action':'mode','mode':'simulation'})
  result=self.act('A',action='host_command',command='ping 192.0.2.2');self.assertIn('queued',result)
  while simulation(self.lab,{'action':'step'}):pass
  self.assertTrue(next(iter(self.lab.simulation['pdus'].values()))['result']['ok'])
 def test_dns_cache_expiry_and_email_account_delete(self):
  self.cmds('add pc A','add server S','connect A eth0 S eth0','ip A eth0 192.0.2.1/24','ip S eth0 192.0.2.2/24','dns-client A 192.0.2.2')
  self.act('S',action='service',service='dns',enabled=True);self.act('S',action='dns_record',name='example.lab',type='A',value='192.0.2.2',ttl=1)
  self.assertEqual(self.lab.resolve_dns('A','example.lab'),'192.0.2.2');cache=self.act('S',action='dns_cache');self.assertIn('example.lab',cache)
  self.lab.devices['S'].dns_records['example.lab']='192.0.2.9';self.assertEqual(self.lab.resolve_dns('A','example.lab'),'192.0.2.2')
  simulation(self.lab,{'action':'advance','seconds':2});self.assertEqual(self.lab.resolve_dns('A','example.lab'),'192.0.2.9')
  self.act('S',action='service_user',service='smtp',username='old',password='pw');self.act('S',action='service_user',service='smtp',username='old',delete=True)
  self.assertNotIn('old',self.lab.devices['S'].config['services']['pop3']['users'])
 def test_rip_advertisement_and_link_withdrawal(self):
  self.cmds('add router R1','add router R2','add pc A','connect R1 g0/0 R2 g0/0','connect R2 g0/1 A eth0','ip R1 g0/0 192.0.2.1/24','ip R2 g0/0 192.0.2.2/24','ip R2 g0/1 198.51.100.1/24','ip A eth0 198.51.100.2/24')
  for node in ('R1','R2'):self.act(node,action='rip',network='192.0.2.0/24')
  self.assertFalse(any(r.network=='198.51.100.0/24' for r in self.lab.devices['R1'].routes))
  self.act('R2',action='rip',network='198.51.100.0/24');self.assertTrue(any(r.source=='rip' and r.network=='198.51.100.0/24' for r in self.lab.devices['R1'].routes))
  self.cmds('down R2 g0/0');self.assertFalse(any(r.source=='rip' for r in self.lab.devices['R1'].routes))
 def test_enable_secret_and_remote_terminal_mode_persist(self):
  from netsim.ios import IOSSession
  self.cmds('add pc A','add router R','connect A eth0 R g0/0','ip A eth0 192.0.2.2/24','ip R g0/0 192.0.2.1/24')
  self.act('R',action='service',service='ssh',enabled=True);self.act('R',action='local_user',username='student',password='pw');self.act('R',action='global',enable_secret='secret')
  def remote(text):return self.act('A',action='remote_cli',server='R',username='student',password='pw',command=text)
  self.assertIn('Password:',remote('enable'));self.assertIn('Authentication failed',remote('reload'));self.assertTrue(remote('end').endswith('R>'))
  remote('enable');remote('secret');remote('configure terminal');remote('interface g0/0');remote('description Remote configured')
  self.assertEqual(self.lab.devices['R'].interfaces['g0/0'].description,'Remote configured');self.roundtrip()
  self.assertIn('privileged EXEC',IOSSession(self.lab,'R').execute('erase startup-config'))
 def test_phone_call_state_and_observer_findings(self):
  self.cmds('add pc A','add pc B','add server S','add switch SW','connect A eth0 SW fa0/1','connect B eth0 SW fa0/2','connect S eth0 SW fa0/3','ip A eth0 192.0.2.1/24','ip B eth0 192.0.2.2/24','ip S eth0 192.0.2.3/24')
  self.act('S',action='service',service='telephony',enabled=True)
  for node,number in (('A','1001'),('B','1002')):self.act(node,action='telephony',number=number,server='S')
  with self.assertRaises(LabError):self.act('B',action='call',number='1001',operation='answer')
  self.act('A',action='call',number='1002');self.assertEqual(self.lab.devices['B'].config['telephony']['state'],'ringing')
  self.act('B',action='call',number='1001',operation='answer');self.act('A',action='call',number='1002',operation='note',note='C');self.assertEqual(self.lab.devices['B'].config['telephony']['last_note'],'C')
  self.act('A',action='call',operation='hangup');self.assertEqual(self.lab.devices['B'].config['telephony']['state'],'idle')
  self.act('A',action='service',service='telnet',enabled=True);findings=self.act('S',action='observer_scan',network='192.0.2.0/24');self.assertIn('Plaintext Telnet enabled',findings['A']['vulnerabilities'])
 def test_clientless_https_portal_proxies_private_bookmark(self):
  self.cmds('add pc A','add router R','add server S','connect A eth0 R g0/0','connect S eth0 R g0/1','ip A eth0 192.0.2.2/24','ip R g0/0 192.0.2.1/24','ip R g0/1 10.0.0.1/24','ip S eth0 10.0.0.2/24','http-page S / "<h1>VPN bookmark</h1>"')
  self.act('R',action='local_user',username='student',password='pw');self.act('R',action='clientless_vpn',enabled=True,bookmarks={'Lab':'http://10.0.0.2/'})
  with self.assertRaises(LabError):self.act('A',action='clientless_login',server='R',username='student',password='bad')
  session=self.act('A',action='clientless_login',server='R',username='student',password='pw');response=self.act('A',action='clientless_open',token=session['token'],name='Lab')
  self.assertIn('VPN bookmark',response['html']);self.assertEqual(response['via'],'R');self.assertFalse(response['encrypted']);self.roundtrip()
  self.cmds('down R g0/1')
  with self.assertRaises(LabError):self.act('A',action='clientless_open',token=session['token'],name='Lab')
 def test_firewall_application_ports_and_multiple_rules(self):
  self.cmds('add pc A','add router R','add server S','connect A eth0 R g0/0','connect S eth0 R g0/1','ip A eth0 192.0.2.2/24','ip R g0/0 192.0.2.1/24','ip R g0/1 10.0.0.1/24','ip S eth0 10.0.0.2/24','gateway A 192.0.2.1','gateway S 10.0.0.1')
  for application in ('http','ftp'):self.act('R',action='firewall_rule',interface='g0/0',match='protocol',value=application)
  self.assertFalse(self.lab._transit('A','10.0.0.2','tcp',destination_port=80)[0]);self.assertFalse(self.lab._transit('A','10.0.0.2','tcp',destination_port=21)[0]);self.assertTrue(self.lab._transit('A','10.0.0.2','tcp',destination_port=443)[0])
  self.act('R',action='firewall_rule',interface='g0/0',match='protocol',sequence=10,delete=True);self.assertTrue(self.lab._transit('A','10.0.0.2','tcp',destination_port=80)[0])
 def test_bad_queue_load_is_atomic_via_command(self):
  self.cmds('add pc A');before=copy.deepcopy(self.lab.to_dict())
  with tempfile.TemporaryDirectory() as tmp:
   bad=copy.deepcopy(before);bad['simulation']['pending']=[{}];path=Path(tmp)/'bad.json';path.write_text(json.dumps(bad))
   self.assertTrue(self.cp.execute('load '+str(path)).startswith('ERROR:'));self.assertEqual(before,self.lab.to_dict())

if __name__=='__main__':unittest.main()

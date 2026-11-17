"""Functional media, nonvolatile configuration and service-engine regressions."""
import json,tempfile,unittest
from pathlib import Path
from copy import deepcopy
from netsim.model import NetworkLab,LabError
from netsim.cli import CommandProcessor
from netsim.device_config import action,view
from netsim.device_services import service

class DeviceEngineTests(unittest.TestCase):
 def setUp(self):
  self.lab=NetworkLab();self.cp=CommandProcessor(self.lab)
  for cmd in ('add pc A','add server S','add switch SW','connect A eth0 SW fa0/1','connect S eth0 SW fa0/2','ip A eth0 192.0.2.1/24','ip S eth0 192.0.2.2/24'):self.cmd(cmd)
 def cmd(self,line):
  out=self.cp.execute(line);self.assertFalse(out.startswith('ERROR:'),out);return out
 def act(self,device='S',**body):return action(self.lab,{'device':device,**body})
 def roundtrip(self):
  with tempfile.TemporaryDirectory() as folder:
   path=Path(folder)/'lab.json';self.lab.save(str(path));lab=NetworkLab();lab.load(str(path));return lab
 def enable(self,name,**extra):self.act(action='service',service=name,enabled=True,**extra)
 def test_fiber_serial_and_console_media(self):
  self.cmd('disconnect A eth0');self.cmd('disconnect S eth0')
  for name in ('A','S'):
   self.act(name,action='power',enabled=False);self.act(name,action='add_port',port='f0',media='fiber-sm')
   self.act(name,action='interface',interface='f0',ip='198.51.100.'+('1' if name=='A' else '2')+'/24');self.act(name,action='power',enabled=True)
  self.cmd('connect A f0 S f0 fiber-sm');self.assertIn('success',self.cmd('ping A 198.51.100.2'))
  self.cmd('disconnect A f0')
  with self.assertRaises(LabError):self.lab.connect('A','f0','S','f0','fiber-mm')
  for name in ('A','S'):
   self.act(name,action='power',enabled=False);self.act(name,action='add_port',port='s0',media='serial');self.act(name,action='power',enabled=True)
  self.cmd('connect A s0 S s0 serial-dce');self.assertFalse(self.lab.link_operational(self.lab.links[-1]))
  self.act('A',action='interface',interface='s0',clock_rate=64000);self.assertTrue(self.lab.link_operational(self.lab.links[-1]))
  self.roundtrip()
 def test_console_session_and_framing(self):
  self.cmd('add router R')
  for name,medium in (('A','rs232'),('R','console')):
   self.act(name,action='power',enabled=False);self.act(name,action='add_port',port='tty',media=medium);self.act(name,action='power',enabled=True)
  self.cmd('connect A tty R tty console')
  out=self.act('A',action='console',interface='tty',command='enable\nshow ip interface brief');self.assertIn('g0/0',out)
  with self.assertRaises(LabError):self.act('A',action='console',interface='tty',settings={'baud':115200},command='enable')
  self.assertFalse(self.lab._iface_effective_up('A','tty'))
 def test_startup_saved_unsaved_legacy_and_rommon(self):
  self.cmd('add router R');self.cmd('ip R g0/0 10.0.0.1/24')
  self.cmd('power R off');self.cmd('power R on');self.assertEqual(self.lab.devices['R'].interfaces['g0/0'].ip,'10.0.0.1/24')
  self.act('R',action='save_startup');self.cmd('ip R g0/0 10.1.0.1/24');self.cmd('power R off');self.cmd('power R on')
  self.assertEqual(self.lab.devices['R'].interfaces['g0/0'].ip,'10.0.0.1/24')
  self.act('R',action='file_delete',file='simulated-ios.bin');self.act('R',action='boot')
  self.assertEqual(self.lab.devices['R'].config['boot_state'],'rommon')
  self.assertIn('ROMMON',self.cmd('ios R enable'))
  self.act('R',action='file_write',file='simulated-ios.bin',content='Packet Tracker and Simulator simulated IOS image restored')
  self.act('R',action='boot');self.assertEqual(self.lab.devices['R'].config['boot_state'],'running');self.roundtrip()
 def test_hostname_merge_and_import_atomicity(self):
  self.cmd('add router R')
  self.act('R',action='merge_running',text='hostname Edge\ninterface g0/0\nip address 10.1.0.1 255.255.255.0\nno shutdown\nend')
  self.assertIn('Edge>',self.cmd('ios R show ip interface brief'))
  before=self.lab.to_dict()
  with self.assertRaises(LabError):self.act('R',action='merge_running',text='interface g0/0\nip address 10.2.0.1 255.255.255.0\nnot-a-command')
  self.assertEqual(before,self.lab.to_dict())
 def test_ftp_permissions_tftp_and_network_failure(self):
  self.enable('ftp');self.enable('tftp')
  self.act(action='service_user',service='ftp',username='reader',password='pw',permissions=['read','list'])
  self.act(action='file_write',file='hello.txt',content='hello')
  self.assertIn('hello.txt',self.act('A',action='transfer',server='192.0.2.2',protocol='ftp',operation='list',username='reader',password='pw'))
  self.assertEqual(self.act('A',action='transfer',server='192.0.2.2',protocol='tftp',operation='get',file='hello.txt'),'hello')
  with self.assertRaises(LabError):self.act('A',action='transfer',server='S',protocol='ftp',operation='put',username='reader',password='pw',file='new',content='no')
  self.cmd('down S eth0')
  with self.assertRaises(LabError):self.act('A',action='transfer',server='S',protocol='tftp',operation='list')
 def test_dns_aliases_negative_and_loop(self):
  self.enable('dns');self.cmd('dns-client A 192.0.2.2')
  self.act(action='dns_record',name='target.lab',type='A',value='192.0.2.2')
  self.act(action='dns_record',name='alias.lab',type='CNAME',value='target.lab')
  self.assertEqual(self.lab.resolve_dns('A','alias.lab'),'192.0.2.2')
  self.act(action='dns_record',name='target.lab',type='CNAME',value='alias.lab')
  with self.assertRaises(LabError):self.lab.resolve_dns('A','alias.lab')
 def test_email_accounts_delivery_pop3_and_auth(self):
  self.enable('smtp',domain='lab.local');self.enable('pop3')
  self.act(action='service_user',service='smtp',username='alice',password='pw')
  self.act(action='service_user',service='smtp',username='bob',password='pw2')
  self.act('A',action='mail_send',server='S',username='alice',password='pw',to='bob@lab.local',subject='Lab',text='It works')
  messages=self.act('A',action='mail_receive',server='S',username='bob',password='pw2')
  self.assertEqual(messages[0]['text'],'It works')
  with self.assertRaises(LabError):self.act('A',action='mail_receive',server='S',username='bob',password='wrong')
  self.roundtrip()
 def test_aaa_ntp_snmp_and_syslog(self):
  for protocol in ('radius','ntp','snmp','syslog'):self.enable(protocol)
  self.act(action='service_user',service='radius',username='student',password='pw')
  self.act(action='aaa_client',protocol='radius',client_ip='192.0.2.1',secret='shared')
  self.assertTrue(self.act('A',action='aaa_authenticate',server='S',username='student',password='pw',secret='shared')['authenticated'])
  with self.assertRaises(LabError):self.act('A',action='aaa_authenticate',server='S',username='student',password='pw',secret='wrong')
  self.act('A',action='clock_sync',server='S');self.assertEqual(self.lab.devices['A'].config['clock']['protocol'],'ntp')
  self.act(action='service',service='snmp',enabled=True,community='read',write_community='write')
  self.assertEqual(self.act('A',action='snmp',server='S',community='read',oid='sysName'),'S')
  self.act('A',action='snmp',server='S',community='write',operation='set',oid='sysLocation',value='Room 5')
  self.assertEqual(self.act('A',action='snmp',server='S',community='read',oid='sysLocation'),'Room 5')
  self.act('A',action='logging',server='192.0.2.2');self.act('A',action='emit_log',message='Test message')
  self.assertEqual(service(self.lab.devices['S'],'syslog')['records'][0]['message'],'Test message')
 def test_controller_discovery_provision_and_license(self):
  self.act(action='controller',username='admin',password='pw')
  inventory=self.act(action='discover',network='192.0.2.0/24');self.assertIn('A',inventory)
  self.act(action='provision',target='A',settings={'action':'global','hostname':'ManagedHost'})
  self.assertEqual(self.lab.devices['A'].config['hostname'],'ManagedHost')
  issued=self.act(action='license',operation='issue',target='A',level='network-advantage')
  registered=self.act('A',action='license',operation='register',server='S',token=issued['token'])
  self.assertTrue(registered['registered'])
  with self.assertRaises(LabError):self.act('A',action='license',operation='register',server='S',token=issued['token'])
 def test_plc_logic_timer_counter_and_historian(self):
  self.act('A',action='industrial',tags={'input':1})
  self.act('A',action='plc_program',blocks=[{'op':'timer','inputs':['input'],'output':'delay','preset':2},{'op':'and','inputs':['delay','input'],'output':'output'}])
  self.assertEqual(self.act('A',action='plc_run',seconds=1)['output'],0)
  self.assertEqual(self.act('A',action='plc_run',seconds=1)['output'],1)
  self.enable('historian');count=self.act(action='historian_collect',source='A');self.assertGreater(count,0)
  self.assertEqual(self.act(action='historian_import',csv='A,temp,23.5,2026-11-04T12:00:00Z'),1)
  before=self.lab.to_dict()
  with self.assertRaises(LabError):self.act('A',action='plc_program',blocks=[{'op':'exec','output':'bad','inputs':[]}])
  self.assertEqual(before,self.lab.to_dict());self.roundtrip()
 def test_wireless_authentication_and_range(self):
  self.cmd('add-model AccessPoint-PT AP');self.cmd('physical place A building0');self.cmd('physical place AP building0')
  self.act('AP',action='wireless',ssid='Lab',security='wpa2-psk',key='password1',range_m=50)
  self.cmd('connect AP eth0 SW fa0/3')
  self.cmd('physical device-position A 100 100');self.cmd('physical device-position AP 100 100')
  with self.assertRaises(LabError):self.act('A',action='associate',ssid='Lab',security='wpa2-psk',key='wrongkey')
  self.cmd('disconnect A eth0')
  associated=self.act('A',action='associate',ssid='Lab',security='wpa2-psk',key='password1',ip='192.0.2.3/24')
  self.assertEqual(associated['associated'],'AP');self.assertIn('success',self.cmd('ping A 192.0.2.2'))
  self.cmd('physical device-position A 1000 1000');self.assertNotIn('success',self.cmd('ping A 192.0.2.2'));self.roundtrip()
 def test_iox_lifecycle_requires_files_and_no_host_execution(self):
  self.cmd('add-model 829 IR')
  self.act('IR',action='file_write',file='app.json',content='{"kind":"example"}')
  self.act('IR',action='iox',operation='install',name='demo',file='app.json')
  self.act('IR',action='iox',operation='start',name='demo')
  with self.assertRaises(LabError):self.act('IR',action='iox',operation='uninstall',name='demo')
  self.act('IR',action='iox',operation='stop',name='demo');self.act('IR',action='iox',operation='uninstall',name='demo')
  self.assertEqual(self.act('IR',action='iox',operation='list'),{})

if __name__=='__main__':unittest.main()

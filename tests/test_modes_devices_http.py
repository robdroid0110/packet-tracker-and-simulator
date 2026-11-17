"""Real HTTP/API/autosave integration for operating modes and device engines."""
import json,unittest
import test_physical_special_notes_http as isolated
from netsim.model import NetworkLab

class ModesDevicesHTTPTests(unittest.TestCase):
 setUpClass=isolated.PhysicalSpecialNotesHTTPTests.__dict__['setUpClass']
 tearDownClass=isolated.PhysicalSpecialNotesHTTPTests.__dict__['tearDownClass']
 setUp=isolated.PhysicalSpecialNotesHTTPTests.setUp
 request=isolated.PhysicalSpecialNotesHTTPTests.request
 def command(self,line):
  code,data=self.request('/api/command',{'command':line});self.assertEqual(code,200,data);self.assertTrue(data['ok'],data);return data
 def configure(self,**body):return self.request('/api/device-config/action',body)
 def simulate(self,**body):return self.request('/api/simulation/action',body)
 def test_command_reference_index(self):
  code,index=self.request('/api/command-reference');self.assertEqual(code,200);self.assertEqual(len(index['profiles']),65)
  code,profile=self.request('/api/command-reference?profile=PC1.0');self.assertEqual(code,200);self.assertEqual(profile['section'],138)
  code,error=self.request('/api/command-reference?profile=missing');self.assertEqual(code,400)
 def test_eigrp_through_device_api(self):
  self.command('add router R')
  code,data=self.configure(device='R',action='eigrp',asn=100,network='10.0.0.0/24',enabled=True);self.assertEqual(code,200,data)
  self.assertEqual(data['state']['devices']['R']['config']['eigrp']['100'],['10.0.0.0/24'])
  before=self.app.STATE.read_bytes();code,data=self.configure(device='R',action='eigrp',asn=0,network='10.0.0.0/24');self.assertEqual(code,400);self.assertEqual(before,self.app.STATE.read_bytes())
 def test_industrial_protocols_through_api(self):
  self.seed();code,data=self.configure(device='S',action='service',service='modbus',enabled=True);self.assertEqual(code,200,data)
  code,data=self.configure(device='A',action='modbus_send',server='S',data={'input':12});self.assertEqual(code,200,data)
  self.assertEqual(data['state']['devices']['S']['config']['industrial']['modbus_inbox'][0]['data'],{'input':12})
  code,data=self.configure(device='S',action='cip_identity',identity={'name':'PLC'});self.assertEqual(code,200,data)
  code,data=self.configure(device='A',action='cip_request',server='S',operation='identity');self.assertEqual(code,200,data)
  self.assertEqual(json.loads(data['output'])['name'],'PLC')
 def test_sample_library_load_check_undo_and_translation(self):
  code,data=self.request('/api/samples?language=spa');self.assertEqual(code,200);self.assertEqual(len(data['samples']),4)
  self.command('add pc Original');before=self.app.LAB.to_dict();raw=self.app.STATE.read_bytes()
  code,data=self.request('/api/samples/action',{'action':'load','id':'../../bad'});self.assertEqual(code,400);self.assertEqual(before,self.app.LAB.to_dict());self.assertEqual(raw,self.app.STATE.read_bytes())
  code,data=self.request('/api/samples/action',{'action':'load','id':'skill-dhcp'});self.assertEqual(code,200,data)
  code,data=self.request('/api/samples/action',{'action':'check','id':'skill-dhcp'});self.assertFalse(json.loads(data['output'])['passed'])
  self.command('dhcp Client eth0');code,data=self.request('/api/samples/action',{'action':'check','id':'skill-dhcp'});self.assertTrue(json.loads(data['output'])['passed'])
  self.command('undo');self.command('undo');self.assertEqual(before,self.app.LAB.to_dict())
  code,data=self.request('/api/samples/translation-template');pack=data['template'];pack.update(id='hin',name='हिन्दी')
  code,data=self.request('/api/samples/validate-translation',pack);self.assertEqual(code,200,data)
  del pack['translations']['concept-arp'];code,data=self.request('/api/samples/validate-translation',pack);self.assertEqual(code,400)
 def seed(self):
  for c in ('add pc A','add server S','connect A eth0 S eth0','ip A eth0 192.0.2.1/24','ip S eth0 192.0.2.2/24'):self.command(c)
 def test_discovery_configuration_and_saved_state(self):
  self.seed()
  for path,key in (('/api/simulation/schema','actions'),('/api/device-config/schema','actions')):
   code,data=self.request(path);self.assertEqual(code,200);self.assertIn(key,data)
  code,data=self.configure(device='S',action='service',service='tftp',enabled=True);self.assertEqual(code,200,data)
  self.configure(device='S',action='file_write',file='sample.txt',content='API transfer')
  code,data=self.configure(device='A',action='transfer',server='S',protocol='tftp',operation='get',file='sample.txt');self.assertEqual(code,200,data)
  self.assertEqual(data['state']['devices']['A']['config']['files']['sample.txt'],'API transfer')
  code,data=self.request('/api/device-config?device=A');self.assertEqual(code,200);self.assertIn('running_text',data)
  loaded=NetworkLab();loaded.load(str(self.app.STATE));self.assertEqual(loaded.devices['A'].config['files']['sample.txt'],'API transfer')
 def test_http_and_ping_freeze_until_capture(self):
  self.seed();self.command('http-page S / "<h1>API captured</h1>"')
  self.simulate(action='mode',mode='simulation')
  code,data=self.request('/api/web',{'source':'A','url':'http://192.0.2.2/'});self.assertEqual(code,202,data);ident=data['job']
  self.assertFalse(data['state']['devices']['A']['arp_table'])
  self.command('ping A 192.0.2.2')
  for _ in range(25):
   code,data=self.simulate(action='step');self.assertEqual(code,200,data)
  p=data['state']['simulation']['pdus'][ident];self.assertEqual(p['status'],'Successful');self.assertIn('API captured',p['result']['output']['html'])
  self.assertTrue(data['state']['devices']['A']['arp_table'])
  loaded=NetworkLab();loaded.load(str(self.app.STATE));self.assertEqual(loaded.simulation['pdus'][ident]['status'],'Successful')
 def test_bad_requests_preserve_model_and_saved_bytes(self):
  self.seed();self.simulate(action='mode',mode='simulation');before=self.app.LAB.to_dict();raw=self.app.STATE.read_bytes()
  cases=[('/api/simulation/action',{'action':'pdu_add','source':'A','destination':'S','size':-1}),('/api/simulation/action',{'action':'preferences','filters':['bad']}),('/api/device-config/action',{'action':'interface','device':'A','interface':'eth0','speed':123}),('/api/device-config/action',{'action':'merge_running','device':'A','text':'hostname Changed\ninvalid ios statement'}),('/api/device-config/action',{'action':'service','device':'S','service':'tftp','enabled':'yes'})]
  for path,body in cases:
   code,data=self.request(path,body);self.assertEqual(code,400,data);self.assertEqual(self.app.LAB.to_dict(),before);self.assertEqual(self.app.STATE.read_bytes(),raw)
 def test_typed_hardware_action_uses_same_authority(self):
  self.command('add pc A')
  code,data=self.configure(action='set_port',device='A',port='eth0',speed='100',auto_mdix=True,admin_up=False);self.assertEqual(code,200,data)
  self.assertFalse(data['state']['devices']['A']['interfaces']['eth0']['admin_up'])
  code,data=self.configure(action='add_port',device='A',port='fiber0',media='fiber-sm');self.assertEqual(code,400,data)
  self.configure(action='power',device='A',enabled=False)
  code,data=self.configure(action='add_port',device='A',port='fiber0',media='fiber-sm');self.assertEqual(code,200,data)

if __name__=='__main__':unittest.main()

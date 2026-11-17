"""Industrial messages use real topology, service state and simulation capture."""
import tempfile,unittest
from pathlib import Path
from netsim.model import NetworkLab,LabError
from netsim.cli import CommandProcessor
from netsim.device_config import action
from netsim.simulation import action as simulation

class IndustrialProtocols(unittest.TestCase):
 def setUp(self):
  self.lab=NetworkLab();cp=CommandProcessor(self.lab)
  for line in ('add pc Client','add server PLC','connect Client eth0 PLC eth0','ip Client eth0 192.0.2.1/24','ip PLC eth0 192.0.2.2/24'):
   result=cp.execute(line);self.assertFalse(result.startswith('ERROR:'),result)
 def act(self,device,**body):return action(self.lab,{'device':device,**body})
 def test_modbus_delivery_state_and_persistence(self):
  with self.assertRaises(LabError):self.act('Client',action='modbus_send',server='PLC',data={'sensor':42})
  self.act('PLC',action='service',service='modbus',enabled=True)
  self.act('Client',action='modbus_send',server='PLC',data={'sensor':42})
  with tempfile.TemporaryDirectory() as tmp:
   file=Path(tmp)/'lab.json';self.lab.save(str(file));loaded=NetworkLab();loaded.load(str(file))
   self.assertEqual(action(loaded,{'device':'PLC','action':'modbus_receive'}),{'source':'Client','data':{'sensor':42}})
  self.assertEqual(self.act('PLC',action='modbus_receive')['data'],{'sensor':42});self.assertIsNone(self.act('PLC',action='modbus_receive'))
  self.lab.set_interface_state('Client','eth0',False)
  with self.assertRaises(LabError):self.act('Client',action='modbus_send',server='PLC',data={})
 def test_cip_objects_and_capture(self):
  self.act('PLC',action='cip_identity',identity={'vendor':939,'name':'Lab PLC'})
  self.act('PLC',action='cip_object',class_id=3000,instance_id=1,data={'value':1})
  self.assertEqual(self.act('Client',action='cip_request',server='PLC',operation='identity')['name'],'Lab PLC')
  simulation(self.lab,{'action':'mode','mode':'simulation'})
  job=self.act('Client',action='cip_request',server='PLC',operation='set',class_id=3000,instance_id=1,data={'value':2})['queued']
  self.assertEqual(self.lab.devices['PLC'].config['industrial']['cip_objects']['3000:1']['value'],1)
  for _ in range(40):
   if not simulation(self.lab,{'action':'step'}):break
  self.assertEqual(self.lab.devices['PLC'].config['industrial']['cip_objects']['3000:1']['value'],2)
  self.assertEqual(self.lab.simulation['pdus'][job]['status'],'Successful')
  self.assertTrue(any(e['protocol']=='CIP' for e in self.lab.simulation['events']))
 def test_receiving_empty_inbox_does_not_cancel_pending_modbus(self):
  self.act('PLC',action='service',service='modbus',enabled=True)
  simulation(self.lab,{'action':'mode','mode':'simulation'})
  job=self.act('Client',action='modbus_send',server='PLC',data={'value':3})['queued']
  self.assertIsNone(self.act('PLC',action='modbus_receive'))
  self.assertIn(job,self.lab.simulation['pdus'])
  for _ in range(30):
   if not simulation(self.lab,{'action':'step'}):break
  self.assertEqual(self.act('PLC',action='modbus_receive')['data'],{'value':3})
 def test_invalid_json_and_unknown_object_are_atomic(self):
  self.act('PLC',action='cip_identity',identity={});before=self.lab.to_dict()
  with self.assertRaises(LabError):self.act('PLC',action='cip_object',class_id=1,instance_id=1,data={'invalid':float('nan')})
  self.assertEqual(before,self.lab.to_dict())
  with self.assertRaises(LabError):self.act('Client',action='cip_request',server='PLC',operation='get',class_id=1,instance_id=1)
  self.assertEqual(before,self.lab.to_dict())

if __name__=='__main__':unittest.main()

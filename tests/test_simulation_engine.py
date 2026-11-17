"""Authoritative simulation timing/scenarios; no browser state required."""
import json,tempfile,unittest
from pathlib import Path
from copy import deepcopy
from netsim.model import NetworkLab,LabError
from netsim.cli import CommandProcessor
from netsim.simulation import action,view,defaults

class SimulationTests(unittest.TestCase):
 def setUp(self):
  self.lab=NetworkLab();self.cp=CommandProcessor(self.lab)
  for command in ('add pc A','add pc B','connect A eth0 B eth0','ip A eth0 192.0.2.1/24','ip B eth0 192.0.2.2/24'):
   self.assertFalse(self.cp.execute(command).startswith('ERROR:'))
 def act(self,**body):return action(self.lab,body)
 def add(self,**body):return self.act(action='pdu_add',source='A',destination='B',**body)
 def finish(self):
  for _ in range(30):
   if not self.act(action='step'):return
  self.fail('Unexpected infinite event queue')
 def test_freeze_capture_and_effects(self):
  self.act(action='mode',mode='simulation');ident=self.add()
  self.assertFalse(self.lab.devices['A'].arp_table);self.assertFalse(self.lab.packet_events)
  first=self.act(action='step');self.assertEqual(first['protocol'],'ARP');self.assertIn('arp',first['headers']);self.assertNotIn('ipv4',first['headers']);self.assertEqual(first['osi']['4'],'Not applicable to ARP')
  self.assertTrue(self.lab.devices['A'].arp_table)
  self.finish();self.assertEqual(self.lab.simulation['pdus'][ident]['status'],'Successful')
  self.assertGreater(self.lab.simulation['master_time'],0)
 def test_back_is_inspection_and_filters_do_not_affect_delivery(self):
  self.act(action='mode',mode='simulation');ident=self.add();self.act(action='preferences',filters=[])
  self.finish();before=self.lab.simulation['master_time'];arp=deepcopy(self.lab.devices['A'].arp_table)
  self.act(action='back');self.assertEqual(self.lab.simulation['master_time'],before)
  self.assertEqual(self.lab.devices['A'].arp_table,arp);self.assertEqual(view(self.lab)['visible_events'],[])
  self.assertEqual(self.lab.simulation['pdus'][ident]['status'],'Successful')
 def test_realtime_dispatch_and_future_scheduled(self):
  ident=self.add();self.assertEqual(self.lab.simulation['pdus'][ident]['status'],'Successful')
  later=self.add(start=10);self.assertEqual(self.lab.simulation['pdus'][later]['status'],'Not sent')
  self.act(action='advance',seconds=11);self.assertEqual(self.lab.simulation['pdus'][later]['runs'],1)
 def test_periodic_and_reset_preserve_definition(self):
  self.act(action='mode',mode='simulation');ident=self.add(start=1,interval=2)
  self.act(action='advance',seconds=5.5)
  self.assertEqual(self.lab.simulation['pdus'][ident]['runs'],3)
  master=self.lab.simulation['master_time'];self.act(action='reset')
  self.assertEqual(self.lab.simulation['time'],0);self.assertEqual(self.lab.simulation['master_time'],master)
  self.assertEqual(self.lab.simulation['pdus'][ident]['next_due'],1)
 def test_scenario_independence_and_last_delete(self):
  self.act(action='mode',mode='simulation');ident=self.add()
  second=self.act(action='scenario_add',name='Broken cable',description='Exercise')
  self.act(action='scenario_select',id=second);self.assertIsNone(self.lab.simulation['pdus'][ident]['next_due'])
  self.assertIsNone(self.act(action='step'))
  self.act(action='scenario_delete',id=second)
  with self.assertRaises(LabError):self.act(action='scenario_delete',id='scenario0')
 def test_invalid_requests_and_event_budget_are_atomic(self):
  for body in ({'action':'pdu_add','source':'Missing','destination':'B'},
   {'action':'pdu_add','source':'A','destination':'B','ttl':True},
   {'action':'pdu_add','source':'A','destination':'B','start':float('nan')},
   {'action':'preferences','filters':['NOPE']},{'action':'mode','mode':[]},
   {'action':'scenario_delete','id':'missing'}):
   before=self.lab.to_dict()
   with self.assertRaises((LabError,TypeError)):action(self.lab,body)
   self.assertEqual(before,self.lab.to_dict())
  self.act(action='mode',mode='simulation');self.add(interval=.001)
  before=self.lab.to_dict()
  with self.assertRaises(LabError):self.act(action='advance',seconds=100,limit=10)
  self.assertEqual(before,self.lab.to_dict())
 def test_saved_pending_queue_and_legacy(self):
  self.act(action='mode',mode='simulation');self.add();self.act(action='step')
  with tempfile.TemporaryDirectory() as folder:
   file=Path(folder)/'lab.json';self.lab.save(str(file));loaded=NetworkLab();loaded.load(str(file))
   self.assertEqual(loaded.simulation,self.lab.simulation)
   while action(loaded,{'action':'step'}):pass
   self.assertEqual(next(iter(loaded.simulation['pdus'].values()))['status'],'Successful')
   data=json.loads(file.read_text());data.pop('simulation');file.write_text(json.dumps(data));loaded.load(str(file))
   self.assertEqual(loaded.simulation,defaults())
 def test_network_edit_resets_events_without_erasing_pdu(self):
  self.act(action='mode',mode='simulation');ident=self.add();self.act(action='step')
  self.cp.execute('down A eth0');self.assertFalse(self.lab.simulation['events']);self.assertIn(ident,self.lab.simulation['pdus'])
  self.finish();self.assertEqual(self.lab.simulation['pdus'][ident]['status'],'Failed')
 def test_headers_qos_and_transport_status(self):
  self.act(action='mode',mode='simulation');ident=self.add(protocol='TCP',destination_port=80,source_port=12345,tos=184,sequence=99,size=512)
  self.finish();event=self.lab.simulation['events'][-1]
  self.assertEqual(event['headers']['transport']['source_port'],80);self.assertEqual(event['headers']['transport']['destination_port'],12345);self.assertEqual(event['headers']['direction'],'reply')
  self.assertEqual(event['headers']['transport']['sequence'],99);self.assertEqual(event['qos'],46)
  self.assertEqual(self.lab.simulation['pdus'][ident]['status'],'Successful')
 def test_switches_appear_in_forwarding_trace(self):
  self.cp.execute('disconnect A eth0');self.cp.execute('add switch SW')
  self.cp.execute('connect A eth0 SW fa0/1');self.cp.execute('connect B eth0 SW fa0/2')
  self.act(action='mode',mode='simulation');self.add();self.finish()
  self.assertTrue(any(e['source']=='SW' or e['destination']=='SW' for e in self.lab.simulation['events']))
 def test_ttl_expires_at_router(self):
  self.cp.execute('disconnect A eth0');self.cp.execute('add router R')
  for cmd in ('connect A eth0 R g0/0','connect B eth0 R g0/1','ip R g0/0 192.0.2.254/24','ip R g0/1 198.51.100.254/24','ip B eth0 198.51.100.2/24','gateway A 192.0.2.254','gateway B 198.51.100.254'):self.cp.execute(cmd)
  self.act(action='mode',mode='simulation');ident=self.add(ttl=1);self.finish()
  self.assertEqual(self.lab.simulation['pdus'][ident]['status'],'Failed')

if __name__=='__main__':unittest.main()

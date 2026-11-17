import base64
import json
import os
from pathlib import Path
import subprocess
import sys
import tempfile
import time
import unittest
import struct
import zlib
from urllib.error import HTTPError
from urllib.request import Request, urlopen

from netsim.lab_import import decode_file
from netsim.model import NetworkLab
from netsim.pkt_codec.eax import EAX
from netsim.pkt_codec.twofish import Twofish

ROOT = Path(__file__).resolve().parents[1]
SAMPLE = Path(os.environ.get('PTS_TEST_PKT', '/nonexistent/optional-legacy-fixture.pkt'))

def make_pkt(xml):
 raw=xml.encode(); inner=struct.pack('>I',len(raw))+zlib.compress(raw); length=len(inner)
 inner=bytes(b ^ ((length-i)&255) for i,b in enumerate(inner))
 cipher,tag=EAX(Twofish(bytes([137])*16).encrypt).encrypt(nonce=bytes([16])*16,plaintext=inner)
 data=cipher+tag; result=bytearray(len(data))
 for i,b in enumerate(data):result[len(data)-1-i]=b ^ ((len(data)-i*len(data))&255)
 return bytes(result)

class LabImportTests(unittest.TestCase):
 def test_controller_management_address(self):
  xml='''<PACKETTRACER5><NETWORK><DEVICES><DEVICE><ENGINE><TYPE model="WLC-2504">WirelessLanController</TYPE><NAME>WLC1</NAME><WLC_INTERFACES><PORT><NAME>management</NAME><PHYSICAL_PORT_NUMBER>1</PHYSICAL_PORT_NUMBER><IP>192.168.1.1</IP><SUBNET>255.255.255.240</SUBNET></PORT></WLC_INTERFACES></ENGINE></DEVICE></DEVICES><LINKS/></NETWORK></PACKETTRACER5>'''
  lab,_=decode_file(base64.b64encode(make_pkt(xml)).decode(),'wlc.pkt')
  self.assertEqual(lab.devices['WLC1'].interfaces['g1'].ip,'192.168.1.1/28')
 def test_modern_saved_references_and_configuration(self):
  xml='''<PACKETTRACER5><NETWORK><DEVICES>
  <DEVICE><ENGINE><TYPE model="PC-PT">Pc</TYPE><NAME>PC1</NAME><SAVE_REF_ID>save-ref-id:1</SAVE_REF_ID><MODULE><PORT><IP>10.1.0.2</IP><SUBNET>255.255.255.0</SUBNET></PORT></MODULE><GATEWAY>10.1.0.1</GATEWAY></ENGINE></DEVICE>
  <DEVICE><ENGINE><TYPE model="2960-24TT">Switch</TYPE><NAME>SW1</NAME><SAVE_REF_ID>save-ref-id:2</SAVE_REF_ID><RUNNINGCONFIG><LINE>hostname SW-Original</LINE><LINE>interface FastEthernet0/1</LINE><LINE>switchport access vlan 20</LINE><LINE>!</LINE><LINE>interface FastEthernet0/2</LINE><LINE>shutdown</LINE></RUNNINGCONFIG></ENGINE></DEVICE>
  <DEVICE><ENGINE><TYPE model="2911">Router</TYPE><NAME>R1</NAME><SAVE_REF_ID>save-ref-id:3</SAVE_REF_ID><RUNNINGCONFIG><LINE>interface GigabitEthernet0/0</LINE><LINE>ip address 10.1.0.1 255.255.255.0</LINE><LINE>no shutdown</LINE><LINE>!</LINE><LINE>ip route 192.168.0.0 255.255.255.0 10.1.0.3</LINE></RUNNINGCONFIG></ENGINE></DEVICE>
  </DEVICES><LINKS><LINK><TYPE>eCopper</TYPE><CABLE><FROM>save-ref-id:1</FROM><PORT>FastEthernet0</PORT><TO>save-ref-id:2</TO><PORT>FastEthernet0/1</PORT><TYPE>eStraightThrough</TYPE></CABLE></LINK>
  <LINK><TYPE>eCopper</TYPE><CABLE><FROM>save-ref-id:2</FROM><PORT>FastEthernet0/2</PORT><TO>save-ref-id:3</TO><PORT>GigabitEthernet0/0</PORT><TYPE>eStraightThrough</TYPE></CABLE></LINK></LINKS></NETWORK></PACKETTRACER5>'''
  lab,warnings=decode_file(base64.b64encode(make_pkt(xml)).decode(),'lab.pkt')
  self.assertEqual((len(lab.devices),len(lab.links)),(3,2))
  self.assertEqual(lab.devices['PC1'].interfaces['eth0'].ip,'10.1.0.2/24')
  self.assertEqual(lab.devices['PC1'].default_gateway,'10.1.0.1')
  self.assertEqual(lab.devices['SW1'].interfaces['fa0/1'].access_vlan,20)
  self.assertFalse(lab.devices['SW1'].interfaces['fa0/2'].admin_up)
  self.assertEqual(lab.devices['R1'].interfaces['g0/0'].ip,'10.1.0.1/24')
  self.assertEqual(lab.devices['R1'].routes[0].network,'192.168.0.0/24')
  self.assertIn('ip route',lab.devices['R1'].config['packet_tracer_running_config'])
  self.assertNotIn('g0/3',lab.devices['R1'].interfaces)
  self.assertTrue(warnings)

 def test_serial_cable_and_clock_rate_are_preserved(self):
  xml='''<PACKETTRACER5><NETWORK><DEVICES>
  <DEVICE><ENGINE><TYPE model="2911">Router</TYPE><NAME>R1</NAME><SAVE_REF_ID>save-ref-id:1</SAVE_REF_ID><RUNNINGCONFIG><LINE>interface Serial0/0/0</LINE><LINE>clock rate 64000</LINE></RUNNINGCONFIG></ENGINE></DEVICE>
  <DEVICE><ENGINE><TYPE model="2911">Router</TYPE><NAME>R2</NAME><SAVE_REF_ID>save-ref-id:2</SAVE_REF_ID><RUNNINGCONFIG><LINE>interface Serial0/0/0</LINE></RUNNINGCONFIG></ENGINE></DEVICE>
  </DEVICES><LINKS><LINK><TYPE>eSerial</TYPE><CABLE><FROM>save-ref-id:1</FROM><PORT>Serial0/0/0</PORT><TO>save-ref-id:2</TO><PORT>Serial0/0/0</PORT><DCEDEV>save-ref-id:1</DCEDEV></CABLE></LINK></LINKS></NETWORK></PACKETTRACER5>'''
  lab,warnings=decode_file(base64.b64encode(make_pkt(xml)).decode(),'serial.pkt')
  self.assertEqual(len(lab.links),1);self.assertEqual(lab.links[0].cable,'serial-dce')
  self.assertEqual(lab.devices['R1'].interfaces['s0/0/0'].clock_rate,64000)
  self.assertTrue(lab.link_operational(lab.links[0]))
 def test_invalid_file_does_not_look_like_a_lab(self):
  for name, content in [('bad.json', b'{}'), ('bad.pkt', b'not a pkt'), ('bad.txt', b'{}')]:
   with self.assertRaises(ValueError): decode_file(base64.b64encode(content).decode(), name)

 @unittest.skipUnless(SAMPLE.is_file(), 'local legacy network simulator sample not installed')
 def test_real_packet_tracer_ftp_lab(self):
  lab, warnings = decode_file(base64.b64encode(SAMPLE.read_bytes()).decode(), 'FTP.pkt')
  self.assertEqual((len(lab.devices), len(lab.links)), (5, 4))
  self.assertEqual(lab.devices['PC0'].interfaces['eth0'].ip, '192.168.1.2/24')
  self.assertTrue(lab.ping('PC0', '192.168.0.2')[0])
  self.assertTrue(warnings)

 @unittest.skipUnless(SAMPLE.is_file(), 'local legacy network simulator sample not installed')
 def test_names_with_spaces_are_reported_and_preserved_in_links(self):
  sample=SAMPLE.parent.parent/'DNS'/'Multilevel_DNS.pkt'
  if not sample.is_file():self.skipTest('local DNS sample not installed')
  lab,warnings=decode_file(base64.b64encode(sample.read_bytes()).decode(),sample.name)
  self.assertIn('Local_DNS_Server',lab.devices)
  self.assertTrue(any('Local DNS Server: imported as Local_DNS_Server' in w for w in warnings))

 def test_preview_commit_and_backup_are_atomic(self):
  with tempfile.TemporaryDirectory() as folder:
   root=Path(folder); ready=root/'ready.json'; state=root/'state.json'
   lab=NetworkLab(); lab.add_device('pc','Original'); lab.save(str(state))
   other=NetworkLab(); other.add_device('pc','Imported'); payload=base64.b64encode(json.dumps(other.to_dict()).encode()).decode()
   process=subprocess.Popen([sys.executable,'desktop.py','--server','--port','0','--state',str(state),'--ready-file',str(ready)],cwd=ROOT,stdout=subprocess.DEVNULL,stderr=subprocess.DEVNULL)
   try:
    for _ in range(100):
     if ready.exists(): break
     if process.poll() is not None: self.fail('server exited')
     time.sleep(.05)
    url='http://127.0.0.1:'+str(json.loads(ready.read_text())['port'])
    def post(data):
     req=Request(url+'/api/lab/import',json.dumps(data).encode(),{'Content-Type':'application/json'})
     with urlopen(req,timeout=10) as response:return json.load(response)
    data={'filename':'lab.json','data':payload}
    self.assertEqual(post(data)['devices'],1)
    self.assertIn('Original',json.loads(state.read_text())['devices'])
    with self.assertRaises(HTTPError) as error:post({'filename':'broken.json','data':base64.b64encode(b'{}').decode(),'commit':True})
    error.exception.close()
    self.assertIn('Original',json.loads(state.read_text())['devices'])
    result=post({**data,'commit':True})
    self.assertIn('Imported',result['state']['devices'])
    backup=json.loads((root/'backups'/result['safety_backup']).read_text())
    self.assertIn('Original',backup['devices'])
    self.assertIn('Imported',json.loads(state.read_text())['devices'])
   finally:
    process.terminate();process.wait(timeout=5)

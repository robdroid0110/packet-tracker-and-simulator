"""Runnable practice patterns, safe checks, undo and Unicode translations."""
import copy,tempfile,unittest
from pathlib import Path
from netsim.model import NetworkLab,LabError
from netsim.cli import CommandProcessor
from netsim.samples import catalog,validate_translation,translation_template

class SamplesTests(unittest.TestCase):
 def setUp(self):self.lab=NetworkLab();self.cp=CommandProcessor(self.lab)
 def command(self,line):
  output=self.cp.execute(line);self.assertFalse(output.startswith('ERROR:'),output);return output
 def test_all_patterns_load_and_check_without_mutating(self):
  import json
  for sample in catalog()['samples']:
   self.command('sample load '+sample['id']);before=copy.deepcopy(self.lab.to_dict())
   result=json.loads(self.command('sample check '+sample['id']))
   self.assertEqual(result['passed'],sample['id']=='concept-arp');self.assertEqual(before,self.lab.to_dict())
 def test_undo_and_redo_restore_existing_lab(self):
  self.command('add pc Original');self.command('ip Original eth0 203.0.113.3/24');before=copy.deepcopy(self.lab.to_dict())
  self.command('sample load troubleshoot-link');loaded=copy.deepcopy(self.lab.to_dict());self.assertNotEqual(before,loaded)
  self.command('undo');self.assertEqual(before,self.lab.to_dict());self.command('redo');self.assertEqual(loaded,self.lab.to_dict())
  with tempfile.TemporaryDirectory() as tmp:
   path=Path(tmp)/'lab.json';self.lab.save(str(path));other=NetworkLab();other.load(str(path));self.assertEqual(other.to_dict(),loaded)
 def test_skill_troubleshoot_and_open_design_solutions(self):
  import json
  for ident,commands in [('skill-dhcp',['dhcp Client eth0']),('troubleshoot-link',['up SW1 fa0/2']),('design-addressing',['ip HostA eth0 10.31.1.2/24','gateway HostA 10.31.1.1','ip R1 g0/0 10.31.1.1/24','ip R1 g0/1 10.31.2.1/24','ip HostB eth0 10.31.2.2/24','gateway HostB 10.31.2.1'])]:
   self.command('sample load '+ident)
   for cmd in commands:self.command(cmd)
   self.assertTrue(json.loads(self.command('sample check '+ident))['passed'])
 def test_invalid_sample_and_translations(self):
  before=copy.deepcopy(self.lab.to_dict());self.assertTrue(self.cp.execute('sample load ../../etc/passwd').startswith('ERROR:'));self.assertEqual(before,self.lab.to_dict())
  for language in ('rus','zho','hin','ara','por','fra','ben','ind','jpn'):
   self.assertEqual(len(catalog(language)['samples']),4)
  self.assertEqual(catalog('spa')['samples'][0]['title'],'Seguir ARP e ICMP')
  pack=translation_template();pack.update(id='hin',name='हिन्दी');self.assertEqual(validate_translation(pack)['name'],'हिन्दी')
  pack['translations']['concept-arp']['title']+='%1'
  with self.assertRaises(LabError):validate_translation(pack)
  pack['translations']['concept-arp']['title']=translation_template()['translations']['concept-arp']['title']
  del pack['translations']['concept-arp']
  with self.assertRaises(LabError):validate_translation(pack)
  with self.assertRaises(LabError):catalog('bad')

if __name__=='__main__':unittest.main()

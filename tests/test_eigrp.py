"""EIGRP routes must follow configured AS, networks, reachability and persistence."""
import tempfile,unittest
from pathlib import Path
from netsim.model import NetworkLab
from netsim.cli import CommandProcessor
from netsim.device_config import action
from netsim.ios import IOSSession

class EigrpTests(unittest.TestCase):
 def setUp(self):
  self.lab=NetworkLab();cp=CommandProcessor(self.lab)
  for line in ('add pc A','add pc B','add router R1','add router R2','connect A eth0 R1 g0/0','connect R1 g0/1 R2 g0/0','connect R2 g0/1 B eth0','ip A eth0 10.1.0.2/24','ip R1 g0/0 10.1.0.1/24','ip R1 g0/1 10.0.0.1/24','ip R2 g0/0 10.0.0.2/24','ip R2 g0/1 10.2.0.1/24','ip B eth0 10.2.0.2/24','gateway A 10.1.0.1','gateway B 10.2.0.1'):
   result=cp.execute(line);self.assertFalse(result.startswith('ERROR:'),result)
 def config(self,node,asn,network,**extra):return action(self.lab,{'device':node,'action':'eigrp','asn':asn,'network':network,**extra})
 def test_advertise_withdraw_and_reload(self):
  for node,network in [('R1','10.1.0.0/24'),('R1','10.0.0.0/24'),('R2','10.0.0.0/24'),('R2','10.2.0.0/24')]:self.config(node,100,network)
  self.assertTrue(self.lab.ping('A','10.2.0.2')[0]);self.assertTrue(any(r.source=='eigrp' for r in self.lab.devices['R1'].routes))
  with tempfile.TemporaryDirectory() as directory:
   path=Path(directory)/'lab.json';self.lab.save(str(path));loaded=NetworkLab();loaded.load(str(path));self.assertTrue(loaded.ping('A','10.2.0.2')[0])
  self.lab.set_interface_state('R2','g0/0',False);self.assertFalse(self.lab.ping('A','10.2.0.2')[0]);self.assertFalse(any(r.source=='eigrp' for r in self.lab.devices['R1'].routes))
 def test_as_mismatch_and_cli(self):
  self.config('R1',100,'10.0.0.0/24');self.config('R1',100,'10.1.0.0/24');self.config('R2',101,'10.0.0.0/24');self.config('R2',101,'10.2.0.0/24')
  self.assertFalse(self.lab.ping('A','10.2.0.2')[0])
  ios=IOSSession(self.lab,'R2')
  for command in ('enable','configure terminal','router eigrp 100','network 10.0.0.0 0.0.0.255','network 10.2.0.0 0.0.0.255','end'):
   result=ios.execute(command);self.assertFalse(result.startswith('%'),result)
  self.assertTrue(self.lab.ping('A','10.2.0.2')[0]);self.assertIn('router eigrp 100',ios._running_config())

if __name__=='__main__':unittest.main()

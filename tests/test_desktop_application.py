"""Desktop server and installer use isolated state and share the existing API."""
import json,os,subprocess,sys,tempfile,time,unittest
from pathlib import Path
from urllib.request import Request,urlopen
from unittest.mock import patch
import desktop
from tools.install_linux_desktop import install

class DesktopTests(unittest.TestCase):
 def test_server_handles_existing_lab_and_api(self):
  with tempfile.TemporaryDirectory(prefix='pt-desktop-test-') as folder:
   root=Path(folder);ready=root/'ready.json';state=root/'lab.json'
   process=subprocess.Popen([sys.executable,'desktop.py','--server','--port','0','--state',str(state),'--ready-file',str(ready)],stdout=subprocess.DEVNULL,stderr=subprocess.PIPE)
   try:
    for _ in range(100):
     if ready.exists():break
     if process.poll() is not None:self.fail(process.stderr.read().decode())
     time.sleep(.05)
    url='http://127.0.0.1:'+str(json.loads(ready.read_text())['port']);self.assertTrue(desktop.health(url))
    req=Request(url+'/api/command',data=json.dumps({'command':'add pc DesktopPC'}).encode(),headers={'content-type':'application/json'})
    with urlopen(req,timeout=5) as response:self.assertTrue(json.load(response)['ok'])
    self.assertIn('DesktopPC',json.loads(state.read_text())['devices'])
   finally:
    process.terminate();process.wait(timeout=5)
    if process.stderr:process.stderr.close()
 def test_corrupt_saved_lab_never_starts_empty_server(self):
  with tempfile.TemporaryDirectory(prefix='pt-desktop-bad-') as folder:
   state=Path(folder)/'bad.json';state.write_text('{invalid');ready=Path(folder)/'ready.json'
   run=subprocess.run([sys.executable,'desktop.py','--server','--port','0','--state',str(state),'--ready-file',str(ready)],capture_output=True,timeout=8)
   self.assertNotEqual(run.returncode,0);self.assertFalse(ready.exists());self.assertEqual(state.read_text(),'{invalid')
 @unittest.skipUnless(sys.platform.startswith('linux'),'Linux desktop entry')
 def test_install_in_isolated_xdg_home(self):
  with tempfile.TemporaryDirectory(prefix='pt-install-') as folder:
   path=install(folder);text=path.read_text();self.assertIn('Name=Packet Tracker and Simulator',text);self.assertIn('desktop.py',text);self.assertTrue(os.access(path,os.X_OK))
 def test_state_override_and_existing_web_server(self):
  with patch.dict(os.environ,{'PACKETTRACKER_STATE':'/tmp/pt-selected-lab.json'}):self.assertEqual(desktop.default_state(),Path('/tmp/pt-selected-lab.json'))
  self.assertFalse(desktop.health('http://127.0.0.1:1'))

if __name__=='__main__':unittest.main()

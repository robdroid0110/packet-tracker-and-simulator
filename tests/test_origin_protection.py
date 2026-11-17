import json
import subprocess
import sys
import tempfile
import time
import unittest
from pathlib import Path
from urllib.error import HTTPError
from urllib.request import Request, urlopen

ROOT = Path(__file__).resolve().parents[1]


class OriginProtectionTests(unittest.TestCase):
    def test_cross_origin_is_rejected_and_agents_and_same_origin_still_work(self):
        with tempfile.TemporaryDirectory() as folder:
            folder = Path(folder)
            ready = folder / 'ready'
            process = subprocess.Popen([sys.executable, str(ROOT / 'desktop.py'), '--server', '--port', '0', '--state', str(folder / 'lab.json'), '--ready-file', str(ready)], stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
            try:
                for _ in range(200):
                    if ready.exists(): break
                    if process.poll() is not None: self.fail('server exited')
                    time.sleep(.05)
                url = 'http://127.0.0.1:' + str(json.loads(ready.read_text())['port'])
                def post(command, origin=None):
                    headers = {'Content-Type': 'text/plain'}
                    if origin is not None: headers['Origin'] = origin
                    request = Request(url + '/api/command', data=json.dumps({'command': command}).encode(), headers=headers)
                    try:
                        with urlopen(request) as response: return response.status, json.load(response)
                    except HTTPError as error:
                        with error: return error.code, json.load(error)
                for origin in ('http://127.0.0.1:1', 'https://attacker.example', 'null'):
                    status, result = post('add pc Rejected', origin)
                    self.assertEqual(status, 403)
                    self.assertFalse(result['ok'])
                status, result = post('add pc Agent')
                self.assertEqual(status, 200)
                self.assertNotIn('Rejected', result['state']['devices'])
                status, result = post('add pc Browser', url)
                self.assertEqual(status, 200)
                self.assertIn('Browser', result['state']['devices'])
            finally:
                process.terminate()
                process.wait(timeout=10)

#!/usr/bin/env python3
"""Isolated Chromium/CDP functional check for Sections 33–73.

Requires Chromium and Python websockets. Does not connect to the user's server
or change any saved lab. Optional --artifacts DIR keeps screenshots and report.
Run: python3 tools/verify_workspace_accessibility.py --artifacts /tmp/pt23-32-check
"""
from __future__ import annotations
import argparse
import base64
import hashlib
import json
import os
from pathlib import Path
import shutil
import socket
import subprocess
import sys
import tempfile
import time
from urllib.request import urlopen
from websockets.sync.client import connect

ROOT=Path(__file__).resolve().parents[1]


def free_port():
    with socket.socket() as sock:
        sock.bind(('127.0.0.1',0))
        return sock.getsockname()[1]


def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--artifacts',type=Path)
    args=parser.parse_args()
    browser=shutil.which('chromium') or shutil.which('google-chrome')
    if not browser:raise SystemExit('Chromium or Google Chrome is required')
    live=ROOT/'labs/autosave.json'
    original=hashlib.sha256(live.read_bytes()).hexdigest() if live.exists() else None
    report=[]
    with tempfile.TemporaryDirectory(prefix='packet-tracker-sections33-73-browser-') as folder:
        temp=Path(folder);port=free_port();debug=free_port()
        env={**os.environ,'PACKETTRACKER_STATE':str(temp/'state.json'),'PACKETTRACKER_BACKUPS':str(temp/'backups')}
        with (temp/'server.log').open('w') as server_log,(temp/'browser.log').open('w') as browser_log:
            server=subprocess.Popen([sys.executable,'server.py','--port',str(port)],cwd=ROOT,env=env,stdout=server_log,stderr=subprocess.STDOUT)
            chrome=None
            try:
                base=f'http://127.0.0.1:{port}'
                def wait_json(url):
                    deadline=time.monotonic()+20
                    while time.monotonic()<deadline:
                        try:
                            with urlopen(url,timeout=1) as response:return json.load(response)
                        except Exception:time.sleep(.1)
                    raise RuntimeError('Timed out: '+url)
                wait_json(base+'/api/state')
                chrome=subprocess.Popen([browser,'--headless','--no-sandbox','--disable-gpu',
                    '--disable-dev-shm-usage','--no-first-run','--no-default-browser-check',
                    '--remote-debugging-address=127.0.0.1','--remote-debugging-port='+str(debug),
                    '--user-data-dir='+str(temp/'profile'),'--window-size=1600,1000',base],
                    stdout=browser_log,stderr=subprocess.STDOUT)
                pages=wait_json(f'http://127.0.0.1:{debug}/json/list')
                page=next(p for p in pages if p['type']=='page')
                with connect(page['webSocketDebuggerUrl'],max_size=25000000) as ws:
                    sequence=0;errors=[]
                    def cdp(method,params=None):
                        nonlocal sequence
                        sequence+=1
                        ws.send(json.dumps({'id':sequence,'method':method,'params':params or {}}))
                        while True:
                            result=json.loads(ws.recv())
                            if result.get('method')=='Runtime.exceptionThrown':errors.append(result['params']['exceptionDetails'])
                            if result.get('id')==sequence:
                                if 'error' in result:raise RuntimeError(result['error'])
                                return result.get('result',{})
                    def js(source):
                        result=cdp('Runtime.evaluate',{'expression':source,'awaitPromise':True,'returnByValue':True})
                        if 'exceptionDetails' in result:raise RuntimeError(result['exceptionDetails'])
                        return result.get('result',{}).get('value')
                    def check(label,source):
                        result=js(source)
                        report.append({'check':label,'result':result})
                        print(label,json.dumps(result),flush=True)
                        return result
                    def screenshot(label):
                        if args.artifacts:
                            args.artifacts.mkdir(parents=True,exist_ok=True)
                            raw=cdp('Page.captureScreenshot',{'format':'png','captureBeyondViewport':False})
                            (args.artifacts/(label+'.png')).write_bytes(base64.b64decode(raw['data']))
                    cdp('Runtime.enable');cdp('Page.enable')
                    deadline=time.monotonic()+30
                    while not js("typeof PacketTrackerSimulation!=='undefined' && typeof PacketTrackerDeviceConfig!=='undefined' && !!document.querySelectorAll('.workspace-tab')[1] && typeof state!=='undefined'"):
                        if time.monotonic()>deadline:raise RuntimeError('App failed to initialize: '+json.dumps({'errors':errors,'globals':js("({simulation:typeof PacketTrackerSimulation,config:typeof PacketTrackerDeviceConfig,state:typeof state,title:document.title,body:document.body.innerText.slice(-350)})")}))
                        time.sleep(.1)
                    js("""window.waitUI=async fn=>{for(let i=0;i<150;i++){if(fn())return;await new Promise(r=>setTimeout(r,40))}throw Error('UI wait timed out')};window.assertUI=(v,msg)=>{if(!v)throw Error(msg)};
                    window.api=async(path,body)=>{const r=await fetch(path,{method:'POST',headers:{'content-type':'application/json'},body:JSON.stringify(body)});const d=await r.json();assertUI(d.ok,d.output||d.error);await fetchState();return d};
                    window.cmd=command=>api('/api/command',{command});
                    window.choose=action=>{const s=document.querySelector('#ptEngineOperation');s.value=action;s.dispatchEvent(new Event('change'))};
                    window.submitEngine=async fields=>{for(const [key,value] of Object.entries(fields)){const n=document.querySelector('#ptEngineForm [name='+key+']');assertUI(n,'Missing field '+key);if(n.type==='checkbox')n.checked=value;else n.value=typeof value==='object'?JSON.stringify(value):value}document.querySelector('#ptEngineForm').requestSubmit();await waitUI(()=>!document.querySelector('#ptEngineForm button[type=submit]').disabled);return document.querySelector('#ptEngineOutput').textContent};""")
                    def click(selector):
                        box=js("(()=>{const n=document.querySelector("+json.dumps(selector)+");if(!n)throw Error('Missing '+"+json.dumps(selector)+");const r=n.getBoundingClientRect();return {x:r.x+r.width/2,y:r.y+r.height/2}})()")
                        cdp('Input.dispatchMouseEvent',{'type':'mousePressed','x':box['x'],'y':box['y'],'button':'left','clickCount':1})
                        cdp('Input.dispatchMouseEvent',{'type':'mouseReleased','x':box['x'],'y':box['y'],'button':'left','clickCount':1})
                    def point(x,y):
                        cdp('Input.dispatchMouseEvent',{'type':'mousePressed','x':x,'y':y,'button':'left','clickCount':1})
                        cdp('Input.dispatchMouseEvent',{'type':'mouseReleased','x':x,'y':y,'button':'left','clickCount':1})
                    def wait(source):
                        try:js('(async()=>{await waitUI(()=>'+source+')})()')
                        except RuntimeError as error:raise RuntimeError(str(error)+' UI='+json.dumps(js("({power:state.devices.R1?.powered,status:document.querySelector('#statusText')?.textContent,slots:[...document.querySelectorAll('.pt-physical-slots button')].map(x=>x.disabled),dialog:dialogTab,errors:document.querySelector('#dialogBody')?.textContent.slice(-500)})"))) from error
                    click('[data-model="1941"]');point(450,300);wait("!!state.devices.R1")
                    click('[data-model="1941"]');point(760,330);wait("!!state.devices.R2")
                    check('Place two routers through palette',"Object.keys(state.devices)")
                    box=js("(()=>{let r=document.querySelector('.node[data-name=R1]').getBoundingClientRect();return {x:r.x+r.width/2,y:r.y+r.height/2}})()")
                    cdp('Input.dispatchMouseEvent',{'type':'mouseMoved','x':box['x'],'y':box['y']})
                    cdp('Input.dispatchMouseEvent',{'type':'mousePressed','x':box['x'],'y':box['y'],'button':'left','clickCount':1})
                    cdp('Input.dispatchMouseEvent',{'type':'mouseMoved','x':box['x']+80,'y':box['y']+60,'button':'left','buttons':1})
                    cdp('Input.dispatchMouseEvent',{'type':'mouseReleased','x':box['x']+80,'y':box['y']+60,'button':'left','clickCount':1})
                    wait("state.devices.R1.x>400");check('Drag router without opening dialog',"(()=>{assertUI(document.querySelector('#deviceDialog').classList.contains('hidden'),'Drag opened the device');return {x:state.devices.R1.x,dialog:false}})()")
                    click('.node[data-name=R1]');wait("!document.querySelector('#deviceDialog').classList.contains('hidden')")
                    check('Single click opens router window',"(()=>{const tabs=[...document.querySelectorAll('#dialogTabs [data-tab]')].map(n=>n.textContent);assertUI(['Physical','Config','CLI','Attributes'].every(t=>tabs.includes(t))&&!!document.querySelector('#ptDevicePower'),'Missing router tabs or physical view');return {title:document.querySelector('#dialogName').textContent,tabs,physical:true}})()")
                    wait("!!document.querySelector('.pt-physical-slots select')")
                    click('#ptDevicePower');wait("state.devices.R1.powered===false && !!document.querySelector('.pt-physical-slots button:not([disabled])')")
                    js("document.querySelector('.pt-physical-slots select').value='PT-FIBER-MM-1'");click('.pt-physical-slots button');wait("state.devices.R1.modules.slot0==='PT-FIBER-MM-1'")
                    click('#ptDevicePower');wait("state.devices.R1.powered===true")
                    check('Physical window installs module when powered off',"state.devices.R1.modules")
                    click('#dialogTabs [data-tab=config]');wait("!!document.querySelector('#ptStartupSave')")
                    check('Config panel exposes hostname and NVRAM',"({hostname:!document.querySelector('#ptHostname').disabled,save:!document.querySelector('#ptStartupSave').disabled})")
                    click('#ptHostname');js("document.querySelector('#ptHostname').select()");cdp('Input.insertText',{'text':'EdgeRouter'});check('Hostname input before apply',"document.querySelector('#ptHostname').value");click('#ptGlobalApply');wait("state.devices.R1.config.hostname==='EdgeRouter'")
                    click('#ptStartupSave');wait("state.devices.R1.config.startup_managed===true")
                    check('Hostname and startup save update backend',"({hostname:state.devices.R1.config.hostname,saved:state.devices.R1.config.startup_managed})")
                    click('#dialogTabs [data-tab=cli]');check('CLI tab opens terminal',"!!document.querySelector('#deviceCliIn')")
                    click('#dialogTabs [data-tab=attributes]');check('Attributes tab opens',"document.querySelector('#dialogBody').textContent.includes('interfaces')")
                    click('#dialogClose');click('[data-group="3"]');wait("!!document.querySelector('[data-connection=copper-cross]')")
                    click('[data-connection=copper-cross]');click('.node[data-name=R1]');wait("!document.querySelector('#ptPortDialog').classList.contains('hidden')")
                    check('First click asks for source port',"document.querySelector('#ptPortDialog').textContent")
                    click('#ptPortDialog button:first-of-type')
                    cdp('Input.dispatchMouseEvent',{'type':'mouseMoved','x':740,'y':340});check('Cable preview follows pointer',"(()=>{assertUI(!!document.querySelector('#ptCablePreview'),'Cable preview missing');return true})()")
                    click('.node[data-name=R2]');wait("!document.querySelector('#ptPortDialog').classList.contains('hidden')")
                    click('#ptPortDialog button:first-of-type')
                    wait('state.links.length===1');check('Cable creates operational link and endpoint lights',"(()=>{assertUI(state.links[0].up&&state.links[0].lights.every(l=>l.color==='green')&&document.querySelectorAll('#wires polygon').length===2,'Link or endpoint lights missing');return {link:state.links[0],lights:2}})()")
                    click('[data-connection=fiber-mm]');click('.node[data-name=R1]');wait("!document.querySelector('#ptPortDialog').classList.contains('hidden')")
                    click('#ptPortDialog button:first-of-type');click('.node[data-name=R2]');wait("!document.querySelector('#ptPortDialog').classList.contains('hidden')")
                    check('Incompatible destination offers cancel',"(()=>{assertUI(document.querySelector('#ptPortDialog').textContent.includes('No free compatible interfaces'),'Incompatible port not explained');return true})()")
                    click('#ptPortDialog button:last-of-type');check('Cancel preserves existing link',"(()=>{assertUI(state.links.length===1&&activeTool==='select','Cancel changed the topology');return true})()")
                    screenshot('router-interactions')
                    if errors:raise RuntimeError('Browser errors: '+json.dumps(errors))
                    report.append({'browser_exceptions':errors})
                saved=json.loads((temp/'state.json').read_text())
                assert len(saved['devices'])==2 and len(saved['links'])==1
                assert saved['devices']['R1']['x']>400 and saved['devices']['R1']['modules']['slot0']=='PT-FIBER-MM-1'
                assert saved['devices']['R1']['config']['hostname']=='EdgeRouter' and saved['devices']['R1']['config']['startup_managed']
            finally:
                for process in (chrome,server):
                    if process:
                        process.terminate()
                        try:process.wait(timeout=5)
                        except subprocess.TimeoutExpired:process.kill();process.wait(timeout=5)
                if args.artifacts:
                    args.artifacts.mkdir(parents=True,exist_ok=True)
                    for name in ('server.log','browser.log'):shutil.copyfile(temp/name,args.artifacts/name)
    after=hashlib.sha256(live.read_bytes()).hexdigest() if live.exists() else None
    assert original==after,'User autosave changed during isolated browser tests'
    report.append({'active_lab_preserved':True,'sha256':original})
    if args.artifacts:(args.artifacts/'report.json').write_text(json.dumps(report,indent=2))
    print('PASS: isolated browser behaviour; active lab preserved',flush=True)


if __name__=='__main__':main()

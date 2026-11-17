#!/usr/bin/env python3
"""Isolated Chromium/CDP functional check for Section 22.

Requires Chromium and Python websockets. Does not connect to the user's server
or change any saved lab. Optional --artifacts DIR keeps screenshots and report.
Run: python3 tools/verify_physical_special_notes.py --artifacts /tmp/pt22-check
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
    with tempfile.TemporaryDirectory(prefix='packet-tracker-section22-browser-') as folder:
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
                    deadline=time.monotonic()+15
                    while not js("typeof PacketTrackerPhysicalSettings!=='undefined' && !!document.querySelectorAll('.workspace-tab')[1] && typeof state!=='undefined'"):
                        if time.monotonic()>deadline:raise RuntimeError('App failed to initialize')
                        time.sleep(.1)
                    # Helpers run in the actual browser and poll rendered authoritative state.
                    js("""window.pt22wait=async fn=>{for(let i=0;i<100;i++){if(fn())return;await new Promise(r=>setTimeout(r,40))}throw Error('UI wait timed out')};
                    window.pt22assert=(v,msg)=>{if(!v)throw Error(msg)};
                    window.pt22location=async location=>{dispatchEvent(new CustomEvent('pt-physical-focus-location',{detail:{location}}));await pt22wait(()=>document.querySelector('#ptPhysicalWorkspace').dataset.location===location)};
                    window.pt22cmd=async command=>{const r=await fetch('/api/command',{method:'POST',headers:{'content-type':'application/json'},body:JSON.stringify({command})});const data=await r.json();pt22assert(data.ok,data.output);return data};
                    document.querySelectorAll('.workspace-tab')[1].click();""")
                    check('initial metric grid',"""(async()=>{await pt22wait(()=>document.querySelector('.pt-metric-grid pattern'));const p=document.querySelector('.pt-metric-grid pattern');pt22assert(p.getAttribute('width')==='25','Initial metric width');return {width:p.getAttribute('width'),height:p.getAttribute('height')}})()""")
                    check('configure city grid through dialog',"""(async()=>{
                      document.querySelector('[title="Configure Physical Grid"]').click();
                      await pt22wait(()=>document.querySelector('#ptPhysicalSettings').open);
                      document.querySelector('#ptGridType').value='city';document.querySelector('#ptGridType').dispatchEvent(new Event('change'));
                      document.querySelector('#ptGridSpacing').value='125';document.querySelector('#ptGridColor').value='#cc2244';
                      document.querySelector('#ptPhysicalSettings form').requestSubmit();
                      await pt22wait(()=>!document.querySelector('#ptPhysicalSettings').open&&state.physical_grids.city.spacing_m===125);
                      await pt22location('city0');await pt22wait(()=>document.querySelector('.pt-metric-grid pattern')?.getAttribute('width')==='25');
                      const p=document.querySelector('.pt-metric-grid pattern');pt22assert(p.querySelector('path').getAttribute('stroke')==='#cc2244','Grid color');
                      return {profile:state.physical_grids.city,width:p.getAttribute('width'),height:p.getAttribute('height')};
                    })()""")
                    screenshot('city-grid')
                    check('grid geometry follows resize API',"""(async()=>{
                      await pt22cmd('physical dimensions city0 2500 1250 500');await fetchState();
                      await pt22wait(()=>document.querySelector('.pt-metric-grid pattern')?.getAttribute('width')==='50');
                      return {width:document.querySelector('.pt-metric-grid pattern').getAttribute('width'),height:document.querySelector('.pt-metric-grid pattern').getAttribute('height')};
                    })()""")
                    check('seed functioning network',"""(async()=>{
                      for(const cmd of ['add pc PC1','add router R1','connect PC1 eth0 R1 g0/0','ip PC1 eth0 192.0.2.2/24','ip R1 g0/0 192.0.2.1/24'])await pt22cmd(cmd);
                      await fetchState();const p=await pt22cmd('ping PC1 192.0.2.1');pt22assert(p.output.includes('PING success'),'Seed ping');return p.output;
                    })()""")
                    check('delete tool previews and cancel preserves equipment',"""(async()=>{
                      await pt22location('building0');document.querySelector('[data-tool="delete"]').click();
                      document.querySelector('.pt-location[data-location="closet0"]').click();
                      await pt22wait(()=>document.querySelector('#ptPhysicalSettings').open);
                      pt22assert(document.querySelector('[data-delete-location="closet0"]'),'Delete tool selected wrong object');
                      const text=document.querySelector('#ptPhysicalSettings').textContent;
                      pt22assert(text.includes('Extract 1 device(s)'),'Extraction count');
                      document.querySelector('#ptPhysicalSettings button[type=button]').click();
                      pt22assert(state.physical_locations.closet0&&state.device_locations.R1==='closet0','Cancel mutated');
                      return {preview:text,cancelled:true};
                    })()""")
                    check('delete current closet extracts router and keeps ping',"""(async()=>{
                      document.querySelector('[data-tool="select"]').click();await pt22location('closet0');
                      document.querySelector('[title="Delete Current Physical Location"]').click();
                      await pt22wait(()=>document.querySelector('#ptPhysicalSettings').open);
                      document.querySelector('#ptPhysicalSettings form').requestSubmit();
                      await pt22wait(()=>!state.physical_locations.closet0&&!document.querySelector('#ptPhysicalSettings').open);
                      pt22assert(state.device_locations.R1==='building0','Router not extracted');
                      pt22assert(state.physical_device_details.R1.surface==='floor','Router not on floor');
                      const p=await pt22cmd('ping PC1 192.0.2.1');pt22assert(p.output.includes('PING success'),'Extraction broke ping');
                      return {location:state.device_locations.R1,mount:state.physical_device_details.R1.surface,links:state.links.length,ping:p.output};
                    })()""")
                    screenshot('extracted-router')
                    check('shared undo and redo restore physical state',"""(async()=>{
                      await pt22cmd('undo');await fetchState();pt22assert(state.device_locations.R1==='closet0','Undo failed');
                      await pt22cmd('redo');await fetchState();pt22assert(state.device_locations.R1==='building0','Redo failed');
                      return {location:state.device_locations.R1,closet:!!state.physical_locations.closet0};
                    })()""")
                    check('tiny grid suppresses visual lines, saves exact meters',"""(async()=>{
                      await pt22cmd('physical grid building on 0.01 #abcdef');await fetchState();
                      await pt22wait(()=>document.querySelector('.pt-map-cards')?.dataset.gridDensity==='hidden');
                      pt22assert(!document.querySelector('.pt-metric-grid'),'Dense lines visible');return state.physical_grids.building;
                    })()""")
                    check('disabled grid and reload persistence',"""(async()=>{
                      await pt22cmd('physical grid building off 2.5 #aabbcc');await fetchState();
                      await pt22wait(()=>document.querySelector('.pt-map-cards')?.dataset.gridEnabled==='false');
                      pt22assert(!document.querySelector('.pt-metric-grid'),'Disabled grid visible');
                      return {grid:state.physical_grids.building,devices:Object.keys(state.devices)};
                    })()""")
                    cdp('Page.addScriptToEvaluateOnNewDocument',{'source':
                        "window.pt22wait=async fn=>{for(let i=0;i<100;i++){if(fn())return;await new Promise(r=>setTimeout(r,40))}throw Error('UI wait timed out')};"
                        "window.pt22assert=(v,msg)=>{if(!v)throw Error(msg)};"})
                    cdp('Page.reload',{'ignoreCache':True});time.sleep(.6)
                    check('reload uses saved lab',"""(async()=>{
                      await pt22wait(()=>typeof state!=='undefined'&&state.physical_grids?.building.spacing_m===2.5);
                      pt22assert(state.device_locations.R1==='building0','Reload placement');
                      pt22assert(!state.physical_locations.closet0,'Reload deleted closet');
                      return {grid:state.physical_grids.building,location:state.device_locations.R1};
                    })()""")
                    check('responsive dialog and keyboard Escape',"""(async()=>{
                      document.querySelectorAll('.workspace-tab')[1].click();await PacketTrackerPhysicalSettings.openGrid();
                      const d=document.querySelector('#ptPhysicalSettings');pt22assert(d.open,'Grid dialog absent');
                      return {width:d.getBoundingClientRect().width,focus:document.activeElement.id};
                    })()""")
                    cdp('Emulation.setDeviceMetricsOverride',{'width':390,'height':844,'deviceScaleFactor':1,'mobile':False})
                    check('390px dialog fits',"""(()=>{const d=document.querySelector('#ptPhysicalSettings').getBoundingClientRect();pt22assert(d.left>=0&&d.right<=innerWidth,'Dialog overflow');return {left:d.left,right:d.right,width:innerWidth}})()""")
                    screenshot('mobile-grid-dialog')
                    cdp('Input.dispatchKeyEvent',{'type':'keyDown','key':'Escape','code':'Escape','windowsVirtualKeyCode':27})
                    cdp('Input.dispatchKeyEvent',{'type':'keyUp','key':'Escape','code':'Escape','windowsVirtualKeyCode':27})
                    check('Escape closes and restores focus',"""(()=>{pt22assert(!document.querySelector('#ptPhysicalSettings').open,'Escape failed');pt22assert(document.activeElement.title==='Configure Physical Grid','Focus restoration failed');return {closed:true,focus:document.activeElement.title}})()""")
                    check('physical palette creation after removing original locations',"""(async()=>{
                      await PacketTrackerPhysicalSettings.openDelete('city0');
                      document.querySelector('#ptPhysicalSettings form').requestSubmit();
                      await pt22wait(()=>Object.keys(state.physical_locations).length===0&&!document.querySelector('#ptPhysicalSettings').open);
                      document.querySelector('[data-model]').click();
                      const map=document.querySelector('.pt-map-cards'),bounds=map.getBoundingClientRect();
                      map.dispatchEvent(new MouseEvent('click',{bubbles:true,clientX:bounds.left+200,clientY:bounds.top+200}));
                      await pt22wait(()=>!!state.devices.R2);
                      pt22assert(state.device_locations.R2==='intercity','Palette created orphaned device');
                      pt22assert(state.physical_device_details.R2.surface==='floor','Palette wrong mounting');
                      return {device:state.devices.R2.name,model:state.devices.R2.model,location:state.device_locations.R2};
                    })()""")
                    if errors:raise RuntimeError('Browser errors: '+json.dumps(errors))
                    report.append({'browser_exceptions':errors})
                saved=json.loads((temp/'state.json').read_text())
                assert saved['device_locations']['R1']=='intercity'
                assert saved['device_locations']['R2']=='intercity'
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

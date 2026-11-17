#!/usr/bin/env python3
"""Isolated Chromium/CDP functional check for Sections 23–32.

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
    with tempfile.TemporaryDirectory(prefix='packet-tracker-sections23-32-browser-') as folder:
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
                    while not js("typeof PacketTrackerTools!=='undefined' && !!document.querySelectorAll('.workspace-tab')[1] && typeof state!=='undefined'"):
                        if time.monotonic()>deadline:raise RuntimeError('App failed to initialize')
                        time.sleep(.1)
                    js("""window.ptwait=async fn=>{for(let i=0;i<100;i++){if(fn())return;await new Promise(r=>setTimeout(r,40))}throw Error('UI wait timed out')};
                    window.ptassert=(v,msg)=>{if(!v)throw Error(msg)};
                    window.ptcmd=async command=>{const r=await fetch('/api/command',{method:'POST',headers:{'content-type':'application/json'},body:JSON.stringify({command})});const d=await r.json();ptassert(d.ok,d.output);await fetchState();return d};""")
                    check('seed lab',"""(async()=>{await ptcmd('add pc A 1800 1200');await ptcmd('add pc B 2000 1200');await ptcmd('connect A eth0 B eth0');await ptcmd('ip A eth0 192.0.2.1/24');await ptcmd('ip B eth0 192.0.2.2/24');await ptcmd('pdu A B');return (await ptcmd('ping A 192.0.2.2')).output})()""")
                    check('template manager captures configured device',"""(async()=>{document.querySelector('#ptWorkspaceToolsButton').click();document.querySelector('#ptTemplateName').value='Host';document.querySelector('#ptTemplateSource').value='A';[...document.querySelectorAll('#ptWorkspaceToolsDialog button')].find(b=>b.textContent==='Add template').click();await ptwait(()=>state.workspace_tools.templates.Host);return Object.keys(state.workspace_tools.templates.Host.lab.devices)})()""")
                    check('template manager creates an instance',"""(async()=>{[...document.querySelectorAll('#ptWorkspaceToolsDialog button')].find(b=>b.textContent==='Create from template').click();await ptwait(()=>Object.keys(state.devices).length===3);ptassert(state.devices.A_1.interfaces.eth0.ip==='192.0.2.1/24','Lost configuration');return {devices:Object.keys(state.devices),mac:state.devices.A_1.interfaces.eth0.mac}})()""")
                    check('contrast and DPI saved through controls',"""(async()=>{document.querySelector('#ptContrast').value='high';document.querySelector('#ptApplicationScale').value='1.5';[...document.querySelectorAll('#ptWorkspaceToolsDialog button')].find(b=>b.textContent==='Apply accessibility').click();await ptwait(()=>document.body.classList.contains('pt-high-contrast'));ptassert(getComputedStyle(document.body).backgroundColor==='rgb(0, 0, 0)','Contrast not rendered');return {settings:state.workspace_tools.accessibility,scale:getComputedStyle(document.documentElement).getPropertyValue('--pt-global-scale')}})()""")
                    screenshot('high-contrast-tools')
                    check('accessible packet event inspection',"""(()=>{[...document.querySelectorAll('#ptWorkspaceToolsDialog button')].find(b=>b.textContent==='Accessible simulation events').click();const d=document.querySelector('dialog[open]');ptassert(d.querySelectorAll('tbody tr').length>0,'No trace events');d.querySelector('summary').click();const count=d.querySelectorAll('tbody tr').length;d.querySelector('button').click();return count})()""")
                    check('viewport modes and backend pan',"""(async()=>{await PacketTrackerTools.toggleViewport();await ptwait(()=>document.querySelector('#ptViewport .pt-viewport-map'));const select=document.querySelector('#ptViewport select');select.value='workspace';select.dispatchEvent(new Event('change'));await ptwait(()=>state.workspace_tools.viewport.mode==='workspace');const map=document.querySelector('#ptViewport .pt-viewport-map'),rect=map.getBoundingClientRect();map.dispatchEvent(new MouseEvent('click',{bubbles:true,clientX:rect.left+rect.width*.8,clientY:rect.top+rect.height*.8}));await ptwait(()=>state.workspace_tools.viewport.x>0);ptassert(document.querySelector('#workspace').scrollLeft>0,'Viewport did not scroll workspace');return state.workspace_tools.viewport})()""")
                    screenshot('viewport')
                    check('physical viewport',"""(async()=>{document.querySelectorAll('.workspace-tab')[1].click();await ptwait(()=>document.querySelector('#ptViewport .pt-viewport-map'));const r=await fetch('/api/workspace-tools?workspace=physical&location=intercity');const d=await r.json();ptassert(d.items.some(i=>i.type==='location'),'No physical container markers');return d.items})()""")
                    check('physical viewport radio coverage',"""(async()=>{await ptcmd('add-model AccessPoint-PT AP1');const prefs=JSON.parse(localStorage.getItem('packetTracker.preferences.v1'))||{};prefs.showWirelessGrid=true;localStorage.setItem('packetTracker.preferences.v1',JSON.stringify(prefs));dispatchEvent(new CustomEvent('pt-physical-presentation',{detail:{showWirelessGrid:true}}));dispatchEvent(new CustomEvent('pt-physical-focus-location',{detail:{location:'building0'}}));await ptwait(()=>document.querySelector('.pt-viewport-radio'));return document.querySelectorAll('.pt-viewport-radio').length})()""")
                    check('keyboard accessible physical navigation',"""(()=>{document.querySelectorAll('.workspace-tab')[1].click();document.body.focus();return true})()""")
                    cdp('Input.dispatchKeyEvent',{'type':'keyDown','key':'N','code':'KeyN','modifiers':8,'windowsVirtualKeyCode':78})
                    cdp('Input.dispatchKeyEvent',{'type':'keyUp','key':'N','code':'KeyN','modifiers':8,'windowsVirtualKeyCode':78})
                    check('Shift N opens textual physical navigation',"""(async()=>{await ptwait(()=>!document.querySelector('#ptAccessiblePhysical').hidden);PacketTrackerAccessible.close();return true})()""")
                    check('logical visual API and rendered background',"""(async()=>{document.querySelectorAll('.workspace-tab')[0].click();await fetch('/api/visuals/action',{method:'POST',headers:{'content-type':'application/json'},body:JSON.stringify({action:'set_background',location:'logical:root',asset_id:null,tiled:false,color:'#112233'})});await fetchState();ptassert(document.querySelector('#workspace').style.backgroundColor==='rgb(17, 34, 51)','Background not applied');return document.querySelector('#workspace').style.backgroundColor})()""")
                    check('cluster icon picker opens',"""(async()=>{await ptcmd('cluster add Room none');[...document.querySelectorAll('.pt-cluster-card button')].find(b=>b.textContent==='Customize Icon').click();await ptwait(()=>!document.querySelector('#ptVisualDialog').hidden);return true})()""")
                    sys.path.insert(0,str(ROOT));sys.path.insert(0,str(ROOT/'tests'))
                    from test_visual_customization import png
                    asset_file=temp/'custom-icon.png';asset_file.write_bytes(png())
                    doc=cdp('DOM.getDocument');node_id=cdp('DOM.querySelector',{'nodeId':doc['root']['nodeId'],'selector':'#ptVisualFile'})['nodeId']
                    cdp('DOM.setFileInputFiles',{'nodeId':node_id,'files':[str(asset_file)]})
                    check('cluster icon upload apply and render',"""(async()=>{await ptwait(()=>Object.keys(state.visual_assets).length>0&&!document.querySelector('#ptVisualApply').disabled);document.querySelector('#ptVisualApply').click();await ptwait(()=>!!state.cluster_icons.Cluster0);ptassert(!!document.querySelector('.pt-cluster-card img'),'Cluster icon not rendered');return state.cluster_icons.Cluster0})()""")
                    check('custom template component palette places configured instance',"""(async()=>{document.querySelector('#ptTemplatePaletteButton').click();document.querySelector('[data-template="Host"]').click();const workspace=document.querySelector('#workspace'),r=workspace.getBoundingClientRect();workspace.dispatchEvent(new MouseEvent('click',{bubbles:true,clientX:r.left+250,clientY:r.top+200}));await ptwait(()=>!!state.devices.A_2);ptassert(state.devices.A_2.interfaces.eth0.ip==='192.0.2.1/24','Palette lost configuration');return state.devices.A_2.name})()""")
                    check('all button controls have accessible labels',"""(()=>{const missing=[...document.querySelectorAll('button')].filter(b=>!b.textContent.trim()&&!b.getAttribute('aria-label'));ptassert(!missing.length,'Unnamed buttons');return {buttons:document.querySelectorAll('button').length,missing:missing.length}})()""")
                    check('embedded web view has a labelled sandbox and native content',"""(()=>{openDevice('A');dialogTab='desktop';desktopTool='browser';renderDialog();const f=document.querySelector('#ptWebFrame');ptassert(f.title==='Simulated HTTP page'&&f.hasAttribute('sandbox'),'Unlabelled or unsafe web view');f.srcdoc='<html lang="en"><body><h1>Accessible lab page</h1><label>Answer<input></label><a href="#answer">Answer link</a></body></html>';return {title:f.title,sandbox:f.getAttribute('sandbox')}})()""")
                    time.sleep(.2)
                    check('terminal focus escape',"""(()=>{dialogTab='desktop';desktopTool='cmd';renderDialog();document.querySelector('#pcCmdIn').focus();return document.activeElement.id})()""")
                    cdp('Input.dispatchKeyEvent',{'type':'keyDown','key':'F6','code':'F6','modifiers':2,'windowsVirtualKeyCode':117})
                    cdp('Input.dispatchKeyEvent',{'type':'keyUp','key':'F6','code':'F6','modifiers':2,'windowsVirtualKeyCode':117})
                    check('Ctrl F6 leaves terminal inside device dialog',"""(()=>{ptassert(document.activeElement.id!=='pcCmdIn','Terminal focus trapped');ptassert(document.querySelector('#deviceDialog').contains(document.activeElement),'Focus escaped modal');closeDevice();return true})()""")
                    ax=cdp('Accessibility.getFullAXTree');assert any(n.get('role',{}).get('value')=='button' and n.get('name',{}).get('value')=='Workspace Tools' for n in ax['nodes'])
                    cdp('Emulation.setEmulatedMedia',{'features':[{'name':'forced-colors','value':'active'}]})
                    check('OS forced-colors detection',"matchMedia('(forced-colors:active)').matches")
                    cdp('Emulation.setDeviceMetricsOverride',{'width':3840,'height':2160,'deviceScaleFactor':2,'mobile':False})
                    js('PacketTrackerTools.open()');screenshot('4k-tools')
                    check('4K settings dialog is visible',"""(()=>{const r=document.querySelector('#ptWorkspaceToolsDialog').getBoundingClientRect();ptassert(r.width>0&&r.right<innerWidth,'4k overflow');return {width:r.width,viewport:innerWidth}})()""")
                    js('document.querySelector("#ptWorkspaceToolsDialog").close()')
                    cdp('Page.addScriptToEvaluateOnNewDocument',{'source':"window.ptwait=async fn=>{for(let i=0;i<100;i++){if(fn())return;await new Promise(r=>setTimeout(r,40))}throw Error('UI wait timed out')};window.ptassert=(v,msg)=>{if(!v)throw Error(msg)};"})
                    cdp('Page.reload',{'ignoreCache':True});time.sleep(.6)
                    check('saved settings and templates survive reload',"""(async()=>{await ptwait(()=>typeof state!=='undefined'&&state.workspace_tools?.templates.Host);ptassert(state.workspace_tools.accessibility.scale===1.5,'Lost scaling');ptassert(document.body.classList.contains('pt-high-contrast'),'Lost contrast');return {templates:Object.keys(state.workspace_tools.templates),contrast:state.workspace_tools.accessibility.contrast}})()""")
                    if errors:raise RuntimeError('Browser errors: '+json.dumps(errors))
                    report.append({'browser_exceptions':errors})
                saved=json.loads((temp/'state.json').read_text())
                assert saved['workspace_tools']['templates']['Host']['kind']=='device'
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

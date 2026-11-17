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
                    check('seed functional lab',"""(async()=>{for(const c of ['add pc A','add server S','add switch SW','add router R','connect A eth0 SW fa0/1','connect S eth0 SW fa0/2','connect R g0/0 SW fa0/3','ip A eth0 192.0.2.1/24','ip S eth0 192.0.2.2/24','ip R g0/0 192.0.2.254/24'])await cmd(c);return Object.keys(state.devices)})()""")
                    check('Simulation freezes queued PDU',"""(async()=>{document.querySelector('#simulationBtn').click();await waitUI(()=>state.simulation.mode==='simulation');document.querySelector('[data-tool="pdu-simple"]').click();document.querySelector('.node[data-name=A]').click();document.querySelector('.node[data-name=S]').click();await waitUI(()=>Object.keys(state.simulation.pdus).length===1);assertUI(!Object.keys(state.devices.A.arp_table).length,'Queued PDU learned ARP early');assertUI(!state.simulation.events.length,'Queued PDU already captured');return {pdus:Object.keys(state.simulation.pdus),events:state.simulation.events.length}})()""")
                    check('Capture step and inspect PDU fields',"""(async()=>{document.querySelector('[data-sim-step=forward]').click();await waitUI(()=>state.simulation.cursor===1);document.querySelector('#simulationEvents button').click();const d=document.querySelector('#ptPduInspector');assertUI(d.open,'Inspector closed');const labels=[...d.querySelectorAll('[role=tab]')].map(n=>n.textContent);assertUI(labels.includes('OSI Model')&&labels.includes('Inbound PDU Details'),'Missing inspector panels');return labels})()""")
                    screenshot('capture-inspector')
                    js("document.querySelector('#ptPduInspector > button:last-child').click()")
                    check('PDU completes and Back keeps master time',"""(async()=>{for(let i=0;i<10;i++)await PacketTrackerSimulation.act({action:'step'});const p=Object.values(state.simulation.pdus)[0];assertUI(p.status==='Successful','PDU failed');const time=state.simulation.master_time;await PacketTrackerSimulation.act({action:'back'});assertUI(time===state.simulation.master_time,'Back rewound master time');return {status:p.status,time}})()""")
                    check('Scenario controls are backed by saved state',"""(async()=>{const original=window.prompt;window.prompt=()=> 'Scenario Browser';document.querySelector('#scenarioNewBtn').click();window.prompt=original;await waitUI(()=>Object.keys(state.simulation.scenarios).length===2);const select=document.querySelector('#scenarioPane select');select.value=[...select.options].at(-1).value;select.dispatchEvent(new Event('change'));await waitUI(()=>state.simulation.active!=='scenario0');assertUI(state.simulation.cursor===0,'Scenario did not reset capture');return state.simulation.scenarios})()""")
                    check('Complex PDU editor schedules periodic traffic',"""(async()=>{document.querySelector('[data-tool="pdu-complex"]').click();document.querySelector('.node[data-name=A]').click();assertUI(document.querySelector('#ptPduEditor').open,'Complex editor closed: '+activeTool+' handler='+nodeClick.toString().slice(0,250));for(const [key,value] of Object.entries({destination:'S',protocol:'UDP',destination_port:69,ttl:16,size:256,start:1,interval:2})){document.querySelector('#ptPduEditor [name='+key+']').value=value}document.querySelector('#ptPduEditor form').requestSubmit();await waitUI(()=>!document.querySelector('#ptPduEditor').open);const p=Object.values(state.simulation.pdus).find(p=>p.protocol==='UDP');assertUI(p.ttl===16&&p.size===256&&p.interval===2,'Complex fields lost');await PacketTrackerSimulation.act({action:'advance',seconds:5.5});assertUI(Object.values(state.simulation.pdus).find(p=>p.protocol==='UDP').runs===3,'Periodic scheduler did not run three times');return p})()""")
                    check('Operating mode return to realtime',"""(async()=>{document.querySelector('#realtimeBtn').click();await waitUI(()=>state.simulation.mode==='realtime');return state.simulation.mode})()""")
                    check('Device configuration interface form',"""(async()=>{await PacketTrackerDeviceConfig.open('R','interface');await submitEngine({interface:'g0/0',ip:'192.0.2.254/24',speed:'1000',duplex:'full'});assertUI(state.devices.R.interfaces['g0/0'].speed==='1000','Speed not saved: '+document.querySelector('#ptEngineOutput').textContent);return state.devices.R.interfaces['g0/0']})()""")
                    check('NVRAM saves and restores actual configuration',"""(async()=>{choose('save_startup');await submitEngine({});choose('interface');await submitEngine({interface:'g0/0',ip:'192.0.2.99/24'});assertUI(state.devices.R.interfaces['g0/0'].ip==='192.0.2.99/24','Live IP edit failed');choose('power');await submitEngine({enabled:false});await submitEngine({enabled:true});assertUI(state.devices.R.interfaces['g0/0'].ip==='192.0.2.254/24','Startup restore failed '+document.querySelector('#ptEngineOutput').textContent+' powered='+state.devices.R.powered+' managed='+state.devices.R.config.startup_managed);return state.devices.R.config.startup_managed})()""")
                    check('Physical module install uses media-aware ports',"""(async()=>{choose('power');await submitEngine({enabled:false});choose('module');await submitEngine({slot:'slot0',module:'PT-FIBER-MM-1'});assertUI(state.devices.R.interfaces['m0/1'].media==='fiber-mm','Wrong module medium');choose('power');await submitEngine({enabled:true});document.querySelector('#ptDeviceEngine>button:last-child').click();return state.devices.R.modules})()""")
                    check('FTP account and file from device forms',"""(async()=>{await PacketTrackerDeviceConfig.open('S','service');await submitEngine({service:'ftp',enabled:true});choose('service_user');await submitEngine({service:'ftp',username:'reader',password:'pw',permissions:['read','list']});choose('file_write');await submitEngine({file:'hello.txt',content:'Hello from the simulated FTP server'});document.querySelector('#ptDeviceEngine>button:last-child').click();await PacketTrackerDeviceConfig.open('A','transfer');const text=await submitEngine({server:'S',protocol:'ftp',operation:'get',file:'hello.txt',username:'reader',password:'pw'});assertUI(state.devices.A.config.files['hello.txt']==='Hello from the simulated FTP server','FTP client did not transfer file');document.querySelector('#ptDeviceEngine>button:last-child').click();return text})()""")
                    check('Queued browser HTTP waits for capture',"""(async()=>{await cmd('http-page S / "<h1>Captured HTTP completion</h1>"');await PacketTrackerSimulation.act({action:'scenario_select',id:'scenario0'});document.querySelector('#simulationBtn').click();await waitUI(()=>state.simulation.mode==='simulation');openDevice('A');dialogTab='desktop';desktopTool='browser';renderDialog();document.querySelector('#ptWebAddress').value='http://192.0.2.2/';document.querySelector('#ptWebForm').requestSubmit();await waitUI(()=>Object.values(state.simulation.pdus).some(p=>p.task?.operation==='http'));assertUI(document.querySelector('#ptWebFrame').srcdoc.includes('Waiting'),'HTTP rendered before capture');closeDevice();for(let i=0;i<30;i++)await PacketTrackerSimulation.act({action:'step'}).then(()=>document.dispatchEvent(new CustomEvent('packettracker:packet-step',{detail:state.simulation.last_event||{seq:0}})));openDevice('A');dialogTab='desktop';desktopTool='browser';renderDialog();assertUI(document.querySelector('#ptWebFrame').srcdoc.includes('Captured HTTP completion'),'HTTP completion not delivered');closeDevice();document.querySelector('#realtimeBtn').click();await waitUI(()=>state.simulation.mode==='realtime');return true})()""")
                    check('Industrial program form executes a timer',"""(async()=>{await cmd('add-model PLC-PT PLC');await PacketTrackerDeviceConfig.open('PLC','industrial');await submitEngine({tags:{input:1}});choose('plc_program');await submitEngine({blocks:[{op:'timer',inputs:['input'],output:'done',preset:1}]});choose('plc_run');await submitEngine({seconds:1.1});assertUI(state.devices.PLC.config.industrial.tags.done===1,'PLC timer did not execute');return state.devices.PLC.config.industrial.tags})()""")
                    check('Controller discovery and provisioning from native forms',"""(async()=>{document.querySelector('#ptDeviceEngine>button:last-child').click();await PacketTrackerDeviceConfig.open('S','controller');await submitEngine({username:'admin',password:'pw'});choose('discover');await submitEngine({network:'192.0.2.0/24'});assertUI(state.devices.S.config.controller.inventory.A,'Discovery did not find A');choose('provision');await submitEngine({target:'A',settings:{action:'global',hostname:'ManagedHost'}});assertUI(state.devices.A.config.hostname==='ManagedHost','Provision did not apply');document.querySelector('#ptDeviceEngine>button:last-child').click();return state.devices.A.config.hostname})()""")
                    check('WLC WLAN and AP group forms push real configuration',"""(async()=>{for(const c of ['add-model WLC-3504 WLC','add-model AccessPoint-PT AP','connect WLC eth0 SW fa0/4','connect AP eth0 SW fa0/5','ip WLC eth0 192.0.2.10/24','ip AP eth0 192.0.2.11/24'])await cmd(c);await PacketTrackerDeviceConfig.open('WLC','wlc_wlan');await submitEngine({ssid:'Browser WLAN',security:'wpa2-psk',key:'password1',vlan:1});choose('wlc_group');await submitEngine({name:'Office',aps:['AP'],wlans:['Browser WLAN']});assertUI(state.devices.AP.config.wireless.ssid==='Browser WLAN','WLAN did not reach AP');return state.devices.AP.config.wireless.ssid})()""")
                    check('Command reference explorer and authoritative execution',"""(async()=>{document.querySelector('#ptDeviceEngine>button:last-child').click();document.querySelector('#ptCommandReferenceOpen').click();await waitUI(()=>document.querySelector('#ptCommandReference').open);const d=document.querySelector('#ptCommandReference'),selectors=d.querySelectorAll('select');assertUI(selectors[0].options.length===65,'Missing reference profiles');selectors[0].value='PC1.0';selectors[0].dispatchEvent(new Event('change'));assertUI(d.querySelector('pre').textContent.includes('ipconfig'),'Host vocabulary missing');selectors[1].value='A';d.querySelector('input').value='ipconfig';d.querySelector('form').requestSubmit();await waitUI(()=>!d.querySelector('button[type=submit]').disabled);assertUI(d.querySelector('[role=status]').textContent.includes('192.0.2.1'),'Reference command did not execute');return {profiles:selectors[0].options.length,executed:true}})()""")
                    check('EIGRP configuration through device form',"""(async()=>{document.querySelector('#ptCommandReference button:last-child').click();await PacketTrackerDeviceConfig.open('R','eigrp');await submitEngine({asn:100,network:'192.0.2.0/24',enabled:true});assertUI(state.devices.R.config.eigrp['100'].includes('192.0.2.0/24'),'EIGRP network not saved');return state.devices.R.config.eigrp})()""")
                    check('Modbus and CIP device forms',"""(async()=>{document.querySelector('#ptDeviceEngine>button:last-child').click();await PacketTrackerDeviceConfig.open('S','service');await submitEngine({service:'modbus',enabled:true});choose('cip_identity');await submitEngine({identity:{name:'Browser PLC'}});document.querySelector('#ptDeviceEngine>button:last-child').click();await PacketTrackerDeviceConfig.open('A','modbus_send');await submitEngine({server:'S',data:{sensor:7}});assertUI(state.devices.S.config.industrial.modbus_inbox[0].data.sensor===7,'Modbus payload missing');choose('cip_request');const result=await submitEngine({server:'S',operation:'identity'});assertUI(result.includes('Browser PLC'),'CIP identity missing');return {modbus:true,cip:true}})()""")
                    check('Sample library, translated instructions and undo',"""(async()=>{document.querySelector('#ptDeviceEngine>button:last-child').click();document.querySelector('#menuBar .menu-item').click();const menu=[...document.querySelectorAll('#ptFullMenu button')].find(b=>b.textContent==='Open Samples…');assertUI(menu&&!menu.disabled,'Open Samples missing');menu.click();await waitUI(()=>document.querySelector('#ptSamples').open);const d=document.querySelector('#ptSamples'),locale=d.querySelector('select[aria-label="Sample language"]');locale.value='spa';locale.dispatchEvent(new Event('change'));await waitUI(()=>d.querySelector('#ptSampleSelect option').textContent.includes('Seguir ARP'));const before=Object.keys(state.devices).length;const buttons=[...d.querySelectorAll('button')];buttons.find(b=>b.textContent==='Load sample').click();await waitUI(()=>state.devices.Client&&state.devices.Server);buttons.find(b=>b.textContent==='Check current lab').click();await waitUI(()=>d.querySelector('#ptSampleResult').textContent.includes('Passed'));d.querySelectorAll('button')[2].click();await cmd('undo');assertUI(Object.keys(state.devices).length===before&&state.devices.S,'Undo did not restore network');return {translated:true,check:true,undo:true}})()""")
                    screenshot('device-service-forms')
                    if errors:raise RuntimeError('Browser errors: '+json.dumps(errors))
                    report.append({'browser_exceptions':errors})
                saved=json.loads((temp/'state.json').read_text())
                assert saved['devices']['S']['config']['services']['ftp']['enabled']
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

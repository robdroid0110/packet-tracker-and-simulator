#!/usr/bin/env python3
"""Bounded, isolated enterprise topology and HTTP scalability experiment.

Produces JSON measurements and temporary reproducible native lab fixtures. Fixture
construction calls the model directly to avoid conflating generation with measured
API editing; operations under measurement use normal public model/API paths.
"""
import argparse
import concurrent.futures
import cProfile
import json
import os
from pathlib import Path
import pstats
import resource
import shutil
import statistics
import subprocess
import sys
import tempfile
import time
from urllib.request import Request, urlopen

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
from netsim.model import NetworkLab


def measured(fn):
    wall = time.perf_counter()
    cpu = time.process_time()
    result = fn()
    return result, {'wall_ms': round((time.perf_counter()-wall)*1000, 2),
                    'cpu_ms': round((time.process_time()-cpu)*1000, 2)}


def fixture(access_count):
    lab = NetworkLab()
    lab.load(str(ROOT / 'labs/audit/campus.json'))
    # Core has nine free ports on SW1 and ten on SW2/SW3.
    ports = [(sw, f'fa0/{p}') for sw, start, end in [('SW1',3,11),('SW2',3,12),('SW3',3,12)] for p in range(start,end+1)]
    if access_count > len(ports):
        raise ValueError('too many access switches for this fixture')
    for i in range(access_count):
        name = f'Access{i+1}'
        lab.add_device('switch', name, 100+(i%8)*175, 1000+(i//8)*500)
        core, port = ports[i]
        lab.connect(name, 'g0/1', core, port)
        lab.set_switchport_trunk(core, port, [10,20])
        lab.set_switchport_trunk(name, 'g0/1', [10,20])
        for j in range(10):
            idx = i*10+j
            client = f'Workstation{idx+1}'
            vlan = 10 if idx%2 == 0 else 20
            lab.add_device('pc', client, 100+(i%8)*175+(j%2)*65, 1100+(i//8)*500+(j//2)*65)
            lab.connect(client,'eth0',name,f'fa0/{j+1}')
            lab.set_switchport_access(name,f'fa0/{j+1}',vlan)
            # Deterministic fixture initialization; timed edits use /api/command.
            lab.devices[client].interfaces['eth0'].ip = f'10.10.{vlan}.{110+idx//2}/24'
            lab.devices[client].default_gateway = f'10.10.{vlan}.1'
            lab.devices[client].dns_server = '172.16.3.10'
    lab.recompute_ospf()
    return lab


def request(url, endpoint, body=None):
    start = time.perf_counter()
    req = Request(url+endpoint, data=json.dumps(body).encode() if body is not None else None,
                  headers={'Content-Type':'application/json'})
    with urlopen(req, timeout=90) as response:
        raw = response.read()
        result = json.loads(raw)
    return {'ms':round((time.perf_counter()-start)*1000,2),'bytes':len(raw),'result':result}


def stats(values):
    return {'samples':len(values),'median_ms':round(statistics.median(values),2),
            'min_ms':round(min(values),2),'max_ms':round(max(values),2)}


def worker(access_count, folder):
    folder = Path(folder)
    progress = folder/'progress.json'
    result = {'access_switches':access_count, 'status':'running','stages':{}}
    def stage(name, data):
        result['stages'][name] = data
        progress.write_text(json.dumps(result, indent=2))
    lab, timing = measured(lambda:fixture(access_count))
    stage('construct_fixture', timing)
    result['devices'], result['links'] = len(lab.devices), len(lab.links)
    path = folder/'fixture.json'
    _, timing = measured(lambda:lab.save(str(path)))
    timing['bytes'] = path.stat().st_size
    stage('save', timing)
    loaded, timing = measured(lambda: _load(path))
    stage('load', timing)
    profile=cProfile.Profile()
    def profile_ping():
        profile.enable()
        try: return loaded.ping('PC1','172.16.3.20')
        finally: profile.disable()
    ping, timing = measured(profile_ping)
    timing['success'], timing['output'] = ping
    rows=[]
    for (filename,line,func), vals in pstats.Stats(profile).stats.items():
        cc,nc,tt,ct,callers=vals
        rows.append({'function':f'{Path(filename).name}:{line}:{func}','calls':nc,
                     'self_ms':round(tt*1000,2),'cumulative_ms':round(ct*1000,2)})
    timing['profile_by_self']=sorted(rows,key=lambda x:x['self_ms'],reverse=True)[:12]
    stage('profile_ping', timing)
    if access_count:
        value,timing=measured(lambda:loaded.ping('Workstation1','10.10.20.110'))
        timing['success'],timing['output']=value
        stage('cross_vlan_ping',timing)
    state = folder/'server-state.json'
    shutil.copyfile(path, state)
    ready = folder/'ready.json'
    server = subprocess.Popen([sys.executable,str(ROOT/'desktop.py'),'--server','--port','0',
                               '--state',str(state),'--ready-file',str(ready)],cwd=ROOT,
                              stdout=subprocess.DEVNULL,stderr=subprocess.DEVNULL)
    try:
        start=time.perf_counter()
        for _ in range(1200):
            if ready.exists(): break
            if server.poll() is not None: raise RuntimeError('isolated server exited')
            time.sleep(.05)
        url='http://127.0.0.1:'+str(json.loads(ready.read_text())['port'])
        stage('server_start',{'wall_ms':round((time.perf_counter()-start)*1000,2),'pid':server.pid})
        import psutil
        proc=psutil.Process(server.pid)
        state_results=[request(url,'/api/state') for _ in range(5)]
        stage('api_state',{**stats([r['ms'] for r in state_results]),'bytes':state_results[-1]['bytes'],
                            'server_rss_mib':round(proc.memory_info().rss/1048576,2)})
        commands=[]
        for i in range(8):
            q=request(url,'/api/command',{'command':f'move PC1 {100+i} 100'})
            commands.append(q['ms'])
            if not q['result'].get('ok'): raise AssertionError(q['result'].get('output'))
        stage('api_edit_8',{**stats(commands),'server_rss_mib':round(proc.memory_info().rss/1048576,2)})
        query=request(url,'/api/command',{'command':'ping PC1 172.16.3.20'})
        stage('api_ping',{'ms':query['ms'],'bytes':query['bytes'],
                          'success':'PING success' in query['result'].get('output','')})
        start=time.perf_counter()
        with concurrent.futures.ThreadPoolExecutor(max_workers=4) as pool:
            responses=list(pool.map(lambda _:request(url,'/api/state'),range(8)))
        stage('api_state_concurrent_4', {**stats([r['ms'] for r in responses]),
              'total_wall_ms':round((time.perf_counter()-start)*1000,2),
              'server_rss_mib':round(proc.memory_info().rss/1048576,2)})
        result['status']='completed'
    finally:
        server.terminate()
        try: server.wait(timeout=10)
        except subprocess.TimeoutExpired:server.kill();server.wait()
        stage('process',{'worker_peak_rss_mib':round(resource.getrusage(resource.RUSAGE_SELF).ru_maxrss/1024,2)})
    progress.write_text(json.dumps(result,indent=2))
    return result


def _load(path):
    lab=NetworkLab()
    lab.load(str(path))
    return lab


def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--worker',type=int)
    parser.add_argument('--folder',type=Path)
    parser.add_argument('--output',type=Path,default=ROOT/'research/performance/scale.json')
    parser.add_argument('--sizes',type=int,nargs='+',default=[0,3,9,18,28])
    parser.add_argument('--timeout',type=int,default=150)
    parser.add_argument('--memory-limit-mib',type=int,default=1400)
    parser.add_argument('--fixtures',type=Path,default=Path('/tmp/packet-tracker-scale-fixtures'))
    args=parser.parse_args()
    if args.worker is not None:
        worker(args.worker,args.folder)
        return
    import psutil
    args.fixtures.mkdir(parents=True,exist_ok=True)
    report={'method':'single warm run per size, local loopback, 5 GETs and 8 edits; timeout and memory capped',
            'timeout_seconds':args.timeout,'memory_limit_mib':args.memory_limit_mib,'runs':[]}
    for size in args.sizes:
        folder=Path(tempfile.mkdtemp(prefix=f'pt-scale-{size}-'))
        log=folder/'worker.log'
        print(f'Running {size} access switches',flush=True)
        with log.open('w') as out:
            process=subprocess.Popen([sys.executable,str(Path(__file__).resolve()),'--worker',str(size),'--folder',str(folder)],
                                     cwd=ROOT,stdout=out,stderr=out,start_new_session=True)
            p=psutil.Process(process.pid);start=time.monotonic();peak=0;reason=None
            while process.poll() is None:
                try:
                    family=[p]+p.children(recursive=True)
                    rss=sum(x.memory_info().rss for x in family if x.is_running())
                    peak=max(peak,rss)
                    if rss>args.memory_limit_mib*1048576:reason='memory cap';break
                except (psutil.NoSuchProcess,psutil.AccessDenied):pass
                if time.monotonic()-start>args.timeout:reason='timeout';break
                time.sleep(.2)
            if reason:
                # This process group contains only the isolated benchmark worker and server.
                import signal
                os.killpg(process.pid,signal.SIGTERM)
                try:process.wait(timeout=5)
                except subprocess.TimeoutExpired:os.killpg(process.pid,signal.SIGKILL);process.wait()
            else:process.wait()
        progress=folder/'progress.json'
        entry=json.loads(progress.read_text()) if progress.exists() else {'access_switches':size,'stages':{}}
        if reason:entry['status']='terminated: '+reason
        entry.update({'termination':reason,'exit_code':process.returncode,'peak_family_rss_mib':round(peak/1048576,2),
                      'elapsed_s':round(time.monotonic()-start,2)})
        if process.returncode and not reason:entry['worker_log']=log.read_text()[-5000:]
        if (folder/'fixture.json').exists():shutil.copyfile(folder/'fixture.json',args.fixtures/f'{size}.json')
        shutil.rmtree(folder)
        report['runs'].append(entry)
        args.output.parent.mkdir(parents=True,exist_ok=True)
        args.output.write_text(json.dumps(report,indent=2))
        print(json.dumps({'size':size,'devices':entry.get('devices'),'status':entry['status'] if 'status' in entry else 'failed',
                          'termination':reason,'exit_code':process.returncode,'elapsed_s':entry['elapsed_s']}),flush=True)

if __name__=='__main__':
    main()

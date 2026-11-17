#!/usr/bin/env python3
"""Measure an agent batch, memory and a competing read on an isolated server."""
import argparse
import concurrent.futures
import json
from pathlib import Path
import shutil
import subprocess
import sys
import tempfile
import time
from urllib.request import Request,urlopen
import psutil
ROOT=Path(__file__).resolve().parents[1]

def req(url,path,body=None):
    start=time.perf_counter();request=Request(url+path,data=json.dumps(body).encode() if body is not None else None,headers={'content-type':'application/json'})
    with urlopen(request,timeout=120) as response:raw=response.read()
    return json.loads(raw),round((time.perf_counter()-start)*1000,2),len(raw)

def run(source,count):
    with tempfile.TemporaryDirectory(prefix='pt-agent-batch-') as temp:
        initial_devices=len(json.loads(source.read_text())['devices'])
        folder=Path(temp);state=folder/'lab.json';shutil.copyfile(source,state);ready=folder/'ready'
        process=subprocess.Popen([sys.executable,str(ROOT/'desktop.py'),'--server','--port','0','--state',str(state),'--ready-file',str(ready)],cwd=ROOT,stdout=subprocess.DEVNULL,stderr=subprocess.DEVNULL)
        try:
            for _ in range(600):
                if ready.exists():break
                if process.poll() is not None:raise RuntimeError('server exited')
                time.sleep(.05)
            url='http://127.0.0.1:'+str(json.loads(ready.read_text())['port']);proc=psutil.Process(process.pid)
            before=proc.memory_info().rss;cpu0=proc.cpu_times();commands=[f'add pc BatchHost{i}' for i in range(1,count+1)]
            with concurrent.futures.ThreadPoolExecutor(max_workers=2) as pool:
                future=pool.submit(req,url,'/api/batch',{'commands':commands});time.sleep(.1)
                competing=pool.submit(req,url,'/api/state')
                batch=future.result();read=competing.result()
            cpu1=proc.cpu_times();after=proc.memory_info().rss
            return {'initial_devices':initial_devices,
                    'commands':count,'batch_ok':batch[0].get('ok'),'executed':batch[0].get('executed'),
                    'batch_wall_ms':batch[1],'response_bytes':batch[2],
                    'competing_get_ms':read[1],'competing_read_devices':len(read[0]['devices']),
                    'server_cpu_ms':round(((cpu1.user+cpu1.system)-(cpu0.user+cpu0.system))*1000,2),
                    'server_rss_before_mib':round(before/1048576,2),'server_rss_after_mib':round(after/1048576,2)}
        finally:
            process.terminate();process.wait(timeout=10)

if __name__=='__main__':
    parser=argparse.ArgumentParser();parser.add_argument('--fixtures',type=Path,default=Path('/tmp/packet-tracker-scale-fixtures'));parser.add_argument('--sizes',type=int,nargs='+',default=[0,9]);parser.add_argument('--count',type=int,default=40);parser.add_argument('--output',type=Path,default=ROOT/'research/performance/batch.json');args=parser.parse_args()
    report=[]
    for size in args.sizes:
        result=run(args.fixtures/f'{size}.json',args.count);result['access_switches']=size;report.append(result);print(json.dumps(result),flush=True)
    args.output.write_text(json.dumps(report,indent=2))

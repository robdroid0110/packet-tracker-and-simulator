#!/usr/bin/env python3
"""Measure discrete-event simulation on isolated fixtures, not line-rate throughput."""
import argparse
import json
from pathlib import Path
import sys
import time
sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
from netsim.model import NetworkLab
from netsim.simulation import action


def run(path):
    lab=NetworkLab();lab.load(str(path));t=time.perf_counter()
    action(lab,{'action':'mode','mode':'simulation'})
    ident=action(lab,{'action':'pdu_add','source':'PC1','destination':'WEB'})
    setup=time.perf_counter()-t;steps=0;times=[];protocols=[]
    while steps<100:
        start=time.perf_counter();event=action(lab,{'action':'step'});elapsed=time.perf_counter()-start
        if not event:break
        steps+=1;times.append(round(elapsed*1000,2));protocols.append(event.get('protocol'))
    pdu=lab.simulation['pdus'][ident]
    return {'devices':len(lab.devices),'links':len(lab.links),'setup_ms':round(setup*1000,2),
            'events':steps,'step_ms':times,'protocols':protocols,'wall_s':round(sum(times)/1000,3),
            'simulated_master_time_s':lab.simulation['master_time'],'pdu_status':pdu['status'],
            'limit_reached':steps==100}

if __name__=='__main__':
    p=argparse.ArgumentParser();p.add_argument('--fixtures',type=Path,default=Path('/tmp/packet-tracker-scale-fixtures'))
    p.add_argument('--sizes',type=int,nargs='+',default=[0,3,9]);p.add_argument('--output',type=Path,default=Path('research/performance/simulation.json'));args=p.parse_args()
    result=[]
    for size in args.sizes:
        value=run(args.fixtures/f'{size}.json');result.append(value);args.output.write_text(json.dumps(result,indent=2));print(json.dumps(value),flush=True)

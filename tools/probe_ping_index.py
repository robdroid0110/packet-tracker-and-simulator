#!/usr/bin/env python3
"""Operation-scoped lookup/STP proof of concept; no Packet Tracker and Simulator code is changed.

Caches are safe ONLY for this single read-only-topology ping in an isolated lab.
This does not implement invalidation, concurrency control, or production caching.
"""
import argparse
from contextlib import nullcontext
import json
from pathlib import Path
import statistics
import sys
import time
from unittest.mock import patch
sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
from netsim.model import NetworkLab


def run(path, variant, source='PC1', target='172.16.3.20'):
    lab=NetworkLab();lab.load(str(path))
    if variant in ('index','both'):
        index={}
        for link in lab.links:
            for endpoint in link.endpoints():index.setdefault(endpoint,link)
        def fast_link_for(device,interface):return index.get(lab._physical_endpoint(device,interface))
        lab.link_for=fast_link_for
    if variant in ('stp','both'):
        stp={};original=lab.spanning_tree
        def cached_stp(vlan=1):
            if vlan not in stp:stp[vlan]=original(vlan)
            return stp[vlan]
        lab.spanning_tree=cached_stp
    start=time.perf_counter();cpu=time.process_time()
    # Measure this historical experiment without the production scope; the
    # four variants would otherwise all use the production optimization.
    with patch.object(NetworkLab, '_forwarding_scope', lambda self: nullcontext()):
        outcome=lab.ping(source,target)
    wall_ms=(time.perf_counter()-start)*1000;cpu_ms=(time.process_time()-cpu)*1000
    # Equality checks include reachable path and relevant forwarding side effects.
    side_effects={n:{'arp':d.arp_table,'mac':d.mac_table,'nat':d.nat_sessions} for n,d in lab.devices.items()}
    return round(wall_ms,2),round(cpu_ms,2),outcome,side_effects


def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--fixtures',type=Path,default=Path('/tmp/packet-tracker-scale-fixtures'))
    parser.add_argument('--output',type=Path,default=Path('research/performance/ping_poc.json'))
    parser.add_argument('--sizes',type=int,nargs='+',default=[0,3,9,18])
    parser.add_argument('--repeat',type=int,default=2)
    args=parser.parse_args();results=[]
    for size in args.sizes:
        path=args.fixtures/f'{size}.json'
        if not path.exists():results.append({'size':size,'status':'fixture unavailable'});continue
        row={'size':size,'devices':16+size*11,'variants':{},'status':'running'};baseline=None
        for variant in ('baseline','index','stp','both'):
            walls=[];cpus=[];equal=True
            for _ in range(args.repeat):
                wall,cpu,outcome,side_effects=run(path,variant)
                if baseline is None:baseline=(outcome,side_effects)
                else:equal=equal and (outcome,side_effects)==baseline
                walls.append(wall);cpus.append(cpu)
            row['variants'][variant]={'wall_ms':walls,'cpu_ms':cpus,'median_ms':round(statistics.median(walls),2),'same_outcome_and_tables':equal}
            if not equal:raise AssertionError(f'behavior changed in {size}: {variant}')
            print(json.dumps({'size':size,'variant':variant,'median_ms':statistics.median(walls)}),flush=True)
        row['status']='completed';results.append(row)
        args.output.parent.mkdir(parents=True,exist_ok=True);args.output.write_text(json.dumps({'limitations':'One stable topology per ping; cache is discarded immediately and must never be used across edits.','results':results},indent=2))

if __name__=='__main__':main()

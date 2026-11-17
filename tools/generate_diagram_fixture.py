#!/usr/bin/env python3
"""Generate an isolated chain/grid lab; print its temporary JSON path."""
import argparse
import sys
import tempfile
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from netsim.model import NetworkLab

parser = argparse.ArgumentParser(description=__doc__)
parser.add_argument('--count', type=int, default=200)
parser.add_argument('--grid', action='store_true')
args = parser.parse_args()
if not 1 <= args.count <= 1000: parser.error('count must be 1..1000')
lab = NetworkLab()
for i in range(args.count): lab.add_device('switch', 'S'+str(i), 80+i%20*150, 60+i//20*140)
for i in range(1,args.count): lab.connect('S'+str(i-1), 'fa0/2', 'S'+str(i), 'fa0/1')
if args.grid:
    for i in range(20,args.count): lab.connect('S'+str(i-20), 'fa0/4', 'S'+str(i), 'fa0/3')
output = Path(tempfile.mkdtemp(prefix='pt-diagram-fixture-'))/'lab.json'
lab.save(str(output)); print(output)

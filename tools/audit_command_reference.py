#!/usr/bin/env python3
'''Validate the independently distributed command index without external software.'''
import json
from pathlib import Path
p=Path(__file__).resolve().parents[1]/'netsim/data/command_reference.json'
data=json.loads(p.read_text())
modes=data['mode_records']
for entry in data['profiles']:
 assert entry['url'] is None
 assert all(isinstance(i,int) and 0<=i<len(modes) for i in entry['mode_refs'])
print('Validated',len(data['profiles']),'profiles')

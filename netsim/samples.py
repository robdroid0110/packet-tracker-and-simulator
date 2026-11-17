"""Original, reproducible learning examples. Loading is one undoable edit."""
from copy import deepcopy
from .model import NetworkLab,LabError

SAMPLES={
 'concept-arp':{'category':'concept','title':'Trace ARP and ICMP','instructions':'Enter Simulation Mode. Send a simple PDU from Client to Server and step through ARP and ICMP events. Inspect how the switch learns MAC addresses.','commands':['add pc Client 120 180','add switch SW1 350 180','add server Server 590 180','connect Client eth0 SW1 fa0/1','connect Server eth0 SW1 fa0/2','ip Client eth0 192.0.2.1/24','ip Server eth0 192.0.2.2/24'], 'checks':[{'source':'Client','target':'192.0.2.2','expect':True}]},
 'skill-dhcp':{'category':'skill','title':'Configure a DHCP client','instructions':'Configure the client to obtain an address from R1 using DHCP. Check the lease and test reachability to 192.168.50.1.','commands':['add pc Client 120 180','add switch SW1 350 180','add router R1 590 180','connect Client eth0 SW1 fa0/1','connect R1 g0/0 SW1 fa0/2','ip R1 g0/0 192.168.50.1/24','dhcp-pool R1 LAN 192.168.50.0/24 192.168.50.1 192.168.50.100 192.168.50.120'], 'checks':[{'source':'Client','target':'192.168.50.1','expect':True}]},
 'design-addressing':{'category':'design','title':'Design a routed addressing plan','instructions':'Choose two non-overlapping IPv4 subnets. Configure R1 and both hosts, including host default gateways, then verify bidirectional connectivity. Multiple valid addressing plans are accepted.','commands':['add pc HostA 120 100','add router R1 350 180','add pc HostB 590 260','connect HostA eth0 R1 g0/0','connect HostB eth0 R1 g0/1'], 'checks':[{'source':'HostA','target_device':'HostB','expect':True},{'source':'HostB','target_device':'HostA','expect':True}]},
 'troubleshoot-link':{'category':'troubleshooting','title':'Restore a disabled link','instructions':'Client cannot reach Server. Inspect the topology and interface state, identify the fault, repair it and verify connectivity.','commands':['add pc Client 120 180','add switch SW1 350 180','add server Server 590 180','connect Client eth0 SW1 fa0/1','connect Server eth0 SW1 fa0/2','ip Client eth0 198.51.100.1/24','ip Server eth0 198.51.100.2/24','down SW1 fa0/2'], 'checks':[{'source':'Client','target':'198.51.100.2','expect':True}]},
}


def translation_template():
 return {'id':'xxx','name':'Language name','translations':{key:{'title':item['title'],'instructions':item['instructions']} for key,item in SAMPLES.items()}}

def validate_translation(pack):
 import re
 from collections import Counter
 if not isinstance(pack,dict) or set(pack)!={'id','name','translations'} or not isinstance(pack['id'],str) or not re.fullmatch('[a-z]{3}',pack['id']) or pack['id']=='eng':raise LabError('translation id must be a three-letter code other than eng')
 if not isinstance(pack['name'],str) or not pack['name'].strip() or len(pack['name'])>80:raise LabError('invalid language name')
 translations=pack['translations']
 if not isinstance(translations,dict) or set(translations)!=set(SAMPLES):raise LabError('translation must include each sample exactly once')
 for key,entry in translations.items():
  if not isinstance(entry,dict) or set(entry)!={'title','instructions'}:raise LabError('translation needs title and instructions')
  for field in ('title','instructions'):
   value=entry[field]
   if not isinstance(value,str) or not value.strip() or len(value)>4000:raise LabError('invalid translation '+field)
   pattern=r'%[1-9][0-9]*|%n|\[\[[A-Z_0-9]+\]\]|\{[a-zA-Z_][a-zA-Z_0-9]*\}'
   if Counter(re.findall(pattern,value))!=Counter(re.findall(pattern,SAMPLES[key][field])):raise LabError('translation must preserve placeholders')
 return deepcopy(pack)

def available_languages():
 import json
 from pathlib import Path
 packs={}
 for path in sorted((Path(__file__).parent/'data'/'sample_languages').glob('*.json')):
  pack=validate_translation(json.loads(path.read_text(encoding='utf-8')))
  if path.stem!=pack['id'] or pack['id'] in packs:raise LabError('translation filename/id mismatch')
  packs[pack['id']]=pack
 return packs

def catalog(language='eng'):
 packs=available_languages()
 if language!='eng' and language not in packs:raise LabError('unknown sample language')
 samples=[]
 for ident,data in SAMPLES.items():
  translation=packs[language]['translations'][ident] if language!='eng' else data
  samples.append({'id':ident,'category':data['category'],'title':translation['title'],'instructions':translation['instructions'],'checks':deepcopy(data['checks'])})
 return {'ok':True,'language':language,'languages':[{'id':'eng','name':'English'}]+[{'id':p['id'],'name':p['name']} for p in packs.values()],'samples':samples,'format':'Native Packet Tracker and Simulator JSON examples; vendor PKT import is partial (see File import); PKA/PKZ are unsupported'}

def load(lab,ident):
 if ident not in SAMPLES:raise LabError('unknown sample')
 from .cli import CommandProcessor
 candidate=NetworkLab();processor=CommandProcessor(candidate)
 for line in SAMPLES[ident]['commands']:
  result=processor.execute(line)
  if result.startswith('ERROR:'):raise LabError('sample failed: '+result)
 lab.__dict__.clear();lab.__dict__.update(candidate.__dict__)
 return 'Loaded sample '+ident+'. Use Undo to restore the previous lab.'

def check(lab,ident):
 if ident not in SAMPLES:raise LabError('unknown sample')
 candidate=deepcopy(lab);candidate.simulation['mode']='realtime';results=[]
 for item in SAMPLES[ident]['checks']:
  target=item.get('target')
  try:
   if 'target_device' in item:
    d=candidate._device(item['target_device']);target=next((str(i.ipv4.ip) for i in d.interfaces.values() if i.ip),None)
   if not target:raise LabError('destination needs an IPv4 address')
   ok,detail=candidate.ping(item['source'],target)
  except (LabError,ValueError) as exc:ok=False;detail=str(exc)
  results.append({'source':item['source'],'target':target,'passed':ok==item['expect'],'detail':detail})
 if ident=='design-addressing':
  try:
   a=candidate._device('HostA');b=candidate._device('HostB');router=candidate._device('R1')
   left=next(i.ipv4 for i in a.interfaces.values() if i.ip);right=next(i.ipv4 for i in b.interfaces.values() if i.ip)
   interfaces=[i.ipv4 for i in router.interfaces.values() if i.ip]
   passed=not left.network.overlaps(right.network) and any(x.network==left.network and str(x.ip)==a.default_gateway for x in interfaces) and any(x.network==right.network and str(x.ip)==b.default_gateway for x in interfaces)
   detail='Two distinct subnets and matching R1 gateways' if passed else 'Use two non-overlapping subnets and R1 as both host gateways'
  except (LabError,StopIteration,ValueError):passed=False;detail='Configure both hosts, R1 interfaces and gateways'
  results.append({'source':'Addressing','target':'R1 gateways','passed':passed,'detail':detail})
 return {'sample':ident,'passed':all(r['passed'] for r in results),'checks':results,'note':'Connectivity checks are guidance; design solutions may vary.'}

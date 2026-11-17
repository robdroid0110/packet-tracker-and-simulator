"""Authoritative deterministic scenario scheduler and event inspection (§§33–40).

Scheduled traffic is evaluated against the current lab at dispatch. Planning
uses an isolated lab; learned state is published at capture time, never queue
creation. Back is an inspection cursor, not a rollback of network history.
"""
from __future__ import annotations
from copy import deepcopy
from ipaddress import IPv4Address
import math,re,time,uuid
from .model import LabError

APPLICATIONS={'ICMP':('icmp',0),'TCP':('tcp',0),'UDP':('udp',0),'DNS':('udp',53),
 'HTTP':('tcp',80),'HTTPS':('tcp',443),'FTP':('tcp',21),'SFTP':('tcp',22),
 'SSH':('tcp',22),'TELNET':('tcp',23),'SMTP':('tcp',25),'POP3':('tcp',110),
 'IMAP':('tcp',143),'TFTP':('udp',69),'SNMP':('udp',161),'FINGER':('tcp',79),
 'NETBIOS':('udp',137),'OTHER':('udp',0)}
COLORS={'ARP':'#ffcc00','ICMP':'#17a2b8','TCP':'#407bff','UDP':'#e77817','DNS':'#8855cc','HTTP':'#1b9956','HTTPS':'#285fa0','STP':'#ce4987','OSPF':'#e5aa28','DHCP':'#259e93'}
PROTOCOLS=set(APPLICATIONS)|set(COLORS)|{'RADIUS','TACACS','NTP','PTP','SYSLOG','CAPWAP','CIP','RIP','MODBUS','ICMPv6','DHCPv6'}
MAX_EVENTS=2000

def defaults():
 return {'mode':'realtime','master_time':0.0,'time':0.0,'cursor':0,'playing':False,
 'constant_delay':True,'speed':55,'filters':sorted(PROTOCOLS),'active':'scenario0',
 'scenarios':{'scenario0':{'name':'Scenario 0','description':''}},'pdus':{},'events':[],
 'pending':[],'last_event':None}

def finite(value,low,high):
 if isinstance(value,bool) or not isinstance(value,(int,float)) or not math.isfinite(value) or not low<=value<=high:raise LabError(f'value must be finite in {low}..{high}')
 return float(value)

def integer(value,low,high):
 finite(value,low,high)
 if int(value)!=value:raise LabError('integer required')
 return int(value)

def label(value,maxlen=120):
 if not isinstance(value,str) or not value.strip() or len(value)>maxlen or any(ord(c)<32 for c in value):raise LabError('nonempty printable text required')
 return value

def validate_pdu(lab,body,old=None):
 p={**(old or {}),**body};source=label(p.get('source'),31);lab._device(source)
 destination=p.get('destination','');address=p.get('destination_ip','')
 if destination:
  lab._device(destination)
  if not address:address=next((str(i.ipv4.ip) for i in lab.devices[destination].interfaces.values() if i.ip),'')
 if not address:raise LabError('destination must have an IP address, or supply destination_ip')
 address=str(IPv4Address(address))
 source_ip=p.get('source_ip','')
 if source_ip:
  source_ip=str(IPv4Address(source_ip))
  if not any(i.ip and str(i.ipv4.ip)==source_ip for i in lab.devices[source].interfaces.values()):raise LabError('source IP is not assigned to source device')
 protocol=p.get('protocol','ICMP').upper()
 if protocol not in APPLICATIONS:raise LabError('unsupported PDU application')
 color=p.get('color',COLORS.get(protocol,'#7755aa'))
 if not isinstance(color,str) or not re.fullmatch('#[0-9a-fA-F]{6}',color):raise LabError('color must be #RRGGBB')
 scenario=p.get('scenario',lab.simulation['active'])
 if scenario not in lab.simulation['scenarios']:raise LabError('unknown scenario')
 interface=p.get('interface','')
 if interface:lab._iface(source,interface)
 if not isinstance(p.get('url',''),str) or len(p.get('url',''))>2048:raise LabError('PDU URL must be at most 2048 characters')
 return {'source':source,'destination':destination,'destination_ip':address,'source_ip':source_ip,
 'protocol':protocol,'interface':interface,'ttl':integer(p.get('ttl',32),1,255),
 'tos':integer(p.get('tos',0),0,255),'size':integer(p.get('size',100),28,65535),
 'source_port':integer(p.get('source_port',1025),0,65535),
 'destination_port':integer(p.get('destination_port',APPLICATIONS[protocol][1]),0,65535),
 'sequence':integer(p.get('sequence',1),0,4294967295),
 'start':finite(p.get('start',p.get('time',0)),0,86400),
 'interval':finite(p.get('interval',0),0,86400),'color':color.lower(),'scenario':scenario,
 'url':p.get('url',''),'status':'Not sent','result':None,'next_due':None,'runs':0}

def reset(lab):
 s=lab.simulation;s.update(time=0.0,cursor=0,events=[],pending=[],playing=False,last_event=None)
 s['pdus']={key:p for key,p in s['pdus'].items() if p.get('user_created',True)}
 for p in s['pdus'].values():p.update(status='Not sent',result=None,next_due=p['start'] if p['scenario']==s['active'] else None,runs=0)

def _expanded_path(lab,path):
 """Include actual traversed switch ports between routed nodes."""
 result=[]
 for index,name in enumerate(path):
  if name not in lab.devices:continue
  if not result or result[-1]!=name:result.append(name)
  if index+1>=len(path) or path[index+1] not in lab.devices:continue
  other=path[index+1]
  found=None
  for a in lab.devices[name].interfaces.values():
   if not a.ip:continue
   for b in lab.devices[other].interfaces.values():
    if b.ip and b.ipv4.ip in a.ipv4.network:
     found=lab.l2_path((name,a.name),(other,b.name))
     if found:break
   if found:break
  for node,_ in found or []:
   if result[-1]!=node:result.append(node)
 return result

def plan(lab,p):
 candidate=deepcopy(lab);candidate.simulation['mode']='realtime'
 if p.get('task'):
  task=p['task'];payload=task['payload'];before=candidate.packet_counter
  try:
   if task['operation']=='http':output=candidate.http_request(payload['source'],payload['url'])
   elif task['operation']=='ping':
    verification=candidate.ping_detailed(payload['source'],payload['destination_ip'])
    output={'ok':verification['reachable'],'message':verification['message'],'verification':verification}
   else:
    from .device_config import action as configure
    output=configure(candidate,payload)
   result={'ok':output.get('ok',True) if isinstance(output,dict) else True,'output':output}
  except LabError as exc:result={'ok':False,'message':str(exc)}
  result['status']='Successful' if result['ok'] else 'Failed'
  messages=[(e['protocol'],e['source'],e['destination'],e['detail'],e['ok']) for e in candidate.packet_events if e['seq']>before]
  if not messages:messages=[(p['protocol'],p['source'],p.get('destination') or p['source'],str(result.get('message','Operation completed')),result['ok'])]
  result['_device_updates']={name:candidate._device_to_dict(d) for name,d in candidate.devices.items() if name in lab.devices and vars(d)!=vars(lab.devices[name])}
  return messages,result,{}

 source=p['source'];address=p['destination_ip'];protocol=p['protocol'];transport=APPLICATIONS[protocol][0]
 # The candidate is an isolated copy. Share lookups only while its topology is
 # unchanged; application/device actions below run outside this read scope.
 with candidate._forwarding_scope():
  origin=p['source_ip'] or candidate._source_ip_for_destination(source,address)
  if p['interface']:
   interface=candidate._iface(source,p['interface'])
   if not interface.ip or not candidate._iface_effective_up(source,p['interface']):raise LabError('selected source interface is not operational with an IP address')
   origin=str(interface.ipv4.ip)
  if not origin:ok,go,back=False,[source,'no-route'],[]
  else:
   # The forwarding engine enforces router ACLs/NAT and loop detection.
   meta={'translated_source':origin,'final_destination':address,'ttl':p['ttl'],'source_port':p['source_port'],'destination_port':p['destination_port']}
   ok,go=candidate._forward(source,address,set(),[],origin,transport,None,meta)
   receiver=meta.get('final_owner') or (candidate.owner_of_ip(address) or ('',''))[0]
   back=[]
   if ok:
    ok_back,back=candidate._forward(receiver,meta.get('translated_source',origin),set(),[],meta.get('final_destination',address),transport,None,{'source_port':meta.get('destination_port'),'destination_port':meta.get('source_port')})
    ok=ok and ok_back
  go=_expanded_path(candidate,go);back=_expanded_path(candidate,back)
 messages=[]
 if origin and not lab.devices[source].arp_table.get(address) and go:
  messages.append(('ARP',source,go[1] if len(go)>1 else source,'ARP resolution',True))
 def hops(path,detail,success):
  for a,b in zip(path,path[1:]):messages.append((protocol,a,b,detail,success))
  if len(path)==1:messages.append((protocol,path[0],path[0],detail,success))
 hops(go,'Echo Request' if protocol=='ICMP' else ('SYN' if transport=='tcp' else 'Datagram'),ok)
 if ok:hops(back,'Echo Reply' if protocol=='ICMP' else ('SYN ACK' if transport=='tcp' else 'Response path'),True)
 result={'ok':ok,'status':'Successful' if ok else 'Failed','message':'Delivered' if ok else 'Unreachable or denied','forward':go,'reply':back}
 # Application requests use actual service engines; transport delivery alone is
 # explicitly distinguished until a service implementation handles the port.
 if protocol=='HTTP' and ok:
  try:result.update(candidate.http_request(source,p['url'] or 'http://'+address+'/'))
  except LabError as exc:result.update(ok=False,status='Failed',message=str(exc))
 elif protocol not in ('ICMP','TCP','UDP','OTHER'):
  try:
   from .device_services import pdu_service
   result.update(pdu_service(candidate,{**p,'destination_ip':meta.get('final_destination',address) if origin else address},ok))
  except ImportError:result['application_status']='transport-only'
 if not messages:messages=[(protocol,source,p.get('destination') or source,result['message'],False)]
 dynamics={name:{field:deepcopy(getattr(d,field)) for field in ('arp_table','mac_table','nat_sessions')} for name,d in candidate.devices.items() if name in go or name in back}
 return messages,result,dynamics

def dispatch(lab,ident):
 s=lab.simulation;p=s['pdus'][ident];p['status']='In Progress';p['runs']+=1
 try:messages,result,dynamics=plan(lab,p)
 except (LabError,ValueError) as exc:messages=[(p['protocol'],p['source'],p.get('destination') or p['source'],str(exc),False)];result={'ok':False,'status':'Failed','message':str(exc)};dynamics={}
 for index,(protocol,source,dest,detail,ok) in enumerate(messages):
  reply=any(word in detail.lower() for word in ('reply','syn ack','response'))
  task=p.get('task',{}).get('payload',{});ipv6=':' in task.get('destination_ip','')
  source_address=p['source_ip'] or lab._source_ip_for_destination(p['source'],p['destination_ip'])
  target_address=p['destination_ip']
  if ipv6:
   source_address=next((i.ipv6.split('/')[0] for i in lab.devices[p['source']].interfaces.values() if i.ipv6),None);target_address=task['destination_ip']
  headers={'ethernet':{'model':'derived from forwarding path'},'direction':'reply' if reply else 'request'}
  if protocol=='ARP':
   headers['arp']={'operation':'request','sender_ip':source_address,'target_ip':target_address}
   headers['ethernet']['ether_type']='0x0806'
  else:
   headers['ipv6' if ipv6 else 'ipv4']={'source':target_address if reply else source_address,'destination':source_address if reply else target_address,('hop_limit' if ipv6 else 'ttl'):p['ttl'],'tos':p['tos'],'length':p['size']}
   headers['transport']={'protocol':'icmpv6' if ipv6 else APPLICATIONS[p['protocol']][0],'source_port':p['destination_port'] if reply else p['source_port'],'destination_port':p['source_port'] if reply else p['destination_port'],'sequence':p['sequence']}
  s['pending'].append({'pdu':ident,'protocol':protocol,'source':source,'destination':dest,'detail':detail,'ok':ok,
   'headers':headers,
   'color':p['color'],'qos':p['tos']>>2,'final':index==len(messages)-1,
   'result':result if index==len(messages)-1 else None,
   'dynamics':{n:dynamics[n] for n in {source,dest} if n in dynamics}})
 p['next_due']=round(s['time']+p['interval'],6) if p['interval'] else None


def step(lab):
 s=lab.simulation
 # A previous Back action only changes the inspection cursor.
 if s['cursor']<len(s['events']):s['cursor']+=1;s['last_event']=s['events'][s['cursor']-1];return s['last_event']
 if not s['pending']:
  due=[(p['next_due'],key) for key,p in s['pdus'].items() if p['scenario']==s['active'] and p['next_due'] is not None]
  if not due:s['playing']=False;return None
  at,ident=min(due);delta=max(0,at-s['time']);s['time']+=delta;s['master_time']+=delta;dispatch(lab,ident)
 event=s['pending'].pop(0);p=s['pdus'].get(event['pdu'])
 delay=.001 if s['constant_delay'] else max(.000001,(p['size'] if p else 100)*8/100000000+.0001)
 s['time']=round(s['time']+delay,6);s['master_time']=round(s['master_time']+delay,6)
 for name,tables in event.pop('dynamics',{}).items():
  if name in lab.devices:
   for field,value in tables.items():setattr(lab.devices[name],field,value)
 result=event.pop('result');final=event.pop('final')
 lab._packet_event(event['protocol'],event['source'],event['destination'],event['detail'],event['ok'],capture=False)
 arp=event['protocol']=='ARP';ipv6='ipv6' in event['headers']
 event.update(seq=lab.packet_counter,time=s['time'],master_time=s['master_time'],osi={
  '1':'Physical carrier and medium','2':'Ethernet / ARP address resolution' if arp else 'Link forwarding',
  '3':'Not applicable to ARP' if arp else 'IPv6 forwarding' if ipv6 else 'IPv4 route/ACL/NAT',
  '4':'Not applicable to ARP' if arp else event['headers'].get('transport',{}).get('protocol',event['protocol']).upper(),
  '5':'No independent session model','6':'No independent presentation model','7':'Not applicable to ARP' if arp else event['protocol']})
 lab.packet_events[-1].update(deepcopy(event))
 s['events'].append(event);s['events']=s['events'][-MAX_EVENTS:];s['cursor']=len(s['events']);s['last_event']=event
 if final and p:
  updates=result.pop('_device_updates',{}) if result else {}
  if updates:
   from .workspace_tools import read_lab
   saved=lab.to_dict()
   for name,raw in updates.items():
    if name in saved['devices']:saved['devices'][name]=raw
   restored=read_lab(saved)
   for name in updates:
    if name in lab.devices:lab.devices[name]=restored.devices[name]
  p['result']=result;p['status']=result['status'];event['result']=deepcopy(result)

 return event

def advance(lab,seconds=0,limit=1000):
 s=lab.simulation;seconds=finite(seconds,0,86400);target=s['time']+seconds
 count=0
 while count<limit:
  due=[p['next_due'] for p in s['pdus'].values() if p['scenario']==s['active'] and p['next_due'] is not None]
  if not s['pending'] and (not due or min(due)>target):break
  step(lab);count+=1
 if count>=limit and (s['pending'] or any(x<=target for x in due)):raise LabError('event budget reached; advance a shorter time interval')
 delta=max(0,target-s['time']);s['time']+=delta;s['master_time']+=delta
 return count

def sync(lab):
 now=time.monotonic();previous=getattr(lab,'_simulation_wall',now);lab._simulation_wall=now
 if lab.simulation['mode']=='simulation' and lab.simulation['playing']:
  count=min(100,int(max(0,now-previous)/max(.05,1.2-lab.simulation['speed']*.01)))
  if count==0:lab._simulation_wall=previous
  for _ in range(count):
   if not step(lab):break
 if lab.simulation['mode']=='realtime':
  try:advance(lab,min(max(0,now-previous),60))
  except LabError:pass  # bounded realtime work; pending traffic is retained

def apply(lab,body):
 if not isinstance(body,dict):raise LabError('expected JSON object')
 s=lab.simulation;action=body.get('action')
 if action=='mode':
  mode=body.get('mode')
  if mode not in ('simulation','realtime'):raise LabError('invalid operating mode')
  if mode==s['mode']:return
  if mode=='realtime':
   s['cursor']=len(s['events']);advance(lab,0)
  if mode=='simulation':reset(lab)
  else:
   elapsed=s['time'];s.update(time=0.0,cursor=0,events=[],pending=[],playing=False,last_event=None)
   for p in s['pdus'].values():
    if p['next_due'] is not None:p['next_due']=max(0,p['next_due']-elapsed)
  s['mode']=mode;lab._simulation_wall=time.monotonic()
 elif action in ('scenario_add','scenario_edit'):
  ident=body.get('id') or 'scenario_'+uuid.uuid4().hex[:12]
  if action=='scenario_edit' and ident not in s['scenarios']:raise LabError('unknown scenario')
  if action=='scenario_add' and (ident in s['scenarios'] or len(s['scenarios'])>=100):raise LabError('scenario exists or 100 scenario limit reached')
  old=s['scenarios'].get(ident,{'description':''});description=body.get('description',old['description'])
  if not isinstance(description,str) or len(description)>2000:raise LabError('description must be at most 2000 characters')
  s['scenarios'][ident]={'name':label(body.get('name',old.get('name','New Scenario'))),'description':description};return ident
 elif action=='scenario_select':
  if body.get('id') not in s['scenarios']:raise LabError('unknown scenario')
  s['active']=body['id'];reset(lab)
 elif action=='scenario_delete':
  ident=body.get('id')
  if ident not in s['scenarios'] or len(s['scenarios'])==1:raise LabError('cannot remove last or unknown scenario')
  s['pdus']={k:p for k,p in s['pdus'].items() if p['scenario']!=ident};del s['scenarios'][ident]
  if s['active']==ident:s['active']=next(iter(s['scenarios']))
  reset(lab)
 elif action in ('pdu_add','pdu_edit'):
  ident=body.get('id') or 'pdu_'+uuid.uuid4().hex[:12]
  if action=='pdu_add' and (ident in s['pdus'] or len(s['pdus'])>=500):raise LabError('PDU exists or 500 PDU limit reached')
  if action=='pdu_edit' and ident not in s['pdus']:raise LabError('unknown PDU')
  p=validate_pdu(lab,body,s['pdus'].get(ident));p['next_due']=max(p['start'],s['time']) if p['scenario']==s['active'] else None
  s['pdus'][ident]=p
  if s['mode']=='realtime' and p['start']<=s['time']:advance(lab,0)
  return ident
 elif action in ('pdu_delete','pdu_fire'):
  ident=body.get('id')
  if ident not in s['pdus']:raise LabError('unknown PDU')
  if action=='pdu_delete':del s['pdus'][ident];reset(lab)
  else:
   if s['pdus'][ident]['scenario']!=s['active']:raise LabError('PDU belongs to inactive scenario')
   s['pdus'][ident]['next_due']=s['time']
   if s['mode']=='realtime':advance(lab,0)
 elif action=='step':return step(lab)
 elif action=='back':s['cursor']=max(0,s['cursor']-1);s['last_event']=s['events'][s['cursor']-1] if s['cursor'] else None
 elif action=='reset':reset(lab)
 elif action=='advance':return advance(lab,body.get('seconds',0),integer(body.get('limit',1000),1,10000))
 elif action=='play':
  if not isinstance(body.get('enabled'),bool):raise LabError('enabled must be boolean')
  s['playing']=body['enabled'];lab._simulation_wall=time.monotonic()
 elif action=='preferences':
  if 'filters' in body:
   if not isinstance(body['filters'],list) or any(not isinstance(x,str) or x not in PROTOCOLS for x in body['filters']):raise LabError('invalid filters')
   s['filters']=list(dict.fromkeys(body['filters']))
  if 'constant_delay' in body:
   if not isinstance(body['constant_delay'],bool):raise LabError('constant_delay must be boolean')
   s['constant_delay']=body['constant_delay']
  if 'speed' in body:s['speed']=integer(body['speed'],0,100)
 else:raise LabError('unsupported simulation action')

def action(lab,body):
 candidate=deepcopy(lab);result=apply(candidate,body)
 lab.__dict__.clear();lab.__dict__.update(candidate.__dict__);return result

def view(lab,synchronize=True):
 if synchronize:sync(lab)
 s=deepcopy(lab.simulation)
 s['visible_events']=[e for e in s['events'][:s['cursor']] if e['protocol'] in s['filters']]
 s.pop('pending');return {'ok':True,**s,'applications':APPLICATIONS,'legend':{p:COLORS.get(p,'#7755aa') for p in PROTOCOLS}}

def schema():
 return {'version':1,'read':'GET /api/simulation','write':'POST /api/simulation/action',
 'actions':['mode','scenario_add','scenario_edit','scenario_select','scenario_delete','pdu_add','pdu_edit','pdu_delete','pdu_fire','step','back','reset','advance','play','preferences'],
 'applications':APPLICATIONS,'limits':{'events':MAX_EVENTS,'pdus':500,'scenarios':100},
 'semantics':['Queued traffic has no forwarding effects until dispatch/capture.','Back inspects captured events; it never rewinds master time or learned network state.','Filters change visibility, not packet delivery.','Application_status=transport-only explicitly denotes an application whose server engine is not available.','Modelled event delays are deterministic estimates, not a vendor IOS timing emulator.']}

def load(lab,raw):
 if raw is None:return defaults()
 if not isinstance(raw,dict) or set(raw)!=set(defaults()):raise LabError('invalid saved simulation state')
 s=deepcopy(raw);lab.simulation=s
 if s['mode'] not in ('realtime','simulation') or not isinstance(s['scenarios'],dict) or not s['scenarios'] or len(s['scenarios'])>100 or s['active'] not in s['scenarios']:raise LabError('invalid saved scenarios')
 for value in ('master_time','time'):finite(s[value],0,1e12)
 if not isinstance(s['events'],list) or len(s['events'])>MAX_EVENTS or not isinstance(s['pending'],list) or len(s['pending'])>4000:raise LabError('invalid event queue')
 integer(s['cursor'],0,len(s['events']))
 if not isinstance(s['pdus'],dict) or len(s['pdus'])>500:raise LabError('invalid saved PDUs')
 if not isinstance(s['playing'],bool) or not isinstance(s['constant_delay'],bool):raise LabError('invalid playback settings')
 finite(s['speed'],1,100)
 if not isinstance(s['filters'],list) or any(p not in PROTOCOLS for p in s['filters']):raise LabError('invalid protocol filters')
 for ident,scenario in s['scenarios'].items():
  label(ident);label(scenario.get('name'))
  if not isinstance(scenario.get('description'),str) or len(scenario['description'])>2000:raise LabError('invalid saved scenario description')
 for event in s['events']+s['pending']:
  if not isinstance(event,dict) or not isinstance(event.get('headers'),dict) or not isinstance(event.get('detail'),str) or not isinstance(event.get('ok'),bool):raise LabError('invalid saved packet event')
  if not all(isinstance(event.get(k),str) for k in ('protocol','source','destination','color')):raise LabError('invalid saved event fields')
 for event in s['pending']:
  if event.get('pdu') not in s['pdus'] or not isinstance(event.get('dynamics'),dict) or not isinstance(event.get('final'),bool) or event.get('result') is not None and not isinstance(event['result'],dict):raise LabError('invalid pending packet')
 for key,p in s['pdus'].items():
  label(key)
  if not isinstance(p,dict):raise LabError('invalid saved PDU')
  validate_pdu(lab,p)
  integer(p.get('runs'),0,1e12)
  if p.get('status') not in ('Not sent','In Progress','Successful','Failed'):raise LabError('invalid PDU status')
  if 'task' in p:
   task=p['task']
   if not isinstance(task,dict) or task.get('operation') not in ('http','ping','device-config') or not isinstance(task.get('payload'),dict):raise LabError('invalid saved task')
   if task['operation']=='device-config' and task['payload'].get('action') not in CLIENT_ACTIONS:raise LabError('invalid saved client task')
  if p['next_due'] is not None:finite(p['next_due'],0,1e12)
 s['playing']=False
 return s

CLIENT_ACTIONS={'modbus_send','cip_request','host_command','transfer','mail_send','mail_receive','aaa_authenticate','clock_sync','snmp','remote_cli','historian_collect'}

def enqueue_task(lab,operation,payload):
 source=payload.get('source') if operation in ('http','ping') else payload.get('device')
 lab._device(source)
 protocol='HTTP' if operation=='http' else 'ICMP' if operation=='ping' else {'modbus_send':'TCP','cip_request':'TCP','host_command':'TCP','transfer':payload.get('protocol','TFTP').upper(),'mail_send':'SMTP','mail_receive':'POP3','aaa_authenticate':payload.get('protocol','RADIUS').upper(),'clock_sync':payload.get('protocol','NTP').upper(),'snmp':'SNMP','remote_cli':payload.get('protocol','SSH').upper(),'historian_collect':'TCP'}[payload['action']]
 if protocol not in APPLICATIONS:protocol='UDP'
 ip=payload.get('destination_ip','0.0.0.0')
 if ':' in ip:ip='0.0.0.0'  # task payload retains the authoritative IPv6 destination
 if operation=='device-config' and payload.get('server'):
  from .device_services import endpoint
  _,ip=endpoint(lab,payload['server'])
 ident=apply(lab,{'action':'pdu_add','source':source,'destination_ip':ip,'protocol':protocol})
 p=lab.simulation['pdus'][ident];p['task']={'operation':operation,'payload':deepcopy(payload)}
 p['user_created']=False
 return ident

def record_external(lab,event):
 s=lab.simulation
 if s['mode']!='realtime':return
 s['time']=round(s['time']+.001,6);s['master_time']=round(s['master_time']+.001,6)
 entry={**deepcopy(event),'time':s['time'],'master_time':s['master_time'],'pdu':None,'color':COLORS.get(event['protocol'],'#7755aa'),'qos':0,'headers':{},'osi':{'7':event['protocol'],'3':'IPv4 forwarding'}}
 s['events'].append(entry);s['events']=s['events'][-MAX_EVENTS:];s['cursor']=len(s['events']);s['last_event']=entry

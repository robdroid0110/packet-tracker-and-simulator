"""Shared device configuration and nonvolatile lifecycle (§§42–73).

All configuration edits apply to an isolated candidate and publish atomically.
Legacy labs retain their power-cycle behaviour until startup lifecycle is enabled.
"""
from __future__ import annotations
from copy import deepcopy
from ipaddress import IPv4Interface,IPv4Address,IPv4Network
import json,re,uuid
from .model import LabError,Interface,Route


def settings(d):
 return {'hostname':d.name,'display_name':d.name,'startup_managed':False,'startup':None,
 'boot_image':'simulated-ios.bin','boot_state':'running','files':{'simulated-ios.bin':'Packet Tracker and Simulator simulated IOS image'},
 'users':{},'services':{},'wireless':{},'cloud':{},'controller':{},'industrial':{},'logs':[],
 'clock':None,'syslog_host':None,'rip':[],'license':{},'iox':{},**deepcopy(d.config)}

def snapshot(lab,d):
 raw=lab._device_to_dict(d)
 for k in ('name','kind','model','x','y','powered','modules','arp_table','mac_table','nat_sessions'):raw.pop(k,None)
 config=settings(d);config.pop('startup',None);config['startup_managed']=True;raw['config']=config
 return raw

def restore(lab,d,raw):
 if raw is None:
  fresh=type(d)(name=d.name,kind=d.kind,model=d.model)
  raw={'interfaces':{n:{'name':n,'admin_up':True,'ip':None} for n in d.interfaces},
       'routes':[],'vlans':[1],'ospf_enabled':False,'ospf_networks':[],
       'default_gateway':None,'dns_server':None,'dhcp_pools':{},'acls':{},'nat_static':{},'nat_overload':[],
       'config':{'startup_managed':True,'startup':None}}
 base=lab.to_dict();device=base['devices'][d.name];old=deepcopy(device['interfaces'])
 for key,value in raw.items():
  if key!='interfaces':device[key]=deepcopy(value)
 # Startup snapshots made before area-aware OSPF must use legacy defaults,
 # rather than inheriting OSPF fields from the current running configuration.
 if 'ospf_enabled' in raw:
  for key in ('ospf_auto','ospf_areas','ospf_process_id'):
   if key not in raw:device.pop(key,None)
 for name,p in old.items():
  if name in raw.get('interfaces',{}):
   saved=raw['interfaces'][name]
   p.update({k:v for k,v in saved.items() if k not in ('name','media','mac')})
  else:p['ip']=None
 device['interfaces']=old
 previous=settings(d);device['config'].update(startup_managed=previous['startup_managed'],startup=previous['startup'],files=previous['files'])
 device['arp_table']={};device['mac_table']={};device['nat_sessions']={}
 from .workspace_tools import read_lab
 candidate=read_lab(base);lab.devices[d.name]=candidate.devices[d.name]

def boot(lab,name):
 d=lab._device(name);c=settings(d)
 if c['startup_managed']:restore(lab,d,c['startup']);d=lab._device(name);c=settings(d)
 image=c['files'].get(c['boot_image'])
 c['boot_state']='running' if image and image.startswith('Packet Tracker and Simulator simulated IOS') else 'rommon'
 d.config=c;lab.recompute_ospf()

def merge_text(lab,name,text):
 from .ios import IOSSession
 if not isinstance(text,str) or len(text)>200000:raise LabError('configuration text exceeds 200KB')
 if text.lstrip().startswith('{'):
  raw=json.loads(text)
  if not isinstance(raw,dict) or 'interfaces' not in raw:raise LabError('invalid native configuration JSON')
  restore(lab,lab.devices[name],raw);return
 session=IOSSession(lab,name);session.mode='config'
 for line in text.splitlines():
  line=line.strip()
  if not line or line.startswith(('!','Building configuration','Current configuration','version ')):continue
  if line in ('end','exit') or line.startswith('hostname '):session.mode='config'
  if line.startswith(('ip dhcp pool ','ip access-list ','ipv6 unicast-routing','interface ','router ','ip route ','vlan ','access-list ','hostname ')):session.mode='config'
  result=session.execute(line)
  if result.startswith('%'):raise LabError('configuration merge failed at '+line+': '+result)

def validate_saved(raw):
 if not isinstance(raw,dict):raise LabError('device config must be an object')
 if len(json.dumps(raw))>4_000_000:raise LabError('device configuration exceeds 4MB')
 for field in ('users','services','wireless','cloud','controller','industrial','eigrp','license','iox','files','terminal_sessions','management_sessions'):
  if field in raw and not isinstance(raw[field],dict):raise LabError('invalid device '+field)
 for asn,networks in raw.get('eigrp',{}).items():
  if not str(asn).isdigit() or not 1<=int(asn)<=65535 or not isinstance(networks,list):raise LabError('invalid saved EIGRP process')
  for network in networks:IPv4Network(network,strict=False)
 if raw.get('startup') is not None and not isinstance(raw['startup'],dict):raise LabError('invalid startup configuration')
 if 'startup_managed' in raw and not isinstance(raw['startup_managed'],bool):raise LabError('invalid startup lifecycle flag')
 if raw.get('boot_state','running') not in ('running','rommon'):raise LabError('invalid boot state')
 return deepcopy(raw)

def _apply(lab,body):
 from .simulation import label,integer
 if not isinstance(body,dict):raise LabError('expected JSON object')
 name=body.get('device');d=lab._device(name);c=settings(d);action=body.get('action')
 if action=='global':
  if 'ipv6_routing' in body:
   if not isinstance(body['ipv6_routing'],bool):raise LabError('ipv6_routing must be boolean')
   c['ipv6_routing']=body['ipv6_routing']
  if 'hostname' in body:
   hostname=body['hostname']
   if not isinstance(hostname,str) or not re.fullmatch(r'[A-Za-z][A-Za-z0-9_-]{0,62}',hostname):raise LabError('invalid IOS hostname')
   c['hostname']=hostname
  if 'display_name' in body:c['display_name']=label(body['display_name'],80)
  if 'enable_secret' in body:c['enable_secret']=label(body['enable_secret'],128) if body['enable_secret'] else None
  d.config=c
 elif action in ('interface','set_port'):
  if action=='set_port':body={**body,'interface':body['port']}
  from .hardware import set_port
  set_port(lab,name,body['interface'],body)
  if 'ip' in body:
   if body['ip']:lab.set_ip(name,body['interface'],str(IPv4Interface(body['ip'])))
   else:lab._iface(name,body['interface']).ip=None;lab.recompute_ospf()
  if 'ipv6' in body:
   from ipaddress import IPv6Interface
   lab._iface(name,body['interface']).ipv6=str(IPv6Interface(body['ipv6'])) if body['ipv6'] else None
  if 'ipv6_link_local' in body:
   from ipaddress import IPv6Address
   address=IPv6Address(body['ipv6_link_local'])
   if not address.is_link_local:raise LabError('IPv6 link-local address must be in fe80::/10')
   lab._iface(name,body['interface']).ipv6_link_local=str(address)
  if 'ipv6_dns_server' in body:c['ipv6_dns_server']=str(__import__('ipaddress').IPv6Address(body['ipv6_dns_server']));d.config=c
  if 'ipv6_gateway' in body:c['ipv6_gateway']=str(__import__('ipaddress').IPv6Address(body['ipv6_gateway']));d.config=c
  if 'gateway' in body:d.default_gateway=str(IPv4Address(body['gateway'])) if body['gateway'] else None
  if 'dns_server' in body:d.dns_server=str(IPv4Address(body['dns_server'])) if body['dns_server'] else None
  lab.recompute_ospf()
 elif action=='add_port':
  from .hardware import add_port
  add_port(lab,name,body['port'],body['media'])
 elif action=='module':lab.set_module(name,body['slot'],body.get('module'))
 elif action=='power':lab.set_power(name,body['enabled'])
 elif action=='save_startup':
  c['startup_managed']=True;d.config=c;c['startup']=snapshot(lab,d);d.config=c
 elif action=='erase_startup':c.update(startup_managed=True,startup=None);d.config=c
 elif action=='startup_import':
  before=snapshot(lab,d);merge_text(lab,name,body['text']);loaded=snapshot(lab,lab._device(name));restore(lab,lab._device(name),before)
  c=settings(lab._device(name));c.update(startup_managed=True,startup=loaded);lab._device(name).config=c
 elif action=='merge_running':merge_text(lab,name,body['text'])
 elif action=='boot_image':c['boot_image']=label(body['file'],80);d.config=c
 elif action=='boot':boot(lab,name)
 elif action=='file_write':
  file=label(body['file'],80);text=body.get('content')
  if '/' in file or '\\' in file or not isinstance(text,str) or len(text)>200000:raise LabError('invalid simulated file')
  if len(c['files'])>=100 and file not in c['files']:raise LabError('100-file limit')
  c['files'][file]=text;d.config=c
 elif action=='file_delete':
  if body.get('file') not in c['files']:raise LabError('unknown simulated file')
  del c['files'][body['file']];d.config=c
 elif action=='local_user':
  user=label(body['username'],64)
  if body.get('delete'):c['users'].pop(user,None)
  else:c['users'][user]={'password':label(body['password'],128),'privilege':integer(body.get('privilege',1),1,15)}
  d.config=c
 elif action in ('ipv6_dhcp','dhcpv6_pool'):
  from .ipv6 import dhcp,pool
  return dhcp(lab,name,body['interface']) if action=='ipv6_dhcp' else pool(lab,name,body)
 elif action=='ipv6_autoconfigure':
  from .ipv6 import autoconfigure
  return autoconfigure(lab,name,body['interface'])
 elif action=='ipv6_route':
  from ipaddress import IPv6Network,IPv6Address
  prefix=str(IPv6Network(body['network'],strict=False));next_hop=str(IPv6Address(body['next_hop']));c.setdefault('ipv6_routes',[])
  c['ipv6_routes']=[r for r in c['ipv6_routes'] if r['network']!=prefix]
  if not body.get('delete'):c['ipv6_routes'].append({'network':prefix,'next_hop':next_hop,'interface':body.get('interface')})
  d.config=c
 elif action=='acl_rule':
  return vars(lab.add_acl_rule(name,body['name'],body['policy'],body.get('protocol','ip'),body.get('source','any'),body.get('destination','any'),body.get('sequence'),body.get('source_port'),body.get('destination_port')))
 elif action=='access_group':lab.set_access_group(name,body['interface'],body.get('name'),body.get('direction','in'))
 elif action=='eigrp':
  from .eigrp import configure
  return configure(lab,body)
 elif action=='rip':
  if 'enabled' in body and not isinstance(body['enabled'],bool):raise LabError('RIP enabled must be boolean')
  network=str(IPv4Network(body['network'],strict=False))
  if body.get('enabled',True):
   if network not in c['rip']:c['rip'].append(network)
  else:c['rip']=[n for n in c['rip'] if n!=network]
  d.config=c;recompute_rip(lab)
 elif action=='vlan_delete':
  vlan=integer(body['vlan'],2,4094)
  if any(i.access_vlan==vlan for i in d.interfaces.values()):raise LabError('move ports off VLAN before deleting')
  d.vlans.discard(vlan)
  lab._refresh_dynamic_routing()
 elif action=='console':
  from .hardware import console
  from .ios import IOSSession
  remote=console(lab,body)
  return terminal_session(lab,name,remote,'console:'+body['interface'],body.get('command',''))
 else:
  from .device_services import apply
  return apply(lab,body)
 return {'device':name,'action':action}

def action(lab,body):
 candidate=deepcopy(lab)
 from .simulation import CLIENT_ACTIONS,enqueue_task
 if candidate.simulation["mode"]=="simulation" and isinstance(body,dict) and body.get("action") in CLIENT_ACTIONS and (body.get('action')!='host_command' or str(body.get('command','')).split(' ')[0].lower() in ('ping','tracert','traceroute','nslookup','ftp','ssh','telnet','snmpget','snmpgetbulk','snmpset')):
  result={"queued":enqueue_task(candidate,"device-config",body)}
 else:result=_apply(candidate,body)
 for d in candidate.devices.values():validate_saved(d.config)
 lab.__dict__.clear();lab.__dict__.update(candidate.__dict__)
 if lab.simulation["mode"]=="simulation" and body.get("action") not in CLIENT_ACTIONS and body.get("action") not in {"modbus_receive"}:
  from .simulation import reset
  reset(lab)
 return result

def recompute_rip(lab):
 # Deterministic distance-vector fixed point with hop metric and 15-hop limit.
 routers=[d for d in lab.devices.values() if d.kind=='router' and d.powered and settings(d)['rip']]
 for d in lab.devices.values():d.routes=[r for r in d.routes if r.source!='rip']
 def active(d,i):return i.ip and lab._iface_effective_up(d.name,i.name) and any(i.ipv4.ip in IPv4Network(n) for n in settings(d)['rip'])
 adjacency={d.name:[] for d in routers}
 for a in routers:
  for b in routers:
   if a==b:continue
   for ia in a.interfaces.values():
    if not active(a,ia):continue
    for ib in b.interfaces.values():
     if active(b,ib) and ib.ipv4.ip in ia.ipv4.network and lab.l2_reachable((a.name,ia.name),(b.name,ib.name)):
      adjacency[a.name].append((b.name,str(ib.ipv4.ip)));break
 for origin in routers:
  seen={origin.name};queue=[(origin.name,0,None)]
  while queue:
   current,hops,first=queue.pop(0)
   if hops>15:continue
   if hops:
    for route in lab.connected_routes(current):
     if not active(lab.devices[current],lab.devices[current].interfaces[route.interface]):continue
     if not any(r.network==route.network for r in lab.connected_routes(origin.name)) and not any(r.network==route.network and r.source=='rip' for r in origin.routes):origin.routes.append(Route(route.network,next_hop=first,source='rip',metric=hops))
   for neighbor,ip in adjacency[current]:
    if neighbor not in seen:seen.add(neighbor);queue.append((neighbor,hops+1,first or ip))

def view(lab,name):
 from .ios import IOSSession
 d=lab._device(name);c=settings(d)
 from .device_services import profile
 return {'ok':True,'device':name,'kind':d.kind,'model':d.model,'profile':profile(d),
  'settings':c,'interfaces':{n:vars(i).copy() for n,i in d.interfaces.items()},'modules':lab.module_slots(name),
  'running':snapshot(lab,d),'running_text':IOSSession(lab,name)._running_config(),
  'startup':c['startup'],'routes':[vars(r) for r in lab.routing_table(name)],
  'limitations':['Deterministic simulator; no vendor IOS image execution or cryptographic SSH/TLS/VPN implementation.',
  'Legacy labs retain power-cycle configuration until save/erase startup enables the NVRAM lifecycle.']}

def schema():
 from .hardware import schema as hardware_schema
 from .device_services import schema as services_schema
 return {'version':1,'read':'GET /api/device-config?device=R1','write':'POST /api/device-config/action',
 'hardware':hardware_schema(),'services':services_schema(),
 'actions':{'global':['hostname','display_name','enable_secret','ipv6_routing'],'ipv6_dhcp':['interface'],'dhcpv6_pool':['name','prefix','gateway','dns_server','enabled','delete'],'ipv6_autoconfigure':['interface'],'ipv6_route':['network','next_hop','interface','delete'],
 'interface':['interface','ip','ipv6','ipv6_link_local','ipv6_dns_server','ipv6_gateway','gateway','dns_server','speed','duplex','clock_rate','auto_mdix','mac','mtu','tx_ring_limit','admin_up'],
 'module':['slot','module'],'power':['enabled'],'save_startup':[],'erase_startup':[],
 'merge_running':['text'],'startup_import':['text'],'boot_image':['file'],'boot':[],
 'file_write':['file','content'],'file_delete':['file'],'local_user':['username','password','privilege','delete'],
 'acl_rule':['name','policy','protocol','source','destination','sequence','source_port','destination_port'],'access_group':['interface','name','direction'],
 'eigrp':['asn','network','enabled','delete_process'],'rip':['network','enabled'],'vlan_delete':['vlan']}}


def terminal_session(lab,local,target,key,text):
 from .ios import IOSSession
 from .device_services import conf
 current=lab._device(local).config.get('terminal_sessions',{}).get(key,{})
 session=IOSSession(lab,target)
 for field in ('mode','interface','ospf_process','pending_dot1q','awaiting_enable','context'):
  if field in current:setattr(session,field,deepcopy(current[field]))
 result='\n'.join(session.execute(line) for line in text.splitlines() or [''])
 conf(lab._device(local)).setdefault('terminal_sessions',{})[key]={field:deepcopy(getattr(session,field)) for field in ('mode','interface','ospf_process','pending_dot1q','awaiting_enable','context')}
 return result

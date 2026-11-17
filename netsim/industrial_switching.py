"""Deterministic REP recovery and transparent two-way Layer-2 IPv4 NAT."""
from ipaddress import IPv4Address
from .model import LabError
from .device_services import conf
from .simulation import integer


def alias_owner(lab,address):
 for bridge in lab.devices.values():
  state=bridge.config.get('l2nat',{})
  for direction in ('inside','outside'):
   for original,alias in state.get(direction,{}).items():
    if alias==str(address):
     for d in lab.devices.values():
      for p in d.interfaces.values():
       if p.ip and str(p.ipv4.ip)==original:return d.name,p.name
 return None

def translate(lab,start,goal,source,destination,meta):
 path=lab.l2_path(start,goal) or [];seen=set()
 for name,port in path:
  if name in seen:continue
  seen.add(name);c=lab.devices[name].config.get('l2nat',{})
  if not c or c.get('interfaces') and not any(n==name and p in c['interfaces'] for n,p in path):continue
  original_source=source;original_destination=destination
  for side in ('inside','outside'):
   table=c.get(side,{})
   if source in table:source=table[source]
   inverse={v:k for k,v in table.items()}
   if destination in inverse:destination=inverse[destination]
  if source!=original_source or destination!=original_destination:
   c['translated_packets']=c.get('translated_packets',0)+1
   meta['translated_source']=source;meta['final_destination']=destination
 return source,destination

def rep_status(lab,segment):
 edges=[];parent={}
 def root(x):
  parent.setdefault(x,x)
  while parent[x]!=x:x=parent[x]
  return x
 for link in lab.links:
  a=lab.devices[link.a_device].config.get('rep_ports',{}).get(link.a_if)
  b=lab.devices[link.b_device].config.get('rep_ports',{}).get(link.b_if)
  if a and b and a['segment']==b['segment']==segment and lab.link_operational(link):edges.append(link)
 blocked=set()
 for link in sorted(edges,key=lambda l:sorted(l.endpoints())):
  a=root(link.a_device);b=root(link.b_device)
  if a==b:blocked.add(max(link.endpoints()))
  else:parent[a]=b
 return blocked

def rep_forwarding(lab,name,port):
 value=lab.devices[name].config.get('rep_ports',{}).get(port)
 return True if not value else (name,port) not in rep_status(lab,value['segment'])

def apply(lab,b):
 d=lab._device(b['device']);c=conf(d)
 if b['action']=='svi':return svi(lab,d,b)
 if b['action']=='l2nat':
  side=b.get('direction','inside')
  if side not in ('inside','outside'):raise LabError('L2 NAT direction must be inside/outside')
  original=str(IPv4Address(b['original']));alias=str(IPv4Address(b['translated']))
  state=c.setdefault('l2nat',{});table=state.setdefault(side,{})
  if b.get('delete'):table.pop(original,None)
  else:table[original]=alias
  if b.get('interfaces') is not None:
   if not isinstance(b['interfaces'],list):raise LabError('interfaces must be a list')
   for port in b['interfaces']:lab._iface(d.name,port)
   state['interfaces']=b['interfaces']
  return state
 if b['action']=='rep':
  port=b['interface'];lab._iface(d.name,port);ports=c.setdefault('rep_ports',{})
  if b.get('delete'):ports.pop(port,None)
  else:ports[port]={'segment':integer(b['segment'],1,1024),'edge':bool(b.get('edge',False))}
  return {'ports':ports,'blocked':[list(p) for segment in {p['segment'] for p in ports.values()} for p in rep_status(lab,segment)]}
 if b['action']=='dhcp_binding':
  mac=b['mac'].lower();ip=str(IPv4Address(b['ip']))
  if not __import__('re').fullmatch('[0-9a-f]{2}(?::[0-9a-f]{2}){5}',mac):raise LabError('invalid client MAC')
  if b.get('delete'):c.setdefault('dhcp_bindings',{}).pop(mac,None)
  else:c.setdefault('dhcp_bindings',{})[mac]=ip
  return c['dhcp_bindings']
 raise LabError('unsupported industrial switching action')


def svi(lab,d,b):
 from ipaddress import IPv4Interface,IPv6Interface
 from .model import Interface
 vlan=integer(b['vlan'],1,4094)
 if d.kind!='switch' and not d.config.get('multilayer_switch'):raise LabError('SVI requires a switch profile')
 c=conf(d);c['multilayer_switch']=True;d.kind='router';d.vlans.add(vlan)
 for port in list(d.interfaces.values()):
  if port.media not in ('copper','fiber-mm','fiber-sm') or port.parent:continue
  if port.mode=='access':port.bridge_group='vlan'+str(port.access_vlan)
  else:
   for tag in d.vlans:
    if tag not in port.allowed_vlans:continue
    name=port.name+'.'+str(tag)
    if name not in d.interfaces:d.interfaces[name]=Interface(name,parent=port.name,encapsulation_vlan=tag,bridge_group='vlan'+str(tag),media=port.media)
 name='vlan'+str(vlan);port=d.interfaces.setdefault(name,Interface(name,media='bridge',bridge_group=name,access_vlan=vlan,allowed_vlans=[vlan]))
 if b.get('ip'):port.ip=str(IPv4Interface(b['ip']))
 if b.get('ipv6'):port.ipv6=str(IPv6Interface(b['ipv6']))
 if 'admin_up' in b:
  if not isinstance(b['admin_up'],bool):raise LabError('admin_up must be boolean')
  port.admin_up=b['admin_up']
 lab.recompute_ospf();return vars(port).copy()

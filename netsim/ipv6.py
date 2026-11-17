"""IPv6 interface/static routing, NDP and SLAAC using the existing L2 engine."""
from ipaddress import IPv6Address,IPv6Interface,IPv6Network
from .model import LabError

def link_local(port):
 if port.ipv6_link_local:return port.ipv6_link_local
 mac=bytearray.fromhex(port.mac.replace(':',''));mac[0]^=2
 iid=int.from_bytes(mac[:3]+b'\xff\xfe'+mac[3:],'big')
 return str(IPv6Address(int(IPv6Address('fe80::'))|iid))

def routes(lab,name):
 d=lab._device(name);result=[]
 for p in d.interfaces.values():
  if p.ipv6 and lab._iface_effective_up(name,p.name):
   result.append({'network':str(IPv6Interface(p.ipv6).network),'interface':p.name,'next_hop':None})
   result.append({'network':'fe80::/64','interface':p.name,'next_hop':None})
 result+=d.config.get('ipv6_routes',[])
 if d.config.get('ipv6_gateway'):result.append({'network':'::/0','next_hop':d.config['ipv6_gateway'],'interface':None})
 return sorted(result,key=lambda r:-IPv6Network(r['network']).prefixlen)

def owners(lab,address):
 for d in lab.devices.values():
  for p in d.interfaces.values():
   if p.ipv6 and IPv6Interface(p.ipv6).ip==address or IPv6Address(link_local(p))==address:yield d.name,p.name

def permit(d,source,destination,protocol):
 rules=d.config.get('ipv6_firewall',[])
 if not rules:return True
 for r in rules:
  if r['protocol'] in ('ipv6',protocol) and IPv6Address(source) in IPv6Network(r['source']) and IPv6Address(destination) in IPv6Network(r['destination']):return r['action']=='permit'
 return False

def _forward(lab,name,address,source,visited,trace,limit,diagnostic=None):
 d=lab._device(name)
 if diagnostic is not None:diagnostic['hops'].append(name)
 def fail(code,markers):
  if diagnostic is not None:diagnostic['reason']={'code':code,'device':name}
  return False,trace+markers
 if name in visited or limit<=0:return fail('hop_limit_or_loop',['IPv6-hop-limit/loop'])
 if not d.powered:return fail('device_powered_off',[name,'powered-off'])
 trace=trace+[name];visited=visited|{name}
 if not permit(d,source,str(address),'icmpv6'):return fail('ipv6_firewall_denied',['IPv6-firewall-deny'])
 if any(dev==name and lab._iface_effective_up(dev,port) for dev,port in owners(lab,address)):return True,trace
 if visited!={name} and address.is_link_local:return fail('link_local_not_routed',['IPv6-link-local-is-not-routed'])
 if visited!={name} and not d.config.get('ipv6_routing',False):return fail('ipv6_forwarding_disabled',['IPv6-forwarding-disabled'])
 route=next((r for r in routes(lab,name) if address in IPv6Network(r['network'])),None)
 if not route:return fail('no_route',['no-ipv6-route'])
 target=IPv6Address(route['next_hop']) if route['next_hop'] else address
 for port in d.interfaces.values():
  if route.get('interface') and route['interface']!=port.name or not port.ipv6 or not lab._iface_effective_up(name,port.name):continue
  if route.get('next_hop') and not target.is_link_local and target not in IPv6Interface(port.ipv6).network:continue
  for receiver,remote in owners(lab,target):
   if receiver==name:continue
   path=lab.l2_path((name,port.name),(receiver,remote))
   if not path:continue
   d.config.setdefault('ndp',{})[str(target)]=lab._iface(receiver,remote).mac
   lab.devices[receiver].config.setdefault('ndp',{})[str(IPv6Interface(port.ipv6).ip)]=port.mac
   return _forward(lab,receiver,address,source,visited,trace,limit-1,diagnostic)
 return fail('ndp_unreachable',['NDP-unreachable'])

def ping(lab,source,address,hop_limit=64):
 value=ping_detailed(lab,source,address,hop_limit)
 return value['reachable'],value['message']

def ping_detailed(lab,source,address,hop_limit=64):
 from .connectivity import result
 address=IPv6Address(address);d=lab._device(source)
 origin=next((str(IPv6Interface(p.ipv6).ip) for p in d.interfaces.values() if p.ipv6 and lab._iface_effective_up(source,p.name)),None)
 if not origin:return result(source,str(address),6,'failed','IPv6 source has no operational address',reason={'code':'source_address_unavailable','stage':'source','device':source})
 diagnostic={'hops':[],'reason':None}
 ok,forward=_forward(lab,source,address,origin,set(),[],hop_limit,diagnostic)
 if not ok:return result(source,str(address),6,'failed','IPv6 PING failed: '+' -> '.join(forward),forward=diagnostic['hops'],reason={**diagnostic['reason'],'stage':'forward'})
 owner=next((n for n,p in owners(lab,address) if n==forward[-1]),None)
 response={'hops':[],'reason':None}
 reply,back=_forward(lab,owner,IPv6Address(origin),str(address),set(),[],hop_limit,response)
 lab._trace_packet('ICMPv6',forward,'IPv6 Echo Request',ok)
 if reply:lab._trace_packet('ICMPv6',back,'IPv6 Echo Reply',True)
 message=('IPv6 PING success' if reply else 'IPv6 PING failed reply')+'\nforward: '+' -> '.join(forward)+'\nreply: '+' -> '.join(back)
 reason=None if reply else {**response['reason'],'stage':'reply'}
 return result(source,str(address),6,'success' if reply else 'failed',message,forward=diagnostic['hops'],reply=response['hops'],reason=reason)

def autoconfigure(lab,name,interface):
 d=lab._device(name);p=lab._iface(name,interface)
 for router in lab.devices.values():
  if not router.config.get('ipv6_routing'):continue
  for rp in router.interfaces.values():
   if not rp.ipv6 or not lab.l2_reachable((name,interface),(router.name,rp.name)):continue
   prefix=IPv6Interface(rp.ipv6).network
   if prefix.prefixlen!=64:continue
   iid=int(IPv6Address(link_local(p)))&((1<<64)-1);p.ipv6=str(IPv6Interface(str(IPv6Address(int(prefix.network_address)|iid))+'/64'))
   d.config['ipv6_gateway']=str(IPv6Interface(rp.ipv6).ip)
   if router.config.get('ipv6_dns_server'):d.config['ipv6_dns_server']=router.config['ipv6_dns_server']
   return p.ipv6
 raise LabError('no reachable IPv6 router advertisement with a /64 prefix')


def pool(lab,name,b):
 from .simulation import label
 d=lab._device(name);pools=d.config.setdefault('dhcpv6_pools',{});key=label(b.get('name','LAN'),64)
 if b.get('delete'):pools.pop(key,None);return pools
 network=IPv6Network(b['prefix'],strict=False)
 if network.num_addresses<8:raise LabError('DHCPv6 prefix needs at least eight addresses')
 gateway=str(IPv6Address(b['gateway'])) if b.get('gateway') else None
 dns=str(IPv6Address(b['dns_server'])) if b.get('dns_server') else None
 enabled=b.get('enabled',True)
 if not isinstance(enabled,bool):raise LabError('DHCPv6 enabled must be boolean')
 pools[key]={'prefix':str(network),'gateway':gateway,'dns_server':dns,'enabled':enabled,'leases':pools.get(key,{}).get('leases',{})}
 return pools[key]


def dhcp(lab,name,interface):
 d=lab._device(name);p=lab._iface(name,interface)
 if not lab._iface_effective_up(name,interface):raise LabError('DHCPv6 client interface is down')
 for server in lab.devices.values():
  if server.name==name or not server.powered:continue
  for entry in server.config.get('dhcpv6_pools',{}).values():
   if not entry['enabled']:continue
   network=IPv6Network(entry['prefix'])
   for remote in server.interfaces.values():
    if not remote.ipv6 or IPv6Interface(remote.ipv6).ip not in network or not lab.l2_reachable((name,interface),(server.name,remote.name)):continue
    address=entry['leases'].get(p.mac)
    if address is None:
     used={IPv6Interface(port.ipv6).ip for node in lab.devices.values() for port in node.interfaces.values() if port.ipv6}
     used.update(IPv6Address(value) for value in entry['leases'].values())
     address=next((str(network.network_address+offset) for offset in range(2,min(network.num_addresses,65536)) if network.network_address+offset not in used),None)
     if address is None:raise LabError('DHCPv6 allocation range exhausted')
     entry['leases'][p.mac]=address
    p.ipv6=address+'/'+str(network.prefixlen)
    if entry['gateway']:d.config['ipv6_gateway']=entry['gateway']
    if entry['dns_server']:d.config['ipv6_dns_server']=entry['dns_server']
    lab._packet_event('DHCPv6',name,server.name,'Solicit / Advertise / Request / Reply: '+p.ipv6)
    return {'address':p.ipv6,'gateway':entry['gateway'],'dns_server':entry['dns_server'],'server':server.name}
 raise LabError('no reachable DHCPv6 server on the client VLAN')

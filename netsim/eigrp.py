"""Simplified IPv4 EIGRP adjacency and reachable-prefix propagation.

This is a deterministic hop-based model; it does not simulate DUAL or EIGRP
packet timing. Only matching AS numbers and enabled network interfaces peer.
"""
from ipaddress import IPv4Network
from .model import LabError,Route
from .simulation import integer

def configure(lab,body):
 d=lab._device(body['device'])
 if d.kind!='router':raise LabError('EIGRP requires a router')
 asn=integer(body.get('asn'),1,65535);key=str(asn);processes=d.config.setdefault('eigrp',{})
 if 'delete_process' in body and not isinstance(body['delete_process'],bool):raise LabError('delete_process must be boolean')
 if body.get('delete_process'):
  processes.pop(key,None);lab.recompute_ospf();return processes
 networks=processes.setdefault(key,[])
 if 'network' in body:
  network=str(IPv4Network(body['network'],strict=False));enabled=body.get('enabled',True)
  if not isinstance(enabled,bool):raise LabError('enabled must be boolean')
  if enabled and network not in networks:networks.append(network)
  if not enabled and network in networks:networks.remove(network)
 lab.recompute_ospf();return processes

def recompute(lab):
 for d in lab.devices.values():d.routes=[r for r in d.routes if r.source!='eigrp']
 routers=[d for d in lab.devices.values() if d.kind=='router' and d.powered and d.config.get('eigrp')]
 for origin in routers:
  own={r.network for r in lab.connected_routes(origin.name)};learned={}
  for asn,networks in sorted(origin.config['eigrp'].items()):
   def active(d,p):
    return bool(p.ip and lab._iface_effective_up(d.name,p.name) and any(p.ipv4.ip in IPv4Network(n) for n in d.config.get('eigrp',{}).get(asn,[])))
   queue=[(origin,0,None)];seen={origin.name}
   while queue:
    node,hops,first=queue.pop(0)
    if hops:
     for route in lab.connected_routes(node.name):
      if active(node,node.interfaces[route.interface]) and route.network not in own:
       candidate=(hops,first)
       if route.network not in learned or candidate<learned[route.network]:learned[route.network]=candidate
    for neighbor in sorted(routers,key=lambda item:item.name):
     if neighbor.name in seen or asn not in neighbor.config.get('eigrp',{}):continue
     found=None
     for a in node.interfaces.values():
      if not active(node,a):continue
      for b in neighbor.interfaces.values():
       if active(neighbor,b) and a.ipv4.network==b.ipv4.network and lab.l2_reachable((node.name,a.name),(neighbor.name,b.name)):
        found=str(b.ipv4.ip);break
      if found:break
     if found:seen.add(neighbor.name);queue.append((neighbor,hops+1,first or found))
  for network,(hops,hop) in sorted(learned.items()):origin.routes.append(Route(network,next_hop=hop,source='eigrp',metric=90+hops))

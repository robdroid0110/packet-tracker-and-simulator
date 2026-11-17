"""Additional reference commands that operate on existing NetworkLab engines.

Return None only for commands this adapter does not recognize. Unsupported
protocols are deliberately rejected by IOSSession rather than acknowledged.
"""
import json,re,shlex
from ipaddress import IPv4Address,IPv4Network
from .model import LabError


def interface_name(device,value):
 aliases={'gigabitethernet':'g','fastethernet':'fa','ethernet':'eth','serial':'s','vlan':'vlan'}
 value=value.lower()
 for prefix,short in aliases.items():
  if value.startswith(prefix):value=short+value[len(prefix):];break
 matches=[name for name in device.interfaces if name.lower()==value]
 if len(matches)==1:return matches[0]
 return value


def execute(session,line,low):
 lab=session.lab;d=lab._device(session.device);parts=shlex.split(line)
 from .device_config import action
 def configure(**body):return action(lab,{'device':d.name,**body})
 if low in ('exit','end'):return None
 if low in ('?','help'):
  return 'Supported subset: enable, disable, configure terminal, interface, router ospf/rip, ip route, ip access-list, ip dhcp pool, show, ping, traceroute, copy, clear, reload. Unsupported protocol commands return an error.'
 if low.startswith('do ') and session.mode not in ('user','priv'):
  mode=session.mode
  try:session.mode='priv';return session._execute(line[3:],low[3:])
  finally:session.mode=mode
 if low in ('logout','quit'):
  session.mode='user';session.interface=None;return 'Session closed'
 if low.startswith('terminal length ') or low.startswith('terminal width '):
  if len(parts)!=3 or not parts[2].isdigit() or not 0<=int(parts[2])<=512:raise LabError('terminal size must be 0..512')
  return 'Terminal uses the browser scrollback; pagination is disabled'
 if low.startswith('ping ip ') or low.startswith('ping ipv6 '):return lab.ping(d.name,parts[2])[1]
 if low.startswith('show ipv6 '):
  from .ipv6 import routes,link_local
  if low=='show ipv6 route':return json.dumps(routes(lab,d.name),indent=2)
  if low in ('show ipv6 neighbors','show ipv6 neighbour'):return json.dumps(d.config.get('ndp',{}),indent=2)
  if low in ('show ipv6 interface','show ipv6 interface brief'):return '\n'.join(f'{p.name} {p.ipv6 or "unassigned"} link-local {link_local(p)}' for p in d.interfaces.values())
 if low=='show ip protocols':return json.dumps({'ospf':d.ospf_enabled,'ospf_networks':d.ospf_networks,'ospf_areas':d.ospf_areas,'ospf_auto':d.ospf_auto,'rip':d.config.get('rip',[]),'eigrp':d.config.get('eigrp',{})},indent=2)
 if low in ('show ip ospf neighbor','show ip ospf neighbors','show ip ospf interface'):
  state=lab.ospf_status(d.name)
  return json.dumps(state['interfaces' if low.endswith('interface') else 'neighbors'],indent=2)
 if low=='show ip dhcp binding':return json.dumps({n:p.leases for n,p in d.dhcp_pools.items()},indent=2)
 if low=='show ip dhcp pool':return json.dumps({n:vars(p) for n,p in d.dhcp_pools.items()},indent=2)
 if low.startswith('show interfaces ') or low.startswith('show interface '):
  name=interface_name(d,parts[2]);p=lab._iface(d.name,name)
  return f'{name} is {"up" if p.admin_up else "administratively down"}, line protocol is {"up" if lab._iface_effective_up(d.name,name) else "down"}\n'+json.dumps(vars(p),indent=2)
 if low=='show clock':return json.dumps(d.config.get('clock'))
 if low in ('show flash','show file systems'):return '\n'.join(d.config.get('files',{}))
 if low.startswith('clear '):
  if session.mode!='priv':raise LabError('privileged EXEC mode required')
  if low in ('clear arp','clear arp-cache','clear ip arp'):d.arp_table.clear();d.config.pop('ndp',None);return ''
  if low in ('clear mac address-table dynamic','clear mac-address-table dynamic'):d.mac_table.clear();return ''
  if low=='clear ip nat translation *':d.nat_sessions.clear();return ''
  raise LabError('unsupported clear command')
 if session.mode=='config':
  if low.startswith('interface '):
   name=interface_name(d,line.split(None,1)[1])
   if name not in d.interfaces:return None
   session.interface=name;session.mode='interface';return ''
  if low.startswith('ip default-gateway '):d.default_gateway=str(IPv4Address(parts[2]));return ''
  if low.startswith('ip name-server '):d.dns_server=str(IPv4Address(parts[2]));return ''
  if low.startswith('no ip route '):
   network=str(IPv4Network(parts[3]+'/'+parts[4],strict=False));d.routes=[r for r in d.routes if not (r.source=='static' and r.network==network and (len(parts)<6 or r.next_hop==parts[5]))];lab.recompute_ospf();return ''
  if low.startswith('ip route ') and len(parts)==5:
   name=interface_name(d,parts[4])
   if name in d.interfaces:lab.add_static_route(d.name,str(IPv4Network(parts[2]+'/'+parts[3],strict=False)),interface=name);return ''
  if low.startswith('ip access-list '):
   if len(parts)!=4 or parts[2] not in ('standard','extended'):raise LabError('ip access-list standard|extended NAME')
   session.context={'acl':parts[3],'standard':parts[2]=='standard'};session.mode='acl';return ''
  if low.startswith('ip dhcp pool '):
   if len(parts)!=4:raise LabError('ip dhcp pool NAME')
   session.context={'pool':parts[3]};session.mode='dhcp';d.config.setdefault('ios_dhcp_pools',{}).setdefault(parts[3],{});return ''
  if low.startswith('no ip dhcp pool '):
   name=parts[4];d.dhcp_pools.pop(name,None);d.config.get('ios_dhcp_pools',{}).pop(name,None);return ''
  if low=='no router rip':
   d.config['rip']=[];lab.recompute_ospf();return ''
  if low.startswith('no router ospf '):
   if len(parts)!=4 or not parts[3].isdigit() or int(parts[3])!=d.ospf_process_id:
    raise LabError('OSPF process is not configured')
   lab.disable_ospf(d.name,clear=True);return ''
 if session.mode=='acl':
  from .ios import _ios_acl_operand
  from .acl_ports import parse
  context=session.context;name=context['acl'];index=0;sequence=None
  if parts[0].isdigit():sequence=int(parts[0]);index+=1
  if parts[index]=='no':
   if len(parts)!=index+2 or not parts[index+1].isdigit():raise LabError('no SEQUENCE')
   d.acls[name]=[r for r in d.acls.get(name,[]) if r.sequence!=int(parts[index+1])];return ''
  policy=parts[index];index+=1
  if policy not in ('permit','deny'):raise LabError('permit or deny required')
  if context['standard']:
   source,index=_ios_acl_operand(parts,index);protocol='ip';destination='any';sp=dp=None
  else:
   protocol=parts[index];source,index=_ios_acl_operand(parts,index+1);sp,index=parse(parts,index);destination,index=_ios_acl_operand(parts,index);dp,index=parse(parts,index)
  if index!=len(parts):raise LabError('unsupported ACL suffix')
  lab.add_acl_rule(d.name,name,policy,protocol,source,destination,sequence,sp,dp);return ''
 if session.mode=='dhcp':
  key=session.context['pool'];settings=d.config.setdefault('ios_dhcp_pools',{}).setdefault(key,{})
  if parts[0]=='network' and len(parts)==3:settings['network']=str(IPv4Network(parts[1]+'/'+parts[2],strict=False))
  elif parts[0] in ('default-router','dns-server') and len(parts)==2:settings[parts[0]]=str(IPv4Address(parts[1]))
  else:raise LabError('DHCP pool: network ADDRESS MASK, default-router IP or dns-server IP')
  if 'network' in settings and 'default-router' in settings:
   network=IPv4Network(settings['network']);first=network.network_address+2;last=network.broadcast_address-1
   lab.add_dhcp_pool(d.name,key,str(network),settings['default-router'],str(first),str(last),settings.get('dns-server'))
  return ''
 if session.mode=='interface':
  name=session.interface
  if low in ('ip address dhcp','ipv6 address dhcp','ipv6 address autoconfig'):
   if low=='ip address dhcp':return lab.dhcp_request(d.name,name)
   return str(configure(action='ipv6_dhcp' if low.endswith('dhcp') else 'ipv6_autoconfigure',interface=name))
  if low.startswith(('mtu ','tx-ring-limit ','mac-address ')):
   key={'mtu':'mtu','tx-ring-limit':'tx_ring_limit','mac-address':'mac'}[parts[0]];value=parts[1]
   if key=='mac':value=value.replace('.','').replace(':','');value=':'.join(value[i:i+2] for i in range(0,len(value),2))
   configure(action='interface',interface=name,**{key:int(value) if key!='mac' else value});return ''
  if low in ('mdix auto','no mdix auto'):configure(action='interface',interface=name,auto_mdix=not low.startswith('no '));return ''
  if low=='no description':lab._iface(d.name,name).description='';return ''
 return None

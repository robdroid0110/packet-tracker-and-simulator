"""Simulated PPPoE, VPN, host firewalls and client utilities; no host networking."""
from copy import deepcopy
from ipaddress import IPv4Address,IPv4Network,IPv4Interface,IPv6Network
from .model import LabError,Interface,Link,Route
from .device_services import conf,service,transit,auth
from .simulation import label,integer


def pppoe(lab,d,b):
 interface=b.get('interface') or next(iter(d.interfaces));p=lab._iface(d.name,interface);c=conf(d)
 if b.get('operation','connect')=='disconnect':
  old=c.pop('pppoe_session',None)
  if old:p.ip=old.get('previous_ip');d.default_gateway=old.get('previous_gateway')
  return {'connected':False}
 c['pppoe_pending']=True
 for server in lab.devices.values():
  s=service(server,'pppoe')
  if not s.get('enabled') or b.get('server') and b['server'] not in (server.name,*[str(i.ipv4.ip) for i in server.interfaces.values() if i.ip]):continue
  for remote in server.interfaces.values():
   if not lab.l2_reachable((d.name,interface),(server.name,remote.name)):continue
   auth(server,'pppoe',b.get('username'),b.get('password'))
   network=IPv4Network(s.get('prefix','10.254.0.0/24'));gateway=str(IPv4Address(s.get('gateway',network.network_address+1)))
   if network.num_addresses<8:raise LabError('PPPoE pool needs at least eight addresses')
   used={str(i.ipv4.ip) for node in lab.devices.values() for i in node.interfaces.values() if i.ip}
   address=next((str(network.network_address+i) for i in range(2,min(network.num_addresses-1,65536)) if str(network.network_address+i) not in used),None)
   if not address:raise LabError('PPPoE address pool exhausted')
   c['pppoe_session']={'server':server.name,'interface':interface,'previous_ip':p.ip,'previous_gateway':d.default_gateway,'address':address}
   p.ip=address+'/'+str(network.prefixlen);remote.ip=gateway+'/'+str(network.prefixlen);d.default_gateway=gateway
   c.pop('pppoe_pending',None);lab._packet_event('PPPOE',d.name,server.name,'Authenticated PPPoE session');lab.recompute_ospf();return {'connected':True,'address':p.ip,'gateway':gateway}
 raise LabError('no reachable PPPoE server or port mapping')

def dialup(lab,d,b):
 c=conf(d)
 if b.get('operation','dial')=='disconnect':
  old=c.pop('dialup_session',None)
  if old:
   cloud=lab.devices.get(old['cloud']);remote=lab.devices.get(old['server'])
   if cloud:conf(cloud)['cloud']['mappings']=old['mappings']
   if remote:remote.config.get('dialup_sessions',{}).pop(d.name,None)
  lab.recompute_ospf();return {'connected':False}
 interface=b.get('interface') or next((p.name for p in d.interfaces.values() if p.media=='modem'),None)
 p=lab._iface(d.name,interface)
 if p.media!='modem':raise LabError('dial-up requires a modem interface')
 peer=lab.peer(d.name,interface)
 if not peer:raise LabError('modem must be connected to a phone cloud')
 cloud=lab._device(peer[0]);cloudconf=conf(cloud)['cloud'];number=label(b.get('number'),40)
 port=next((n for n,v in cloudconf.get('ports',{}).items() if v.get('phone_number')==number),None)
 if not port or port==peer[1]:raise LabError('phone number is unavailable')
 remote=lab.peer(cloud.name,port)
 if not remote:raise LabError('called modem is disconnected')
 server=lab._device(remote[0]);user=conf(server)['users'].get(b.get('username'))
 if not user or user.get('password')!=b.get('password'):raise LabError('dial-up authentication failed')
 if not lab.link_operational(lab.link_for(d.name,interface)) or not lab.link_operational(lab.link_for(*remote)):raise LabError('phone line has no carrier')
 if c.get('dialup_session'):raise LabError('disconnect the existing call first')
 previous=deepcopy(cloudconf.get('mappings',[]))
 if any(port in (m['a'],m['b']) for m in previous):raise LabError('called modem is busy')
 cloudconf.setdefault('mappings',[]).append({'a':peer[1],'b':port})
 c['dialup_session']={'cloud':cloud.name,'server':server.name,'interface':interface,'number':number,'mappings':previous}
 conf(server).setdefault('dialup_sessions',{})[d.name]=True
 lab.recompute_ospf();lab._packet_event('PPP',d.name,server.name,'Authenticated modem call; IP settings remain manual')
 return {'connected':True,'server':server.name,'number':number}


def vpn(lab,d,b):
 c=conf(d)
 if b.get('operation','connect')=='disconnect':
  session=c.pop('vpn_session',None)
  if session:
   lab.links=[l for l in lab.links if l.cable!='vpn' or d.name not in (l.a_device,l.b_device)]
   d.interfaces.pop('vpn0',None);d.routes=[r for r in d.routes if r.source!='vpn']
   server=lab.devices.get(session['server'])
   if server:server.interfaces.pop('vpn@'+d.name,None)
  return {'connected':False}
 server,ip=transit(lab,d.name,b['server'],'vpn');s=service(server,'vpn');auth(server,'vpn',b.get('username'),b.get('password'))
 if s.get('group')!=b.get('group') or s.get('key')!=b.get('key'):raise LabError('VPN group/key mismatch')
 network=IPv4Network(b.get('network',s.get('network','10.0.0.0/8')),strict=False)
 # The underlay is evaluated before virtual routes/links are installed.
 ok,go,ret=lab._transit(d.name,ip,'udp')
 if not ok:raise LabError('VPN underlay unreachable')
 from .simulation import _expanded_path
 path=_expanded_path(lab,go);underlay=[]
 for a,bnode in zip(path,path[1:]):
  for link in lab.links:
   if {link.a_device,link.b_device}=={a,bnode}:underlay.append([list(e) for e in link.endpoints()])
 index=sum('vpn_session' in n.config for n in lab.devices.values())
 if index>=16000:raise LabError('VPN session pool exhausted')
 base=int(IPv4Address('10.253.0.0'))+index*4
 local=str(IPv4Address(base+2));remote=str(IPv4Address(base+1))
 d.interfaces['vpn0']=Interface('vpn0',ip=local+'/30',media='vpn')
 server.interfaces['vpn@'+d.name]=Interface('vpn@'+d.name,ip=remote+'/30',media='vpn')
 server.kind='router';lab.links.append(Link(d.name,'vpn0',server.name,'vpn@'+d.name,'vpn'))
 d.routes.append(Route(str(network),next_hop=remote,source='vpn'))
 c['vpn_session']={'server':server.name,'underlay':underlay,'network':str(network),'address':local}
 lab.recompute_ospf();lab._packet_event('VPN',d.name,server.name,'Authenticated simulated VPN tunnel (no cryptographic encryption)')
 return {'connected':True,'address':local,'network':str(network),'encrypted':False}

def vpn_up(lab,link):
 client=lab.devices[link.a_device];session=client.config.get('vpn_session')
 if not session or session['server']!=link.b_device:return False
 for endpoints in session['underlay']:
  found=next((l for l in lab.links if l.cable!='vpn' and {tuple(e) for e in l.endpoints()}=={tuple(e) for e in endpoints}),None)
  if not found or not lab.link_operational(found):return False
 return True

def host_firewall(lab,d,b):
 version=integer(b.get('version',4),4,6)
 if version not in (4,6):raise LabError('IP version must be 4 or 6')
 key='ipv6_firewall' if version==6 else 'host_firewall';c=conf(d);rules=c.setdefault(key,[])
 if b.get('clear'):rules.clear();return rules
 action=b.get('policy','deny');protocol=b.get('protocol','ipv6' if version==6 else 'ip')
 if action not in ('permit','deny') or protocol not in ('ip','ipv6','icmp','icmpv6','tcp','udp'):raise LabError('invalid firewall policy')
 network=IPv6Network if version==6 else IPv4Network;anynet='::/0' if version==6 else '0.0.0.0/0'
 rules.append({'action':action,'protocol':protocol,'source':str(network(b.get('source',anynet),strict=False)),'destination':str(network(b.get('destination',anynet),strict=False))})
 return rules

def host_permits(d,source,destination,protocol):
 rules=d.config.get('host_firewall',[])
 if not rules:return True
 for r in rules:
  if r['protocol'] not in ('ip',protocol):continue
  if IPv4Address(source) in IPv4Network(r['source']) and IPv4Address(destination) in IPv4Network(r['destination']):return r['action']=='permit'
 return False

def historian_query(lab,d,b):
 server,ip=transit(lab,d.name,b['server'],'historian')
 if service(server,'historian').get('users'):auth(server,'historian',b.get('username'),b.get('password'))
 return [deepcopy(r) for r in conf(server)['industrial'].get('records',[]) if (not b.get('source') or r['device']==b['source']) and (not b.get('tag') or r['tag']==b['tag'])]

def apply(lab,b):
 d=lab._device(b['device']);action=b['action']
 if action=='dialup':return dialup(lab,d,b)
 if action=='pppoe':return pppoe(lab,d,b)
 if action=='vpn':return vpn(lab,d,b)
 if action=='host_firewall':return host_firewall(lab,d,b)
 if action=='historian_query':return historian_query(lab,d,b)
 if action=='management_login':return management_login(lab,d,b)
 if action=='management_apply':return management_apply(lab,d,b)
 raise LabError('unsupported client action')


def management_login(lab,d,b):
 server,ip=transit(lab,d.name,b['server'],b.get('protocol','http'));c=conf(server)
 from .device_services import profile
 family=profile(server)
 if family not in ('home-router','meraki','controller','wlc','observer','firewall','iox-router'):raise LabError('target has no web management interface')
 users=c['services'].get('controller',{}).get('users',{}) or c['users']
 username=b.get('username');password=b.get('password','')
 if not users and family in ('controller','observer','wlc') and b.get('setup'):
  users[__import__('netsim.simulation',fromlist=['label']).label(username,64)]={'password':label(password,128),'permissions':['admin']};c['users']=users
 elif not users:
  if family=='meraki':users={c['controller'].get('serial',server.name):{'password':''}}
  else:users={'admin':{'password':'admin'}}
 if username not in users or users[username]['password']!=password:raise LabError('web management login failed')
 import uuid
 token=uuid.uuid4().hex;conf(d).setdefault('management_sessions',{})[token]={'target':server.name,'server':ip,'username':username,'protocol':b.get('protocol','http'),'expires':lab.simulation['master_time']+3600}
 return {'token':token,'device':server.name,'profile':family}


def management_apply(lab,d,b):
 session=d.config.get('management_sessions',{}).get(b.get('token'))
 if not session or session['expires']<lab.simulation['master_time']:raise LabError('web management session is missing or expired')
 server,ip=transit(lab,d.name,session['server'],session['protocol'])
 settings=b.get('settings')
 if server.name!=session['target'] or not isinstance(settings,dict) or settings.get('action') in ('management_apply','management_login','console','remote_cli'):raise LabError('invalid web management operation')
 from .device_config import _apply
 return _apply(lab,{**settings,'device':server.name})

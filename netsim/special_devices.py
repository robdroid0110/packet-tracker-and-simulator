"""Wireless, controller, WAN relay and industrial models for device-family labs."""
from __future__ import annotations
from copy import deepcopy
from datetime import datetime,timezone
from ipaddress import IPv4Address,IPv4Interface,IPv4Network
import csv,io,json,re,uuid
from .model import LabError,Interface,Link
from .simulation import label,integer,finite
from .device_services import conf,service,profile,transit,auth


def _radio(d):
 return d.config.get('wireless',{})

def configure_wireless(lab,d,b):
 c=conf(d);w=deepcopy(c['wireless'])
 for key in ('ssid','security','key','channel','radius_server','radius_secret','mac_mode','macs','band','controller','group'):
  if key in b:w[key]=b[key]
 w.setdefault('ssid','PacketTracker');w.setdefault('security','open');w.setdefault('key','');w.setdefault('channel',6)
 label(w['ssid'],32);integer(w['channel'],1,165)
 if w['security'] not in ('open','wep','wpa-psk','wpa2-psk','wpa-enterprise','wpa2-enterprise'):raise LabError('unsupported wireless security')
 if w['security']=='wep' and not re.fullmatch(r'[0-9a-fA-F]{10}',w['key']):raise LabError('WEP needs 10 hexadecimal digits')
 if w['security'] in ('wpa-psk','wpa2-psk') and not 8<=len(w['key'])<=63:raise LabError('WPA passphrase must contain 8..63 characters')
 if w['security'].endswith('enterprise'):
  w['radius_server']=str(IPv4Address(w.get('radius_server','')));label(w.get('radius_secret'),128)
 if 'range_m' in b:w['range_m']=finite(b['range_m'],.1,100000)
 w.setdefault('range_m',140)
 if w.get('mac_mode','off') not in ('off','allow','deny') or not isinstance(w.get('macs',[]),list):raise LabError('invalid MAC filter')
 w['macs']=[x.lower() for x in w.get('macs',[])]
 if any(not re.fullmatch(r'[0-9a-f]{2}(?::[0-9a-f]{2}){5}',x) for x in w['macs']):raise LabError('invalid MAC filter entry')
 c['wireless']=w
 home=profile(d) in ('home-router','meraki')
 d.kind='router' if home else 'switch'
 if 'wlan0' not in d.interfaces:d.interfaces['wlan0']=Interface('wlan0',media='wifi',bridge_group='lan' if home else None)
 if home:
  for index in range(1,5):
   name='Ethernet'+str(index)
   if name not in d.interfaces:d.interfaces[name]=Interface(name,bridge_group='lan')
  if 'lan0' not in d.interfaces:d.interfaces['lan0']=Interface('lan0',media='bridge',bridge_group='lan')
  if 'lan_ip' in b:d.interfaces['lan0'].ip=str(IPv4Interface(b['lan_ip']))
  elif not d.interfaces['lan0'].ip:d.interfaces['lan0'].ip='192.168.0.1/24'
  if 'wan_ip' in b:d.interfaces[next(iter(d.interfaces))].ip=str(IPv4Interface(b['wan_ip']))
  if 'gateway' in b:
   d.default_gateway=str(IPv4Address(b['gateway']));lab.add_static_route(d.name,'0.0.0.0/0',next_hop=d.default_gateway)
  wan=next(iter(d.interfaces));d.interfaces[wan].nat_role='outside';d.interfaces['lan0'].nat_role='inside'
  for name,p in d.interfaces.items():
   if p.bridge_group=='lan':p.nat_role='inside'
  if 'nat' in b and not isinstance(b['nat'],bool):raise LabError('nat must be boolean')
  if 'dhcp' in b and not isinstance(b['dhcp'],bool):raise LabError('dhcp must be boolean')
  if not b.get('nat',True):d.nat_overload=[x for x in d.nat_overload if x.get('outside_iface')!=wan]
  if not b.get('dhcp',True):d.dhcp_pools.pop('homeLAN',None)
  if b.get('nat',True):lab.add_nat_overload(d.name,str(d.interfaces['lan0'].ipv4.network),wan)
  if b.get('dhcp',True):
   network=d.interfaces['lan0'].ipv4.network
   if network.num_addresses<8:raise LabError('home LAN needs a subnet of at least eight addresses')
   lab.add_dhcp_pool(d.name,'homeLAN',str(network),str(d.interfaces['lan0'].ipv4.ip),str(network.network_address+2),str(network.broadcast_address-1),b.get('dns_server'))
 refresh_wireless(lab);lab.recompute_ospf();return w

def _compatible(lab,client,ap,port):
 from .physical_distance import distance_m
 w=_radio(ap);c=client.config.get('wireless_client',{})
 if not ap.powered or not client.powered or not w or c.get('ssid')!=w.get('ssid'):return False
 if lab.physical_device_details.get(client.name,{}).get('surface')=='shelf':return False
 if not client.interfaces[port].admin_up or not ap.interfaces.get('wlan0',Interface('wlan0')).admin_up:return False
 if c.get('security','open')!=w.get('security','open'):return False
 if not w['security'].endswith('enterprise') and c.get('key','')!=w.get('key',''):return False
 if w.get('mac_mode')=='allow' and client.interfaces[port].mac not in w.get('macs',[]):return False
 if w.get('mac_mode')=='deny' and client.interfaces[port].mac in w.get('macs',[]):return False
 return distance_m(lab,client.name,ap.name)<=lab.radio_ranges.get(ap.name,w.get('range_m',140))+1e-8

def refresh_wireless(lab):
 if not any(d.config.get('wireless_client') or d.config.get('wireless') for d in lab.devices.values()):return
 from .physical_distance import distance_m
 # Keep interface identity and saved settings for associations that remain active.
 radios={(d.name,n):p for d in lab.devices.values() for n,p in d.interfaces.items() if n.startswith('radio@')}
 lab.links=[l for l in lab.links if l.cable!='wireless']
 for d in lab.devices.values():
  for name in list(d.interfaces):
   if name.startswith('radio@'):del d.interfaces[name]
 aps=[d for d in lab.devices.values() if d.config.get('wireless')]
 for client in lab.devices.values():
  c=client.config.get('wireless_client')
  if not c:continue
  port=c.get('interface','wlan0');c['associated']=None
  if port not in client.interfaces:continue
  candidates=[(0 if lab.device_locations.get(client.name)==lab.device_locations.get(ap.name) and lab.physical_locations.get(lab.device_locations.get(ap.name),{}).get('type')=='closet' else distance_m(lab,client.name,ap.name),index,ap) for index,ap in enumerate(aps) if _compatible(lab,client,ap,port)]
  if not candidates:continue
  ap=min(candidates,key=lambda item:item[:2])[2]
  name='radio@'+client.name;ap.interfaces[name]=radios.get((ap.name,name)) or Interface(name,media='wifi',bridge_group='lan' if ap.kind=='router' else None)
  lab.links.append(Link(client.name,port,ap.name,name,'wireless'));c['associated']=ap.name

def associate(lab,d,b):
 c=conf(d);port=b.get('interface') or next((n for n,p in d.interfaces.items() if p.media=='wifi'),'wlan0')
 if port not in d.interfaces:d.interfaces[port]=Interface(port,media='wifi')
 if d.interfaces[port].media!='wifi':raise LabError('wireless association requires a Wi-Fi interface')
 client={'ssid':label(b.get('ssid'),32),'security':b.get('security','open'),'key':b.get('key',''),'interface':port,'associated':None}
 c['wireless_client']=client
 # Enterprise credentials are checked over the AP's actual RADIUS path.
 enterprise=[a for a in lab.devices.values() if _radio(a).get('ssid')==client['ssid'] and _radio(a).get('security','').endswith('enterprise')]
 if enterprise:
  from .device_services import authenticate
  for ap in enterprise:
   try:authenticate(lab,{'device':ap.name,'server':_radio(ap)['radius_server'],'protocol':'radius','secret':_radio(ap)['radius_secret'],'username':b.get('username'),'password':b.get('password')});break
   except LabError:continue
  else:raise LabError('wireless RADIUS authentication failed')
 refresh_wireless(lab)
 if not c['wireless_client']['associated']:raise LabError('no compatible access point in range')
 if 'ip' in b:d.interfaces[port].ip=str(IPv4Interface(b['ip']))
 if b.get('gateway'):d.default_gateway=str(IPv4Address(b['gateway']))
 if b.get('dhcp'):lab.dhcp_request(d.name,port)
 lab.recompute_ospf();return deepcopy(c['wireless_client'])

def cloud_allows(d,a,b):
 mappings=d.config.get('cloud',{}).get('mappings')
 if mappings is None:return True
 return any({a,b}=={m['a'],m['b']} for m in mappings)

def cloud_map(lab,d,b):
 if profile(d) in ('cloud','patch-panel','bridge'):d.kind='switch'
 a=lab._iface(d.name,b['a_port']);other=lab._iface(d.name,b['b_port'])
 if a==other:raise LabError('cloud mapping needs different ports')
 pair={a.media,other.media}
 if not (pair<={'serial'} or pair<={'copper','fiber-mm','fiber-sm','modem','coax'}):raise LabError('incompatible cloud mapping media')
 c=conf(d);maps=c['cloud'].setdefault('mappings',[])
 if b.get('delete'):c['cloud']['mappings']=[m for m in maps if {m['a'],m['b']}!={a.name,other.name}]
 elif not any({m['a'],m['b']}=={a.name,other.name} for m in maps):maps.append({'a':a.name,'b':other.name,'dlci_a':integer(b.get('dlci_a',100),16,1007),'dlci_b':integer(b.get('dlci_b',200),16,1007)})
 d.kind='switch';lab.recompute_ospf();return c['cloud']

def controller(lab,d,b):
 c=conf(d);user=label(b['username'],64);password=label(b['password'],128)
 c['services'].setdefault('controller',{'enabled':True}).setdefault('users',{})[user]={'password':password,'permissions':['admin']}
 c['controller'].setdefault('inventory',{});c['controller'].setdefault('tokens',{})
 return {'username':user,'configured':True}

def discover(lab,d,b,observer=False):
 network=IPv4Network(b['network'],strict=False)
 if network.num_addresses>65536:raise LabError('discovery range is limited to /16 or smaller')
 inventory={}
 for target in lab.devices.values():
  if target.name==d.name or not target.powered:continue
  ip=next((str(p.ipv4.ip) for p in target.interfaces.values() if p.ip and p.ipv4.ip in network and lab._iface_effective_up(target.name,p.name)),None)
  if not ip:continue
  ok,go,ret=lab._transit(d.name,ip,'icmp')
  if not ok:continue
  if not observer and b.get('username'):
   user=conf(target)['users'].get(b['username'])
   if not user or user['password']!=b.get('password'):continue
  vulnerabilities=[]
  if service(target,'telnet')['enabled']:vulnerabilities.append('Plaintext Telnet enabled')
  if service(target,'ftp')['enabled']:vulnerabilities.append('Plaintext FTP enabled')
  if service(target,'http')['enabled']:vulnerabilities.append('Unencrypted HTTP enabled')
  if any(u['password'] in ('admin','cisco','password') for u in conf(target)['users'].values()):vulnerabilities.append('Weak simulated management credential')
  inventory[target.name]={'ip':ip,'model':target.model,'kind':target.kind,'interfaces':list(target.interfaces),'vulnerabilities':vulnerabilities,'reachable':True}
 c=conf(d);c['controller']['inventory']=inventory
 lab._packet_event('ICMP',d.name,d.name,'Discovery completed: '+str(len(inventory))+' devices')
 return inventory

def provision(lab,d,b):
 c=conf(d);name=b['target']
 if name not in c['controller'].get('inventory',{}):raise LabError('target must first be discovered')
 target=lab._device(name);ip=c['controller']['inventory'][name]['ip']
 ok,_,_=lab._transit(d.name,ip,'tcp')
 if not ok:raise LabError('managed device unreachable')
 from .device_config import _apply
 settings=b.get('settings')
 if not isinstance(settings,dict) or settings.get('action') not in ('global','interface','service','save_startup','wireless','firewall_rule'):raise LabError('unsupported provisioning action')
 return _apply(lab,{**settings,'device':target.name})

def licensing(lab,d,b):
 c=conf(d);operation=b.get('operation','status');lic=c['license']
 if operation=='status':return lic
 if operation=='issue':
  level=label(b.get('level','network-essentials'),64);token=uuid.uuid4().hex
  c['controller'].setdefault('tokens',{})[token]={'level':level,'target':b.get('target'),'used':False}
  return {'token':token,'level':level,'simulated':True}
 if operation=='register':
  server,ip=transit(lab,d.name,b['server'],'controller');record=conf(server)['controller'].get('tokens',{}).get(b['token'])
  if not record or record['used'] or record.get('target') not in (None,d.name):raise LabError('invalid, consumed or wrong-device license token')
  record['used']=True;lic.update(level=record['level'],registered=True,controller=server.name);return lic
 raise LabError('license operation must be status/issue/register')

def license_command(lab,name,line):
 d=lab._device(name);c=conf(d);parts=line.split();low=line.lower()
 if low.startswith('show license'):return json.dumps(c['license'],indent=2)
 if low.startswith('license smart url cslu '):c['license']['server']=parts[-1].removeprefix('http://').removeprefix('https://').split('/')[0];return ''
 if low.startswith('license boot level '):c['license']['requested_level']=parts[-1];return ''
 if low.startswith('license smart trust idtoken '):return json.dumps(licensing(lab,d,{'operation':'register','server':c['license'].get('server',''),'token':parts[4]}))
 raise LabError('unsupported simulated license command')

def iox(lab,d,b):
 c=conf(d);apps=c['iox'].setdefault('applications',{});op=b.get('operation');name=label(b.get('name','app'),64)
 if op=='list':return apps
 if op=='install':
  file=b.get('file')
  if file not in c['files']:raise LabError('application package must exist in device simulated files')
  if name in apps:raise LabError('application already installed')
  apps[name]={'file':file,'state':'installed','activated':False};return apps[name]
 if name not in apps:raise LabError('application not installed')
 if op=='uninstall':
  if apps[name]['state']=='running':raise LabError('stop application before uninstall')
  del apps[name];return
 if op in ('activate','deactivate'):apps[name]['activated']=op=='activate'
 elif op=='start':apps[name].update(state='running',activated=True)
 elif op=='stop':apps[name]['state']='stopped'
 else:raise LabError('IOx operation must be install/activate/start/stop/deactivate/uninstall/list')
 return apps[name]

def iox_command(lab,name,line):
 parts=line.split();d=lab._device(name)
 if line.lower().startswith('show iox') or parts[-1]=='list':return json.dumps(iox(lab,d,{'operation':'list'}),indent=2)
 verbs={'install','uninstall','activate','deactivate','start','stop'};verb=next((p for p in parts if p in verbs),None)
 if not verb:raise LabError('unsupported IOx lifecycle command')
 index=parts.index(verb);return json.dumps(iox(lab,d,{'operation':verb,'name':parts[index+1] if len(parts)>index+1 else 'app','file':parts[index+2] if len(parts)>index+2 else None}))

def industrial(lab,d,b):
 c=conf(d);s=c['industrial'];tags=b.get('tags',{})
 if not isinstance(tags,dict) or len(tags)>100:raise LabError('tags must be an object with at most 100 entries')
 for name,value in tags.items():label(name,64);finite(value,-1e9,1e9)
 s.setdefault('tags',{}).update(tags)
 if 'server' in b:s['server']=str(IPv4Address(b['server']))
 if 'enabled' in b:
  if not isinstance(b['enabled'],bool):raise LabError('enabled must be boolean')
  s['enabled']=b['enabled']
 return s

def plc_program(lab,d,b):
 blocks=b.get('blocks')
 if not isinstance(blocks,list) or len(blocks)>100:raise LabError('PLC program must contain at most 100 function blocks')
 allowed={'copy','and','or','not','xor','greater','less','equal','latch','timer','counter','add','multiply'}
 for block in blocks:
  if not isinstance(block,dict) or block.get('op') not in allowed:raise LabError('unsupported PLC function block')
  label(block.get('output'),64)
  if not isinstance(block.get('inputs',[]),list) or len(block.get('inputs',[]))>16:raise LabError('invalid PLC inputs')
  for value in block.get('inputs',[]):
   if isinstance(value,str):label(value,64)
   else:finite(value,-1e9,1e9)
  if 'preset' in block:finite(block['preset'],0,86400)
 c=conf(d);c['industrial'].update(program=deepcopy(blocks),block_state={});return blocks

def plc_run(lab,d,b):
 seconds=finite(b.get('seconds',.1),0,86400);c=conf(d);s=c['industrial'];tags=s.setdefault('tags',{});states=s.setdefault('block_state',{})
 for index,block in enumerate(s.get('program',[])):
  inputs=[tags.get(v,0) if isinstance(v,str) else v for v in block.get('inputs',[])];op=block['op'];values=inputs or [0]
  previous=states.setdefault(str(index),{'elapsed':0,'value':0,'input':False})
  if op=='copy':result=values[0]
  elif op=='and':result=int(all(values))
  elif op=='or':result=int(any(values))
  elif op=='not':result=int(not values[0])
  elif op=='xor':result=sum(bool(v) for v in values)%2
  elif op in ('greater','less','equal'):
   if len(values)!=2:raise LabError('comparison needs two inputs')
   result=int(values[0]>values[1] if op=='greater' else values[0]<values[1] if op=='less' else values[0]==values[1])
  elif op=='add':result=sum(values)
  elif op=='multiply':
   result=1
   for value in values:result*=value
  elif op=='latch':result=0 if len(values)>1 and values[1] else 1 if values[0] else previous['value']
  elif op=='timer':previous['elapsed']=previous['elapsed']+seconds if values[0] else 0;result=int(previous['elapsed']>=block.get('preset',1))
  elif op=='counter':
   if len(values)>1 and values[1]:previous['value']=0
   elif values[0] and not previous['input']:previous['value']+=1
   previous['input']=bool(values[0]);result=int(previous['value']>=block.get('preset',1))
  if op!='counter':previous['value']=result
  tags[block['output']]=finite(result,-1e12,1e12)
 # Hardware port values drive/read connected IoE devices without pretending to
 # execute arbitrary Python/JavaScript or real PLC firmware.
 for link in lab.links:
  if link.cable!='ioe':continue
  if link.a_device==d.name:port=link.a_if;other=lab.devices[link.b_device];remote=link.b_if
  elif link.b_device==d.name:port=link.b_if;other=lab.devices[link.a_device];remote=link.a_if
  else:continue
  if port in tags:conf(other)['industrial'].setdefault('tags',{})[remote]=tags[port]
 return deepcopy(tags)

def historian_import(lab,d,b):
 text=b.get('csv')
 if not isinstance(text,str) or len(text)>1000000:raise LabError('CSV exceeds 1MB')
 records=[]
 for row in csv.reader(io.StringIO(text)):
  if not row:continue
  if len(row)!=4:raise LabError('CSV needs device,tag,value,UTC timestamp')
  device,tag,value,stamp=(v.strip() for v in row)
  if device.lower()=='device name':continue
  label(device,80);label(tag,64);value=finite(float(value),-1e12,1e12)
  parsed=datetime.fromisoformat(stamp.replace('Z','+00:00'))
  if parsed.tzinfo is None:raise LabError('historian timestamp needs UTC timezone')
  records.append({'device':device,'tag':tag,'value':value,'timestamp':parsed.astimezone(timezone.utc).isoformat()})
 c=conf(d);s=c['industrial'];limit=integer(b.get('limit',s.get('limit',10000)),1,1000000);s['limit']=limit
 entries=s.setdefault('records',[]);entries.extend(records);del entries[:-limit];return len(records)

def historian_collect(lab,d,b):
 source=lab._device(b['source']);target,ip=transit(lab,source.name,d.name,'historian')
 if service(target,'historian').get('users'):auth(target,'historian',b.get('username'),b.get('password'))
 tags=conf(source)['industrial'].get('tags',{});s=conf(d)['industrial'];entries=s.setdefault('records',[])
 stamp=datetime.now(timezone.utc).isoformat()
 for tag,value in tags.items():entries.append({'device':source.name,'tag':tag,'value':value,'timestamp':stamp})
 del entries[:-s.get('limit',10000)];return len(tags)

def telephone(lab,d,b):
 c=conf(d);number=str(b['number'])
 if not re.fullmatch('[0-9]{1,16}',number):raise LabError('phone number must be 1..16 digits')
 server,ip=transit(lab,d.name,b['server'],'telephony')
 c['telephony']={'number':number,'server':server.name,'state':'idle','peer':None};return c['telephony']

def call(lab,d,b):
 c=conf(d);phone=c.get('telephony')
 if not phone:raise LabError('phone must be registered')
 operation=b.get('operation','dial')
 target=next((p for p in lab.devices.values() if p.config.get('telephony',{}).get('number')==str(b.get('number')) and p.config['telephony']['server']==phone['server']),None)
 if operation=='hangup':
  peer=lab.devices.get(phone.get('peer'))
  if peer:peer.config['telephony'].update(state='idle',peer=None)
  phone.update(state='idle',peer=None);return phone
 if not target or not target.powered:raise LabError('destination phone is unavailable')
 ok,_,_=lab._transit(d.name,next(str(p.ipv4.ip) for p in target.interfaces.values() if p.ip),'udp')
 if not ok:raise LabError('voice path unreachable')
 remote=target.config['telephony']
 if operation=='dial':
  if remote['state']!='idle':raise LabError('destination busy')
  phone.update(state='calling',peer=target.name);remote.update(state='ringing',peer=d.name)
 elif operation=='answer':
  if phone['state']!='ringing' or phone.get('peer')!=target.name:raise LabError('no incoming call from that number')
  phone['state']='connected';remote['state']='connected'
 elif operation=='note':
  if phone['state']!='connected':raise LabError('call is not connected')
  if b.get('note') not in ('C','D','E'):raise LabError('note must be C, D or E')
  remote['last_note']=b['note']
 else:raise LabError('call operation must be dial/answer/hangup/note')
 lab._packet_event('UDP',d.name,target.name,'Voice signalling '+operation);return phone

def apply(lab,b):
 d=lab._device(b['device']);action=b['action']
 if action=='wlc_wlan':return wlc_wlan(lab,d,b)
 if action=='wlc_group':return wlc_group(lab,d,b)
 if action=='wireless':return configure_wireless(lab,d,b)
 if action=='associate':return associate(lab,d,b)
 if action=='cloud_port':
  p=lab._iface(d.name,b['interface']);ports=conf(d)['cloud'].setdefault('ports',{});value=ports.setdefault(p.name,{})
  if 'phone_number' in b:
   if p.media!='modem':raise LabError('phone numbers require a modem port')
   number=label(b['phone_number'],40)
   if any(n!=p.name and v.get('phone_number')==number for n,v in ports.items()):raise LabError('duplicate phone number')
   value['phone_number']=number
  for key,allowed in (('provider',('DSL','Cable')),('lmi',('ANSI','Cisco','Q933a'))):
   if key in b:
    if b[key] not in allowed:raise LabError('invalid '+key)
    value[key]=b[key]
  if 'dlcis' in b:
   if not isinstance(b['dlcis'],list):raise LabError('DLCIs must be a list')
   value['dlcis']=[integer(x,16,1007) for x in b['dlcis']]
  return value
 if action=='cloud_map':return cloud_map(lab,d,b)
 if action=='controller':return controller(lab,d,b)
 if action=='discover':return discover(lab,d,b)
 if action=='observer_scan':return discover(lab,d,b,True)
 if action=='provision':return provision(lab,d,b)
 if action=='license':return licensing(lab,d,b)
 if action=='iox':return iox(lab,d,b)
 if action=='industrial':return industrial(lab,d,b)
 if action=='plc_program':return plc_program(lab,d,b)
 if action=='plc_run':return plc_run(lab,d,b)
 if action=='historian_import':return historian_import(lab,d,b)
 if action=='historian_collect':return historian_collect(lab,d,b)
 if action=='telephony':return telephone(lab,d,b)
 if action=='call':return call(lab,d,b)
 raise LabError('unsupported special device action')

def initialize_new(lab,d):
 """Typed default inventory for newly created models; never rewrite old labs."""
 if not d.model:return
 family=profile(d)
 if d.kind in ('router','switch'):
  d.interfaces.setdefault('console',Interface('console',media='console'))
 if d.kind in ('pc','server'):
  d.interfaces.setdefault('rs232',Interface('rs232',media='rs232'))
 if family in ('controller','observer','historian','wlc'):
  d.interfaces.setdefault('eth1',Interface('eth1'))
 if family=='plc':
  c=conf(d);tags=c['industrial'].setdefault('tags',{})
  for prefix,count in (('Digital',6),('Analog',10)):
   for i in range(count):
    name=prefix+str(i);d.interfaces[name]=Interface(name,media='ioe');tags[name]=0
 if family=='patch-panel':
  count=4 if 'wall' in d.model else 17 if 'fiber' in d.model else 24
  media='fiber-mm' if 'fiber' in d.model else 'copper';d.kind='switch';d.interfaces={}
  mappings=[]
  for index in range(1,count+1):
   for side in ('front','back'):d.interfaces[side+str(index)]=Interface(side+str(index),media=media)
   mappings.append({'a':'front'+str(index),'b':'back'+str(index)})
  d.config={'cloud':{'mappings':mappings},'passive':True}
 if family=='bridge' and any(x in d.model for x in ('hub','repeater','bridge')):
  d.kind='switch';count=10 if 'hub' in d.model else 2
  for index in range(count):d.interfaces.setdefault('eth'+str(index),Interface('eth'+str(index)))
 if family=='bridge' and 'modem' in d.model:
  d.kind='switch';media='modem' if 'dsl' in d.model else 'coax';d.interfaces['line0']=Interface('line0',media=media)
  d.config={'cloud':{'mappings':[{'a':'eth0','b':'line0'}]}}
 if family=='meraki':conf(d)['controller']['serial']=uuid.uuid5(uuid.NAMESPACE_DNS,d.model+':'+d.name).hex[:12]
 if family=='bridge' and 'splitter' in d.model:
  d.kind='switch';d.interfaces={str(i):Interface(str(i),media='coax') for i in range(3)};d.config={'cloud':{'mappings':[{'a':str(a),'b':str(b)} for a in range(3) for b in range(a+1,3)]}}
 if family=='cloud':
  d.kind='switch'
  for name,media in (('serial0','serial'),('serial1','serial'),('modem0','modem'),('coax0','coax')):d.interfaces[name]=Interface(name,media=media)
  d.config={'cloud':{'mappings':[]}}
 if family=='firewall':
  d.kind='router'
  for i in range(1,4):d.interfaces['eth'+str(i)]=Interface('eth'+str(i))
 if d.model=='7960':
  d.interfaces['eth0'].bridge_group='phone-lan'
  d.interfaces.setdefault('pc',Interface('pc',bridge_group='phone-lan'))
 if d.model in ('analog-phone-pt','power-distribution-device'):
  # These models do not have an Ethernet port; the generic default would
  # otherwise let automatic cabling invent an impossible copper connection.
  d.interfaces.pop('eth0',None)
 if d.model in ('7960','analog-phone-pt','home-voip-pt'):
  d.interfaces.setdefault('line0',Interface('line0',media='modem'))


def wlc_wlan(lab,d,b):
 c=conf(d);wlans=c['controller'].setdefault('wlans',{});name=label(b.get('ssid'),32)
 if b.get('delete'):wlans.pop(name,None)
 else:
  wlans[name]={'ssid':name,'security':b.get('security','open'),'key':b.get('key',''),'vlan':integer(b.get('vlan',1),1,4094),'radius_server':b.get('radius_server',''),'radius_secret':b.get('radius_secret','')}
 c['services'].setdefault('capwap',{})['enabled']=True
 return wlans

def wlc_group(lab,d,b):
 name=label(b.get('name','default-group'),64);aps=b.get('aps',[]);wlans=b.get('wlans',[]);c=conf(d)
 if not isinstance(aps,list) or not isinstance(wlans,list) or any(ssid not in c['controller'].get('wlans',{}) for ssid in wlans):raise LabError('group must reference defined WLANs/APs')
 for ap in aps:lab._device(ap)
 c['controller'].setdefault('groups',{})[name]={'aps':aps,'wlans':wlans}
 controller_ip=next((str(p.ipv4.ip) for p in d.interfaces.values() if p.ip),None)
 if not controller_ip:raise LabError('controller needs a management IP')
 for ap in aps:
  transit(lab,ap,controller_ip,'capwap')
  if wlans:configure_wireless(lab,lab.devices[ap],{**c['controller']['wlans'][wlans[0]],'controller':controller_ip,'group':name})
 return c['controller']['groups'][name]

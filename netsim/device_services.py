"""Functional, network-gated service/device models for configuration labs.

These services exchange simulated packets through NetworkLab's actual forwarding,
ACL/NAT and power logic. They never dial the Internet or execute user programs.
"""
from __future__ import annotations
from copy import deepcopy
from datetime import datetime,timezone,timedelta
from ipaddress import IPv4Address,IPv4Network
import csv,io,json,re,uuid
from .model import LabError,Interface
from .simulation import label,integer,finite

PORTS={'http':('tcp',80),'https':('tcp',443),'dns':('udp',53),'ftp':('tcp',21),'tftp':('udp',69),
 'smtp':('tcp',25),'pop3':('tcp',110),'ntp':('udp',123),'syslog':('udp',514),'radius':('udp',1812),
 'tacacs':('tcp',49),'snmp':('udp',161),'ssh':('tcp',22),'telnet':('tcp',23),'cip':('tcp',44818),
 'modbus':('tcp',502),'vpn':('udp',500),'pppoe':('udp',0),'capwap':('udp',5246),'telephony':('udp',5060),'ptp':('udp',319),'controller':('tcp',443),'historian':('tcp',44818),'observer':('tcp',443)}

def profile(d):
 model=(d.model or '').lower()
 if 'historian' in model:return 'historian'
 if 'observer' in model:return 'observer'
 if 'plc' in model:return 'plc'
 if 'controller' in model:return 'controller'
 if 'wlc' in model:return 'wlc'
 if model=='meraki-server':return 'controller'
 if 'meraki' in model:return 'meraki'
 if 'isa' in model or 'asa' in model:return 'firewall'
 if model in ('wrt300n','home-router','home router','home-gateway','home gateway'):return 'home-router'
 if any(x in model for x in ('accesspoint','lap-pt','3702')):return 'access-point'
 if 'cloud' in model:return 'cloud'
 if any(x in model for x in ('patch-panel','wall-mount','patch panel','wall mount')):return 'patch-panel'
 if any(x in model for x in ('hub-pt','repeater','bridge','splitter','modem')):return 'bridge'
 if 'phone' in model:return 'phone'
 if '819' in model or '829' in model:return 'iox-router'
 if 'ie-' in model or 'ie2000' in model:return 'industrial-switch'
 return d.kind

def conf(d):
 from .device_config import settings
 c=settings(d);d.config=c;return c

def service(d,name):
 from .device_config import settings
 c=settings(d)
 return c['services'].get(name,{'enabled':d.http_enabled if name=='http' else d.dns_enabled if name=='dns' else False})

def endpoint(lab,address):
 if address in lab.devices:
  d=lab.devices[address]
  ip=next((str(i.ipv4.ip) for i in d.interfaces.values() if i.ip),None)
  if not ip:raise LabError('target has no IP address')
  return d,ip
 ip=str(IPv4Address(address));owner=lab.owner_of_ip(ip)
 if not owner:raise LabError('no device owns destination IP')
 return lab.devices[owner[0]],ip

def transit(lab,source,target,protocol):
 d,ip=endpoint(lab,target)
 if protocol not in PORTS:raise LabError('unknown service protocol')
 ok,go,back=lab._transit(source,ip,PORTS[protocol][0],destination_port=PORTS[protocol][1]);lab._trace_packet(protocol.upper(),go,'Service request to '+str(PORTS[protocol][1]),ok)
 if not ok:raise LabError(protocol.upper()+' request unreachable or denied')
 if go and go[-1] in lab.devices:d=lab.devices[go[-1]]
 if not service(d,protocol).get('enabled'):raise LabError(protocol.upper()+' service is disabled')
 lab._trace_packet(protocol.upper(),back,'Service response',True)
 return d,ip

def auth(d,protocol,user,password,permission=None):
 accounts=service(d,protocol).get('users',{})
 account=accounts.get(user)
 if not account or account['password']!=password:raise LabError('authentication failed')
 if permission and permission not in account.get('permissions',[]):raise LabError('permission denied: '+permission)
 return account

def resolve_dns(lab,source,hostname):
 name=lab._valid_dns_name(hostname);client=lab._device(source)
 if not client.dns_server:raise LabError('Host Name Unresolved (DNS server not configured)')
 current=client.dns_server;seen=set()
 for _ in range(16):
  if (current,name) in seen:raise LabError('DNS alias/delegation loop')
  seen.add((current,name));d,ip=transit(lab,source,current,'dns');s=service(d,'dns');records=s.get('records',{})
  cache=conf(d)['services'].setdefault('dns',{'enabled':d.dns_enabled}).setdefault('cache',{})
  cached=cache.get(name)
  if cached and cached['expires']>lab.simulation['master_time']:return cached['value']
  cache.pop(name,None)
  if name in d.dns_records:
   address=d.dns_records[name];cache[name]={'value':address,'expires':lab.simulation['master_time']+records.get(name,{}).get('ttl',300)};return address
  record=records.get(name)
  if record and record['type']=='A':
   cache[name]={'value':record['value'],'expires':lab.simulation['master_time']+record.get('ttl',300)};return record['value']
  if record and record['type']=='CNAME':name=record['value'];continue
  delegates=[(zone,r) for zone,r in records.items() if r['type']=='NS' and (name==zone or name.endswith('.'+zone))]
  if delegates:
   zone,r=max(delegates,key=lambda item:len(item[0]));server=r['value']
   try:current=str(IPv4Address(server))
   except ValueError:
    current=d.dns_records.get(server)
    if not current:raise LabError('DNS delegation server address not found')
   continue
  lab._packet_event('DNS',d.name,source,'NXDOMAIN '+name,False);raise LabError('Host Name Unresolved (NXDOMAIN)')
 raise LabError('DNS recursion limit')

def _write_service(lab,d,body):
 name=body.get('service')
 if name not in PORTS and name not in ('dhcp','telephony','iot'):raise LabError('unknown service')
 enabled=body.get('enabled',True)
 if not isinstance(enabled,bool):raise LabError('enabled must be boolean')
 c=conf(d);s=deepcopy(service(d,name));s['enabled']=enabled
 for key in ('domain','community','write_community','secret','key','server_time','location','prefix','gateway','group','network'):
  if key in body:
   value=body[key]
   if not isinstance(value,str) or len(value)>256:raise LabError('invalid service '+key)
   s[key]=value
 if name=='dns' and 'domain' in s:s['domain']=lab._valid_dns_name(s['domain'])
 if name=='ntp' and s.get('server_time'):
  stamp=datetime.fromisoformat(s['server_time'].replace('Z','+00:00'))
  if stamp.tzinfo is None:raise LabError('NTP date/time needs a UTC offset')
 if name=='pppoe' and s.get('prefix'):
  s['prefix']=str(IPv4Network(s['prefix'],strict=False))
  if s.get('gateway') and IPv4Address(s['gateway']) not in IPv4Network(s['prefix']):raise LabError('PPPoE gateway is outside pool prefix')
 if name=='vpn' and s.get('network'):s['network']=str(IPv4Network(s['network'],strict=False))
 c['services'][name]=s
 if name=='http':d.http_enabled=enabled
 if name=='dns':d.dns_enabled=enabled
 return s

def _account(d,body):
 name=body.get('service');c=conf(d)
 if name not in ('ftp','smtp','pop3','radius','tacacs','controller','historian','observer','pppoe','vpn'):raise LabError('service does not have user accounts')
 s=c['services'].setdefault(name,{'enabled':False});users=s.setdefault('users',{});user=label(body.get('username'),64)
 if body.get('delete'):
  users.pop(user,None)
  if name in ('smtp','pop3'):c['services'].get('pop3' if name=='smtp' else 'smtp',{}).get('users',{}).pop(user,None)
  return
 permissions=body.get('permissions',['read','list'])
 if not isinstance(permissions,list) or any(x not in ('read','write','delete','rename','list','admin') for x in permissions):raise LabError('invalid permissions')
 users[user]={'password':label(body.get('password'),128),'permissions':permissions}
 # Email accounts belong to the same mailbox service for both SMTP and POP3.
 if name in ('smtp','pop3'):
  other='pop3' if name=='smtp' else 'smtp';c['services'].setdefault(other,{'enabled':False}).setdefault('users',{})[user]=deepcopy(users[user])

def transfer(lab,body):
 source=body['device'];protocol=body.get('protocol','tftp');op=body.get('operation','list')
 if protocol not in ('ftp','tftp'):raise LabError('transfer requires FTP or TFTP')
 d,ip=transit(lab,source,body['server'],protocol);c=conf(d);client=lab._device(source);cc=c if client is d else conf(client)
 if protocol=='ftp':auth(d,'ftp',body.get('username'),body.get('password'),{'get':'read','put':'write'}.get(op,op))
 file=body.get('file','')
 if op=='list':return sorted(c['files'])
 if not isinstance(file,str) or not file or len(file)>80 or any(ch in file for ch in ('/','\\')):raise LabError('invalid simulated file name')
 if op=='get':
  if file not in c['files']:raise LabError('file not found')
  cc['files'][file]=c['files'][file];return c['files'][file]
 if op=='put':
  content=body.get('content',cc['files'].get(file))
  if not isinstance(content,str) or len(content)>200000:raise LabError('file missing or exceeds 200KB')
  c['files'][file]=content;return 'stored'
 if op=='delete':
  if file not in c['files']:raise LabError('file not found')
  del c['files'][file];return 'deleted'
 if op=='rename':
  new=label(body['new_name'],80)
  if '/' in new or '\\' in new or new in c['files'] or file not in c['files']:raise LabError('invalid rename')
  c['files'][new]=c['files'].pop(file);return new
 raise LabError('unsupported transfer operation')

def mail(lab,body,receive=False):
 protocol='pop3' if receive else 'smtp';d,ip=transit(lab,body['device'],body['server'],protocol)
 user=body.get('username');auth(d,protocol,user,body.get('password'));c=conf(d)
 boxes=c['services'][protocol].setdefault('mailboxes',{})
 if receive:return deepcopy(c['services'].get('smtp',{}).get('mailboxes',{}).get(user,[]))
 address=body.get('to','');parts=address.rsplit('@',1)
 if len(parts)!=2:raise LabError('recipient must be user@domain')
 recipient,domain=parts;domain=lab._valid_dns_name(domain)
 dest=d
 if domain!=service(d,'smtp').get('domain'):
  address=resolve_dns(lab,d.name,domain);dest,_=transit(lab,d.name,address,'smtp')
 if recipient not in service(dest,'smtp').get('users',{}):raise LabError('mailbox does not exist')
 text=body.get('text','');subject=body.get('subject','')
 if not isinstance(text,str) or len(text)>20000 or not isinstance(subject,str) or len(subject)>256:raise LabError('email too large')
 message={'from':user+'@'+service(d,'smtp').get('domain','local'),'to':body['to'],'subject':subject,'text':text,'time':lab.simulation['master_time']}
 mailbox=conf(dest)['services']['smtp'].setdefault('mailboxes',{}).setdefault(recipient,[])
 if len(mailbox)>=200:raise LabError('mailbox limit reached')
 mailbox.append(message);return message

def authenticate(lab,body):
 protocol=body.get('protocol','radius')
 if protocol not in ('radius','tacacs'):raise LabError('AAA protocol must be radius or tacacs')
 server,ip=transit(lab,body['device'],body['server'],protocol);s=service(server,protocol)
 source=lab._source_ip_for_destination(body['device'],ip);client=s.get('clients',{}).get(source)
 if not client or client['secret']!=body.get('secret'):raise LabError('AAA client/shared-secret mismatch')
 auth(server,protocol,body.get('username'),body.get('password'));return {'authenticated':True,'protocol':protocol}

def clock_sync(lab,body):
 protocol=body.get('protocol','ntp')
 if protocol not in ('ntp','ptp'):raise LabError('clock protocol must be NTP or PTP')
 server,ip=transit(lab,body['device'],body['server'],protocol);s=service(server,protocol)
 if s.get('key') and s['key']!=body.get('key'):raise LabError('clock authentication mismatch')
 stamp=s.get('server_time') or datetime.now(timezone.utc).isoformat()
 datetime.fromisoformat(stamp.replace('Z','+00:00'))
 conf(lab._device(body['device']))['clock']={'utc':stamp,'master_time':lab.simulation['master_time'],'protocol':protocol,'server':server.name}
 return stamp

def emit_log(lab,device,message):
 c=conf(lab._device(device));record={'time':lab.simulation['master_time'],'hostname':c['hostname'],'message':str(message)}
 c['logs'].append(record);c['logs']=c['logs'][-1000:]
 if c['syslog_host']:
  try:server,_=transit(lab,device,c['syslog_host'],'syslog')
  except LabError:return
  service_logs=conf(server)['services']['syslog'].setdefault('records',[]);service_logs.append(record);del service_logs[:-1000]

def snmp(lab,body):
 server,ip=transit(lab,body['device'],body['server'],'snmp');s=service(server,'snmp');operation=body.get('operation','get')
 expected=s.get('write_community') if operation=='set' else s.get('community','public')
 if not expected or body.get('community')!=expected:raise LabError('SNMP community denied')
 oid=body.get('oid');c=conf(server)
 if oid in ('sysName','1.3.6.1.2.1.1.5.0'):
  if operation=='set':c['hostname']=label(body['value'],63)
  return c['hostname']
 if oid in ('sysLocation','1.3.6.1.2.1.1.6.0'):
  if operation=='set':s['location']=label(body['value'],128);c['services']['snmp']=s
  return s.get('location','')
 if isinstance(oid,str) and oid.startswith(('ifAdminStatus.','ifOperStatus.')):
  field,port=oid.split('.',1);p=lab._iface(server.name,port)
  if operation=='set':
   if field!='ifAdminStatus' or body['value'] not in (1,2):raise LabError('only ifAdminStatus 1/2 is writable')
   lab.set_interface_state(server.name,port,body['value']==1)
  return 1 if (p.admin_up if field=='ifAdminStatus' else lab._iface_effective_up(server.name,port)) else 2
 raise LabError('OID not implemented')

def firewall(lab,d,body):
 interface=body['interface'];lab._iface(d.name,interface);mode=body['match'];value=body.get('value')
 if d.kind!='router':d.kind='router'
 acl='fw_'+interface.replace('/','_');c=conf(d)
 if body.get('delete'):
  if mode=='url':c['url_blocks']=[r for r in c.get('url_blocks',[]) if r['url']!=value]
  else:d.acls[acl]=[r for r in d.acls.get(acl,[]) if r.sequence!=body.get('sequence')]
  return [vars(rule) for rule in d.acls.get(acl,[])]
 sequence=body.get('sequence') or max([r.sequence for r in d.acls.get(acl,[]) if r.sequence<65535]+[0])+10
 source=body.get('source','any')
 if mode in ('source','destination'):
  ip=str(IPv4Address(value));lab.add_acl_rule(d.name,acl,'deny','ip',ip+'/32' if mode=='source' else 'any',ip+'/32' if mode=='destination' else 'any',sequence)
 elif mode=='protocol':
  protocol,port=PORTS.get(str(value).lower(),(str(value).lower(),None))
  lab.add_acl_rule(d.name,acl,'deny',protocol,source,'any',sequence,destination_port=port)
 elif mode=='url':c.setdefault('url_blocks',[]).append({'host':source,'url':label(value,2048)})
 else:raise LabError('firewall match must be source/destination/protocol/url')
 lab.add_acl_rule(d.name,acl,'permit','ip','any','any',65535);lab.set_access_group(d.name,interface,acl,'in')
 return [vars(rule) for rule in d.acls[acl]]

def pdu_service(lab,p,network_ok):
 if not network_ok:return {'ok':False,'status':'Failed'}
 protocol=p['protocol'].lower();server,ip=endpoint(lab,p['destination_ip'])
 if protocol in PORTS:
  enabled=service(server,protocol).get('enabled',False)
  return {'ok':enabled,'status':'Successful' if enabled else 'Failed','application_status':'service-enabled' if enabled else 'service-disabled',
   'message':protocol.upper()+' endpoint accepts transport requests' if enabled else protocol.upper()+' service is disabled'}
 return {'application_status':'transport-only'}

def apply(lab,body):
 d=lab._device(body['device']);action=body.get('action')
 if action in ('modbus_send','modbus_receive','cip_identity','cip_object','cip_request'):
  from .industrial_protocols import apply as industrial_protocol
  return industrial_protocol(lab,body)
 if action in ('clientless_vpn','clientless_login','clientless_open'):
  from .clientless_vpn import apply as webvpn
  return webvpn(lab,body)
 if action in ('dialup','pppoe','vpn','host_firewall','historian_query','management_login','management_apply'):
  from .access_services import apply as client_apply
  return client_apply(lab,body)
 if action in ('l2nat','rep','dhcp_binding','svi'):
  from .industrial_switching import apply as switch_apply
  return switch_apply(lab,body)
 if action=='service':return _write_service(lab,d,body)
 if action=='host_command':
  from .host_commands import execute
  return execute(lab,d.name,body.get('command',''))
 if action in ('port_forward','dmz'):
  from .port_forwarding import configure
  return configure(lab,d,body)
 if action=='service_user':return _account(d,body)
 if action=='dns_cache':
  cache=conf(d)['services'].setdefault('dns',{'enabled':d.dns_enabled}).setdefault('cache',{})
  if body.get('clear'):cache.clear()
  return deepcopy(cache)
 if action=='dns_record':
  c=conf(d);s=c['services'].setdefault('dns',{'enabled':d.dns_enabled});records=s.setdefault('records',{});s['cache']={}
  name=lab._valid_dns_name(body['name'])
  if body.get('delete'):records.pop(name,None);d.dns_records.pop(name,None);return
  kind=body.get('type','A');value=body.get('value')
  if kind=='A':value=str(IPv4Address(value));d.dns_records[name]=value
  elif kind in ('CNAME','NS'):value=lab._valid_dns_name(value) if not re.fullmatch(r'[0-9.]+',str(value)) else str(IPv4Address(value))
  elif kind=='SOA':
   if not isinstance(value,dict) or not {'primary','email'}<=set(value):raise LabError('SOA needs primary/email')
  else:raise LabError('DNS type must be A/CNAME/NS/SOA')
  if kind!='A':d.dns_records.pop(name,None)
  records[name]={'type':kind,'value':value,'ttl':integer(body.get('ttl',300),1,86400)};return records[name]
 if action=='dhcp_pool':return vars(lab.add_dhcp_pool(d.name,body['name'],body['network'],body['gateway'],body['start'],body['end'],body.get('dns_server')))
 if action=='http_page':lab.set_http_page(d.name,body.get('path','/'),body.get('content',''));return
 if action=='dhcp_pool_delete':
  if body.get('name') not in d.dhcp_pools:raise LabError('unknown DHCP pool')
  del d.dhcp_pools[body['name']];return
 if action=='http_page_delete':
  if body.get('path') not in d.http_pages:raise LabError('unknown HTTP page')
  del d.http_pages[body['path']];return
 if action=='aaa_client':
  protocol=body.get('protocol','radius')
  if protocol not in ('radius','tacacs'):raise LabError('invalid AAA protocol')
  s=conf(d)['services'].setdefault(protocol,{'enabled':False});ip=str(IPv4Address(body['client_ip']))
  if body.get('delete'):s.setdefault('clients',{}).pop(ip,None)
  else:s.setdefault('clients',{})[ip]={'name':label(body.get('name','Client'),64),'secret':label(body['secret'],128)}
  return
 if action=='transfer':return transfer(lab,body)
 if action=='mail_send':return mail(lab,body)
 if action=='mail_receive':return mail(lab,body,True)
 if action=='aaa_authenticate':return authenticate(lab,body)
 if action=='clock_sync':return clock_sync(lab,body)
 if action=='snmp':return snmp(lab,body)
 if action=='logging':
  conf(d)['syslog_host']=str(IPv4Address(body['server'])) if body.get('server') else None;return
 if action=='emit_log':emit_log(lab,d.name,label(body['message'],1000));return
 if action=='firewall_rule':return firewall(lab,d,body)
 if action in ('wireless','associate','cloud_port','cloud_map','controller','discover','provision','license','industrial','plc_program','plc_run','historian_import','historian_collect','observer_scan','telephony','call','iox','wlc_wlan','wlc_group'):
  from .special_devices import apply as special_apply
  return special_apply(lab,body)
 if action=='remote_cli':
  protocol=body.get('protocol','ssh');target,ip=transit(lab,d.name,body['server'],protocol);c=conf(target)
  if c.get('aaa_server'):
   authenticate(lab,{'device':target.name,'server':c['aaa_server'],'protocol':c.get('aaa_protocol','radius'),'secret':c.get('aaa_secret'),'username':body.get('username'),'password':body.get('password')})
  else:
   user=c['users'].get(body.get('username'))
   if not user or user['password']!=body.get('password'):raise LabError('remote login failed')
  from .device_config import terminal_session
  return terminal_session(lab,d.name,target.name,protocol+':'+target.name+':'+body.get('username',''),body.get('command',''))
 raise LabError('unsupported device service action')

def schema():
 return {'protocols':PORTS,'actions':{
 'clientless_vpn':['enabled','bookmarks'],'clientless_login':['server','username','password'],'clientless_open':['token','name'],
 'modbus_send':['server','data'],'modbus_receive':[],
 'cip_identity':['identity'],'cip_object':['class_id','instance_id','data','delete'],'cip_request':['server','operation','class_id','instance_id','data'],
 'host_command':['command'],
 'port_forward':['name','protocol','external_port','internal_port','ip','delete'],'dmz':['enabled','ip'],
 'svi':['vlan','ip','ipv6','admin_up'],
 'l2nat':['direction','original','translated','interfaces','delete'],'rep':['interface','segment','edge','delete'],'dhcp_binding':['mac','ip','delete'],
 'service':['service','enabled','domain','community','write_community','secret','key','server_time','prefix','gateway','group','network'],
 'service_user':['service','username','password','permissions','delete'],
 'dhcp_pool':['name','network','gateway','start','end','dns_server'],'http_page':['path','content'],
 'dns_cache':['clear'],
 'dns_record':['name','type','value','ttl','delete'],'dhcp_pool_delete':['name'],'http_page_delete':['path'],
 'aaa_client':['protocol','client_ip','name','secret','delete'],
 'management_login':['server','protocol','username','password','setup'],'management_apply':['token','settings'],
 'dialup':['interface','number','username','password','operation'],
 'cloud_port':['interface','phone_number','provider','lmi','dlcis'],
 'pppoe':['server','interface','username','password','operation'],'vpn':['server','username','password','group','key','network','operation'],
 'host_firewall':['version','policy','protocol','source','destination','clear'],'historian_query':['server','username','password','source','tag'],
 'transfer':['server','protocol','operation','file','new_name','content','username','password'],
 'mail_send':['server','username','password','to','subject','text'],'mail_receive':['server','username','password'],
 'aaa_authenticate':['server','protocol','secret','username','password'],'clock_sync':['server','protocol','key'],
 'snmp':['server','community','operation','oid','value'],'logging':['server'],'emit_log':['message'],
 'firewall_rule':['interface','match','value','source','sequence','delete'],'remote_cli':['server','protocol','username','password','command'],
 'wireless':['ssid','security','key','channel','radius_server','radius_secret','range_m'],
 'associate':['ssid','security','key','username','password'],'cloud_map':['a_port','b_port','dlci_a','dlci_b','delete'],
 'wlc_wlan':['ssid','security','key','vlan','radius_server','radius_secret','delete'],'wlc_group':['name','aps','wlans'],
 'controller':['username','password'],'discover':['network','username','password'],'provision':['target','settings'],
 'license':['operation','level','target','token'],'industrial':['tags','server','enabled'],
 'plc_program':['blocks'],'plc_run':['seconds'],'historian_import':['csv'],'historian_collect':['source','username','password'],
 'observer_scan':['network'],'telephony':['number','server'],'call':['number','operation','note'],'iox':['operation','name','file']}}

"""Reference-compatible host options and authenticated interactive clients."""
import shlex
from ipaddress import IPv4Interface
from .model import LabError


def execute(lab,device,text):
 from .device_services import conf,apply,transfer
 from .device_config import action
 d=lab._device(device);p=shlex.split(text)
 if not p:return None
 op=p[0].lower();session=d.config.get('host_terminal')
 if session:
  if op in ('quit','bye','exit'):
   d.config.pop('host_terminal',None);return 'Connection closed'
  stage=session['stage']
  if stage=='username':session['username']=text;session['stage']='password';return 'Password:'
  if stage=='password':
   session['password']=text
   if session['protocol']=='ftp':transfer(lab,{'device':device,'server':session['server'],'protocol':'ftp','username':session['username'],'password':text,'operation':'list'});lab._device(device).config['host_terminal']['stage']='ready';return 'Authenticated. ftp>'
   result=apply(lab,{'device':device,'action':'remote_cli','server':session['server'],'protocol':session['protocol'],'username':session['username'],'password':text,'command':''});lab._device(device).config['host_terminal']['stage']='ready';return result
  body={'device':device,'server':session['server'],'protocol':session['protocol'],'username':session['username'],'password':session['password']}
  if session['protocol']!='ftp':return apply(lab,{**body,'action':'remote_cli','command':text})
  operations={'dir':'list','ls':'list','get':'get','put':'put','delete':'delete','rename':'rename'}
  if op not in operations:raise LabError('FTP: dir, get FILE, put FILE, delete FILE, rename FILE NEWNAME, quit')
  return transfer(lab,{**body,'operation':operations[op],'file':p[1] if len(p)>1 else '',**({'new_name':p[2]} if len(p)>2 else {})})
 if op in ('ftp','telnet') and len(p)==2 or op=='ssh' and len(p)==4 and p[1]=='-l':
  c=conf(d);c['host_terminal']={'protocol':op,'server':p[-1],'stage':'password' if op=='ssh' else 'username','username':p[2] if op=='ssh' else ''};return 'Password:' if op=='ssh' else 'Username:'
 if op=='arp' and len(p)>1:
  if p[1]=='-d':
   if len(p)==2 or p[2]=='*':d.arp_table.clear()
   else:d.arp_table.pop(p[2],None)
   return 'ARP entries deleted'
  if p[1] in ('-?','/?'):return 'arp -a | arp -d [IP|*]'
 if op in ('ipconfig','ipv6config') and len(p)>1:
  args=p[1:];version=6 if op=='ipv6config' else 4
  if args[0] in ('/?','-?'):return op+' [/all|/renew|/release] [-p INDEX] [ADDRESS MASK GATEWAY DNS]'
  index=0
  if '-p' in args:
   pos=args.index('-p');index=int(args[pos+1]);del args[pos:pos+2]
  ports=[port for port in d.interfaces.values() if port.media in ('copper','wifi','fiber-mm','fiber-sm')]
  if not 0<=index<len(ports):raise LabError('invalid host interface index')
  port=ports[index]
  if args==['/release']:
   if version==6:port.ipv6=None;d.config.pop('ipv6_gateway',None);d.config.pop('ipv6_dns_server',None)
   else:
    port.ip=None;d.default_gateway=None;d.dns_server=None
    for server in lab.devices.values():
     for pool in server.dhcp_pools.values():pool.leases.pop(port.mac,None)
   lab.recompute_ospf();return 'Address released'
  if args==['/renew']:return lab.dhcp_request(device,port.name) if version==4 else str(action(lab,{'device':device,'action':'ipv6_dhcp','interface':port.name}))
  if args and args[0] not in ('/all',):
   if version==4:
    if len(args)<2 or len(args)>4:raise LabError('ipconfig ADDRESS MASK [GATEWAY [DNS]]')
    body={'ip':str(IPv4Interface(args[0]+'/'+args[1]))}
    if len(args)>2:body['gateway']=args[2]
    if len(args)>3:body['dns_server']=args[3]
   else:
    if not 1<=len(args)<=3:raise LabError('ipv6config ADDRESS/PREFIX [GATEWAY [DNS]]')
    body={'ipv6':args[0]}
    if len(args)>1:body['ipv6_gateway']=args[1]
    if len(args)>2:body['ipv6_dns_server']=args[2]
   action(lab,{'device':device,'action':'interface','interface':port.name,**body});return 'IP configuration applied'
 if op=='nslookup' and len(p)==3:
  old=d.dns_server;d.dns_server=p[2]
  try:return lab.resolve_dns(device,p[1])
  finally:lab._device(device).dns_server=old
 if op=='netstat' and p[1:]==['-r']:return [vars(r) for r in lab.routing_table(device)]
 if op=='netsh' and p[1:]==['interface','ipv6','show','neighbors']:return d.config.get('ndp',{})
 if op=='netsh' and p[1:]==['interface','ipv6','show','potentialrouters']:return {'gateway':d.config.get('ipv6_gateway')}
 if op=='ping' and any(flag in p for flag in ('-n','-v','-t')):
  count=1;tos=0;continuous=False;destination=None;index=1
  while index<len(p):
   if p[index] in ('-n','-v'):
    flag=p[index];value=int(p[index+1]);index+=2
    if flag=='-n':count=value
    else:tos=value
   elif p[index]=='-t':continuous=True;index+=1
   elif destination is None:destination=p[index];index+=1
   else:raise LabError('unexpected ping argument')
  if not destination or not 1<=count<=100 or not 0<=tos<=255:raise LabError('ping count must be 1..100 and ToS 0..255')
  if continuous or tos:
   from .simulation import action as simulate
   return {'pdu':simulate(lab,{'action':'pdu_add','source':device,'destination_ip':destination,'protocol':'ICMP','tos':tos,'interval':1 if continuous else 0})}
  return '\n'.join(lab.ping(device,destination)[1] for _ in range(count))
 return None

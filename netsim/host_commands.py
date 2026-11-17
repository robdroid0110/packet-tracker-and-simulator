"""Host command prompt uses the same device services as forms and agents."""
import json,shlex
from .model import LabError

def execute(lab,device,text):
 from .device_services import transfer,apply,snmp
 from .device_config import action,settings
 from .host_reference import execute as reference_execute
 result=reference_execute(lab,device,text)
 if result is not None:return result
 parts=shlex.split(text);op=parts.pop(0).lower() if parts else 'help';d=lab._device(device)
 if op in ('help','?'):return 'ipconfig [ /renew ], ipv6config, arp -a, ping IP, tracert IP, nslookup NAME, dir, delete FILE, netstat, ftp SERVER USER PASSWORD [list|get|put|delete|rename] [FILE] [NEWNAME], ssh|telnet SERVER USER PASSWORD COMMAND, snmpget|snmpset SERVER COMMUNITY OID [VALUE]'
 if op in ('ipconfig','ipv6config'):
  if parts and parts[0]=='/renew':lab.dhcp_request(device,next(p.name for p in d.interfaces.values() if p.media in ('copper','wifi','fiber-mm','fiber-sm')))
  return {name:vars(p).copy() for name,p in d.interfaces.items()}
 if op=='arp':return d.arp_table.copy()
 if op in ('ping','tracert','traceroute') and parts:return (lab.ping if op=='ping' else lab.traceroute)(device,parts[0])[1]
 if op=='nslookup' and parts:return lab.resolve_dns(device,parts[0])
 if op=='dir':return sorted(settings(d)['files'])
 if op=='delete' and parts:return action(lab,{'device':device,'action':'file_delete','file':parts[0]})
 if op=='netstat':return {'pdus':{key:{k:p.get(k) for k in ('protocol','status','source','destination_ip')} for key,p in lab.simulation['pdus'].items() if p['source']==device},'vpn':d.config.get('vpn_session'),'pppoe':d.config.get('pppoe_session')}
 if op=='ftp' and len(parts)>=3:
  server,user,password,*args=parts
  return transfer(lab,{'device':device,'protocol':'ftp','server':server,'username':user,'password':password,'operation':args[0] if args else 'list','file':args[1] if len(args)>1 else '',**({'new_name':args[2]} if len(args)>2 else {})})
 if op in ('ssh','telnet') and len(parts)>=4:
  server,user,password,*command=parts
  return apply(lab,{'action':'remote_cli','device':device,'protocol':op,'server':server,'username':user,'password':password,'command':' '.join(command)})
 if op in ('snmpget','snmpgetbulk','snmpset') and len(parts)>=3:
  server,community,oid,*value=parts
  return snmp(lab,{'device':device,'server':server,'community':community,'oid':oid,'operation':'set' if op=='snmpset' else 'get','value':int(value[0]) if value and oid.startswith('ifAdminStatus') else ' '.join(value)})
 raise LabError('invalid host command; type help for syntax')

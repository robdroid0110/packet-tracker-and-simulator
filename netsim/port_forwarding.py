"""Home/edge simulated port forwarding and DMZ with return translation."""
from ipaddress import IPv4Address
from .simulation import integer,label
from .model import LabError

def configure(lab,d,b):
 if b['action']=='dmz':
  enabled=b.get('enabled',True)
  if not isinstance(enabled,bool):raise LabError('DMZ enabled must be boolean')
  d.config['dmz']=str(IPv4Address(b['ip'])) if enabled else None
  return d.config['dmz']
 name=label(b.get('name','forward'),64);rules=d.config.setdefault('port_forwards',{})
 if b.get('delete'):rules.pop(name,None);return rules
 protocol=b.get('protocol','tcp')
 if protocol not in ('tcp','udp','both'):raise LabError('forward protocol must be tcp, udp or both')
 rules[name]={'protocol':protocol,'external_port':integer(b['external_port'],1,65535),'internal_port':integer(b['internal_port'],1,65535),'ip':str(IPv4Address(b['ip']))}
 return rules

def inbound(lab,d,incoming,src,dst,protocol,meta):
 if not incoming or d.interfaces[incoming].nat_role!='outside' or not d.interfaces[incoming].ip or str(d.interfaces[incoming].ipv4.ip)!=dst:return dst
 rule=next((r for r in d.config.get('port_forwards',{}).values() if r['protocol'] in (protocol,'both') and r['external_port']==meta.get('destination_port')),None)
 target=rule['ip'] if rule else d.config.get('dmz')
 if not target:return dst
 original_port=meta.get('destination_port');internal=rule['internal_port'] if rule else original_port
 key='|'.join(map(str,(target,src,protocol,internal,meta.get('source_port'))))
 d.config.setdefault('port_forward_sessions',{})[key]={'ip':dst,'port':original_port}
 meta['destination_port']=internal;meta['final_destination']=target
 return target

def outbound(d,src,dst,protocol,meta):
 key='|'.join(map(str,(src,dst,protocol,meta.get('source_port'),meta.get('destination_port'))))
 session=d.config.get('port_forward_sessions',{}).get(key)
 if session:meta['source_port']=session['port'];meta['translated_source']=session['ip'];return session['ip']
 return src

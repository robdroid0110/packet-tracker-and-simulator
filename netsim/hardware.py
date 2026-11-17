"""Typed cable media, port settings and modular hardware behaviour (§§41–47).

Catalog profiles expose simulated compatible media; this is not a claim of
cycle-accurate chassis emulation. Existing untyped saved ports remain copper.
"""
from __future__ import annotations
from .model import LabError

CABLE_MEDIA={'copper-straight':{'copper'},'copper-cross':{'copper'},'fiber-mm':{'fiber-mm'},'fiber-sm':{'fiber-sm'},
 'serial-dce':{'serial'},'serial-dte':{'serial'},'phone':{'modem'},'coax':{'coax'},
 'console':{'console','rs232'},'octal':{'async','console'},'usb':{'usb'},'ioe':{'ioe'}}
DATA_MEDIA={'copper','fiber-mm','fiber-sm','serial','wifi'}

def copper_cable(lab,a,ai,b,bi):
 """Choose Ethernet polarity from each port's simulated MDI/MDI-X role."""
 def switch_port(device,interface):
  d=lab._device(device)
  if d.model=='7960':return interface.lower()=='pc'
  return d.kind=='switch' or d.config.get('multilayer_switch',False)
 return 'copper-straight' if switch_port(a,ai)!=switch_port(b,bi) else 'copper-cross'

def validate_cable(lab,a,ai,b,bi,cable):
 ap=lab._iface(a,ai);bp=lab._iface(b,bi)
 if cable=='auto':
  if ap.media==bp.media=='copper':return cable
  cable=next((c for c,media in CABLE_MEDIA.items() if ap.media in media and bp.media in media),None)
 if cable not in CABLE_MEDIA:raise LabError('unknown or incompatible automatic cable')
 if ap.media not in CABLE_MEDIA[cable] or bp.media not in CABLE_MEDIA[cable]:raise LabError(f'unsupported cable on selected ports: {cable} with {ap.media}/{bp.media}')
 if cable=='console' and {ap.media,bp.media}!={'rs232','console'}:raise LabError('console requires a PC RS232 port and device console port')
 return cable

def physical_status(lab,link):
 a=lab._device(link.a_device);b=lab._device(link.b_device)
 ap=lab._iface(link.a_device,link.a_if);bp=lab._iface(link.b_device,link.b_if)
 if not a.powered or not b.powered:return False,'device powered off'
 if not ap.admin_up or not bp.admin_up:return False,'interface shutdown'
 if link.cable=='vpn':
  from .access_services import vpn_up
  return (True,'simulated VPN tunnel') if vpn_up(lab,link) else (False,'VPN underlay down')
 if link.cable=='wireless':
  from .special_devices import _compatible
  client,access,port=(a,b,link.a_if) if a.config.get('wireless_client') else (b,a,link.b_if)
  return (True,'wireless associated') if _compatible(lab,client,access,port) else (False,'wireless authentication/range failure')
 try:validate_cable(lab,link.a_device,link.a_if,link.b_device,link.b_if,link.cable)
 except LabError:return False,'cable/port media mismatch'
 if link.cable in ('auto','copper-straight','copper-cross'):
  required=copper_cable(lab,link.a_device,link.a_if,link.b_device,link.b_if)
  if link.cable!='auto' and link.cable!=required and not (ap.auto_mdix or bp.auto_mdix):return False,'copper polarity mismatch'
 if link.cable.startswith('serial'):
  dce=ap if link.cable=='serial-dce' else bp
  if not dce.clock_rate:return False,'DCE clock rate not configured'
 if ap.speed!='auto' and bp.speed!='auto' and ap.speed!=bp.speed:return False,'port speed mismatch'
 if ap.duplex!='auto' and bp.duplex!='auto' and ap.duplex!=bp.duplex:return True,'duplex mismatch (physical carrier up)'
 if lab.cable_length_effects and link.cable in ('auto','copper-straight','copper-cross'):
  from .physical_distance import cable_length
  if not cable_length(lab,link)['in_range']:return False,'cable length exceeds 100m'
 return True,'operational'

def add_port(lab,name,port,media):
 import re
 from .model import Interface
 d=lab._device(name)
 if d.powered:raise LabError('power device off before adding a port')
 if not isinstance(port,str) or not re.fullmatch(r'[A-Za-z][A-Za-z0-9/_.-]{0,30}',port) or port in d.interfaces:raise LabError('invalid or occupied port name')
 if media not in set.union(*CABLE_MEDIA.values())|{'wifi'}:raise LabError('invalid port medium')
 if len(d.interfaces)>=128:raise LabError('maximum 128 simulated ports')
 d.interfaces[port]=Interface(port,media=media)

def set_port(lab,name,port,body):
 from .simulation import integer
 p=lab._iface(name,port)
 if 'speed' in body:
  speed=str(body['speed'])
  if speed not in ('auto','10','100','1000','10000'):raise LabError('speed must be auto/10/100/1000/10000 Mbps')
  p.speed=speed
 if 'duplex' in body:
  if body['duplex'] not in ('auto','half','full'):raise LabError('duplex must be auto/half/full')
  p.duplex=body['duplex']
 if 'clock_rate' in body:
  if p.media!='serial':raise LabError('clock rate requires serial port')
  p.clock_rate=integer(body['clock_rate'],0,4000000)
 if 'auto_mdix' in body:
  if not isinstance(body['auto_mdix'],bool) or p.media!='copper':raise LabError('auto_mdix requires copper and boolean')
  p.auto_mdix=body['auto_mdix']
 if 'mac' in body:
  import re
  if not isinstance(body['mac'],str) or not re.fullmatch(r'[0-9a-fA-F]{2}(?::[0-9a-fA-F]{2}){5}',body['mac']):raise LabError('MAC must be six colon-separated octets')
  if int(body['mac'][:2],16)&1:raise LabError('interface MAC must be unicast')
  p.mac=body['mac'].lower()
 if 'tx_ring_limit' in body:p.tx_ring_limit=integer(body['tx_ring_limit'],1,4096)
 if 'mtu' in body:p.mtu=integer(body['mtu'],576,9216)
 if 'admin_up' in body:
  if not isinstance(body['admin_up'],bool):raise LabError('admin_up must be boolean')
  p.admin_up=body['admin_up']
 lab.recompute_ospf()

def console(lab,body):
 device=body['device'];port=body['interface'];p=lab._iface(device,port)
 link=lab.link_for(device,port)
 if not link or link.cable!='console' or not lab.link_operational(link):raise LabError('an operational console cable is required')
 if p.media!='rs232':raise LabError('terminal endpoint must be RS232')
 peer=lab.peer(device,port);remote=lab._iface(*peer)
 settings=body.get('settings',{})
 for key in ('baud','data_bits','parity'):
  if settings.get(key,getattr(p,key))!=getattr(remote,key):raise LabError('console '+key+' mismatch')
 for side in (p,remote):
  if side.data_bits not in (7,8) or side.stop_bits not in (1,2):raise LabError('unsupported console framing')
 return peer[0]

def schema():
 return {'version':1,'cables':{k:sorted(v) for k,v in CABLE_MEDIA.items()},'media':sorted(set.union(*CABLE_MEDIA.values())|{'wifi'}),
 'actions':{'add_port':['device','port','media'],'set_port':['device','port','speed','duplex','clock_rate','auto_mdix','mac','mtu','tx_ring_limit','admin_up'],
 'console':['device','interface','settings','command']},'rule':'Typed cable/port matching; serial DCE clock; console framing; non-IP USB/IoE/console ports do not masquerade as Ethernet.'}


def lights(lab,link,cache=None):
 result=[];up=lab.link_operational(link)
 for name,port in link.endpoints():
  color='black' if link.cable in ('console','octal') and up else 'green' if up else 'red'
  if up and lab.devices[name].kind=='switch':
   from .industrial_switching import rep_forwarding
   vlan=lab.infer_vlan((name,port))
   if cache is None:state=lab.stp_port_state(name,port,vlan)
   else:
    if vlan not in cache:cache[vlan]=lab.spanning_tree(vlan)
    state=cache[vlan]['ports'].get(name+':'+port,{'state':'forwarding'})['state']
   if port in lab.devices[name].config.get('rep_ports',{}):state='forwarding' if rep_forwarding(lab,name,port) else 'blocking'
   if state in ('blocking','discarding'):color='amber'
  result.append({'device':name,'interface':port,'color':color,
   'dce':link.cable=='serial-dce' and name==link.a_device or link.cable=='serial-dte' and name==link.b_device})
 return result


def validate_port(p):
 from .simulation import integer
 if p.media not in set.union(*CABLE_MEDIA.values())|{'wifi','bridge','vpn'}:raise LabError('invalid saved port medium')
 if p.speed not in ('auto','10','100','1000','10000') or p.duplex not in ('auto','half','full'):raise LabError('invalid saved speed/duplex')
 integer(p.clock_rate,0,4000000);integer(p.mtu,576,9216);integer(p.tx_ring_limit,1,4096)
 if not isinstance(p.auto_mdix,bool):raise LabError('auto_mdix must be boolean')
 if p.data_bits not in (7,8) or p.stop_bits not in (1,2) or p.parity not in ('none','even','odd','mark','space'):raise LabError('invalid saved console framing')
 integer(p.baud,300,4000000)
 if p.ipv6_link_local:
  from ipaddress import IPv6Address
  if not IPv6Address(p.ipv6_link_local).is_link_local:raise LabError('invalid saved IPv6 link-local address')
 if p.ipv6:
  from ipaddress import IPv6Interface
  IPv6Interface(p.ipv6)

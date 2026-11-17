"""Authenticated HTTPS portal and HTTP bookmark proxy; no TLS implementation."""
from urllib.parse import urlsplit
from ipaddress import IPv4Address
from .model import LabError
from .simulation import label
from .device_services import conf,transit
import uuid

def apply(lab,b):
 d=lab._device(b['device']);action=b['action']
 if action=='clientless_vpn':
  enabled=b.get('enabled',True);bookmarks=b.get('bookmarks',{})
  if not isinstance(enabled,bool) or not isinstance(bookmarks,dict):raise LabError('enabled must be boolean and bookmarks an object')
  for name,url in bookmarks.items():
   label(name,64)
   if not isinstance(url,str) or len(url)>2048 or urlsplit(url).scheme not in ('http','https') or not urlsplit(url).hostname:raise LabError('bookmark requires a simulated HTTP(S) URL')
  c=conf(d);c['clientless_vpn']={'enabled':enabled,'bookmarks':bookmarks};c['services'].setdefault('https',{})['enabled']=enabled;return c['clientless_vpn']
 if action=='clientless_login':
  server,ip=transit(lab,d.name,b['server'],'https');c=conf(server)
  if not c.get('clientless_vpn',{}).get('enabled'):raise LabError('clientless VPN portal is disabled')
  user=c['users'].get(b.get('username'))
  if not user or user['password']!=b.get('password'):raise LabError('clientless VPN authentication failed')
  token=uuid.uuid4().hex;conf(d).setdefault('clientless_sessions',{})[token]={'server':ip,'target':server.name,'expires':lab.simulation['master_time']+3600}
  return {'token':token,'bookmarks':c['clientless_vpn']['bookmarks'],'encrypted':False}
 if action=='clientless_open':
  session=d.config.get('clientless_sessions',{}).get(b.get('token'))
  if not session or session['expires']<lab.simulation['master_time']:raise LabError('clientless VPN session is missing or expired')
  portal,ip=transit(lab,d.name,session['server'],'https');c=conf(portal)
  url=c.get('clientless_vpn',{}).get('bookmarks',{}).get(b.get('name'))
  if not c.get('clientless_vpn',{}).get('enabled') or portal.name!=session['target'] or not url:raise LabError('bookmark is unavailable')
  parsed=urlsplit(url)
  try:address=str(IPv4Address(parsed.hostname))
  except ValueError:address=lab.resolve_dns(portal.name,parsed.hostname)
  server,ip=transit(lab,portal.name,address,parsed.scheme)
  page=server.http_pages.get(parsed.path or '/')
  if page is None:raise LabError('bookmark page not found')
  return {'ok':True,'html':page,'server':server.name,'via':portal.name,'url':url,'encrypted':False}
 raise LabError('invalid clientless VPN action')

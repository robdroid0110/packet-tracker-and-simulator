"""Routed Modbus TCP message exchange and CIP object services.

Data exchanges occur inside NetworkLab. No operating-system sockets or user
programs are executed; message contents are bounded JSON values.
"""
from copy import deepcopy
import json
from .model import LabError
from .simulation import integer,label
from .device_services import conf,transit

MAX_MESSAGE=8192

def json_value(value):
 try:encoded=json.dumps(value,allow_nan=False)
 except (TypeError,ValueError) as exc:raise LabError('data must be finite JSON') from exc
 if len(encoded.encode())>MAX_MESSAGE:raise LabError('industrial message exceeds 8192 bytes')
 return deepcopy(value)

def apply(lab,b):
 d=lab._device(b['device']);action=b['action']
 if action=='modbus_send':
  target,ip=transit(lab,d.name,b['server'],'modbus');payload=json_value(b.get('data'))
  inbox=conf(target)['industrial'].setdefault('modbus_inbox',[])
  if len(inbox)>=200:raise LabError('Modbus inbox is full; consume messages before sending')
  inbox.append({'source':d.name,'data':payload});return {'delivered':True,'server':target.name,'data':payload}
 if action=='modbus_receive':
  inbox=conf(d)['industrial'].setdefault('modbus_inbox',[])
  if not inbox:return None
  return inbox.pop(0)
 if action=='cip_identity':
  data=json_value(b.get('identity',{}))
  if not isinstance(data,dict):raise LabError('identity must be a JSON object')
  c=conf(d);c['industrial']['cip_identity']=data;c['services'].setdefault('cip',{})['enabled']=True;return data
 if action=='cip_object':
  code=integer(b.get('class_id'),1,65535);instance=integer(b.get('instance_id'),0,65535)
  objects=conf(d)['industrial'].setdefault('cip_objects',{});key=str(code)+':'+str(instance)
  if b.get('delete'):objects.pop(key,None);return None
  value=json_value(b.get('data'))
  if not isinstance(value,dict):raise LabError('CIP object data must be a JSON object')
  if key not in objects and len(objects)>=128:raise LabError('CIP object limit reached')
  objects[key]=value;return deepcopy(value)
 if action=='cip_request':
  target,ip=transit(lab,d.name,b['server'],'cip');operation=b.get('operation','identity');industrial=target.config.get('industrial',{})
  if operation=='identity':return deepcopy(industrial.get('cip_identity',{}))
  if operation not in ('get','set'):raise LabError('CIP operation must be identity, get or set')
  key=str(integer(b.get('class_id'),1,65535))+':'+str(integer(b.get('instance_id'),0,65535))
  objects=conf(target)['industrial'].setdefault('cip_objects',{})
  if key not in objects:raise LabError('CIP object does not exist')
  if operation=='set':
   data=json_value(b.get('data'))
   if not isinstance(data,dict):raise LabError('CIP object data must be a JSON object')
   objects[key]=data
  return deepcopy(objects[key])
 raise LabError('unknown industrial protocol action')

"""Port predicates shared by IOS extended ACL parsing and packet forwarding."""
from .model import LabError
from .simulation import integer
NAMES={'www':80,'http':80,'https':443,'domain':53,'ftp':21,'ftp-data':20,'ssh':22,'telnet':23,'smtp':25,'pop3':110,'ntp':123,'snmp':161}

def port(value):
 if isinstance(value,bool):raise LabError('ACL port must be an integer')
 return NAMES[value.lower()] if isinstance(value,str) and value.lower() in NAMES else integer(int(value),0,65535)

def normalize(value):
 if value is None:return None
 if isinstance(value,(int,str)):return {'op':'eq','first':port(value),'last':None}
 if not isinstance(value,dict) or value.get('op') not in ('eq','neq','lt','gt','range'):raise LabError('invalid ACL port predicate')
 first=port(value.get('first'));last=port(value.get('last')) if value['op']=='range' else None
 if last is not None and last<first:raise LabError('ACL port range reversed')
 return {'op':value['op'],'first':first,'last':last}

def matches(predicate,value):
 if predicate is None:return True
 if value is None:return False
 op=predicate['op'];p=predicate['first']
 return value==p if op=='eq' else value!=p if op=='neq' else value<p if op=='lt' else value>p if op=='gt' else p<=value<=predicate['last']

def parse(parts,index):
 if index>=len(parts) or parts[index].lower() not in ('eq','neq','lt','gt','range'):return None,index
 op=parts[index].lower()
 if index+1>=len(parts) or op=='range' and index+2>=len(parts):raise LabError('missing ACL port')
 value={'op':op,'first':parts[index+1],'last':parts[index+2] if op=='range' else None}
 return normalize(value),index+(3 if op=='range' else 2)

#!/usr/bin/env python3
"""Build three original labs and audit the real HTTP API in isolated state."""
import argparse,base64,json,subprocess,sys,tempfile,time
from pathlib import Path
from urllib.request import Request,urlopen
from urllib.error import HTTPError

ROOT=Path(__file__).resolve().parents[1]

def campus():
 c=[]
 for kind,n,x,y in [('router','R1',450,250),('router','R2',750,100),('router','R3',1000,300),('switch','SW1',250,250),('switch','SW2',100,450),('switch','SW3',400,450),('switch','SERVICES',1000,500)]:c.append(f'add {kind} {n} {x} {y}')
 for a,ap,b,bp in [('R1','g0/1','R2','g0/1'),('R2','g0/2','R3','g0/2'),('R1','g0/2','R3','g0/1'),('SW1','g0/1','SW2','g0/1'),('SW2','g0/2','SW3','g0/1'),('SW3','g0/2','SW1','g0/2'),('R1','g0/0','SW1','fa0/12'),('R3','g0/0','SERVICES','g0/1')]:c.append(f'connect {a} {ap} {b} {bp}')
 for r,p,ip in [('R1','g0/1','10.255.0.1/30'),('R2','g0/1','10.255.0.2/30'),('R2','g0/2','10.255.0.5/30'),('R3','g0/2','10.255.0.6/30'),('R1','g0/2','10.255.0.9/30'),('R3','g0/1','10.255.0.10/30'),('R3','g0/0','172.16.3.1/24')]:c.append(f'ip {r} {p} {ip}')
 for sw in ('SW1','SW2','SW3'):
  for port in ('g0/1','g0/2'):c.append(f'switchport {sw} {port} trunk 10,20')
 c+=['switchport SW1 fa0/12 trunk 10,20','stp SW1 priority 0','subif R1 g0/0 10 10.10.10.1/24','subif R1 g0/0 20 10.10.20.1/24']
 for name,ip,port in [('DNS','172.16.3.10/24',1),('WEB','172.16.3.20/24',2),('DHCP','172.16.3.30/24',3)]:
  c += [f'add server {name} {800+port*120} 650',f'connect {name} eth0 SERVICES fa0/{port}',f'ip {name} eth0 {ip}',f'gateway {name} 172.16.3.1']
 c+=['dns-service DNS on','dns-add DNS campus.lab 172.16.3.20','http-page WEB / "<h1>Campus service works</h1>"','dhcp-pool DHCP V10 10.10.10.0/24 10.10.10.1 10.10.10.100 10.10.10.120 172.16.3.10','dhcp-pool DHCP V20 10.10.20.0/24 10.10.20.1 10.10.20.100 10.10.20.120 172.16.3.10','helper R1 g0/0.10 172.16.3.30','helper R1 g0/0.20 172.16.3.30']
 for n in range(1,7):
  sw=('SW1','SW2','SW3')[(n-1)%3];vlan=10 if n<=3 else 20;port=1 if n<=3 else 2
  c += [f'add pc PC{n} {70+n*130} 800',f'connect PC{n} eth0 {sw} fa0/{port}',f'switchport {sw} fa0/{port} access {vlan}']
 for r in ('R1','R2','R3'):c.append(f'ospf {r} enable')
 for n in range(1,7):c.append(f'dhcp PC{n} eth0')
 return c,[]

def branch():
 c=['add router EDGE 400 220','add router ISP 750 220','add switch LAN 220 400','add switch PUBLIC 950 400','connect EDGE g0/0 LAN g0/1','connect EDGE g0/1 ISP g0/0','connect ISP g0/1 PUBLIC g0/1','ip EDGE g0/0 10.20.0.1/24','ip EDGE g0/1 198.51.100.2/30','ip ISP g0/0 198.51.100.1/30','ip ISP g0/1 203.0.113.1/24','route EDGE 0.0.0.0/0 via 198.51.100.1','nat-role EDGE g0/0 inside','nat-role EDGE g0/1 outside','nat-overload EDGE 10.20.0.0/24 g0/1']
 for n in range(1,5):c += [f'add pc Branch{n} {n*150} 600',f'connect Branch{n} eth0 LAN fa0/{n}',f'ip Branch{n} eth0 10.20.0.{10+n}/24',f'gateway Branch{n} 10.20.0.1']
 for name,address,port in [('PublicWeb','203.0.113.10',1),('PublicDNS','203.0.113.20',2)]:c += [f'add server {name} {750+port*160} 600',f'connect {name} eth0 PUBLIC fa0/{port}',f'ip {name} eth0 {address}/24',f'gateway {name} 203.0.113.1']
 c+=['http-page PublicWeb / "<h1>Public service works</h1>"','add server Files 300 720','connect Files eth0 LAN fa0/5','ip Files eth0 10.20.0.50/24','gateway Files 10.20.0.1']
 actions=[dict(device='Files',action='service',service=p,enabled=True) for p in ('ftp','tftp','smtp','pop3','ntp','snmp')]
 actions += [dict(device='Files',action='service_user',service='ftp',username='reader',password='lab-password',permissions=['read','list']),dict(device='Files',action='file_write',file='welcome.txt',content='original branch lab'),dict(device='EDGE',action='service',service='ssh',enabled=True),dict(device='EDGE',action='local_user',username='student',password='lab-password')]
 return c,actions

def industrial():
 c=['add switch CORE 450 300','add-model WLC-3504 WLC 600 100','add-model AccessPoint-PT AP 200 200','add-model Laptop-PT WirelessClient 100 400','add-model PLC-PT PLC 450 500','add-model DataHistorianServer Historian 650 500','add-model 7960 Phone1 800 300','add-model 7960 Phone2 1000 300','add server Services 950 500','add pc Operator 250 600']
 for n,p in [('WLC',1),('AP',2),('PLC',3),('Historian',4),('Phone1',5),('Phone2',6),('Services',7),('Operator',8)]:c.append(f'connect {n} eth0 CORE fa0/{p}')
 for n,i in [('WLC',2),('AP',3),('PLC',4),('Historian',5),('Phone1',6),('Phone2',7),('Services',8),('Operator',9)]:c.append(f'ip {n} eth0 192.0.2.{i}/24')
 c += ['physical place AP building0','physical place WirelessClient building0','physical device-position AP 100 100','physical device-position WirelessClient 100 100']
 a=[dict(device='WLC',action='wlc_wlan',ssid='Operations',security='wpa2-psk',key='lab-password'),dict(device='WLC',action='wlc_group',name='Factory',aps=['AP'],wlans=['Operations']),dict(device='WirelessClient',action='associate',ssid='Operations',security='wpa2-psk',key='lab-password',ip='192.0.2.10/24'),dict(device='PLC',action='service',service='modbus',enabled=True),dict(device='Services',action='service',service='telephony',enabled=True),dict(device='Phone1',action='telephony',number='1001',server='Services'),dict(device='Phone2',action='telephony',number='1002',server='Services')]
 return c,a

_UNSET=object()

class Client:
 def __init__(self,url):self.url=url
 def request(self,path,data=_UNSET):
  request=Request(self.url+path,data=None if data is _UNSET else json.dumps(data).encode(),headers={'content-type':'application/json'})
  try:
   with urlopen(request,timeout=60) as response:return response.status,json.load(response)
  except HTTPError as error:
   with error:return error.code,json.load(error)
 def command(self,text,ok=True):
  status,data=self.request('/api/command',{'command':text})
  if data.get('ok')!=ok:raise AssertionError((text,status,data.get('output')))
  return data
 def action(self,device,action,**kwargs):
  status,data=self.request('/api/device-config/action',dict(device=device,action=action,**kwargs))
  if not data.get('ok'):raise AssertionError((device,action,status,data.get('output')))
  try:return json.loads(data['output'])
  except (ValueError,KeyError):return data.get('output')
 def ping(self,source,target,expected=True):
  data=self.command(f'ping {source} {target}');success='PING success' in data['output'].split('\n',1)[0]
  if success!=expected:raise AssertionError((source,target,expected,data['output']))
  return data['output']


def run(output, executable=None):
 report={'projects':[],'findings':[]};output.mkdir(parents=True,exist_ok=True)
 with tempfile.TemporaryDirectory(prefix='packet-tracker-audit-') as folder:
  folder=Path(folder);ready=folder/'ready.json';process=subprocess.Popen(([str(executable.resolve())] if executable else [sys.executable,str(ROOT/'desktop.py')])+['--server','--port','0','--state',str(folder/'state.json'),'--ready-file',str(ready)],cwd=ROOT,stdout=subprocess.DEVNULL,stderr=subprocess.DEVNULL)
  try:
   for _ in range(200):
    if ready.exists():break
    if process.poll() is not None:raise RuntimeError('Audit server exited')
    time.sleep(.05)
   api=Client('http://127.0.0.1:'+str(json.loads(ready.read_text())['port']))
   for name,build in [('campus',campus),('branch',branch),('industrial',industrial)]:
    api.command('reset');commands,actions=build();status,batch=api.request('/api/batch',{'commands':commands})
    if not batch.get('ok'):raise AssertionError((name,[r for r in batch['results'] if not r['ok']]))
    for a in actions:api.action(**a)
    if name=='campus':
     for n in range(1,7):api.ping('PC'+str(n),'172.16.3.20')
     api.ping('PC1','10.10.20.100');api.ping('WEB','10.10.10.100')
     status,page=api.request('/api/web',{'source':'PC1','url':'http://campus.lab/'})
     if 'Campus service works' not in page.get('html',''):raise AssertionError(page.get('error',page))
     api.command('down R1 g0/2');api.ping('PC1','172.16.3.20');api.command('up R1 g0/2')
     api.command('down SW1 g0/1');api.ping('PC2','172.16.3.20');api.command('up SW1 g0/1')
    elif name=='branch':
     for n in range(1,5):api.ping('Branch'+str(n),'203.0.113.10')
     result=api.action('Branch1','transfer',server='Files',protocol='ftp',operation='get',username='reader',password='lab-password',file='welcome.txt')
     if result!='original branch lab':raise AssertionError(result)
     if api.action('Branch2','transfer',server='Files',protocol='tftp',operation='get',file='welcome.txt')!='original branch lab':raise AssertionError('TFTP transfer failed')
     api.action('Files','service',service='smtp',enabled=True,domain='lab.local')
     for user in ('alice','bob'):api.action('Files','service_user',service='smtp',username=user,password='lab-password')
     api.action('Branch1','mail_send',server='Files',username='alice',password='lab-password',to='bob@lab.local',subject='Branch audit',text='delivery verified')
     if api.action('Branch2','mail_receive',server='Files',username='bob',password='lab-password')[0]['text']!='delivery verified':raise AssertionError('Mail delivery failed')
     api.action('Branch1','clock_sync',server='Files')
     api.action('Files','service',service='snmp',enabled=True,read_community='public')
     if api.action('Branch1','snmp',server='Files',community='public',oid='sysName')!='Files':raise AssertionError('SNMP read failed')
     api.command('acl EDGE BLOCK deny icmp any any');api.command('acl EDGE BLOCK permit ip any any');api.command('access-group EDGE g0/0 BLOCK in');api.ping('Branch1','203.0.113.10',False);api.command('access-group EDGE g0/0 none in');api.ping('Branch1','203.0.113.10')
    else:
     api.ping('WirelessClient','192.0.2.4')
     api.action('Operator','modbus_send',server='PLC',data={'temperature':42});received=api.action('PLC','modbus_receive')
     if received['data']['temperature']!=42:raise AssertionError(received)
     api.action('PLC','industrial',tags={'input':1})
     api.action('PLC','plc_program',blocks=[{'op':'timer','inputs':['input'],'output':'alarm','preset':2}])
     if api.action('PLC','plc_run',seconds=1)['alarm']!=0 or api.action('PLC','plc_run',seconds=1)['alarm']!=1:raise AssertionError('PLC timer failed')
     api.action('Historian','service',service='historian',enabled=True)
     if api.action('Historian','historian_collect',source='PLC')<1:raise AssertionError('Historian collection failed')
     for device,ip in [('Operator','2001:db8::9/64'),('Services','2001:db8::8/64')]:api.action(device,'interface',interface='eth0',ipv6=ip)
     api.ping('Operator','2001:db8::8')
     api.action('Phone1','call',number='1002');api.action('Phone2','call',number='1001',operation='answer');api.action('Phone1','call',operation='hangup')
     api.command('down PLC eth0');api.ping('WirelessClient','192.0.2.4',False);api.command('up PLC eth0');api.ping('WirelessClient','192.0.2.4')
    _,state=api.request('/api/state');path=output/(name+'.json');path.write_text(json.dumps(state,indent=2))
    encoded=base64.b64encode(path.read_bytes()).decode();_,loaded=api.request('/api/lab/import',{'filename':path.name,'data':encoded,'commit':True})
    if not loaded.get('ok') or loaded['state']['devices']!=state['devices'] or loaded['state']['links']!=state['links']:raise AssertionError('Persistence changed devices, configuration, or links')
    source,target={'campus':('PC1','172.16.3.20'),'branch':('Branch1','203.0.113.10'),'industrial':('WirelessClient','192.0.2.4')}[name]
    api.ping(source,target)
    entry={'name':name,'devices':len(state['devices']),'links':len(state['links']),'commands':len(commands),'actions':len(actions),'checks':'passed','lab':str(path)};report['projects'].append(entry);print(json.dumps(entry),flush=True)
   for payload in ([],None,'bad',42,{}, {'command':[]}, {'command':42}):
    try:
     status,data=api.request('/api/command',payload)
     if status!=400:report['findings'].append({'case':'invalid JSON request shape','payload':payload,'status':status})
    except Exception as e:report['findings'].append({'case':'invalid JSON request shape','payload':payload,'error':str(e)})
   for route in ('/api/batch','/api/device-config/action','/api/lab/import','/api/web'):
    status,data=api.request(route,[])
    if status!=400 or data.get('ok') is not False:raise AssertionError((route,status,data))
   for value in ('false',0,1,None):
    status,data=api.request('/api/batch',{'commands':['add pc ShouldNotExist'],'stop_on_error':value})
    if status!=400 or 'ShouldNotExist' in api.request('/api/state')[1]['devices']:raise AssertionError('Invalid batch modified state')
   api.command('add router ErrorProbe')
   api.command('ios ErrorProbe not-a-command',ok=False)
   status,batch=api.request('/api/batch',{'commands':['ios ErrorProbe not-a-command','add pc ShouldNotRun']})
   if batch.get('ok') or batch.get('executed')!=1 or 'ShouldNotRun' in batch['state']['devices']:raise AssertionError('IOS batch failure did not stop execution')
   before=api.request('/api/state')[1]
   api.command('connect Operator eth0 ErrorProbe g0/0',ok=False)
   if api.request('/api/state')[1]['links']!=before['links']:raise AssertionError('Failed connect changed links')
   api.command('add pc RecoveryMarker')
   previous=api.request('/api/state')[1]
   encoded=base64.b64encode((output/'campus.json').read_bytes()).decode()
   api.request('/api/lab/import',{'filename':'campus.json','data':encoded,'commit':True})
   api.command('undo');restored=api.request('/api/state')[1]
   if restored['devices']!=previous['devices'] or restored['links']!=previous['links']:raise AssertionError('Import Undo changed project configuration')
   api.command('redo')
   if set(api.request('/api/state')[1]['devices'])!=set(json.loads((output/'campus.json').read_text())['devices']):raise AssertionError('Import Redo restored the wrong project')
  finally:process.terminate();process.wait(timeout=10)
 (output/'report.json').write_text(json.dumps(report,indent=2));return report

if __name__=='__main__':
 parser=argparse.ArgumentParser();parser.add_argument('--output',type=Path,default=ROOT/'labs'/'audit');parser.add_argument('--executable',type=Path,help='Audit a standalone build instead of source');args=parser.parse_args();result=run(args.output,args.executable);print(json.dumps(result,indent=2))

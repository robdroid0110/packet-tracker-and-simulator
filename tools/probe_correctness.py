#!/usr/bin/env python3
"""Reproduce independent STP and OSPF correctness observations in memory."""
import json
from pathlib import Path
import sys
sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
from netsim.model import NetworkLab
from netsim.ios import IOSSession


def stp_disconnected():
    lab=NetworkLab()
    for name in ('A1','A2','B1','B2'):
        lab.add_device('switch',name)
    lab.devices['A1'].stp_priority=0
    for a,b in (('A1','A2'),('B1','B2')):lab.connect(a,'g0/1',b,'g0/1')
    for i,switch in ((1,'B1'),(2,'B2')):
        name=f'Host{i}';lab.add_device('pc',name);lab.connect(name,'eth0',switch,'fa0/1');lab.set_ip(name,'eth0',f'192.168.10.{i}/24')
    tree=lab.spanning_tree(1);ok,text=lab.ping('Host1','192.168.10.2')
    return {'case':'independent_stp_components','expected':'two independent switched components elect roots; Host1 reaches Host2',
            'observed':{'ping_success':ok,'trace':text,'root':tree['root'],
                        'root_costs':tree['root_costs'],'b1_port':tree['ports'].get('B1:g0/1'),
                        'b2_port':tree['ports'].get('B2:g0/1')},'bug_reproduced':not ok}


def routers():
    lab=NetworkLab()
    for kind,name in (('router','R1'),('router','R2'),('pc','LAN')):lab.add_device(kind,name)
    lab.connect('R1','g0/0','R2','g0/0');lab.connect('R2','g0/1','LAN','eth0')
    for device,interface,address in (('R1','g0/0','10.0.0.1/30'),('R2','g0/0','10.0.0.2/30'),('R2','g0/1','192.168.2.1/24')):
        lab.set_ip(device,interface,address)
    return lab


def ospf_networks():
    lab=routers()
    lab.enable_ospf('R1','198.51.100.0/24');lab.enable_ospf('R2','203.0.113.0/24')
    routes=[{'network':r.network,'next_hop':r.next_hop,'source':r.source} for r in lab.devices['R1'].routes]
    return {'case':'ospf_nonmatching_networks','expected':'no adjacency or learned routes when network statements enable no interfaces',
            'observed':{'r1_networks':lab.devices['R1'].ospf_networks,'r2_networks':lab.devices['R2'].ospf_networks,'r1_routes':routes},
            'bug_reproduced':any(r['source']=='ospf' for r in routes)}


def ospf_area():
    lab=routers();transcript={}
    for name,area in (('R1',0),('R2',1)):
        session=IOSSession(lab,name);transcript[name]=[]
        for command in ('enable','configure terminal','router ospf 1',f'network 10.0.0.0 0.0.0.3 area {area}'):
            result=session.execute(command);transcript[name].append({'command':command,'output':result})
            if result.startswith('% '):raise AssertionError(result)
        session.execute('end');running=session.execute('show running-config')
        transcript[name].append({'command':'show running-config (OSPF network lines)','output':'\n'.join(line for line in running.splitlines() if 'network 10.0.0.0' in line)})
    routes=[{'network':r.network,'next_hop':r.next_hop,'source':r.source} for r in lab.devices['R1'].routes]
    return {'case':'ospf_area_mismatch','expected':'different areas on the shared interface do not form an adjacency',
            'observed':{'commands':transcript,'r1_routes':routes},
            'bug_reproduced':any(r['source']=='ospf' for r in routes)}

if __name__=='__main__':print(json.dumps([stp_disconnected(),ospf_networks(),ospf_area()],indent=2))

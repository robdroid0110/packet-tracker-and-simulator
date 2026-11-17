#!/usr/bin/env python3
"""Exercise three routing domains across one isolated topology."""
import json
from pathlib import Path
import sys
sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
from netsim.model import NetworkLab
from netsim.device_config import action
from netsim.ios import IOSSession


def build():
    lab=NetworkLab()
    for name in ('O1','O2','E1','E2','P1','P2'):lab.add_device('router',name)
    for name in ('HostO','HostE','HostP'):lab.add_device('pc',name)
    for a,ap,b,bp in [('O1','g0/0','O2','g0/0'),('O2','g0/1','E1','g0/0'),('E1','g0/1','E2','g0/0'),('E1','g0/2','P1','g0/0'),('P1','g0/1','P2','g0/0'),('O1','g0/1','HostO','eth0'),('E2','g0/1','HostE','eth0'),('P2','g0/1','HostP','eth0')]:lab.connect(a,ap,b,bp)
    ips=[('O1','g0/0','192.0.2.1/30'),('O2','g0/0','192.0.2.2/30'),('O2','g0/1','198.18.0.1/30'),('E1','g0/0','198.18.0.2/30'),('E1','g0/1','192.0.2.5/30'),('E2','g0/0','192.0.2.6/30'),('E1','g0/2','198.18.0.5/30'),('P1','g0/0','198.18.0.6/30'),('P1','g0/1','192.0.2.9/30'),('P2','g0/0','192.0.2.10/30')]
    ips += [(r,'g0/1',f'10.{i}.0.1/24') for r,i in [('O1',1),('E2',2),('P2',3)]]
    ips += [(h,'eth0',f'10.{i}.0.2/24') for h,i in [('HostO',1),('HostE',2),('HostP',3)]]
    for d,p,ip in ips:lab.set_ip(d,p,ip)
    for h,i in [('HostO',1),('HostE',2),('HostP',3)]:lab.set_gateway(h,f'10.{i}.0.1')
    for name in ('O1','O2'):lab.enable_ospf(name)
    for name,network in [('E1','192.0.2.4/30'),('E2','192.0.2.4/30'),('E2','10.2.0.0/24')]:action(lab,{'device':name,'action':'eigrp','asn':10,'network':network})
    for name,network in [('P1','192.0.2.8/30'),('P2','192.0.2.8/30'),('P2','10.3.0.0/24')]:action(lab,{'device':name,'action':'rip','network':network})
    return lab


def ping(lab,a,b):
    ok,trace=lab.ping(a,b);return {'success':ok,'trace':trace}


def main():
    lab=build()
    routes={n:[{'network':r.network,'source':r.source,'next_hop':r.next_hop} for r in lab.devices[n].routes] for n in ('O1','E1','P1')}
    before=ping(lab,'HostO','10.2.0.2')
    ios=IOSSession(lab,'O2');redistribute=[]
    for cmd in ('enable','configure terminal','router ospf 1','redistribute eigrp 10 subnets'):redistribute.append({'command':cmd,'output':ios.execute(cmd)})
    bgp=IOSSession(lab,'O2');bgp_transcript=[]
    for cmd in ('enable','configure terminal','router bgp 65000'):bgp_transcript.append({'command':cmd,'output':bgp.execute(cmd)})
    static=[('O1','10.2.0.0/24','192.0.2.2'),('O1','10.3.0.0/24','192.0.2.2'),('O2','10.2.0.0/24','198.18.0.2'),('O2','10.3.0.0/24','198.18.0.2'),('E1','10.1.0.0/24','198.18.0.1'),('E1','10.3.0.0/24','198.18.0.6'),('E2','10.1.0.0/24','192.0.2.5'),('E2','10.3.0.0/24','192.0.2.5'),('P1','10.1.0.0/24','198.18.0.5'),('P1','10.2.0.0/24','198.18.0.5'),('P2','10.1.0.0/24','192.0.2.9'),('P2','10.2.0.0/24','192.0.2.9')]
    for router,network,hop in static:lab.add_static_route(router,network,next_hop=hop)
    after={f'{host}->{target}':ping(lab,host,target) for host,target in [('HostO','10.2.0.2'),('HostO','10.3.0.2'),('HostE','10.3.0.2')]}
    lab.set_interface_state('E1','g0/2',False);fault=ping(lab,'HostO','10.3.0.2');lab.set_interface_state('E1','g0/2',True);recovery=ping(lab,'HostO','10.3.0.2')
    print(json.dumps({'devices':len(lab.devices),'links':len(lab.links),'dynamic_routes':routes,
      'cross_domain_without_redistribution':before,'redistribution_cli':redistribute,'bgp_cli':bgp_transcript,
      'cross_domain_with_static_routes':after,'p1_link_down':fault,'p1_link_restored':recovery},indent=2))

if __name__=='__main__':main()

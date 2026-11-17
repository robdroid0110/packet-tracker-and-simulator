import tempfile
import unittest
from pathlib import Path
from netsim.model import NetworkLab
from netsim.cli import CommandProcessor


class NetLabTests(unittest.TestCase):
    def test_single_lan_ping(self):
        n=NetworkLab(); n.add_device('pc','PC1'); n.add_device('pc','PC2'); n.add_device('switch','SW1')
        n.connect('PC1','eth0','SW1','fa0/1'); n.connect('PC2','eth0','SW1','fa0/2')
        n.set_ip('PC1','eth0','192.168.10.10/24'); n.set_ip('PC2','eth0','192.168.10.20/24')
        ok,trace=n.ping('PC1','192.168.10.20'); self.assertTrue(ok,trace)

    def test_vlan_isolation(self):
        n=NetworkLab(); n.add_device('pc','PC1'); n.add_device('pc','PC2'); n.add_device('switch','SW1')
        n.connect('PC1','eth0','SW1','fa0/1'); n.connect('PC2','eth0','SW1','fa0/2')
        n.set_switchport_access('SW1','fa0/1',10); n.set_switchport_access('SW1','fa0/2',20)
        n.set_ip('PC1','eth0','10.0.0.10/24'); n.set_ip('PC2','eth0','10.0.0.20/24')
        ok,_=n.ping('PC1','10.0.0.20'); self.assertFalse(ok)

    def test_static_routing(self):
        n=NetworkLab()
        for kind,name in [('pc','PC1'),('switch','SW1'),('router','R1'),('router','R2'),('switch','SW2'),('pc','PC2')]: n.add_device(kind,name)
        n.connect('PC1','eth0','SW1','fa0/1'); n.connect('R1','g0/0','SW1','fa0/2')
        n.connect('R1','g0/1','R2','g0/1')
        n.connect('R2','g0/0','SW2','fa0/1'); n.connect('PC2','eth0','SW2','fa0/2')
        n.set_ip('PC1','eth0','10.1.0.10/24'); n.set_gateway('PC1','10.1.0.1')
        n.set_ip('R1','g0/0','10.1.0.1/24'); n.set_ip('R1','g0/1','10.255.0.1/30')
        n.set_ip('R2','g0/1','10.255.0.2/30'); n.set_ip('R2','g0/0','10.2.0.1/24')
        n.set_ip('PC2','eth0','10.2.0.10/24'); n.set_gateway('PC2','10.2.0.1')
        n.add_static_route('R1','10.2.0.0/24',next_hop='10.255.0.2')
        n.add_static_route('R2','10.1.0.0/24',next_hop='10.255.0.1')
        ok,trace=n.ping('PC1','10.2.0.10'); self.assertTrue(ok,trace)

    def test_ospf_learns_remote_lan(self):
        n=NetworkLab();
        for kind,name in [('router','R1'),('router','R2'),('pc','PC2')]: n.add_device(kind,name)
        n.connect('R1','g0/1','R2','g0/1'); n.connect('R2','g0/0','PC2','eth0')
        n.set_ip('R1','g0/1','10.255.0.1/30'); n.set_ip('R2','g0/1','10.255.0.2/30'); n.set_ip('R2','g0/0','172.16.2.1/24'); n.set_ip('PC2','eth0','172.16.2.10/24'); n.set_gateway('PC2','172.16.2.1')
        n.enable_ospf('R1'); n.enable_ospf('R2'); n.recompute_ospf()
        routes=[r for r in n.routing_table('R1') if r.source=='ospf']
        self.assertTrue(any(r.network=='172.16.2.0/24' for r in routes),routes)
        ok,trace=n.ping('R1','172.16.2.10'); self.assertTrue(ok,trace)

    def test_reply_path_required(self):
        n=NetworkLab()
        for kind,name in [('pc','PC1'),('router','R1'),('router','R2'),('pc','PC2')]: n.add_device(kind,name)
        n.connect('PC1','eth0','R1','g0/0'); n.connect('R1','g0/1','R2','g0/1'); n.connect('R2','g0/0','PC2','eth0')
        n.set_ip('PC1','eth0','10.1.0.10/24'); n.set_gateway('PC1','10.1.0.1'); n.set_ip('R1','g0/0','10.1.0.1/24')
        n.set_ip('R1','g0/1','10.255.0.1/30'); n.set_ip('R2','g0/1','10.255.0.2/30'); n.set_ip('R2','g0/0','10.2.0.1/24'); n.set_ip('PC2','eth0','10.2.0.10/24')
        n.add_static_route('R1','10.2.0.0/24',next_hop='10.255.0.2'); n.add_static_route('R2','10.1.0.0/24',next_hop='10.255.0.1')
        ok,text=n.ping('PC1','10.2.0.10'); self.assertFalse(ok,text)
        n.set_gateway('PC2','10.2.0.1'); ok,text=n.ping('PC1','10.2.0.10'); self.assertTrue(ok,text)

    def test_router_on_a_stick(self):
        n=NetworkLab()
        for kind,name in [('pc','PC10'),('pc','PC20'),('switch','SW1'),('router','R1')]: n.add_device(kind,name)
        n.connect('PC10','eth0','SW1','fa0/1'); n.connect('PC20','eth0','SW1','fa0/2'); n.connect('R1','g0/0','SW1','g0/1')
        n.set_switchport_access('SW1','fa0/1',10); n.set_switchport_access('SW1','fa0/2',20); n.set_switchport_trunk('SW1','g0/1',[10,20])
        n.set_ip('PC10','eth0','192.168.10.10/24'); n.set_gateway('PC10','192.168.10.1')
        n.set_ip('PC20','eth0','192.168.20.20/24'); n.set_gateway('PC20','192.168.20.1')
        n.add_subinterface('R1','g0/0',10,'192.168.10.1/24'); n.add_subinterface('R1','g0/0',20,'192.168.20.1/24')
        ok,text=n.ping('PC10','192.168.20.20'); self.assertTrue(ok,text)

    def test_dhcp_on_router(self):
        n=NetworkLab(); n.add_device('pc','PC1'); n.add_device('switch','SW1'); n.add_device('router','R1')
        n.connect('PC1','eth0','SW1','fa0/1'); n.connect('R1','g0/0','SW1','fa0/2'); n.set_ip('R1','g0/0','192.168.50.1/24')
        n.add_dhcp_pool('R1','LAN','192.168.50.0/24','192.168.50.1','192.168.50.100','192.168.50.110','1.1.1.1')
        lease=n.dhcp_request('PC1','eth0'); self.assertEqual(lease,'192.168.50.100/24'); self.assertEqual(n.devices['PC1'].default_gateway,'192.168.50.1'); self.assertEqual(n.devices['PC1'].dns_server,'1.1.1.1')
        ok,text=n.ping('PC1','192.168.50.1'); self.assertTrue(ok,text)

    def test_arp_and_mac_learning(self):
        n=NetworkLab(); n.add_device('pc','PC1'); n.add_device('pc','PC2'); n.add_device('switch','SW1')
        n.connect('PC1','eth0','SW1','fa0/1'); n.connect('PC2','eth0','SW1','fa0/2'); n.set_ip('PC1','eth0','192.168.1.10/24'); n.set_ip('PC2','eth0','192.168.1.20/24')
        ok,text=n.ping('PC1','192.168.1.20'); self.assertTrue(ok,text)
        self.assertEqual(n.devices['PC1'].arp_table['192.168.1.20'], n.devices['PC2'].interfaces['eth0'].mac)
        pc1mac=n.devices['PC1'].interfaces['eth0'].mac; pc2mac=n.devices['PC2'].interfaces['eth0'].mac
        self.assertEqual(n.devices['SW1'].mac_table[f'1:{pc1mac}'],'fa0/1')
        self.assertEqual(n.devices['SW1'].mac_table[f'1:{pc2mac}'],'fa0/2')

    def test_save_load(self):
        n=NetworkLab(); n.add_device('pc','PC1'); n.set_ip('PC1','eth0','192.0.2.10/24')
        with tempfile.TemporaryDirectory() as td:
            p=Path(td)/'lab.json'; n.save(str(p)); m=NetworkLab(); m.load(str(p)); self.assertEqual(m.devices['PC1'].interfaces['eth0'].ip,'192.0.2.10/24')

    def test_stp_blocks_redundant_triangle(self):
        n=NetworkLab()
        for sw in ('SW1','SW2','SW3'): n.add_device('switch',sw)
        n.set_stp_priority('SW1',0)
        n.connect('SW1','g0/1','SW2','g0/1'); n.connect('SW2','g0/2','SW3','g0/1'); n.connect('SW3','g0/2','SW1','g0/2')
        st=n.spanning_tree(1)
        self.assertEqual(st['root'],'SW1')
        states=[v['state'] for v in st['ports'].values()]
        self.assertTrue(any(x in {'blocking','discarding'} for x in states),st)

    def test_rstp_uses_discarding_state(self):
        n=NetworkLab()
        for sw in ('SW1','SW2','SW3'): n.add_device('switch',sw); n.set_stp_mode(sw,'rapid-pvst')
        n.set_stp_priority('SW1',0)
        n.connect('SW1','g0/1','SW2','g0/1'); n.connect('SW2','g0/2','SW3','g0/1'); n.connect('SW3','g0/2','SW1','g0/2')
        st=n.spanning_tree(1)
        self.assertIn('discarding',[v['state'] for v in st['ports'].values()])

    def test_lacp_etherchannel_bundles_parallel_links(self):
        n=NetworkLab(); n.add_device('switch','SW1'); n.add_device('switch','SW2')
        n.connect('SW1','g0/1','SW2','g0/1'); n.connect('SW1','g0/2','SW2','g0/2')
        for sw,ports in [('SW1',('g0/1','g0/2')),('SW2',('g0/1','g0/2'))]:
            for port in ports: n.set_channel_group(sw,port,1,'active')
        summary=n.etherchannel_summary('SW1')
        self.assertTrue(summary[0]['operational'],summary)
        st=n.spanning_tree(1)
        for port in ('g0/1','g0/2'):
            self.assertEqual(st['ports'][f'SW1:{port}']['state'],'forwarding')
            self.assertEqual(st['ports'][f'SW2:{port}']['state'],'forwarding')

    def test_native_vlan_configuration(self):
        n=NetworkLab(); n.add_device('switch','SW1'); n.add_device('switch','SW2')
        n.connect('SW1','g0/1','SW2','g0/1')
        n.set_switchport_trunk('SW1','g0/1',[10,99]); n.set_switchport_trunk('SW2','g0/1',[10,99])
        n.set_native_vlan('SW1','g0/1',99); n.set_native_vlan('SW2','g0/1',99)
        self.assertEqual(n.interfaces_native_for_test('SW1','g0/1') if hasattr(n,'interfaces_native_for_test') else n.devices['SW1'].interfaces['g0/1'].native_vlan,99)

    def test_ios_cli_configures_router_interface(self):
        n=NetworkLab(); n.add_device('router','R1'); n.add_device('pc','PC1'); n.connect('R1','g0/0','PC1','eth0')
        c=CommandProcessor(n)
        for cmd in ('ios R1 enable','ios R1 configure terminal','ios R1 interface g0/0','ios R1 ip address 10.10.10.1 255.255.255.0','ios R1 no shutdown'):
            self.assertNotIn('%',c.execute(cmd))
        self.assertEqual(n.devices['R1'].interfaces['g0/0'].ip,'10.10.10.1/24')
        out=c.execute('ios R1 show ip interface brief'); self.assertIn('10.10.10.1',out)

    def test_cdp_and_lldp_neighbors(self):
        n=NetworkLab(); n.add_device('switch','SW1'); n.add_device('router','R1'); n.connect('SW1','g0/1','R1','g0/0')
        self.assertEqual(n.neighbors('SW1','cdp')[0]['device'],'R1')
        self.assertEqual(n.neighbors('SW1','lldp'),[])
        n.set_discovery_protocol('SW1','lldp',True); n.set_discovery_protocol('R1','lldp',True)
        self.assertEqual(n.neighbors('R1','lldp')[0]['device'],'SW1')

    def test_dhcp_relay_helper_address(self):
        n=NetworkLab()
        for kind,name in [('pc','PC1'),('switch','SW1'),('router','R1'),('router','R2'),('switch','SW2'),('server','SRV')]: n.add_device(kind,name)
        n.connect('PC1','eth0','SW1','fa0/1'); n.connect('R1','g0/0','SW1','fa0/2'); n.connect('R1','g0/1','R2','g0/1'); n.connect('R2','g0/0','SW2','fa0/1'); n.connect('SRV','eth0','SW2','fa0/2')
        n.set_ip('R1','g0/0','10.1.0.1/24'); n.set_ip('R1','g0/1','10.255.0.1/30'); n.set_ip('R2','g0/1','10.255.0.2/30'); n.set_ip('R2','g0/0','10.2.0.1/24'); n.set_ip('SRV','eth0','10.2.0.10/24'); n.set_gateway('SRV','10.2.0.1')
        n.add_static_route('R1','10.2.0.0/24',next_hop='10.255.0.2'); n.add_static_route('R2','10.1.0.0/24',next_hop='10.255.0.1')
        n.add_dhcp_pool('SRV','CLIENTS','10.1.0.0/24','10.1.0.1','10.1.0.100','10.1.0.110','1.1.1.1'); n.set_helper_address('R1','g0/0','10.2.0.10')
        lease=n.dhcp_request('PC1','eth0'); self.assertEqual(lease,'10.1.0.100/24'); self.assertEqual(n.devices['PC1'].default_gateway,'10.1.0.1'); self.assertEqual(n.devices['PC1'].dns_server,'1.1.1.1')

if __name__=='__main__': unittest.main()

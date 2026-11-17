import unittest

from netsim.model import NetworkLab
from netsim.cli import CommandProcessor


class ACLTests(unittest.TestCase):
    def routed_lab(self):
        n=NetworkLab()
        for kind,name in [('pc','PC1'),('router','R1'),('router','R2'),('pc','PC2')]:
            n.add_device(kind,name)
        n.connect('PC1','eth0','R1','g0/0')
        n.connect('R1','g0/1','R2','g0/1')
        n.connect('R2','g0/0','PC2','eth0')
        n.set_ip('PC1','eth0','10.1.0.10/24'); n.set_gateway('PC1','10.1.0.1')
        n.set_ip('R1','g0/0','10.1.0.1/24'); n.set_ip('R1','g0/1','10.255.0.1/30')
        n.set_ip('R2','g0/1','10.255.0.2/30'); n.set_ip('R2','g0/0','10.2.0.1/24')
        n.set_ip('PC2','eth0','10.2.0.10/24'); n.set_gateway('PC2','10.2.0.1')
        n.add_static_route('R1','10.2.0.0/24',next_hop='10.255.0.2')
        n.add_static_route('R2','10.1.0.0/24',next_hop='10.255.0.1')
        return n

    def test_inbound_extended_acl_denies_ping(self):
        n=self.routed_lab()
        n.add_acl_rule('R1','100','deny','icmp','10.1.0.0/24','10.2.0.0/24')
        n.add_acl_rule('R1','100','permit','ip','any','any')
        n.set_access_group('R1','g0/0','100','in')
        ok,text=n.ping('PC1','10.2.0.10')
        self.assertFalse(ok,text)
        self.assertIn('ACL-in-deny(g0/0)',text)

    def test_acl_permit_restores_forwarding(self):
        n=self.routed_lab()
        n.add_acl_rule('R1','101','permit','icmp','10.1.0.0/24','10.2.0.0/24')
        n.set_access_group('R1','g0/0','101','in')
        ok,text=n.ping('PC1','10.2.0.10')
        self.assertTrue(ok,text)

    def test_ios_numbered_acl_and_access_group(self):
        n=self.routed_lab(); c=CommandProcessor(n)
        commands=[
            'ios R1 enable','ios R1 conf t',
            'ios R1 access-list 100 deny icmp 10.1.0.0 0.0.0.255 10.2.0.0 0.0.0.255',
            'ios R1 access-list 100 permit ip any any',
            'ios R1 interface g0/0','ios R1 ip access-group 100 in','ios R1 end',
        ]
        for cmd in commands:
            self.assertNotIn('%',c.execute(cmd),cmd)
        out=c.execute('ios R1 show access-lists')
        self.assertIn('deny icmp',out)
        ok,text=n.ping('PC1','10.2.0.10')
        self.assertFalse(ok,text)


if __name__ == '__main__':
    unittest.main()


class NATTests(unittest.TestCase):
    def nat_lab(self):
        n=NetworkLab()
        for kind,name in [('pc','LAN-PC'),('router','EDGE'),('pc','INTERNET-PC')]:
            n.add_device(kind,name)
        n.connect('LAN-PC','eth0','EDGE','g0/0')
        n.connect('EDGE','g0/1','INTERNET-PC','eth0')
        n.set_ip('LAN-PC','eth0','10.0.0.10/24'); n.set_gateway('LAN-PC','10.0.0.1')
        n.set_ip('EDGE','g0/0','10.0.0.1/24'); n.set_ip('EDGE','g0/1','203.0.113.1/24')
        n.set_ip('INTERNET-PC','eth0','203.0.113.10/24'); n.set_gateway('INTERNET-PC','203.0.113.1')
        n.set_nat_role('EDGE','g0/0','inside'); n.set_nat_role('EDGE','g0/1','outside')
        return n

    def test_pat_overload_translates_and_returns(self):
        n=self.nat_lab(); n.add_nat_overload('EDGE','10.0.0.0/24','g0/1')
        ok,text=n.ping('LAN-PC','203.0.113.10')
        self.assertTrue(ok,text)
        self.assertTrue(n.devices['EDGE'].nat_sessions)
        self.assertIn('203.0.113.1|203.0.113.10|icmp',n.devices['EDGE'].nat_sessions)

    def test_static_nat_accepts_inbound_ping(self):
        n=self.nat_lab(); n.add_nat_static('EDGE','10.0.0.10','203.0.113.50')
        ok,text=n.ping('INTERNET-PC','203.0.113.50')
        self.assertTrue(ok,text)
        self.assertIn('LAN-PC',text)

    def test_ios_pat_configuration(self):
        n=self.nat_lab(); c=CommandProcessor(n)
        cmds=[
            'ios EDGE enable','ios EDGE conf t',
            'ios EDGE access-list 1 permit 10.0.0.0 0.0.0.255',
            'ios EDGE interface g0/0','ios EDGE ip nat inside','ios EDGE exit',
            'ios EDGE interface g0/1','ios EDGE ip nat outside','ios EDGE exit',
            'ios EDGE ip nat inside source list 1 interface g0/1 overload','ios EDGE end',
        ]
        for cmd in cmds:
            self.assertNotIn('%',c.execute(cmd),cmd)
        ok,text=n.ping('LAN-PC','203.0.113.10')
        self.assertTrue(ok,text)
        out=c.execute('ios EDGE show ip nat translations')
        self.assertIn('10.0.0.10',out)

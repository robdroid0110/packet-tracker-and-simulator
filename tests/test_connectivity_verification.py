"""Versioned connectivity results, legacy behavior, and simulation jobs."""
from copy import deepcopy
from concurrent.futures import ThreadPoolExecutor
from http.client import HTTPConnection
import json
from pathlib import Path
import tempfile
import unittest
from urllib.error import HTTPError
from urllib.request import Request, urlopen

from netsim.cli import CommandProcessor
from netsim.model import NetworkLab
from netsim.simulation import action, apply, enqueue_task
import test_physical_special_notes_http as isolated

ROOT = Path(__file__).resolve().parents[1]


def lab_fixture(name='campus'):
    lab = NetworkLab()
    lab.load(str(ROOT / 'labs' / 'audit' / (name + '.json')))
    return lab


class ConnectivityModelTests(unittest.TestCase):
    def test_forward_reply_and_acl_failures_have_structured_hops(self):
        lab = lab_fixture()
        success = lab.ping_detailed('PC1', '172.16.3.20')
        self.assertEqual(success['status'], 'success')
        self.assertIs(success['reachable'], True)
        self.assertIsNone(success['reason'])
        self.assertEqual(success['paths']['forward'], ['PC1', 'R1', 'R3', 'WEB'])
        self.assertEqual(success['paths']['reply'], ['WEB', 'R3', 'R1', 'PC1'])
        self.assertEqual(lab.ping('PC1', '172.16.3.20'), (True, success['message']))
        lab.add_acl_rule('R1', 'BLOCK', 'deny', 'icmp', 'any', 'any')
        lab.set_access_group('R1', 'g0/0.10', 'BLOCK', 'in')
        denied = lab.ping_detailed('PC1', '172.16.3.20')
        self.assertEqual(denied['status'], 'failed')
        self.assertIs(denied['reachable'], False)
        self.assertEqual(denied['reason'], {'code': 'acl_in_denied', 'stage': 'forward',
                                             'device': 'R1', 'interface': 'g0/0.10'})
        self.assertEqual(denied['paths'], {'forward': ['PC1', 'R1'], 'reply': []})
        self.assertEqual(lab.ping('PC1', '172.16.3.20'), (False, denied['message']))
        lab.set_access_group('R1', 'g0/0.10', None, 'in')
        lab.set_access_group('R1', 'g0/0.10', 'BLOCK', 'out')
        reply = lab.ping_detailed('PC1', '172.16.3.20')
        self.assertEqual(reply['reason'], {'code': 'acl_out_denied', 'stage': 'reply',
                                           'device': 'R1', 'interface': 'g0/0.10'})
        self.assertEqual(reply['paths']['forward'][-1], 'WEB')
        self.assertEqual(reply['paths']['reply'], ['WEB', 'R3', 'R1'])

    def test_source_destination_l2_and_next_hop_failures(self):
        lab = lab_fixture()
        unknown = lab.ping_detailed('PC1', '192.0.2.99')
        self.assertEqual(unknown['reason'], {'code': 'destination_unassigned', 'stage': 'target'})
        lab.disconnect('PC2', 'eth0')
        broken = lab.ping_detailed('PC1', '10.10.10.101')
        self.assertEqual(broken['reason'], {'code': 'l2_unreachable', 'stage': 'forward',
                                            'device': 'PC1', 'interface': 'eth0'})
        lab.set_gateway('PC1', '10.10.10.254')
        missing = lab.ping_detailed('PC1', '172.16.3.20')
        self.assertEqual(missing['reason'], {'code': 'next_hop_missing', 'stage': 'forward',
                                             'device': 'PC1', 'next_hop': '10.10.10.254'})
        lab.set_interface_state('PC1', 'eth0', False)
        no_route = lab.ping_detailed('PC1', '172.16.3.20')
        self.assertEqual(no_route['reason'], {'code': 'no_source_route', 'stage': 'source', 'device': 'PC1'})

    def test_nat_result_and_state_match_legacy_ping(self):
        detailed = lab_fixture('branch')
        legacy = deepcopy(detailed)
        result = detailed.ping_detailed('Branch1', '203.0.113.10')
        self.assertTrue(result['reachable'])
        self.assertEqual(result['paths']['forward'], ['Branch1', 'EDGE', 'ISP', 'PublicWeb'])
        self.assertEqual(legacy.ping('Branch1', '203.0.113.10'), (True, result['message']))
        self.assertEqual(detailed.to_dict(), legacy.to_dict())
        self.assertTrue(detailed.devices['EDGE'].nat_sessions)

    def test_ipv6_success_outbound_and_reply_failure(self):
        lab = lab_fixture()
        lab.devices['PC1'].interfaces['eth0'].ipv6 = '2001:db8::1/64'
        lab.devices['PC2'].interfaces['eth0'].ipv6 = '2001:db8::2/64'
        success = lab.ping_detailed('PC1', '2001:0db8::2')
        self.assertEqual(success['destination_ip'], '2001:db8::2')
        self.assertEqual(success['ip_version'], 6)
        self.assertEqual(success['paths'], {'forward': ['PC1', 'PC2'], 'reply': ['PC2', 'PC1']})
        self.assertEqual(lab.ping('PC1', '2001:db8::2'), (True, success['message']))
        lab.devices['PC2'].config['ipv6_firewall'] = [
            {'action': 'permit', 'protocol': 'icmpv6', 'source': '2001:db8::1/128', 'destination': '2001:db8::2/128'},
            {'action': 'deny', 'protocol': 'icmpv6', 'source': '::/0', 'destination': '::/0'},
        ]
        failed = lab.ping_detailed('PC1', '2001:db8::2')
        self.assertEqual(failed['reason'], {'code': 'ipv6_firewall_denied', 'stage': 'reply', 'device': 'PC2'})
        self.assertEqual(failed['paths']['reply'], ['PC2'])
        lab.set_interface_state('PC1', 'eth0', False)
        failed = lab.ping_detailed('PC1', '2001:db8::2')
        self.assertEqual(failed['reason']['code'], 'source_address_unavailable')

    def test_queue_defers_verification_and_survives_save(self):
        lab = lab_fixture()
        action(lab, {'action': 'mode', 'mode': 'simulation'})
        before = deepcopy(lab.devices['PC1'].arp_table)
        queued = lab.ping_detailed('PC1', '10.10.10.101')
        self.assertEqual(queued['status'], 'queued')
        self.assertIsNone(queued['reachable'])
        self.assertIsNone(queued['reason'])
        self.assertEqual(lab.devices['PC1'].arp_table, before)
        ident = queued['job_id']
        with tempfile.TemporaryDirectory(prefix='pt-verify-') as tmp:
            path = Path(tmp) / 'lab.json'
            lab.save(str(path))
            restored = NetworkLab()
            restored.load(str(path))
            restored.disconnect('PC2', 'eth0')
            for _ in range(30):
                if action(restored, {'action': 'step'}) is None:
                    break
            else:
                self.fail('simulation did not finish')
            outcome = restored.simulation['pdus'][ident]['result']
            self.assertFalse(outcome['ok'])
            self.assertEqual(outcome['output']['verification']['reason']['code'], 'l2_unreachable')
            self.assertFalse(outcome['output']['verification']['reachable'])

    def test_renaming_source_updates_other_queued_client_tasks(self):
        for operation, payload in (
            ('http', {'source': 'PC1', 'url': 'http://172.16.3.20/'}),
            ('device-config', {'device': 'PC1', 'action': 'host_command', 'command': 'ipconfig'}),
        ):
            with self.subTest(operation=operation):
                lab = lab_fixture()
                action(lab, {'action': 'mode', 'mode': 'simulation'})
                ident = enqueue_task(lab, operation, payload)
                lab.rename_device('PC1', 'Renamed')
                for _ in range(30):
                    if action(lab, {'action': 'step'}) is None:
                        break
                else:
                    self.fail('queued client task did not finish')
                self.assertTrue(lab.simulation['pdus'][ident]['result']['ok'])


class ConnectivityHTTPTests(unittest.TestCase):
    setUpClass = isolated.PhysicalSpecialNotesHTTPTests.__dict__['setUpClass']
    tearDownClass = isolated.PhysicalSpecialNotesHTTPTests.__dict__['tearDownClass']
    setUp = isolated.PhysicalSpecialNotesHTTPTests.setUp
    request = isolated.PhysicalSpecialNotesHTTPTests.request

    def command(self, value):
        code, result = self.request('/api/command', {'command': value})
        self.assertEqual(code, 200)
        self.assertTrue(result['ok'], result)
        return result

    def seed(self):
        for value in ('add pc A', 'add pc B', 'connect A eth0 B eth0',
                      'ip A eth0 192.0.2.1/24', 'ip B eth0 192.0.2.2/24'):
            self.command(value)

    def test_discovery_success_failure_and_legacy_command(self):
        self.seed()
        status, schema = self.request('/api/v1/connectivity/schema')
        self.assertEqual(status, 200)
        self.assertEqual(schema['version'], 1)
        self.assertIn('acl_in_denied', schema['failure_codes'])
        _, capabilities = self.request('/api/capabilities')
        self.assertEqual(capabilities['agent_endpoints']['verify_ping'],
                         'POST /api/v1/connectivity/ping {source,destination_ip}')
        self.assertIn('network.verify_ping', {a['id'] for a in capabilities['actions']})
        status, data = self.request('/api/v1/connectivity/ping', {'source': 'A', 'destination_ip': '192.0.2.2'})
        self.assertEqual(status, 200)
        self.assertTrue(data['ok'])
        self.assertTrue(data['result']['reachable'])
        self.assertEqual(data['result']['paths'], {'forward': ['A', 'B'], 'reply': ['B', 'A']})
        self.assertNotIn('state', data)
        self.assertTrue(self.app.LAB.devices['A'].arp_table)
        restored = NetworkLab()
        restored.load(str(self.app.STATE))
        self.assertTrue(restored.devices['A'].arp_table)
        self.command('down B eth0')
        status, data = self.request('/api/v1/connectivity/ping', {'source': 'A', 'destination_ip': '192.0.2.2'})
        self.assertEqual(status, 200)
        self.assertTrue(data['ok'])
        self.assertFalse(data['result']['reachable'])
        self.assertEqual(data['result']['reason']['code'], 'no_source_route')
        legacy = self.command('ping A 192.0.2.2')
        self.assertIn('PING failed', legacy['output'])

    def test_bad_requests_are_structured_and_do_not_change_saved_lab(self):
        self.seed()
        before = self.app.LAB.to_dict()
        saved = self.app.STATE.read_bytes()
        cases = [({}, 'invalid_request'), ({'source': 'A'}, 'invalid_request'),
                 ({'source': 'A', 'destination_ip': 1}, 'invalid_request'),
                 ({'source': 'A', 'destination_ip': 'bad'}, 'invalid_request'),
                 ({'source': 'A', 'destination_ip': 'fe80::1%eth0'}, 'invalid_request'),
                 ({'source': 'A', 'destination_ip': '192.0.2.2', 'extra': True}, 'invalid_request'),
                 ({'source': 'missing', 'destination_ip': '192.0.2.2'}, 'unknown_source'),
                 ([], 'invalid_request')]
        for body, expected in cases:
            status, response = self.request('/api/v1/connectivity/ping', body)
            self.assertEqual(status, 400, body)
            self.assertEqual(response['error']['code'], expected)
            self.assertEqual(self.app.LAB.to_dict(), before)
            self.assertEqual(self.app.STATE.read_bytes(), saved)
        request = Request(f'http://127.0.0.1:{self.port}/api/v1/connectivity/ping',
                          data=b'{invalid', headers={'content-type': 'application/json'})
        with self.assertRaises(HTTPError) as caught:
            urlopen(request, timeout=5)
        with caught.exception as error:
            self.assertEqual(json.load(error)['error']['code'], 'invalid_request')
        connection = HTTPConnection('127.0.0.1', self.port, timeout=5)
        try:
            connection.request('POST', '/api/v1/connectivity/ping', body=b'',
                               headers={'content-length': '17000001'})
            response = connection.getresponse()
            self.assertEqual(response.status, 413)
            self.assertEqual(json.load(response)['error']['code'], 'request_too_large')
        finally:
            connection.close()
        self.assertEqual(self.app.STATE.read_bytes(), saved)

    def test_full_simulation_queue_rejects_without_changing_state(self):
        self.seed()
        self.request('/api/simulation/action', {'action': 'mode', 'mode': 'simulation'})
        with self.app.LOCK:
            for number in range(500):
                apply(self.app.LAB, {'action': 'pdu_add', 'id': f'full-{number}',
                                     'source': 'A', 'destination': 'B'})
            self.app.save_state()
            before = self.app.LAB.to_dict()
            saved = self.app.STATE.read_bytes()
        status, data = self.request('/api/v1/connectivity/ping', {'source': 'A', 'destination_ip': '192.0.2.2'})
        self.assertEqual(status, 400)
        self.assertEqual(data['error']['code'], 'operation_rejected')
        self.assertEqual(self.app.LAB.to_dict(), before)
        self.assertEqual(self.app.STATE.read_bytes(), saved)

    def test_simultaneous_agent_requests_keep_results_isolated(self):
        self.seed()
        addresses = ['192.0.2.2', '192.0.2.99'] * 10
        def probe(address):
            return self.request('/api/v1/connectivity/ping', {'source': 'A', 'destination_ip': address})
        with ThreadPoolExecutor(max_workers=6) as pool:
            for address, (status, data) in zip(addresses, pool.map(probe, addresses)):
                self.assertEqual(status, 200)
                self.assertEqual(data['result']['destination_ip'], address)
                self.assertEqual(data['result']['reachable'], address == '192.0.2.2')
                if address.endswith('.99'):
                    self.assertEqual(data['result']['reason']['code'], 'destination_unassigned')
        self.assertTrue(self.app.LAB.devices['A'].arp_table)

    def test_ipv6_agent_request_and_queued_result(self):
        self.seed()
        for name, address in (('A', '2001:db8::1/64'), ('B', '2001:db8::2/64')):
            status, data = self.request('/api/device-config/action',
                                        {'device': name, 'action': 'interface', 'interface': 'eth0', 'ipv6': address})
            self.assertEqual(status, 200, data)
        status, data = self.request('/api/v1/connectivity/ping', {'source': 'A', 'destination_ip': '2001:db8::2'})
        self.assertEqual(status, 200)
        self.assertTrue(data['result']['reachable'])
        self.assertEqual(data['result']['ip_version'], 6)
        self.assertEqual(data['result']['paths']['forward'], ['A', 'B'])
        self.request('/api/simulation/action', {'action': 'mode', 'mode': 'simulation'})
        status, data = self.request('/api/v1/connectivity/ping', {'source': 'A', 'destination_ip': '2001:db8::2'})
        self.assertEqual(status, 202)
        ident = data['result']['job_id']
        for _ in range(30):
            _, step = self.request('/api/simulation/action', {'action': 'step'})
            pdu = step['state']['simulation']['pdus'][ident]
            if pdu['result'] is not None:
                break
        else:
            self.fail('queued IPv6 ping did not complete')
        self.assertTrue(pdu['result']['output']['verification']['reachable'])
        self.assertEqual(pdu['result']['output']['verification']['ip_version'], 6)

    def test_simulation_queued_result_can_be_checked_via_api(self):
        self.seed()
        self.request('/api/simulation/action', {'action': 'mode', 'mode': 'simulation'})
        status, queued = self.request('/api/v1/connectivity/ping', {'source': 'A', 'destination_ip': '192.0.2.2'})
        self.assertEqual(status, 202)
        self.assertIsNone(queued['result']['reachable'])
        ident = queued['result']['job_id']
        self.assertFalse(self.app.LAB.devices['A'].arp_table)
        for _ in range(30):
            status, data = self.request('/api/simulation/action', {'action': 'step'})
            self.assertEqual(status, 200)
            pdu = data['state']['simulation']['pdus'][ident]
            if pdu['result'] is not None:
                break
        else:
            self.fail('queued ping did not complete')
        outcome = pdu['result']['output']['verification']
        self.assertEqual(outcome['status'], 'success')
        self.assertTrue(outcome['reachable'])
        self.assertIsNone(outcome['job_id'])
        _, view = self.request('/api/simulation')
        self.assertEqual(view['pdus'][ident]['result']['output']['verification'], outcome)
        restored = NetworkLab()
        restored.load(str(self.app.STATE))
        self.assertTrue(restored.simulation['pdus'][ident]['result']['output']['verification']['reachable'])

    def test_renamed_source_keeps_queued_ping_valid(self):
        self.seed()
        self.request('/api/simulation/action', {'action': 'mode', 'mode': 'simulation'})
        status, queued = self.request('/api/v1/connectivity/ping', {'source': 'A', 'destination_ip': '192.0.2.2'})
        self.assertEqual(status, 202)
        ident = queued['result']['job_id']
        self.command('rename A Renamed')
        for _ in range(30):
            status, data = self.request('/api/simulation/action', {'action': 'step'})
            self.assertEqual(status, 200)
            pdu = data['state']['simulation']['pdus'][ident]
            if pdu['result'] is not None:
                break
        else:
            self.fail('renamed source ping did not complete')
        result = pdu['result']['output']['verification']
        self.assertTrue(result['reachable'])
        self.assertEqual(result['source'], 'Renamed')
        self.assertEqual(result['paths']['forward'][0], 'Renamed')


if __name__ == '__main__':
    unittest.main()

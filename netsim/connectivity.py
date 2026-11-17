"""Versioned, structured connectivity verification on the simulator engine."""
from ipaddress import ip_address

from .model import LabError


FAILURE_CODES = {
    'destination_unassigned': 'Destination IP has no modeled owner.',
    'no_source_route': 'Source has no usable IPv4 route or source address.',
    'source_address_unavailable': 'Source has no operational IPv6 address.',
    'routing_loop': 'The routed IPv4 path revisited a device.',
    'hop_limit_or_loop': 'The IPv6 hop limit was exhausted or a device was revisited.',
    'acl_in_denied': 'An inbound router ACL denied the packet.',
    'acl_out_denied': 'An outbound router ACL denied the packet.',
    'host_firewall_denied': 'A modeled host firewall denied the packet.',
    'ipv6_firewall_denied': 'A modeled IPv6 firewall denied the packet.',
    'device_powered_off': 'An IPv6 forwarding device is powered off.',
    'link_local_not_routed': 'IPv6 link-local traffic cannot be routed.',
    'ipv6_forwarding_disabled': 'An intermediate device has IPv6 forwarding disabled.',
    'no_route': 'The modeled device has no matching IPv4 or IPv6 route.',
    'l2_unreachable': 'The destination is not reachable through the modeled Layer 2 network.',
    'invalid_route': 'A non-connected IPv4 route has no next hop.',
    'next_hop_missing': 'The configured IPv4 next-hop address has no modeled owner.',
    'next_hop_unreachable': 'The IPv4 next hop is not reachable from this device.',
    'ndp_unreachable': 'IPv6 neighbor discovery could not reach the next hop.',
    'ttl_expired': 'The modeled IPv4 hop limit expired.',
}


def result(source, destination, version, status, message, *, forward=None, reply=None,
           reason=None, job_id=None):
    return {'version': 1, 'operation': 'ping', 'source': source,
            'destination_ip': destination, 'ip_version': version, 'status': status,
            'reachable': None if status == 'queued' else status == 'success',
            'reason': reason, 'paths': {'forward': forward or [], 'reply': reply or []},
            'job_id': job_id, 'message': message}


def schema():
    return {
        'version': 1,
        'operation': 'ping',
        'endpoint': 'POST /api/v1/connectivity/ping',
        'request': {'type': 'object', 'required': ['source', 'destination_ip'],
                    'properties': {'source': {'type': 'string', 'minLength': 1},
                                   'destination_ip': {'type': 'string', 'description': 'IPv4 or IPv6 address'}},
                    'additionalProperties': False},
        'response': {'status_values': ['success', 'failed', 'queued'],
                     'reachable': 'true/false for completed probes; null for queued probes',
                     'reason': 'null on success/queue; otherwise code, stage and optional device/interface/next_hop',
                     'reason_stages': ['source', 'target', 'forward', 'reply'],
                     'paths': 'ordered routed device names, not packet-level switch-port traces',
                     'job_id': 'simulation PDU id when queued; otherwise null',
                     'message': 'human-readable legacy ping output'},
        'failure_codes': FAILURE_CODES,
        'http': {'200': 'probe completed, including unreachable results',
                 '202': 'probe queued in Simulation Mode',
                 '400': 'invalid request or simulator rejected the operation',
                 '413': 'request exceeds the server body size limit'},
        'error_codes': ['invalid_request', 'unknown_source', 'operation_rejected', 'request_too_large'],
    }


def ping(lab, source, destination):
    if not isinstance(source, str) or not source:
        raise LabError('source must be a nonempty device name')
    if not isinstance(destination, str) or not destination:
        raise LabError('destination_ip must be an IP address string')
    address = ip_address(destination)
    if getattr(address, 'scope_id', None) is not None:
        raise LabError('IPv6 scope identifiers are not supported')
    destination = str(address)
    lab._device(source)
    if lab.simulation['mode'] == 'simulation':
        from .simulation import enqueue_task
        ident = enqueue_task(lab, 'ping', {'source': source, 'destination_ip': destination})
        prefix = 'IPv6 PING' if address.version == 6 else 'PING'
        return result(source, destination, address.version, 'queued',
                      prefix + ' queued in Simulation Mode: ' + ident, job_id=ident)
    if address.version == 6:
        from .ipv6 import ping_detailed
        return ping_detailed(lab, source, destination)

    target = lab.owner_of_ip(destination)
    if not target:
        return result(source, destination, 4, 'failed',
                      f'Destination {destination} is not assigned to any interface',
                      reason={'code': 'destination_unassigned', 'stage': 'target'})
    origin = lab._source_ip_for_destination(source, destination)
    if not origin:
        return result(source, destination, 4, 'failed', f'PING failed\n{source} -> no-route',
                      forward=[source], reason={'code': 'no_source_route', 'stage': 'source', 'device': source})
    forward = {'hops': [], 'reason': None}
    meta = {'translated_source': origin, 'final_destination': destination, '_diagnostic': forward}
    ok, trace = lab._forward(source, destination, set(), [], origin, 'icmp', None, meta)
    if not ok:
        return result(source, destination, 4, 'failed', 'PING failed\nforward: ' + ' -> '.join(trace),
                      forward=forward['hops'], reason={**forward['reason'], 'stage': 'forward'})
    final_owner = meta.get('final_owner', target[0])
    if final_owner == source:
        return result(source, destination, 4, 'success', 'PING success\nforward: ' + ' -> '.join(trace),
                      forward=forward['hops'])
    reply_source = meta.get('final_destination', destination)
    reply_destination = meta.get('translated_source', origin)
    reply = {'hops': [], 'reason': None}
    reply_meta = {'translated_source': reply_source, 'final_destination': reply_destination, '_diagnostic': reply}
    reply_ok, back = lab._forward(final_owner, reply_destination, set(), [], reply_source, 'icmp', None, reply_meta)
    if not reply_ok:
        return result(source, destination, 4, 'failed',
                      'PING failed (reply path)\nforward: ' + ' -> '.join(trace) + '\nreply:   ' + ' -> '.join(back),
                      forward=forward['hops'], reply=reply['hops'], reason={**reply['reason'], 'stage': 'reply'})
    return result(source, destination, 4, 'success',
                  'PING success\nforward: ' + ' -> '.join(trace) + '\nreply:   ' + ' -> '.join(back),
                  forward=forward['hops'], reply=reply['hops'])

"""Area-aware, deterministic IPv4 OSPF model (not an IOS packet emulator).

Network statements select interface addresses. Adjacencies require matching
areas and L2 reachability. Route propagation is hop-based; area transitions
require a router with an active area-0 interface. Hellos, LSAs and interface
costs are intentionally not modeled.
"""
from heapq import heappop, heappush
from ipaddress import IPv4Address, IPv4Network
from itertools import count

from .model import LabError, Route


def area_id(value):
    if isinstance(value, bool) or not isinstance(value, (str, int)):
        raise LabError('OSPF area must be a number or dotted IPv4 address')
    try:
        if isinstance(value, str) and '.' in value:
            return int(IPv4Address(value))
        if isinstance(value, str) and (not value.isascii() or not value.isdigit()):
            raise ValueError('invalid area')
        result = int(value)
    except (ValueError, TypeError) as exc:
        raise LabError('OSPF area must be a number or dotted IPv4 address') from exc
    if not 0 <= result <= 0xffffffff:
        raise LabError('OSPF area must be between 0 and 4294967295')
    return result


def _process_id(value):
    if isinstance(value, bool) or not isinstance(value, (str, int)):
        raise LabError('OSPF process ID must be between 1 and 65535')
    try:
        if isinstance(value, str) and (not value.isascii() or not value.isdigit()):
            raise ValueError('invalid process ID')
        result = int(value)
    except (ValueError, TypeError) as exc:
        raise LabError('OSPF process ID must be between 1 and 65535') from exc
    if not 1 <= result <= 65535:
        raise LabError('OSPF process ID must be between 1 and 65535')
    return result


def _router(lab, name):
    device = lab._device(name)
    if device.kind != 'router':
        raise LabError('OSPF is supported on routers')
    return device


def configure(lab, name, network=None, area=0, *, automatic=None, process_id=None):
    device = _router(lab, name)
    if automatic is not None and not isinstance(automatic, bool):
        raise LabError('OSPF automatic must be a boolean')
    prefix = str(IPv4Network(network, strict=False)) if network is not None else None
    area = area_id(area)
    pid = _process_id(process_id) if process_id is not None else device.ospf_process_id
    has_config = (device.ospf_enabled or device.ospf_networks or device.ospf_auto
                  or device.ospf_process_id != 1)
    if has_config and pid != device.ospf_process_id:
        raise LabError('only one OSPF process per router is supported')
    was_enabled = device.ospf_enabled
    device.ospf_enabled = True
    device.ospf_process_id = pid
    if prefix is not None:
        if prefix not in device.ospf_networks:
            device.ospf_networks.append(prefix)
        device.ospf_areas[prefix] = area
        # An explicit selection replaces the old all-interfaces shortcut.
        device.ospf_auto = False
    elif automatic is not None:
        # Entering the existing IOS process must not change its configuration.
        if automatic or not was_enabled:
            device.ospf_auto = automatic
    elif not was_enabled and not device.ospf_networks:
        # Compatibility with existing `ospf R1 enable` and older saved labs.
        device.ospf_auto = True
    lab.recompute_ospf()


def disable(lab, name, *, clear=False):
    device = _router(lab, name)
    device.ospf_enabled = False
    if clear:
        device.ospf_networks.clear()
        device.ospf_areas.clear()
        device.ospf_auto = False
        device.ospf_process_id = 1
    lab.recompute_ospf()


def remove_network(lab, name, network, area=None):
    device = _router(lab, name)
    prefix = str(IPv4Network(network, strict=False))
    if prefix not in device.ospf_networks:
        raise LabError('OSPF network is not configured')
    if area is not None and device.ospf_areas.get(prefix, 0) != area_id(area):
        raise LabError('OSPF network is not configured in that area')
    device.ospf_networks.remove(prefix)
    device.ospf_areas.pop(prefix, None)
    lab.recompute_ospf()


def load_config(device, raw):
    networks = raw.get('ospf_networks', [])
    if not isinstance(networks, list) or any(not isinstance(n, str) for n in networks):
        raise LabError('invalid saved OSPF networks')
    canonical = [str(IPv4Network(n, strict=False)) for n in networks]
    if len(set(canonical)) != len(canonical):
        raise LabError('duplicate saved OSPF network')
    areas = raw.get('ospf_areas', {})
    if not isinstance(areas, dict):
        raise LabError('invalid saved OSPF areas')
    if any(k not in networks for k in areas):
        raise LabError('saved OSPF area has no matching network')
    device.ospf_networks = canonical
    device.ospf_areas = {canonical[i]: area_id(areas.get(network, 0))
                         for i, network in enumerate(networks)}
    automatic = raw.get('ospf_auto', bool(device.ospf_enabled and not networks))
    if not isinstance(automatic, bool):
        raise LabError('invalid saved OSPF automatic mode')
    device.ospf_auto = automatic
    device.ospf_process_id = _process_id(raw.get('ospf_process_id', 1))


def interface_area(device, interface):
    """Return selected area even when the interface is down, or None."""
    if not device.ospf_enabled or not interface.ip:
        return None
    address = interface.ipv4.ip
    matches = [(IPv4Network(prefix, strict=False).prefixlen, -index,
                device.ospf_areas.get(prefix, 0))
               for index, prefix in enumerate(device.ospf_networks)
               if address in IPv4Network(prefix, strict=False)]
    if matches:
        return max(matches)[2]
    return 0 if device.ospf_auto else None


def topology(lab):
    routers = sorted((d for d in lab.devices.values() if d.kind == 'router' and d.ospf_enabled),
                     key=lambda d: d.name)
    active = {}
    graph = {}
    for device in routers:
        selected = []
        for interface in device.interfaces.values():
            area = interface_area(device, interface)
            if area is not None and lab._iface_effective_up(device.name, interface.name):
                selected.append((interface, area))
                graph.setdefault((device.name, area), [])
        active[device.name] = selected
    for index, left in enumerate(routers):
        for right in routers[index + 1:]:
            for a, area in active[left.name]:
                for b, other_area in active[right.name]:
                    if (area == other_area and a.ipv4.network == b.ipv4.network
                            and lab.l2_reachable((left.name, a.name), (right.name, b.name))):
                        graph[(left.name, area)].append((right.name, a.name, b.name, str(b.ipv4.ip)))
                        graph[(right.name, area)].append((left.name, b.name, a.name, str(a.ipv4.ip)))
    return routers, active, graph


def status(lab, name):
    device = _router(lab, name)
    _, active, graph = topology(lab)
    enabled_interfaces = {interface.name for interface, _ in active.get(name, [])}
    interfaces = []
    for interface in device.interfaces.values():
        area = interface_area(device, interface)
        if area is not None:
            interfaces.append({'interface': interface.name, 'ip': interface.ip,
                               'area': area, 'up': interface.name in enabled_interfaces})
    neighbors = []
    for (router, area), peers in graph.items():
        if router == name:
            for other, local_if, remote_if, ip in peers:
                neighbors.append({'device': other, 'local_interface': local_if,
                                  'remote_interface': remote_if, 'ip': ip, 'area': area})
    return {'device': name, 'enabled': device.ospf_enabled,
            'process_id': device.ospf_process_id, 'automatic': device.ospf_auto,
            'networks': [{'network': n, 'area': device.ospf_areas.get(n, 0)}
                         for n in device.ospf_networks],
            'interfaces': interfaces, 'neighbors': neighbors,
            'model': 'simplified hop-based area-aware OSPF'}


def recompute(lab):
    for device in lab.devices.values():
        device.routes = [r for r in device.routes if r.source != 'ospf']
    routers, active, graph = topology(lab)
    for source in routers:
        own = {route.network for route in lab.connected_routes(source.name)}
        areas_by_router = {d.name: {a for _, a in active[d.name]} for d in routers}
        queue = []
        order = count()
        distances = {}
        for area in sorted(areas_by_router[source.name]):
            # A route may enter area 0 from its source area and then leave for
            # a destination area. It must not use a non-backbone area as a
            # transit path between two disconnected parts of area 0.
            phase = 1 if area == 0 else 0
            distances[(source.name, area, phase)] = (0, 0)
            heappush(queue, (0, 0, next(order), source.name, area, phase, None))
        learned = {}
        while queue:
            inter, hops, _, current, area, phase, first_hop = heappop(queue)
            if distances.get((current, area, phase)) != (inter, hops):
                continue
            for interface, assigned in active[current]:
                network = str(interface.ipv4.network)
                if assigned == area and network not in own and first_hop is not None:
                    candidate = (inter, hops, first_hop)
                    if network not in learned or candidate < learned[network]:
                        learned[network] = candidate
            for neighbor, _, _, ip in graph.get((current, area), []):
                state = (neighbor, area, phase)
                distance = (inter, hops + 1)
                if state not in distances or distance < distances[state]:
                    distances[state] = distance
                    heappush(queue, (*distance, next(order), neighbor, area, phase, first_hop or ip))
            # Model ABR summaries only via an active backbone interface.
            areas = areas_by_router[current]
            if 0 in areas and len(areas) > 1:
                for target_area in sorted(areas):
                    if area != 0 and phase == 0 and target_area == 0:
                        target_phase = 1
                    elif area == 0 and phase == 1 and target_area != 0:
                        target_phase = 2
                    else:
                        continue
                    state = (current, target_area, target_phase)
                    distance = (1, hops)
                    if state not in distances or distance < distances[state]:
                        distances[state] = distance
                        heappush(queue, (*distance, next(order), current, target_area, target_phase, first_hop))
        for network, (_, hops, hop) in sorted(learned.items()):
            source.routes.append(Route(network, next_hop=hop, source='ospf', metric=110 + hops))

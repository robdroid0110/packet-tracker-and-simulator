"""Import Packet Tracker and Simulator JSON and a limited subset of legacy network simulator labs."""
import base64
import ipaddress
import json
import re
import tempfile
from pathlib import Path
import xml.etree.ElementTree as ET

from .model import Interface, LabError, NetworkLab
from .device_catalog import MODELS

MAX_FILE = 8_000_000


def decode_file(encoded, filename):
    if not isinstance(encoded, str) or len(encoded) > (MAX_FILE * 4 // 3 + 8):
        raise ValueError('File exceeds the 8 MB import limit')
    try:
        raw = base64.b64decode(encoded, validate=True)
    except Exception as exc:
        raise ValueError('Invalid file data') from exc
    if len(raw) > MAX_FILE:
        raise ValueError('File exceeds the 8 MB import limit')
    if not isinstance(filename, str):
        raise ValueError('A filename is required')
    if filename.lower().endswith('.pkt'):
        return import_pkt(raw)
    if not filename.lower().endswith('.json'):
        raise ValueError('Choose a Packet Tracker and Simulator .json or legacy network simulator .pkt file')
    try:
        data = json.loads(raw)
        if not isinstance(data, dict) or data.get('version') != 1 or not isinstance(data.get('devices'), dict) or not isinstance(data.get('links'), list):
            raise ValueError('Not a Packet Tracker and Simulator lab JSON file')
        with tempfile.TemporaryDirectory(prefix='packet-tracker-import-') as folder:
            path = Path(folder) / 'lab.json'
            path.write_bytes(raw)
            candidate = NetworkLab()
            candidate.load(str(path))
        return candidate, []
    except Exception as exc:
        raise ValueError('Invalid Packet Tracker and Simulator lab: ' + str(exc)) from exc


def port_name(name, kind):
    if kind in ('pc', 'server'):
        return 'eth0'
    name = (name or '').strip().lower().replace('tengigabitethernet', 'te').replace('fastethernet', 'fa').replace('gigabitethernet', 'g').replace('ethernet', 'eth').replace('serial', 's').replace(' ', '')
    if not re.fullmatch(r'[a-z][a-z0-9/.-]{0,40}', name):
        raise ValueError('Unsupported interface name')
    return name



def running_lines(engine):
    config = engine.find('RUNNINGCONFIG')
    if config is None:
        config = engine.find('RUNNING_CONFIG')
    return [(line.text or '').strip() for line in config.findall('LINE')] if config is not None else []


def import_running_config(lab, device, lines, warnings):
    """Apply a conservative supported IOS subset and retain the original text."""
    if not lines:
        return
    original = '\n'.join(lines)
    if len(original) <= 200_000:
        device.config['packet_tracer_running_config'] = original
    else:
        warnings.append(device.name + ': original running configuration exceeds the 200 KB preservation limit')
    if device.kind not in ('router', 'switch'):
        warnings.append(device.name + ': the original running configuration was preserved but not applied')
        return
    current = None
    ospf = False
    skipped = 0
    for text in lines:
        lower = text.lower()
        parts = text.split()
        if not text:
            continue
        if text.startswith('!') or lower in ('end', 'exit'):
            current = None; ospf = False
            continue
        if lower.startswith('interface '):
            ospf = False
            try:
                current = port_name(text.split(None,1)[1], device.kind)
                if current not in device.interfaces: current = None
            except ValueError:
                current = None
            continue
        try:
            if current is not None:
                port = device.interfaces[current]
                if lower == 'shutdown': port.admin_up = False
                elif lower == 'no shutdown': port.admin_up = True
                elif lower.startswith('ip address ') and len(parts) == 4:
                    port.ip = str(ipaddress.IPv4Interface(parts[2] + '/' + parts[3]))
                elif lower == 'no ip address': port.ip = None
                elif lower.startswith('description '): port.description = text.split(None,1)[1]
                elif lower.startswith('ip helper-address ') and len(parts) == 3:
                    lab.set_helper_address(device.name,current,parts[2])
                elif lower.startswith('speed ') and parts[-1] in ('auto','10','100','1000','10000'): port.speed = parts[-1]
                elif lower.startswith('duplex ') and parts[-1] in ('auto','half','full'): port.duplex = parts[-1]
                elif lower.startswith('clock rate ') and len(parts) == 3: port.clock_rate = int(parts[2])
                elif lower.startswith('switchport access vlan ') and len(parts) == 4: lab.set_switchport_access(device.name,current,int(parts[3]))
                elif lower == 'switchport mode access': lab.set_switchport_access(device.name,current,port.access_vlan)
                elif lower == 'switchport mode trunk': lab.set_switchport_trunk(device.name,current,port.allowed_vlans)
                elif lower.startswith('switchport trunk native vlan ') and len(parts) == 5: lab.set_native_vlan(device.name,current,int(parts[4]))
                elif lower == 'spanning-tree portfast': lab.set_portfast(device.name,current,True)
                elif lower == 'no spanning-tree portfast': lab.set_portfast(device.name,current,False)
                elif lower.startswith(('ip address ', 'switchport ', 'ip nat ', 'ip access-group ', 'channel-group ', 'encapsulation ')): skipped += 1
            elif lower.startswith('hostname ') and len(parts) == 2:
                device.config['hostname'] = parts[1]
            elif lower.startswith('spanning-tree mode ') and device.kind == 'switch':
                lab.set_stp_mode(device.name,parts[-1])
            elif lower.startswith('vlan ') and len(parts) == 2 and parts[1].isdigit():
                lab.add_vlan(device.name,int(parts[1]))
            elif lower.startswith('ip route ') and len(parts) == 5:
                network = str(ipaddress.IPv4Network(parts[2]+'/'+parts[3],strict=False))
                try:
                    ipaddress.IPv4Address(parts[4]); lab.add_static_route(device.name,network,next_hop=parts[4])
                except ipaddress.AddressValueError:
                    lab.add_static_route(device.name,network,interface=port_name(parts[4],device.kind))
            elif lower.startswith('router ospf ') and device.kind == 'router':
                if len(parts) != 3: raise LabError('invalid OSPF process')
                lab.enable_ospf(device.name, automatic=False, process_id=parts[2]); ospf=True
            elif ospf and lower.startswith('network ') and len(parts) >= 5 and parts[3].lower() == 'area':
                wildcard=int(ipaddress.IPv4Address(parts[2])); mask=str(ipaddress.IPv4Address(0xffffffff ^ wildcard))
                lab.enable_ospf(device.name,str(ipaddress.IPv4Network(parts[1]+'/'+mask,strict=False)),parts[4])
            elif lower.startswith(('router ', 'ip route ', 'access-list ', 'ip access-list ', 'ip nat ', 'ip dhcp ', 'ip routing')):
                skipped += 1
        except (ValueError, LabError, KeyError) as exc:
            skipped += 1
    if skipped:
        warnings.append(device.name + ': ' + str(skipped) + ' configuration command(s) could not be applied; original running configuration is preserved in device attributes')


def import_pkt(raw):
    from .pkt_codec.pt_crypto import decrypt_pkt
    try:
        xml = decrypt_pkt(raw)
        if b'<!DOCTYPE' in xml.upper() or b'<!ENTITY' in xml.upper():
            raise ValueError('XML declarations are not supported')
        root = ET.fromstring(xml)
    except Exception as exc:
        raise ValueError('Could not decode this .pkt file: ' + str(exc)) from exc
    if root.tag != 'PACKETTRACER5':
        raise ValueError('This is not a supported legacy network simulator network file')
    if root.find('./NETWORK/DEVICES') is None:
        raise ValueError('legacy network simulator network is missing its device list')
    elements = root.findall('./NETWORK/DEVICES/DEVICE')
    if len(elements) > 512:
        raise ValueError('Import supports at most 512 devices')
    lab = NetworkLab()
    warnings = ['This is a partial import: device configurations, protocols, services, physical layouts and activities may not be preserved. Verify the imported lab before use.']
    names = []
    references = {}
    for idx, element in enumerate(elements):
        engine = element.find('ENGINE')
        if engine is None:
            raise ValueError('Device is missing its engine data')
        original_name = engine.findtext('NAME') or 'Device' + str(idx)
        name = re.sub(r'[^A-Za-z0-9_-]', '_', original_name)
        if not name or not name[0].isalpha() or not name[0].isascii(): name = 'Device_' + name
        name = name[:31]
        base = name
        suffix = 2
        while name in lab.devices:
            ending = '_' + str(suffix)
            name = base[:31-len(ending)] + ending
            suffix += 1
        if name != original_name: warnings.append(original_name + ': imported as ' + name)
        typ = engine.find('TYPE')
        model = typ.get('model', '') if typ is not None else ''
        category = (typ.text or '').lower() if typ is not None else ''
        model_id = next((key for key, value in MODELS.items() if value['label'].lower() == model.lower()), '')
        kind = MODELS.get(model_id, {}).get('kind', {'pc':'pc', 'server':'server', 'router':'router', 'switch':'switch'}.get(category, 'generic'))
        try:
            x = float(element.findtext('./WORKSPACE/LOGICAL/X', '200'))
            y = float(element.findtext('./WORKSPACE/LOGICAL/Y', '160'))
            if not (0 <= x <= 100000 and 0 <= y <= 100000): raise ValueError()
        except ValueError:
            x, y = 200, 160
            warnings.append(name + ': invalid position replaced')
        device = lab.add_device(kind, name, x, y, model_id)
        # The vendor running configuration lists the real physical interfaces;
        # avoid offering the simulator's generic extra ports for those devices.
        declarations = [line.split(None,1)[1] for line in running_lines(engine)
                        if line.lower().startswith('interface ') and not line.split(None,1)[1].lower().startswith(('vlan','loopback','port-channel','tunnel','dialer','null')) and '.' not in line.split(None,1)[1]]
        if declarations and device.kind in ('router','switch'):
            device.interfaces = {n:p for n,p in device.interfaces.items() if p.media not in ('copper','fiber-mm','fiber-sm','serial')}
            for declaration in declarations[:128]:
                try:
                    pname = port_name(declaration,device.kind)
                    media = 'serial' if declaration.lower().startswith('serial') else 'copper'
                    device.interfaces.setdefault(pname,Interface(pname,media=media))
                except ValueError: warnings.append(name + ': unsupported interface ' + declaration)
        if not model_id: warnings.append(name + ': unsupported model ' + model + ' represented as ' + kind)
        device.powered = engine.findtext('POWER', 'true').lower() != 'false'
        if kind in ('pc', 'server'):
            port = next((p for p in engine.findall('.//PORT') if p.findtext('IP') not in (None,'','0.0.0.0') and p.findtext('SUBNET')), None)
            if port is not None:
                try: device.interfaces['eth0'].ip = str(ipaddress.IPv4Interface(port.findtext('IP') + '/' + port.findtext('SUBNET')))
                except ValueError: warnings.append(name + ': invalid IP address skipped')
            gateway = engine.findtext('GATEWAY')
            if gateway and gateway != '0.0.0.0': device.default_gateway = gateway
            dns = engine.findtext('./DNS_CLIENT/SERVER_IP')
            if dns and dns != '0.0.0.0': device.dns_server = dns
        names.append(name)
        ref = engine.findtext('SAVE_REF_ID')
        if ref:
            if ref in references: raise ValueError('Duplicate legacy network simulator device reference')
            references[ref] = name
    for link in root.findall('./NETWORK/LINKS/LINK'):
        cable = link.find('CABLE')
        try:
            if cable is None: raise ValueError('unsupported link type')
            def endpoint(value):
                if value in references: return references[value]
                index = int(value)
                if index < 0: raise ValueError('invalid endpoint')
                return names[index]
            a, b = endpoint(cable.findtext('FROM')), endpoint(cable.findtext('TO'))
            ports = cable.findall('PORT')
            if len(ports) != 2: raise ValueError('missing ports')
            da, db = lab.devices[a], lab.devices[b]
            cable_kind = link.findtext('TYPE')
            copper_types = {'eStraightThrough':'copper-straight', 'eCrossOver':'copper-cross'}
            if cable_kind == 'eCopper':
                cable_type = copper_types.get(cable.findtext('TYPE'))
                media_a = media_b = 'copper'
            elif cable_kind == 'eSerial':
                dce = cable.findtext('DCEDEV')
                if not dce: raise ValueError('serial DCE endpoint is missing')
                dce_device = endpoint(dce)
                if dce_device not in (a,b): raise ValueError('invalid serial DCE endpoint')
                cable_type = 'serial-dce' if dce_device == a else 'serial-dte'
                media_a = media_b = 'serial'
            else:
                mapped = {'eCoaxial':('coax','coax'), 'ePhoneLine':('phone','modem'),
                          'eFiber':('fiber-mm','fiber-mm'), 'eFiberSingleMode':('fiber-sm','fiber-sm'),
                          'eUSB':('usb','usb')}.get(cable_kind)
                if not mapped: raise ValueError('unsupported cable type ' + str(cable_kind))
                cable_type, media_a = mapped; media_b = media_a
            if not cable_type: raise ValueError('unsupported copper cable type')
            def physical_port(device, text, media):
                if device.model == '7960' and (text or '').lower() == 'switch': return 'eth0'
                if device.kind in ('pc','server') and media != 'copper':
                    value = re.sub(r'[^a-z0-9/_.-]', '', (text or '').lower())
                    return value or media+'0'
                return port_name(text, device.kind)
            pa, pb = physical_port(da,ports[0].text,media_a), physical_port(db,ports[1].text,media_b)
            for device, port, media in ((da, pa, media_a), (db, pb, media_b)):
                if port not in device.interfaces: device.interfaces[port] = Interface(port,media=media)
            lab.connect(a, pa, b, pb, cable_type)
        except (ValueError, IndexError, TypeError, KeyError, LabError) as exc:
            warnings.append('A link could not be imported: ' + str(exc))
    for element, name in zip(elements, names):
        engine=element.find('ENGINE');device=lab.devices[name]
        if engine.findtext('TYPE') == 'WirelessLanController':
            management=next((p for p in engine.findall('./WLC_INTERFACES/PORT') if (p.findtext('NAME') or '').lower()=='management'),None)
            if management is not None and management.findtext('IP') not in (None,'','0.0.0.0'):
                try:
                    number=int(management.findtext('PHYSICAL_PORT_NUMBER'))
                    if not 0 <= number <= 128:raise ValueError('invalid physical port')
                    pname='g'+str(number)
                    if pname not in device.interfaces:device.interfaces[pname]=Interface(pname)
                    device.interfaces[pname].ip=str(ipaddress.IPv4Interface(management.findtext('IP')+'/'+management.findtext('SUBNET')))
                    gateway=management.findtext('PORT_GATEWAY')
                    if gateway and gateway!='0.0.0.0':device.default_gateway=str(ipaddress.IPv4Address(gateway))
                except (ValueError,TypeError) as exc:
                    warnings.append(name+': controller management address could not be imported: '+str(exc))
        import_running_config(lab,device,running_lines(engine),warnings)
    lab.recompute_ospf()
    return lab, warnings

"""Experimental, self-contained network-only .pkt interoperability writer.

The exported XML uses the documented schema for ordinary topologies and the
existing MIT-licensed container codec. It does not include Cisco graphics,
firmware, stock templates, instructor solutions, or activity grading metadata.
Unsupported simulator behavior is reported instead of falsely claiming parity.
"""
from __future__ import annotations

from ipaddress import IPv4Interface, IPv6Interface
import xml.etree.ElementTree as ET

from .device_catalog import MODELS
from .pkt_codec.pt_crypto import encrypt_pkt


def _text(parent, tag, value):
    element = ET.SubElement(parent, tag)
    element.text = str(value)
    return element


def _pt_name(port, device):
    if device.kind in {"pc", "server"}:
        return "FastEthernet0" if port == "eth0" else port
    for prefix, label in (("fa", "FastEthernet"), ("g", "GigabitEthernet"),
                          ("te", "TenGigabitEthernet"), ("s", "Serial"),
                          ("eth", "Ethernet")):
        if port.startswith(prefix) and len(port) > len(prefix) and port[len(prefix)].isdigit():
            return label + port[len(prefix):]
    return port


def _device_model(device):
    if device.model in MODELS:
        return MODELS[device.model]["label"]
    return {"router": "Router-PT", "switch": "Switch-PT", "server": "Server-PT",
            "pc": "PC-PT"}.get(device.kind, "Generic")


def _type_name(device):
    if device.kind == "router": return "Router"
    if device.kind == "switch": return "Switch"
    if device.kind == "pc": return "Pc"
    if device.kind == "server": return "Server"
    return "Generic"


def _running_config(device):
    lines = ["hostname " + device.name]
    if device.kind in {"router", "switch"}:
        for iface in device.interfaces.values():
            lines.append("interface " + _pt_name(iface.name, device))
            if iface.description: lines.append("description " + iface.description[:240])
            if iface.ip:
                address = IPv4Interface(iface.ip)
                lines.append("ip address " + str(address.ip) + " " + str(address.netmask))
            if iface.ipv6:
                lines.append("ipv6 address " + iface.ipv6)
            if device.kind == "switch":
                lines.append("switchport mode " + iface.mode)
                if iface.mode == "access":
                    lines.append("switchport access vlan " + str(iface.access_vlan))
                elif iface.mode == "trunk":
                    lines.append("switchport trunk native vlan " + str(iface.native_vlan))
            lines.append("no shutdown" if iface.admin_up else "shutdown")
            lines.append("!")
        if device.kind == "switch":
            for vlan in sorted(device.vlans):
                if vlan != 1: lines.extend(("vlan " + str(vlan), "!"))
        if device.ospf_enabled and device.kind == "router":
            lines.append("router ospf " + str(device.ospf_process_id))
            for network, area in device.ospf_areas.items():
                # OSPF area-network representation may not be compatible.
                from ipaddress import IPv4Network
                net = IPv4Network(network, strict=False)
                wildcard = net.hostmask
                lines.append(f"network {net.network_address} {wildcard} area {area}")
            lines.append("!")
        for route in device.routes:
            if route.source != "static": continue
            from ipaddress import IPv4Network
            net = IPv4Network(route.network,strict=False)
            via = route.next_hop or _pt_name(route.interface, device) if route.interface else route.next_hop
            if via: lines.append(f"ip route {net.network_address} {net.netmask} {via}")
    return lines


def export_pkt(lab):
    """Return (encoded bytes, warnings); export intentionally excludes activity rubrics."""
    if len(lab.devices) > 512:
        raise ValueError("PKT export currently supports at most 512 devices")
    if len(lab.links) > 4096:
        raise ValueError("PKT export currently supports at most 4096 links")
    warnings = [
        "Network-only legacy PKT export is EXPERIMENTAL and NOT validated with official Cisco Packet Tracer; it may refuse the file. Device internals, unsupported IOS commands, "
        "wireless/services, physical layouts and simulation settings may not round-trip. Keep the native JSON lab."
    ]
    if lab.activity:
        warnings.append("The activity instructions, progress and proprietary assessment rubric are NOT included in .pkt. Save native JSON to preserve activity progress.")
    root = ET.Element("PACKETTRACER5")
    _text(root, "VERSION", "9.0.0.0810")
    ET.SubElement(root, "PIXMAPBANK")
    ET.SubElement(root, "MOVIEBANK")
    network = ET.SubElement(root, "NETWORK")
    devices = ET.SubElement(network, "DEVICES")
    refs = {}
    for i,device in enumerate(lab.devices.values(),1):
        refs[device.name] = "save-ref-id:" + str(6000000000000+i)
        entry = ET.SubElement(devices, "DEVICE")
        engine = ET.SubElement(entry, "ENGINE")
        type_node = _text(engine,"TYPE",_type_name(device))
        type_node.set("model",_device_model(device))
        _text(engine,"NAME",device.name)
        _text(engine,"POWER","true" if device.powered else "false")
        _text(engine,"DESCRIPTION","")
        _text(engine,"SAVE_REF_ID",refs[device.name])
        # The minimal host interface configuration is represented in PORT,
        # while IOS-like config stays accessible as RUNNINGCONFIG/LINE.
        module = ET.SubElement(engine,"MODULE")
        for port in device.interfaces.values():
            item = ET.SubElement(module,"PORT")
            _text(item,"NAME",_pt_name(port.name,device))
            if port.ip:
                address = IPv4Interface(port.ip)
                _text(item,"IP",address.ip)
                _text(item,"SUBNET",address.netmask)
            _text(item,"POWER","true" if port.admin_up else "false")
        if device.default_gateway:
            _text(engine,"GATEWAY",device.default_gateway)
        if device.dns_server:
            dns=ET.SubElement(engine,"DNS_CLIENT");_text(dns,"SERVER_IP",device.dns_server)
        cfg = ET.SubElement(engine,"RUNNINGCONFIG")
        for line in _running_config(device):
            _text(cfg,"LINE",line)
        startup=ET.SubElement(engine,"STARTUPCONFIG")
        for line in _running_config(device):
            _text(startup,"LINE",line)
        workspace=ET.SubElement(entry,"WORKSPACE")
        logical=ET.SubElement(workspace,"LOGICAL")
        _text(logical,"X",int(device.x))
        _text(logical,"Y",int(device.y))
        _text(logical,"DEVCLUSTERID","1-1")
        ET.SubElement(workspace,"PHYSICAL")
        ET.SubElement(workspace,"PHYSICAL_CPUR")
        if device.kind=="generic" or device.config.get("multilayer_switch"):
            warnings.append(device.name + ": nonstandard or specialized device has incomplete PKT model support.")
    links = ET.SubElement(network,"LINKS")
    for link in lab.links:
        node=ET.SubElement(links,"LINK")
        c=ET.SubElement(node,"CABLE")
        types = {
            "copper-straight": ("eCopper","eStraightThrough"),
            "copper-cross": ("eCopper","eCrossOver"),
            "auto": ("eCopper","eStraightThrough"),
            "fiber-mm": ("eFiber",None),
            "fiber-sm": ("eFiberSingleMode",None),
            "serial-dce": ("eSerial",None),
            "serial-dte": ("eSerial",None),
            "phone": ("ePhoneLine",None),
            "coax": ("eCoaxial",None),
        }
        kind, subtype = types.get(link.cable, ("eCopper","eStraightThrough"))
        if link.cable not in types:
            warnings.append("Unsupported cable converted to copper: " + link.cable)
        item=ET.Element("TYPE");item.text=kind;node.insert(0,item)
        _text(c,"LENGTH",1)
        _text(c,"FUNCTIONAL","true")
        _text(c,"FROM",refs[link.a_device])
        _text(c,"PORT",_pt_name(link.a_if,lab.devices[link.a_device]))
        _text(c,"TO",refs[link.b_device])
        _text(c,"PORT",_pt_name(link.b_if,lab.devices[link.b_device]))
        if subtype: _text(c,"TYPE",subtype)
        if link.cable in ("serial-dce","serial-dte"):
            _text(c,"DCEDEV",refs[link.a_device if link.cable=="serial-dce" else link.b_device])
    ET.SubElement(network,"SHAPETESTS")
    ET.SubElement(network,"DESCRIPTION")
    ET.SubElement(root,"SCENARIOSET")
    ET.SubElement(root,"OPTIONS")
    ET.SubElement(root,"PHYSICALWORKSPACE")
    ET.SubElement(root,"FILTERS")
    ET.SubElement(root,"CLUSTERS")
    for tag in ("LINES","RECTANGLES","ELLIPSES","POLYGONS","USER_PROFILE",
                "MULTIUSER","GEOVIEW_GRAPHICSITEMS","SCRIPT_MODULE","CODE_TESTING"):
        ET.SubElement(root,tag)
    xml = ET.tostring(root,encoding="utf-8",xml_declaration=True)
    if len(xml) > 32_000_000:
        raise ValueError("Generated PKT XML exceeds 32 MB")
    return encrypt_pkt(xml), warnings

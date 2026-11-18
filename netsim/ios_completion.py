"""Read-only, context-aware Tab completion for the simulated IOS console.

Only commands implemented by IOSSession/ios_reference are suggested. The
completion code must not execute commands, change IOS modes or mutate a lab.
"""
from __future__ import annotations

import os
import re

from .model import LabError


# Only literal command grammar appears here. Runtime interface/VLAN/ACL names
# are resolved from the selected device, not guessed from a fixed Cisco model.
SHOW = (
    "show version", "show running-config", "show startup-config",
    "show interfaces", "show interfaces @interfaces",
    "show interface @interfaces",
    "show ip interface brief", "show ip route", "show ip protocols",
    "show ip arp", "show ip ospf neighbor", "show ip ospf neighbors",
    "show ip ospf interface", "show ip dhcp binding", "show ip dhcp pool",
    "show ip nat translations", "show ip nat statistics",
    "show ip access-lists", "show arp", "show vlan brief",
    "show mac address-table", "show spanning-tree",
    "show spanning-tree vlan @vlans", "show etherchannel summary",
    "show cdp neighbors", "show lldp neighbors",
    "show ipv6 route", "show ipv6 interface",
    "show ipv6 interface brief", "show ipv6 neighbors",
    "show clock", "show flash", "show file systems",
    "show license", "show iox", "show access-lists",
)
EXEC = (
    "ping", "traceroute", "ping ip", "ping ipv6", "help",
    "terminal length", "terminal width", "exit", "logout",
    "dir", "dir flash:",
)
PRIV = (
    "configure terminal", "disable", "reload",
    "write memory", "copy running-config startup-config",
    "copy running-config flash:", "erase startup-config",
    "clear arp", "clear ip arp", "clear mac address-table dynamic",
    "clear ip nat translation *",
)
CONFIG = (
    "interface @interfaces", "router ospf", "router rip",
    "router eigrp", "ip route", "ip access-list standard",
    "ip access-list extended", "ip dhcp pool", "ip default-gateway",
    "ip name-server", "ipv6 unicast-routing", "ipv6 route",
    "hostname", "vlan @vlans", "spanning-tree mode pvst",
    "spanning-tree mode rapid-pvst", "spanning-tree vlan @vlans",
    "access-list", "enable secret", "enable password",
    "username", "logging", "ntp server", "boot system",
    "cdp run", "lldp run",
    "no cdp run", "no lldp run", "no router rip",
    "no router eigrp", "no ip route", "no ip dhcp pool",
    "no access-list", "exit", "end",
)
INTERFACE = (
    "ip address", "ip address dhcp", "ipv6 address",
    "ipv6 address dhcp", "ipv6 address autoconfig",
    "ip helper-address", "ip nat inside", "ip nat outside",
    "ip access-group @acls in", "ip access-group @acls out",
    "no ip address", "no shutdown", "shutdown",
    "no ip nat inside", "no ip nat outside",
    "no ip helper-address", "no ip access-group",
    "switchport mode access", "switchport mode trunk",
    "switchport access vlan @vlans",
    "switchport trunk native vlan @vlans",
    "switchport trunk allowed vlan",
    "spanning-tree portfast", "no spanning-tree portfast",
    "encapsulation dot1q", "channel-group",
    "no channel-group", "description", "no description",
    "speed", "duplex", "clock rate", "mtu", "mdix auto",
    "no mdix auto", "mac-address", "tx-ring-limit", "exit", "end",
)
ROUTER_MODES = {
    "router-ospf": ("network", "no network", "exit", "end"),
    "router-rip": ("network", "no network", "version", "exit", "end"),
    "router-eigrp": ("network", "no network", "exit", "end"),
    "acl": ("permit", "deny", "no permit", "no deny", "exit", "end"),
    "dhcp": ("network", "default-router", "dns-server",
             "domain-name", "lease", "exit", "end"),
}


def _patterns(session):
    device = session.lab._device(session.device)
    if session.awaiting_enable:
        return ()
    if device.config.get("boot_state") == "rommon":
        return ("boot", "confreg", "dir", "dir flash:", "reset",
                "set", "unset", "tftpdnld", "help")
    if session.mode == "user":
        return SHOW + EXEC + ("enable",)
    if session.mode == "priv":
        return SHOW + EXEC + PRIV
    if session.mode == "config":
        # Completion of "do show ..." is deliberately delegated to the same
        # SHOW grammar, but config-only commands stay context-dependent.
        return CONFIG + tuple("do " + item for item in SHOW)
    if session.mode == "interface":
        is_switch = device.kind == "switch" or device.config.get("multilayer_switch", False)
        base = INTERFACE if is_switch else tuple(
            p for p in INTERFACE if not p.startswith(("switchport ", "spanning-tree portfast",
                                                      "no spanning-tree portfast")))
        return base + tuple("do " + item for item in SHOW)
    return ROUTER_MODES.get(session.mode, ("exit", "end")) + tuple(
        "do " + item for item in SHOW
    )


def _dynamic_values(token, device):
    if token == "@interfaces":
        names = set(device.interfaces)
        aliases = (("fa", "FastEthernet"), ("g", "GigabitEthernet"),
                   ("te", "TenGigabitEthernet"), ("s", "Serial"))
        for name in device.interfaces:
            for short, long in aliases:
                if name.startswith(short) and name[len(short):].startswith(tuple("0123456789")):
                    names.add(long + name[len(short):])
                    break
        return sorted(names, key=str.casefold)
    if token == "@vlans":
        return [str(n) for n in sorted(device.vlans)]
    if token == "@acls":
        return sorted(device.acls, key=str.casefold)
    return [token]


def complete(session, text: str, cursor: int | None = None) -> dict:
    """Complete the token under the cursor without executing a command.

    Returns a token replacement range and a finite set of matches, so the
    UI can preserve text after the caret and show ambiguous options.
    """
    if not isinstance(text, str) or len(text) > 2048 or "\n" in text or "\r" in text:
        raise ValueError("CLI text must be a single line of at most 2048 characters")
    if cursor is None:
        cursor = len(text)
    if type(cursor) is not int or not 0 <= cursor <= len(text):
        raise ValueError("Invalid completion cursor")
    device = session.lab._device(session.device)
    left = text[:cursor]
    word = re.search(r"\S+$", left)
    start = word.start() if word else cursor
    typed = left[start:cursor]
    context = left[:start].split()
    end = cursor
    while end < len(text) and not text[end].isspace():
        end += 1

    words = {}
    for phrase in _patterns(session):
        tokens = phrase.split()
        if len(context) >= len(tokens):
            continue
        if any(
            not any(v.casefold().startswith(actual.casefold())
                    for v in _dynamic_values(tokens[i], device))
            for i, actual in enumerate(context)
        ):
            continue
        for item in _dynamic_values(tokens[len(context)], device):
            if item.casefold().startswith(typed.casefold()):
                words[item.casefold()] = item

    matches = sorted(words.values(), key=lambda x: (x.casefold(), x))
    if not matches:
        return {"start": start, "end": end, "replacement": typed,
                "candidates": [], "changed": False, "mode": session.mode}
    if len(matches) == 1:
        replacement = matches[0]
    else:
        common = os.path.commonprefix([s.casefold() for s in matches])
        replacement = matches[0][:len(common)] if len(common) > len(typed) else typed
    return {
        "start": start, "end": end, "replacement": replacement,
        "candidates": matches[:64], "changed": replacement != text[start:end],
        "mode": session.mode,
    }

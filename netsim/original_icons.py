"""Original, software-generated vector icons. No vendor artwork is imported."""
from __future__ import annotations

import re

STROKE = "#75c8cf"
ACCENT = "#a8d9c6"
MUTED = "#b7c9da"


def icon_svg(identifier: str) -> bytes:
    """Draw a generic icon based on a semantic asset identifier."""
    tokens = re.sub(r"[^a-z0-9]+", " ", identifier.lower())
    def has(*words: str) -> bool:
        return any(word in tokens for word in words)

    base = '<rect x="7" y="7" width="50" height="50" rx="12" opacity=".16" fill="#24566c" stroke="none"/>'
    if has("router", "routing", "isr", "1941", "2901", "2911", "1841"):
        artwork = '<ellipse cx="32" cy="35" rx="23" ry="13"/><path d="M20 35h24m-12-10v20m-5-15 5-5 5 5m-10 10 5 5 5-5"/>'
    elif has("switch", "bridge", "hub", "2960", "3560", "3650", "port"):
        artwork = '<rect x="10" y="19" width="44" height="29" rx="5"/><path d="M16 26h32"/><rect x="16" y="33" width="7" height="7" rx="1"/><rect x="28" y="33" width="7" height="7" rx="1"/><rect x="40" y="33" width="7" height="7" rx="1"/>'
    elif has("server", "historian", "controller", "rack"):
        artwork = '<rect x="18" y="9" width="28" height="46" rx="4"/><path d="M23 20h18m-18 12h18m-18 12h18"/><circle cx="25" cy="16" r="1.5" fill="currentColor" stroke="none"/><circle cx="25" cy="28" r="1.5" fill="currentColor" stroke="none"/><circle cx="25" cy="40" r="1.5" fill="currentColor" stroke="none"/>'
    elif has("desktop", "pc", "workstation", "computer", "laptop", "terminal", "browser", "screen"):
        artwork = '<rect x="10" y="13" width="44" height="33" rx="4"/><path d="M32 46v8m-13 0h26"/><path d="M15 39h34"/>'
    elif has("cloud", "wan", "internet"):
        artwork = '<path d="M18 47h30a10 10 0 0 0 0-20 16 16 0 0 0-31-1 10 10 0 0 0 1 21Z"/>'
    elif has("wifi", "wireless", "accesspoint", "access point", "antenna", "celltower", "bluetooth"):
        artwork = '<path d="M8 25a36 36 0 0 1 48 0M16 34a25 25 0 0 1 32 0M24 43a12 12 0 0 1 16 0"/><circle cx="32" cy="53" r="3" fill="currentColor" stroke="none"/>'
    elif has("cable", "connection", "coax", "fiber", "serial", "console", "usb", "link"):
        artwork = '<path d="M8 18h12l9 13h8l9 14h10"/><path d="M8 12v12m48 15v12"/><circle cx="32" cy="31" r="5" fill="currentColor" stroke="none"/>'
    elif has("phone", "voip", "dial"):
        artwork = '<rect x="19" y="9" width="26" height="46" rx="6"/><path d="M25 17h14m-14 28h14"/><circle cx="32" cy="50" r="2" fill="currentColor" stroke="none"/>'
    elif has("firewall", "security", "asa", "shield", "lock"):
        artwork = '<path d="M32 7 50 15v14c0 12-7 20-18 28-11-8-18-16-18-28V15Z"/><path d="m24 31 6 6 12-14"/>'
    elif has("search", "inspect", "zoom"):
        artwork = '<circle cx="28" cy="27" r="15"/><path d="m39 39 14 14"/>'
    elif has("folder", "open", "file", "save"):
        artwork = '<path d="M8 19h19l6 7h23v27H8Z"/><path d="M8 26h48"/>'
    elif has("print", "copy", "paste", "document", "note", "new"):
        artwork = '<path d="M20 9h20l9 9v37H20Z"/><path d="M40 9v10h9M26 30h18m-18 9h18"/>'
    elif has("delete", "cancel", "close", "remove"):
        artwork = '<circle cx="32" cy="32" r="22"/><path d="m23 23 18 18m0-18L23 41"/>'
    elif has("play", "pause", "step", "forward", "simulation", "pdu", "packet"):
        artwork = '<circle cx="32" cy="32" r="23"/><path d="m26 19 17 13-17 13Z"/>'
    elif has("sensor", "motor", "ioe", "component", "chip", "mcu", "sbc", "led"):
        artwork = '<rect x="18" y="18" width="28" height="28" rx="4"/><path d="M25 9v9m14-9v9m-14 28v9m14-9v9M9 25h9m-9 14h9m28-14h9m-9 14h9"/><circle cx="32" cy="32" r="7"/>'
    else:
        artwork = '<circle cx="32" cy="12" r="6"/><circle cx="14" cy="47" r="6"/><circle cx="50" cy="47" r="6"/><path d="M30 18 17 41m17-23 13 23M20 47h24"/>'
    vector = (f'<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 64 64" '
              f'fill="none" stroke="{STROKE}" stroke-width="3.4" stroke-linecap="round" '
              f'stroke-linejoin="round" color="{ACCENT}" aria-hidden="true">'
              f'{base}{artwork}</svg>')
    return vector.encode("utf-8")

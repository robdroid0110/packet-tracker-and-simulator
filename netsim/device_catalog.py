from __future__ import annotations

import re

SOURCE = "Independent built-in network device model catalogue"

_GROUPS = [
    ("network", "Routers", "router", "router", [
        "PT8200", "ISR4331", "ISR4321", "IR8340", "1941", "2901", "2911", "819", "829", "CGR1240",
        "IR1101", "Router-PT", "1841", "2620XM", "2621XM", "2811",
    ]),
    ("network", "Switches", "switch", "switch", [
        "2960-24TT", "Switch-PT", "3560-24PS", "3650-24PS", "IE2000", "Bridge-PT",
        "2950-24", "2950T-24", "IE-3400", "IE-9320",
    ]),
    ("network", "Hubs", "generic", "hub", ["Hub-PT", "Repeater-PT", "CoAxialSplitter-PT"]),
    ("network", "Wireless Devices", "generic", "access-point", [
        "Meraki-MX65W", "LAP-PT", "3702i", "WLC-PT", "WLC-3504", "WLC-2504", "Home Router",
        "AccessPoint-PT", "AccessPoint-PT-A", "AccessPoint-PT-AC", "AccessPoint-PT-N", "WRT300N",
        "Home Gateway", "Cell Tower", "Central Office Server",
    ]),
    ("network", "Security", "generic", "security", ["ASA 5505", "ASA 5506", "ISA-3000"]),
    ("network", "WAN Emulation", "generic", "cloud", ["Cloud-PT", "DSL-Modem-PT", "Cable-Modem-PT"]),

    ("end", "End Devices", "generic", "end-device", [
        "PC-PT", "Laptop-PT", "Server-PT", "Meraki-Server", "Network Controller", "CyberObserver",
        "DataHistorianServer", "PLC-PT", "Printer-PT", "7960", "Home-VoIP-PT", "Analog-Phone-PT", "TV-PT",
        "TabletPC-PT", "SMARTPHONE-PT", "WirelessEndDevice-PT", "WiredDevice-PT", "Sniffer",
    ]),
    ("end", "Home", "generic", "misc", [
        "AC", "Air Cooler", "Alarm", "Appliance", "Blower", "Bluetooth Speaker", "Ceiling Fan",
        "Ceiling Sprinkler", "Door", "Fire Sprinkler", "Furnace", "Garage Door", "Home Speaker",
        "Humidifier", "Lawn Sprinkler", "Light", "Portable Music Player", "Siren", "Smoke Detector",
        "Smart LED", "Thermostat", "Water Drain", "Webcam", "Window",
    ]),
    ("end", "Smart City", "generic", "misc", [
        "Street Lamp", "Old Car", "Fire Monitor", "Motion Detector", "Smoke Detector", "Webcam",
        "Wind Detector", "Environment Tweaker",
    ]),
    ("end", "Industrial", "generic", "misc", [
        "PT8000 Activated", "Motor", "Servo", "RFID Reader", "RFID Card", "Power Meter",
        "Generic Environment Sensor", "Generic Sensor",
    ]),
    ("end", "Power Grid", "generic", "misc", ["Battery", "Power Meter", "Solar Panel", "Wind Turbine"]),

    ("components", "Boards", "generic", "misc", ["MCU-PT", "SBC-PT", "Thing"]),
    ("components", "Actuators", "generic", "misc", [
        "LED", "RGB LED", "Dimmable LED", "Motor", "Servo", "Speaker", "Piezo Speaker", "Rocker Switch",
        "Push Button", "Toggle Push Button", "LCD", "Signal Generator",
    ]),
    ("components", "Sensors", "generic", "misc", [
        "Atm Pressure Monitor", "Carbon Dioxide Detector", "Carbon Monoxide Detector", "Flex Sensor",
        "Generic Environment Sensor", "Generic Sensor", "Humidity Monitor", "Humidity Sensor",
        "Humiture Monitor", "Humiture Sensor", "Membrane Potentiometer", "Metal Sensor", "Motion Sensor",
        "Photo Sensor", "Potentiometer", "Smoke Sensor", "Sound Frequency Detector", "Sound Sensor",
        "Temperature Monitor", "Temperature Sensor", "Trip Sensor", "Trip Wire", "Water Detector",
        "Water Level Monitor", "Water Sensor", "Wind Sensor",
    ]),
    ("connections", "Structured Cabling", "generic", "structured", [
        "Copper Patch Panel", "Fiber Patch Panel", "Copper Wall Mount", "Fiber Wall Mount",
    ]),
    ("misc", "Miscellaneous", "generic", "misc", ["Power Distribution Device"]),
    ("multiuser", "Multiuser Connection", "generic", "cloud", ["Multiuser Connection"]),
]

_ENGINE_KIND = {
    "PC-PT": "pc", "Laptop-PT": "pc", "WiredDevice-PT": "pc",
    "Server-PT": "server", "Meraki-Server": "server", "DataHistorianServer": "server", "Central Office Server": "server",
}

_ICON_OVERRIDES = {
    "3560-24PS": "switch-l3", "3650-24PS": "switch-l3", "IE-3400": "switch-l3", "IE-9320": "switch-l3",
    "Bridge-PT": "bridge", "Repeater-PT": "repeater", "CoAxialSplitter-PT": "coax-splitter",
    "LAP-PT": "lap", "3702i": "lap", "WLC-PT": "wlc", "WLC-3504": "wlc", "WLC-2504": "wlc",
    "Home Router": "home-router", "WRT300N": "linksys", "Home Gateway": "home-gateway",
    "Cell Tower": "cell-tower", "Central Office Server": "server-co", "DSL-Modem-PT": "dsl", "Cable-Modem-PT": "modem",
    "Meraki-MX65W": "security", "ASA 5505": "security", "ASA 5506": "security", "ISA-3000": "security",
    "PC-PT": "pc", "Laptop-PT": "laptop", "Server-PT": "server", "Meraki-Server": "meraki-server",
    "Network Controller": "controller", "Printer-PT": "printer", "7960": "ip-phone", "Home-VoIP-PT": "home-voip",
    "Analog-Phone-PT": "analog-phone", "TV-PT": "tv", "TabletPC-PT": "tablet", "SMARTPHONE-PT": "wireless-end",
    "WirelessEndDevice-PT": "wireless-end", "WiredDevice-PT": "wired-end", "Sniffer": "sniffer",
    "DataHistorianServer": "historian", "CyberObserver": "cyber-observer",
    "Copper Patch Panel": "patch-copper", "Fiber Patch Panel": "patch-fiber", "Copper Wall Mount": "wall-copper", "Fiber Wall Mount": "wall-fiber",
}

ICON_FILES = {key: key + '.svg' for key in ('router', 'switch', 'switch-l3', 'bridge', 'hub', 'repeater', 'coax-splitter', 'access-point', 'lap', 'wlc', 'home-router', 'linksys', 'home-gateway', 'cell-tower', 'server-co', 'cloud', 'dsl', 'modem', 'security', 'pc', 'laptop', 'server', 'meraki-server', 'controller', 'printer', 'ip-phone', 'home-voip', 'analog-phone', 'tv', 'tablet', 'wireless-end', 'wired-end', 'sniffer', 'historian', 'cyber-observer', 'patch-copper', 'patch-fiber', 'wall-copper', 'wall-fiber', 'structured', 'misc', 'end-device')}


def model_id(label: str) -> str:
    return re.sub(r"[^a-z0-9]+", "-", label.lower()).strip("-")


def catalog() -> dict:
    models = {}; groups = []
    for category, subtype, default_kind, default_icon, labels in _GROUPS:
        ids = []
        for label in labels:
            mid = model_id(label); kind = _ENGINE_KIND.get(label, default_kind)
            if default_kind in {"router", "switch"}: kind = default_kind
            icon = _ICON_OVERRIDES.get(label, default_icon)
            support = "engine" if kind in {"pc", "server", "router", "switch"} else "catalog"
            if any(token in mid for token in ("wlc-","accesspoint-","wrt300n","home-router","meraki-","network-controller","cyberobserver","plc-pt","cloud-pt","patch-panel","wall-mount","asa-","isa-")):support="engine-simplified"
            palette_icon = "device/" + model_id(label) + ".svg"
            models[mid] = {"id":mid,"label":label,"category":category,"subtype":subtype,"kind":kind,"icon":icon,"support":support,"palette_icon":palette_icon}
            ids.append(mid)
        groups.append({"category":category,"subtype":subtype,"models":ids})
    return {"source":SOURCE,"models":models,"groups":groups,"icons":ICON_FILES}


CATALOG = catalog(); MODELS = CATALOG["models"]


def get_model(mid: str) -> dict:
    key = model_id(mid)
    if key not in MODELS: raise KeyError(mid)
    return MODELS[key]

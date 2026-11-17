"""Explicitly simulated expansion modules for Packet Tracker and Simulator generic PT devices.

Media and power constraints are modelled. hardware-labelled cards use simplified
slot profiles, not vendor chassis/ASIC emulation or exact slot compatibility.
"""
from __future__ import annotations

MODULE_TYPES = {
    "PT-ETH-1": {"label": "PT Ethernet 1-port (simulated)", "ports": 1},
    "PT-ETH-4": {"label": "PT Ethernet 4-port (simulated)", "ports": 4},
}
PROFILES = {
    "router-pt": ("slot0", "slot1"),
    "switch-pt": ("slot0", "slot1"),
    "pc-pt": ("slot0",),
    "laptop-pt": ("slot0",),
    "server-pt": ("slot0",),
}
GENERIC_KIND = {
    "router": ("slot0", "slot1"),
    "switch": ("slot0", "slot1"),
    "pc": ("slot0",),
    "server": ("slot0",),
}

def slots_for(device):
    if device.model:
        return PROFILES.get(device.model, ())
    return GENERIC_KIND.get(device.kind, ())

def interfaces_for(slot, module):
    index = int(slot.removeprefix("slot"))
    return [f"m{index}/{p}" for p in range(1, MODULE_TYPES[module]["ports"] + 1)]

# PT medium modules plus documented vendor media cards. Slot identifiers remain
# stable mN/P port names so existing labs and agent scripts are not renumbered.
for _name,_ports,_media in [
 ("PT-FIBER-MM-1",1,"fiber-mm"),("PT-FIBER-SM-1",1,"fiber-sm"),("PT-SERIAL-2",2,"serial"),
 ("PT-MODEM-1",1,"modem"),("PT-COAX-1",1,"coax"),("PT-WIFI-1",1,"wifi"),
 ("PT-USB-1",1,"usb"),("PT-IOE-1",1,"ioe"),("PT-CONSOLE-1",1,"console"),("PT-RS232-1",1,"rs232"),
 ("WIC-1T",1,"serial"),("WIC-2T",2,"serial"),("HWIC-2T",2,"serial"),("NM-1FE-TX",1,"copper"),
 ("NM-2FE2W",2,"copper"),("GLC-T",1,"copper"),("GLC-LH-SMD",1,"fiber-sm"),
 ("GLC-LX-SM-RGD",1,"fiber-sm"),("GLC-SX-MM",1,"fiber-mm")]:
    MODULE_TYPES[_name]={"label":_name,"ports":_ports,"media":_media}
for _family in ("ROUTER","SWITCH","REPEATER","CLOUD","HOST"):
    for _suffix,_media in (("1CE","copper"),("1CFE","copper"),("1CGE","copper"),("1FFE","fiber-mm"),("1FGE","fiber-mm"),("1S","serial"),("1AM","modem"),("1CX","coax"),("1W","wifi")):
        _name=f"PT-{_family}-NM-{_suffix}"
        MODULE_TYPES[_name]={"label":_name,"ports":1,"media":_media}
PROFILES.update({
 '1841':('slot0','slot1'),'1941':('slot0','slot1'),'2811':('slot0','slot1','slot2'),
 '2911':('slot0','slot1','slot2'),'819':('slot0',),'829':('slot0','slot1'),
 '4321':('slot0','slot1'),'4331':('slot0','slot1','slot2'),
 'cloud-pt':tuple('slot'+str(i) for i in range(10)),
 'hub-pt':tuple('slot'+str(i) for i in range(10)),
 'repeater-pt':('slot0','slot1'),'accesspoint-pt':('slot0',),
 'accesspoint-pt-a':('slot0',),'accesspoint-pt-ac':('slot0',),'accesspoint-pt-n':('slot0',),
 'dsl-modem-pt':('slot0',),'cable-modem-pt':('slot0',),
})

def compatible_modules(device):
    # Generic PT cards are a simulator extension. hardware-labelled cards are only
    # advertised on the simulated router slots, not arbitrary end-device bays.
    return [name for name in MODULE_TYPES if name.startswith('PT-') or device.kind=='router']

for _label,_base in [('isr4331','4331'),('isr4321','4321'),('cgr1240','2811'),('ir1101','819'),('ir8340','2911')]:PROFILES[_label]=PROFILES[_base]

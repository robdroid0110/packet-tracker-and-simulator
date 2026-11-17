"""Section 21 Physical Workspace Accessibility — machine-readable view & typed actions.

The UI navigator is a screen-reader-friendly presentation of this authoritative
lab view. There is no shadow topology or browser-only mutation.
"""
from __future__ import annotations

import math
import shlex

from .model import LabError
from .physical_workspace import physical_tree
SURFACES=("rack","table","floor","shelf")

def _free_ports(lab,name):
    d=lab._device(name)
    rows=[]
    for ident,interface in d.interfaces.items():
        if getattr(interface,"parent",None):
            continue
        link=lab.link_for(name,ident)
        peer=None if link is None else ({
            "device":link.b_device,"interface":link.b_if} if link.a_device==name else {
            "device":link.a_device,"interface":link.a_if})
        rows.append({
            "name":ident,"connected":link is not None,"peer":peer,
            "admin_up":bool(interface.admin_up),
            "operational":bool(lab.link_operational(link)) if link else False,
            "cable":link.cable if link else None,
            "status":lab.link_status(link)["reason"] if link else "no cable"
        })
    return rows

def view(lab,location="intercity"):
    if location!="intercity":lab._physical_location(location)
    tree=physical_tree(lab)["tree"]
    current=None if location=="intercity" else lab.physical_locations[location]
    ancestors=[]
    node=current
    while node:
        ancestors.append({"id":node["id"],"name":node["name"],"type":node["type"]})
        node=lab.physical_locations.get(node["parent"])
    ancestors.reverse()
    crumbs=[{"id":"intercity","name":"Intercity","type":"intercity"},*ancestors]
    children=[
        {"id":loc["id"],"name":loc["name"],"type":loc["type"],
         "device_count":sum(lab.device_locations.get(n)==loc["id"] for n in lab.devices)}
        for loc in lab.physical_locations.values()
        if loc["parent"]==(None if location=="intercity" else location)
    ]
    devices=[]
    for name,d in lab.devices.items():
        if lab.device_locations.get(name,"intercity")!=location:
            continue
        detail=lab.physical_device_details.get(name,lab._physical_placement_default(d.kind,location))
        devices.append({
            "name":name,"kind":d.kind,"model":d.model or d.kind,
            "powered":d.powered,"surface":detail["surface"],
            "shelf":detail.get("shelf"),
            "ports":_free_ports(lab,name),
            "slots":lab.module_slots(name) if d.kind in ("pc","server","switch","router") else [],
        })
    connected=[]
    for link in lab.links:
        a=lab.device_locations.get(link.a_device,"intercity")
        b=lab.device_locations.get(link.b_device,"intercity")
        if location not in (a,b):continue
        connected.append({
            "a_device":link.a_device,"a_if":link.a_if,
            "b_device":link.b_device,"b_if":link.b_if,
            "up":lab.link_operational(link),"status":lab.link_status(link)["reason"],
            "cable":link.cable,
        })
    selected_surfaces=[]
    if current and current["type"]=="closet":
        selected_surfaces=[
            {"id":"rack","name":"Rack","count":sum(d["surface"]=="rack" for d in devices)},
            {"id":"table","name":"Table","count":sum(d["surface"]=="table" for d in devices)},
            {"id":"floor","name":"Floor","count":sum(d["surface"]=="floor" for d in devices)},
        ]+[
            {"id":f"shelf:{i}","name":f"Storage shelf {i+1}",
             "count":sum(d["surface"]=="shelf" and d["shelf"]==i for d in devices)}
            for i in range(lab.physical_shelves.get(location,0))
        ]
    elif current and current["type"]=="icp":
        selected_surfaces=[
            {"id":"cabinet","name":"Cabinet","count":sum(d["surface"]=="cabinet" for d in devices)},
            {"id":"door","name":"Door","count":sum(d["surface"]=="door" for d in devices)}
        ]
    # All visible inventory belongs to the current physical location, not another user's hidden session.
    return {
        "ok":True,"location":location,"name":current["name"] if current else "Intercity",
        "type":current["type"] if current else "intercity",
        "parent":current["parent"] or "intercity" if current else None,
        "path":crumbs,"tree":tree,"children":children,
        "surfaces":selected_surfaces,"devices":devices,"links":connected,
        "count":{"locations":len(children),"devices":len(devices),"links":len(connected)},
        "semantics":{
            "screen_reader":"Native buttons/labels, visible focus, live region; host OS screen reader required.",
            "rack_slots":"Wiring closet rack is an arrangement surface. Numbered rack-unit slots are not modeled.",
            "take":"Select source device; persistent state changes only when placed/mounted.",
            "connect":"Pick two available ports; source selection is transient UI state.",
            "disconnect":"Explicit remove-link action preserves both devices.",
            "location_navigation":"Entering a location changes view only; no backend mutation."
        }
    }

def command(body):
    if not isinstance(body,dict):raise LabError("accessibility action must be an object")
    action=body.get("action")
    if action in ("undo","redo"):
        return action
    def word(field):
        value=body.get(field)
        if not isinstance(value,str) or not value or len(value)>100 or any(c.isspace() for c in value):
            raise LabError(field+" must be a non-empty single token")
        return shlex.quote(value)
    def kind(field,choices):
        value=body.get(field)
        if value not in choices:raise LabError(field+" must be one of "+", ".join(choices))
        return str(value)
    if action=="move_device":
        return "physical place "+word("device")+" "+word("location")
    if action=="mount_device":
        surface=kind("surface",SURFACES)
        if surface=="shelf":
            shelf=body.get("shelf")
            if isinstance(shelf,bool) or not isinstance(shelf,int) or not 0<=shelf<20:
                raise LabError("shelf must be an integer 0..19")
            return "physical mount "+word("device")+" shelf "+str(shelf)
        return "physical mount "+word("device")+" "+surface
    if action=="place_icp_device":
        side=kind("side",("door","cabinet"))
        for coordinate in ("x","y"):
            value=body.get(coordinate)
            if isinstance(value,bool) or not isinstance(value,(int,float)) or not math.isfinite(value) or not 0<=value<=1000:
                raise LabError(coordinate+" must be within 0..1000")
        return "icp device-move "+word("device")+" "+side+" "+str(body["x"])+" "+str(body["y"])+" 0 detach"
    if action=="add_device":
        model=word("model")
        name=word("name")
        location=word("location")
        x,y=body.get("x",140),body.get("y",130)
        if any(isinstance(v,bool) or not isinstance(v,(int,float)) or not math.isfinite(v) or not 0<=v<=10000 for v in (x,y)):
            raise LabError("x/y must be finite within 0..10000")
        return "physical add-device "+model+" "+name+" "+str(x)+" "+str(y)+" "+location
    if action=="connect":
        cable=kind("cable",("auto",*__import__("netsim.hardware",fromlist=["CABLE_MEDIA"]).CABLE_MEDIA))
        return "connect "+word("a_device")+" "+word("a_if")+" "+word("b_device")+" "+word("b_if")+" "+cable
    if action=="disconnect":
        return "disconnect "+word("device")+" "+word("interface")
    if action=="power":
        powered=body.get("enabled")
        if not isinstance(powered,bool):raise LabError("enabled must be boolean")
        return "power "+word("device")+" "+("on" if powered else "off")
    if action=="add_shelf":
        return "physical shelf-add "+word("location")
    if action=="set_module":
        slot=word("slot")
        module=word("module")
        return "module "+word("device")+" "+slot+" "+module
    raise LabError("unsupported physical accessibility action")

def schema():
    return {
        "version":1,
        "read":{"view":"GET /api/physical-accessibility?location=closet0",
                "schema":"GET /api/physical-accessibility/schema",
                "physical_tree":"GET /api/physical-workspace/tree"},
        "write":{"method":"POST","path":"/api/physical-accessibility/action",
                 "actions":{
                   "move_device":{"device":"R1","location":"closet0"},
                   "mount_device":{"device":"R1","surface":"rack"},
                   "mount_shelf":{"action":"mount_device","device":"PC1","surface":"shelf","shelf":0},
                   "place_icp_device":{"device":"R1","side":"cabinet","x":200,"y":120},
                   "add_device":{"model":"router","name":"R2","location":"closet0","x":140,"y":130},
                   "connect":{"a_device":"PC1","a_if":"eth0","b_device":"R1","b_if":"g0/0","cable":"auto"},
                   "disconnect":{"device":"PC1","interface":"eth0"},
                   "power":{"device":"R1","enabled":False},
                   "set_module":{"device":"R1","slot":"0","module":"PT-ETH-1"},
                   "add_shelf":{"location":"closet0"},
                   "undo":{},"redo":{},
                 }},
        "navigation":{
            "keys":["Tab/Shift+Tab next/previous control","Arrow Up/Down navigate siblings",
                    "Arrow Right/Enter open location/device","Arrow Left/Backspace back",
                    "Escape close dialog","Alt+Shift+A toggle accessible physical navigation"],
            "read_only_steps":["Navigate location", "Select source device/port"],
            "side_effects":["Place existing device","Mount on rack/table/floor/shelf",
                            "Connect/disconnect ports","Power device",
                            "Add device from supported model"],
        },
        "rules":[
            "All mutating actions use existing CommandProcessor commands and native lab autosave.",
            "Selecting devices, cables and ports in the accessible dialog is temporary UI state.",
            "Rack is a mounting surface, not separately numbered physical rack units.",
            "No simulated console/fiber connection is offered until underlying engine supports it.",
            "The browser does not itself implement speech; use Narrator, VoiceOver, Orca or another screen reader."
        ]
    }

"""Read-only, cluster-scoped Workspace List projection and typed command adapter.

All writes are routed through the existing CommandProcessor for shared validation,
atomic edit-history and autosave. A list view never owns a separate network state.
"""
from __future__ import annotations
import math
import re
import shlex
from .model import NetworkLab, LabError
from .device_catalog import MODELS
from .modules import MODULE_TYPES

def workspace_list(lab: NetworkLab, cluster: str="root", device: str|None=None) -> dict:
    if cluster not in {"root",*lab.clusters}:
        raise LabError(f"unknown logical cluster {cluster}")
    parent = None if cluster=="root" else cluster
    membership={n:key for key,c in lab.clusters.items() for n in c["devices"]}
    visible={name for name in lab.devices if membership.get(name)==parent}
    devices=[
        {
            "type":"device", "name":name, "model":d.model or d.kind,
            "kind":d.kind,"powered":d.powered,"x":d.x,"y":d.y,
            "interface_count":len(d.interfaces), "cluster":parent
        }
        for name,d in lab.devices.items() if name in visible
    ]
    clusters=[
        {"type":"cluster","id":ident,"name":c["name"],"count":len(c["devices"]),
         "child_count":sum(1 for child in lab.clusters.values() if child["parent"]==ident),
         "parent":parent}
        for ident,c in lab.clusters.items() if c["parent"]==parent
    ]
    links=[]
    for link in lab.links:
        if link.a_device not in visible or link.b_device not in visible:continue
        up=lab.link_operational(link)
        reason=lab.link_status(link)["reason"]
        links.append({
            "id":f"{link.a_device}:{link.a_if}|{link.b_device}:{link.b_if}",
            "source":f"{link.a_device}:{link.a_if}",
            "destination":f"{link.b_device}:{link.b_if}",
            "a_device":link.a_device,"a_if":link.a_if,
            "b_device":link.b_device,"b_if":link.b_if,
            "cable":link.cable,"up":up,
            "light":"green" if up else "red","status":reason
        })
    selected=None
    if device is not None:
        if device not in visible: raise LabError("selected device is not visible in this cluster")
        d=lab._device(device)
        fixed=[n for n,i in d.interfaces.items() if not i.parent and not re.fullmatch(r"m[0-9]+/[0-9]+",n)]
        selected={
            "device":device,"model":d.model or d.kind,"powered":d.powered,
            "slots":[
                {"slot":"onboard","module":"Built-in interfaces","editable":False,
                 "available":[],"requires_power_off":False,"interfaces":fixed}
            ]+lab.module_slots(device),
        }
    return {
        "cluster":cluster,"parent":"root" if parent is None else lab.clusters[parent]["parent"] or "root",
        "path":_cluster_path(lab,parent),"devices":devices,"clusters":clusters,"links":links,
        "selected":selected,
        "capabilities":{"device_position":True,"device_power":True,"device_add_remove":True,
                        "link_add_remove":True,"module_profile":"simulated-pt-only",
                        "max_visible_devices":None},
    }

def _cluster_path(lab: NetworkLab, cluster: str|None)->list[dict]:
    chain=[{"id":"root","name":"Root"}]
    names=[]
    current=cluster
    while current is not None:
        c=lab.clusters[current]
        names.append({"id":current,"name":c["name"]})
        current=c["parent"]
    chain.extend(reversed(names))
    return chain

def action_to_command(payload:dict)->str:
    if not isinstance(payload,dict):
        raise LabError("action must be an object")
    action=payload.get("action")
    if not isinstance(action,str):
        raise LabError("action name required")
    def need(name):
        value=payload.get(name)
        if not isinstance(value,str) or not value:
            raise LabError(f"{name} must be a nonempty string")
        return value
    def quote(name):
        return shlex.quote(need(name))
    def number(name):
        raw=payload.get(name)
        if isinstance(raw,bool) or not isinstance(raw,(float,int)) or not math.isfinite(raw) or not 0<=raw<=10000:
            raise LabError(f"{name} must be a finite number between 0 and 10000")
        return str(raw)
    if action=="add_device":
        if not re.fullmatch(r"[A-Za-z][A-Za-z0-9_-]{0,30}",need("name")):raise LabError("invalid device name")
        kind=payload.get("kind")
        model=payload.get("model")
        target=payload.get("cluster","root")
        if not isinstance(target,str):raise LabError("cluster must be a string")
        if model is not None:
            if not isinstance(model,str) or model not in MODELS:raise LabError("unknown model")
            spec=model
        else:
            if kind not in {"pc","server","switch","router","generic"}:raise LabError("unknown device kind")
            spec=kind
        if target!="root":
            return "add-in-cluster "+shlex.quote(spec)+" "+quote("name")+" "+number("x")+" "+number("y")+" "+shlex.quote(target)
        return ("add-model " if model is not None else "add ")+shlex.quote(spec)+" "+quote("name")+" "+number("x")+" "+number("y")
    if action=="remove_device":return "remove "+quote("device")
    if action=="move_device":return "move "+quote("device")+" "+number("x")+" "+number("y")
    if action=="power_device":
        if not isinstance(payload.get("powered"),bool):raise LabError("powered must be boolean")
        return "power "+quote("device")+" "+("on" if payload["powered"] else "off")
    if action=="add_link":
        cable=payload.get("cable","auto")
        if cable not in {"auto",*__import__("netsim.hardware",fromlist=["CABLE_MEDIA"]).CABLE_MEDIA}:raise LabError("unsupported cable")
        return "connect "+" ".join((quote("a_device"),quote("a_if"),quote("b_device"),quote("b_if"),shlex.quote(cable)))
    if action=="remove_link":return "disconnect "+quote("device")+" "+quote("iface")
    if action=="set_module":
        model=payload.get("module")
        if model is not None and model not in MODULE_TYPES:
            raise LabError("unsupported simulated module type")
        return "module "+quote("device")+" "+quote("slot")+" "+(model or "none")
    if action in {"undo","redo"}:return action
    raise LabError("unsupported workspace-list action")
def workspace_list_schema() -> dict:
    """Discovery metadata for agent clients and accessible table integrations."""
    return {
        "version":1,"product":"Packet Tracker and Simulator",
        "read":{
            "method":"GET","path":"/api/workspace-list",
            "query":{"cluster":"root or Cluster0/Cluster1/... (default root)",
                     "device":"optional selected visible device name"},
            "data":["devices","clusters","links","selected.slots","parent","path"],
        },
        "write":{
            "method":"POST","path":"/api/workspace-list/action",
            "body":"JSON object with action and its named fields",
            "optional":["cluster","selected_device"],
            "actions":{
                "add_device":{"model":"router-pt","name":"R1","x":150,"y":180,"cluster":"root"},
                "remove_device":{"device":"R1"},
                "move_device":{"device":"R1","x":240,"y":210},
                "power_device":{"device":"R1","powered":False},
                "add_link":{"a_device":"R1","a_if":"g0/0","b_device":"SW1","b_if":"fa0/1","cable":"auto"},
                "remove_link":{"device":"R1","iface":"g0/0"},
                "set_module":{"device":"R1","slot":"slot0","module":"PT-ETH-1"},
                "undo":{},"redo":{}
            }
        },
        "rules":[
            "All edits share the same CommandProcessor, validations, undo history and persisted lab.",
            "Only simulated generic PT modules are supported; vendor-specific module compatibility is not modeled.",
            "Power off a device before changing a module. Disconnect module ports before removal.",
            "Only auto, copper-straight and copper-cross cable media are modeled.",
            "Workspace List filters by logical cluster. Device configurations and cross-cluster connectivity are not changed by viewing it."
        ],
        "supported_modules":MODULE_TYPES,
        "supported_cables":["auto",*__import__("netsim.hardware",fromlist=["CABLE_MEDIA"]).CABLE_MEDIA],
    }

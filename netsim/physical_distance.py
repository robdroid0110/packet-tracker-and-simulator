"""Deterministic, calibrated 2-D distance geometry for Physical Workspace.

Coordinates are browser-canvas units within each physical container; this
module projects them to meters in a shared intercity frame. The API reports
*straight-line estimates*, not routed cable slack, wall attenuation, height,
or radio protocol association.
"""
from __future__ import annotations
import math
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from .model import NetworkLab

FRAME_WIDTH_PX=1000.0
FRAME_HEIGHT_PX=700.0
INTERCITY_WIDTH_M=100000.0
INTERCITY_LENGTH_M=70000.0
COPPER_MAX_M=100.0
RADIO_DEFAULTS={
    "AccessPoint-PT":("wifi",140.0),
    "AccessPoint-PT-A":("wifi",140.0),
    "AccessPoint-PT-AC":("wifi",140.0),
    "AccessPoint-PT-N":("wifi",140.0),
    "LAP-PT":("wifi",140.0),
    "3702i":("wifi",140.0),
    "WRT300N":("wifi",140.0),
    "Home Router":("wifi",140.0),
    "Home Gateway":("wifi",140.0),
    "Meraki-MX65W":("wifi",140.0),
    "Cell Tower":("cellular",1000.0),
    "Bluetooth Speaker":("bluetooth",10.0),
    "SMARTPHONE-PT":("bluetooth",10.0),
    "TabletPC-PT":("bluetooth",10.0),
}
RADIO_CLIENTS={
    "wifi":{"Laptop-PT","TabletPC-PT","SMARTPHONE-PT","WirelessEndDevice-PT"},
    "cellular":{"TabletPC-PT","SMARTPHONE-PT"},
    "bluetooth":{"TabletPC-PT","SMARTPHONE-PT","Bluetooth Speaker"},
}

def _dims(lab:NetworkLab,location:str)->tuple[float,float]:
    if location=="intercity":
        return INTERCITY_WIDTH_M,INTERCITY_LENGTH_M
    obj=lab.physical_locations[location]
    return float(obj["width"]),float(obj["length"])

def frame_scale(lab:NetworkLab,location:str)->dict:
    width,length=_dims(lab,location)
    return {"location":location,
            "width_m":width,"length_m":length,
            "width_px":FRAME_WIDTH_PX,"height_px":FRAME_HEIGHT_PX,
            "meters_per_x":width/FRAME_WIDTH_PX,
            "meters_per_y":length/FRAME_HEIGHT_PX}

def location_origin_m(lab:NetworkLab,location:str)->tuple[float,float]:
    if location=="intercity":return (0.0,0.0)
    point_x=point_y=0.0
    seen=set()
    cursor=location
    while cursor!="intercity":
        if cursor in seen or cursor not in lab.physical_locations:
            raise ValueError("invalid physical location hierarchy")
        seen.add(cursor)
        entry=lab.physical_locations[cursor]
        parent=entry["parent"] or "intercity"
        scale=frame_scale(lab,parent)
        point_x+=float(entry["x"])*scale["meters_per_x"]
        point_y+=float(entry["y"])*scale["meters_per_y"]
        cursor=parent
    return point_x,point_y

def device_world_position(lab:NetworkLab,device:str)->dict:
    d=lab._device(device)
    location=lab.device_locations.get(device,"intercity")
    placement=lab.physical_device_details.get(device,
        lab._physical_placement_default(d.kind,location))
    ox,oy=location_origin_m(lab,location)
    scale=frame_scale(lab,location)
    return {"device":device,"location":location,
            "x_m":ox+float(placement["x"])*scale["meters_per_x"],
            "y_m":oy+float(placement["y"])*scale["meters_per_y"],
            "local_x":placement["x"],"local_y":placement["y"]}

def projected_position(lab:NetworkLab,device:str,view_location:str)->dict:
    if view_location!="intercity":lab._physical_location(view_location)
    source=device_world_position(lab,device)
    ox,oy=location_origin_m(lab,view_location)
    scale=frame_scale(lab,view_location)
    return {"device":device,"location":source["location"],
            "view_location":view_location,
            "x":(source["x_m"]-ox)/scale["meters_per_x"],
            "y":(source["y_m"]-oy)/scale["meters_per_y"]}

def distance_m(lab:NetworkLab,a:str,b:str)->float:
    p1=device_world_position(lab,a);p2=device_world_position(lab,b)
    return math.hypot(p1["x_m"]-p2["x_m"],p1["y_m"]-p2["y_m"])

def cable_length(lab:NetworkLab,link)->dict:
    from .cable_manipulation import segments,total_length_m
    direct=distance_m(lab,link.a_device,link.b_device)
    path=segments(lab,link)
    total=total_length_m(lab,link)
    limit=COPPER_MAX_M if link.cable in {"auto","copper-straight","copper-cross"} else None
    return {"distance_m":round(direct,4),"total_length_m":round(total,4),
            "segments":path,
            "max_length_m":limit,
            "in_range":(total<=limit+1e-8 if limit is not None else None),
            "enforced":bool(lab.cable_length_effects),
            "unit":"meters","model":"2d-polyline" if len(path)>1 else "2d-straight-line",
            "caveat":"Cable bend points modify simulated path length. 3D height, conduit, slack and wall detours are not modeled."}

def _model_key(model:str)->str:
    import re
    return re.sub(r'[^a-z0-9]+','-',model.lower()).strip('-')

def radio_default(model:str)->tuple[str,float]|None:
    return next((profile for label,profile in RADIO_DEFAULTS.items()
                 if _model_key(label)==_model_key(model)),None)

def radio_sources(lab:NetworkLab,view_location:str="intercity")->list[dict]:
    frame=frame_scale(lab,view_location)
    entries=[]
    for name,d in lab.devices.items():
        defaults=radio_default(d.model or "")
        if defaults is None:continue
        medium,standard=defaults
        radius=lab.radio_ranges.get(name,standard)
        projected=projected_position(lab,name,view_location)
        entry={**projected,"medium":medium,"model":d.model,
               "radius_m":radius,
               "radius_x_px":radius/frame["meters_per_x"],
               "radius_y_px":radius/frame["meters_per_y"],
               "powered":d.powered,"simulated_association":False}
        entries.append(entry)
    return entries

def radio_pairs(lab:NetworkLab)->list[dict]:
    result=[]
    for source,device in lab.devices.items():
        profile=radio_default(device.model or "")
        if profile is None or not device.powered:continue
        medium,default=profile
        radius=lab.radio_ranges.get(source,default)
        for target,client in lab.devices.items():
            if source==target or _model_key(client.model or '') not in {_model_key(label) for label in RADIO_CLIENTS[medium]} or not client.powered:
                continue
            length=distance_m(lab,source,target)
            result.append({"source":source,"target":target,"medium":medium,
                           "distance_m":round(length,4),"range_m":radius,
                           "within_range":length<=radius+1e-8,
                           "protocol_association":"not-modeled"})
    return result

def physics_status(lab:NetworkLab,view_location:str="intercity")->dict:
    if view_location!="intercity":lab._physical_location(view_location)
    return {"ok":True,"geometry":frame_scale(lab,view_location),
            "cable_length_effects":lab.cable_length_effects,
            "ethernet_limit_m":COPPER_MAX_M,
            "links":[{
                "a_device":l.a_device,"a_if":l.a_if,
                "b_device":l.b_device,"b_if":l.b_if,
                "operational":lab.link_operational(l),
                "status":lab.link_status(l)["reason"],
                **cable_length(lab,l)} for l in lab.links],
            "radios":radio_sources(lab,view_location),
            "radio_pairs":radio_pairs(lab),
            "limitations":{
                "wired_geometry":"2D polyline when cable bend points exist; no slack, 3D or wall detours",
                "wireless_association":"not implemented: radio pairs are geometric range estimates",
                "electromagnetic_propagation":"not modeled (no fading, interference or obstructions)",
                "vertical_dimension":"height is used only for container size fit",
                "default_cable_effects":"off for backward compatibility",
            }}

def schema()->dict:
    return {
        "version":1,
        "read":{
            "distance":"GET /api/physical-distance?source=R1&target=R2",
            "cable":"GET /api/physical-distance?device=R1&interface=g0/0",
            "status":"GET /api/physical-distance?location=city0",
            "radio":"GET /api/physical-distance?location=city0",
        },
        "write":{"method":"POST","path":"/api/physical-distance/action",
                 "actions":{
                    "cable_effects":{"enabled":True},
                    "radio_range":{"device":"AP1","radius_m":140.0},
                    "undo":{},"redo":{},
                 }},
        "rules":[
            "Device distance is 2D straight line; cable length is a 2D routed polyline if BendPoints exist.",
            "Intercity default width is 100000m across 1000 canvas units, height 70000m across 700 canvas units.",
            "Set container dimensions with the existing physical dimensions command; this changes projected distances.",
            "Copper links >100m lose simulated carrier only when cable-effects preference is enabled.",
            "Physical cable effects are disabled by default, to keep old labs functional.",
            "Radio coverage is geometric only; wireless association and RF packet forwarding are not implemented.",
            "Defaults: most access points 140m, cell towers 1000m, simulated Bluetooth sources 10m.",
        ],
    }

def action_command(body:dict)->str:
    """Validate typed JSON before invoking the shared CLI CommandProcessor."""
    import shlex
    if not isinstance(body,dict):raise ValueError("expected JSON object")
    action=body.get("action")
    if action=="cable_effects":
        if not isinstance(body.get("enabled"),bool):
            raise ValueError("enabled must be true or false")
        return "physical cable-effects "+("on" if body["enabled"] else "off")
    if action=="radio_range":
        name=body.get("device")
        radius=body.get("radius_m")
        if not isinstance(name,str) or not name or len(name)>31 or any(c.isspace() for c in name):
            raise ValueError("invalid radio source device name")
        if isinstance(radius,bool) or not isinstance(radius,(float,int)) or not math.isfinite(radius) or not 0.1<=radius<=100000:
            raise ValueError("radius_m must be a finite number in 0.1..100000")
        return "physical radio-range "+shlex.quote(name)+" "+str(radius)
    if action in {"undo","redo"}:return action
    raise ValueError("unsupported distance action")

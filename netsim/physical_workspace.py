"""API-first Physical Workspace projection and typed command translation.

All physical edits share NetworkLab and the existing CommandProcessor. No
browser-local simulated world or second geometry authority.
"""
from __future__ import annotations
import math,shlex
from .model import LabError,NetworkLab

def physical_tree(lab:NetworkLab)->dict:
    """Stable, hierarchical navigation structure for API agents and GUI."""
    roots={"intercity":{"id":"intercity","name":"Intercity","type":"intercity",
                        "parent":None,"children":[],"devices":[]}}
    for ident,place in lab.physical_locations.items():
        roots[ident]={"id":ident,"name":place["name"],"type":place["type"],
                      "parent":place["parent"] or "intercity",
                      "children":[],"devices":[],
                      "width":place["width"],"length":place["length"],"height":place["height"]}
    for name,d in lab.devices.items():
        location=lab.device_locations.get(name,"intercity")
        detail=lab.physical_device_details.get(name,lab._physical_placement_default(d.kind,location))
        roots[location]["devices"].append({
            "name":name,"kind":d.kind,"model":d.model or d.kind,
            "surface":detail["surface"],"powered":d.powered,
            "x":detail["x"],"y":detail["y"]
        })
    for ident,loc in lab.physical_locations.items():
        roots[loc["parent"] or "intercity"]["children"].append(roots[ident])
    return {"ok":True,"tree":roots["intercity"],"location_count":len(lab.physical_locations),
            "device_count":len(lab.devices),"max_move_selection":200}

def physical_boundary_links(lab:NetworkLab,location:str)->list[dict]:
    """Aggregate cables between *different visible child areas* in this view.

    Example: routers in two closets in different cities produce an intercity
    line City A <-> City B rather than a false direct link between city icons.
    """
    current=None if location=="intercity" else location
    def visible_branch(ident:str)->str|None:
        if ident=="intercity":return None
        seen=set()
        while ident!="intercity":
            if ident in seen or ident not in lab.physical_locations:return None
            seen.add(ident)
            parent=lab.physical_locations[ident]["parent"]
            if parent==current:return ident
            ident=parent or "intercity"
        return None
    counts={}
    for link in lab.links:
        a=visible_branch(lab.device_locations.get(link.a_device,"intercity"))
        b=visible_branch(lab.device_locations.get(link.b_device,"intercity"))
        if not a or not b or a==b:continue
        source,destination=sorted((a,b))
        key=(source,destination)
        if key not in counts:counts[key]={"source":source,"destination":destination,"links":0,"up":0,"cables":[]}
        counts[key]["links"]+=1
        counts[key]["up"]+=int(lab.link_operational(link))
        from .physical_distance import cable_length
        from .cable_manipulation import route_for
        counts[key]["cables"].append({
            "endpoints":[f"{link.a_device}:{link.a_if}",f"{link.b_device}:{link.b_if}"],
            "length_m":cable_length(lab,link)["total_length_m"],
            "color":route_for(lab,link)["color"],
            "operational":lab.link_operational(link)
        })
    return list(counts.values())

def physical_view(lab:NetworkLab,location:str="intercity")->dict:
    if location!="intercity":lab._physical_location(location)
    from .physical_grid import view as grid_view
    parent=None if location=="intercity" else lab.physical_locations[location]
    current_id=None if location=="intercity" else location
    children=[dict(p) for p in lab.physical_locations.values() if p["parent"]==current_id]
    devices=[]
    for name,d in lab.devices.items():
        if lab.device_locations.get(name)!=location:continue
        detail=lab.physical_device_details.get(name,lab._physical_placement_default(d.kind,location))
        connected=[l for l in lab.links if l.a_device==name or l.b_device==name]
        devices.append({
            "name":name,"kind":d.kind,"model":d.model or d.kind,"powered":d.powered,
            "x":detail["x"],"y":detail["y"],"surface":detail["surface"],"shelf":detail["shelf"],
            "ports":len(d.interfaces),"cables":len(connected),
            "active_cables":sum(lab.link_operational(l) for l in connected),
        })
    # Summary of connected edges crossing locations for a physical-map view.
    connections=[]
    for link in lab.links:
        a=lab.device_locations.get(link.a_device,"intercity")
        b=lab.device_locations.get(link.b_device,"intercity")
        if a==location or b==location:
            connections.append({
                "source":link.a_device,"destination":link.b_device,
                "source_location":a,"destination_location":b,
                "cable":link.cable,"operational":lab.link_operational(link),
                "reason":lab.link_status(link)["reason"],
            })
    return {
        "grid": grid_view(lab,location),
        "grid_profiles":{kind:dict(profile) for kind,profile in lab.physical_grids.items()},
        "delete_preview":lab.physical_delete_preview(location) if parent else None,
        "location":location,
        "parent":"intercity" if parent is None or parent["parent"] is None else parent["parent"],
        "current":dict(parent) if parent else {"id":"intercity","type":"intercity","name":"Intercity","parent":None},
        "children":children,
        "devices":devices,
        "shelves":lab.physical_shelves.get(location,0),
        "links":connections,
        "boundary_links":physical_boundary_links(lab,location),
        "locations":{n:dict(v) for n,v in lab.physical_locations.items()},
        "device_locations":dict(lab.device_locations),
        "limitations":{
            "distance_effects":lab.cable_length_effects,"wireless_propagation":False,
            "cable_bend_points":True,"cable_group_points":True,"cable_colors":True,
            "rack_position_simulation":"visual-only",
            "cable_pegboard":False,
            "generic_container_size_rules":True,
            "shelf_storage_rules":True,
        },
    }

def action_command(data:dict)->str:
    if not isinstance(data,dict):raise LabError("expected a JSON object")
    action=data.get("action")
    def word(key):
        value=data.get(key)
        if not isinstance(value,str) or not value.strip() or len(value)>100:
            raise LabError(key+" must be a nonempty string")
        return shlex.quote(value)
    def num(key):
        value=data.get(key)
        if isinstance(value,bool) or not isinstance(value,(int,float)) or not math.isfinite(value):
            raise LabError(key+" must be a finite number")
        return str(value)
    def location(key):
        value=data.get(key)
        if value=="intercity":return value
        return word(key)
    if action=="set_grid":
        from .physical_grid import validate_profile
        kind=data.get("container_type")
        profile=validate_profile(kind,data.get("enabled"),data.get("spacing_m"),data.get("color"))
        return "physical grid "+kind+" "+("on" if profile["enabled"] else "off")+" "+str(profile["spacing_m"])+" "+profile["color"]
    if action=="delete_location":
        return "physical delete "+word("location")
    if action=="add_device":
        model=word("model")
        name=word("name")
        coords=num("x")+" "+num("y")
        loc=location("location")
        physical_x=data.get("physical_x")
        physical_y=data.get("physical_y")
        if (physical_x is None)!=(physical_y is None):
            raise LabError("physical_x and physical_y must be given together")
        extra=("" if physical_x is None else " "+num("physical_x")+" "+num("physical_y"))
        return "physical add-device "+model+" "+name+" "+coords+" "+loc+extra
    if action=="add_location":
        kind=data.get("kind")
        if kind not in {"city","building","closet","generic","icp"}:raise LabError("invalid container type")
        return "physical add "+kind+" "+word("name")+" "+location("parent")
    if action=="rename_location":
        return "physical rename "+word("location")+" "+word("name")
    if action=="move_location":
        return "physical position "+word("location")+" "+num("x")+" "+num("y")
    if action=="relocate_location":
        return "physical relocate "+word("location")+" "+location("parent")
    if action=="resize_location":
        return "physical dimensions "+word("location")+" "+num("width")+" "+num("length")+" "+num("height")
    if action=="place_device":
        return "physical place "+word("device")+" "+location("location")
    if action=="move_devices":
        members=data.get("devices")
        if not isinstance(members,list) or not 1<=len(members)<=200:
            raise LabError("devices must be a list of 1-200 names")
        if any(not isinstance(n,str) or not n or "," in n or
               any(ch.isspace() for ch in n) or len(n)>31 for n in members):
            raise LabError("invalid device name in move selection")
        if len(set(members))!=len(members):
            raise LabError("duplicate device in move selection")
        return "physical move-devices "+shlex.quote(",".join(members))+" "+location("location")
    if action=="position_device":
        return "physical device-position "+word("device")+" "+num("x")+" "+num("y")
    if action=="mount_device":
        surface=data.get("surface")
        if surface not in {"rack","table","floor","shelf"}:raise LabError("unknown mounting surface")
        tail=""
        if surface=="shelf":
            shelf=data.get("shelf")
            if isinstance(shelf,bool) or not isinstance(shelf,int) or shelf<0:raise LabError("shelf must be a nonnegative integer")
            tail=" "+str(shelf)
        return "physical mount "+word("device")+" "+surface+tail
    if action=="add_shelf":
        return "physical shelf-add "+word("closet")
    if action in {"undo","redo"}:return action
    raise LabError("unsupported physical workspace action")

def physical_schema()->dict:
    return {
        "version":2,"read":{"method":"GET","path":"/api/physical-workspace",
                            "query":{"location":"intercity | city0 | building0 | closet0 | loc0 ..."},
                            "navigation_tree":"GET /api/physical-workspace/tree"},
        "write":{"method":"POST","path":"/api/physical-workspace/action",
                 "actions":{
                    "set_grid":{"container_type":"city","enabled":True,"spacing_m":100,"color":"#5a7890"},
                    "delete_location":{"location":"closet0"},
                    "add_location":{"kind":"generic","name":"Storage","parent":"closet0"},
                    "add_device":{"model":"pc-pt","name":"PC1","x":220,"y":190,"location":"building0","physical_x":290,"physical_y":170},
                    "rename_location":{"location":"loc0","name":"Secure Storage"},
                    "move_location":{"location":"loc0","x":100,"y":80},
                    "relocate_location":{"location":"loc0","parent":"building0"},
                    "resize_location":{"location":"loc0","width":8,"length":7,"height":2},
                    "place_device":{"device":"R1","location":"closet0"},
                    "move_devices":{"devices":["R1","R2"],"location":"closet0"},
                    "position_device":{"device":"R1","x":110,"y":80},
                    "mount_device":{"device":"R1","surface":"rack"},
                    "mount_device_shelf":{"action":"mount_device","device":"R1","surface":"shelf","shelf":0},
                    "add_shelf":{"closet":"closet0"},
                    "undo":{},"redo":{},
                 }},
        "rules":[
            "All writes route through CommandProcessor and persist in the normal saved lab",
            "Generic containers allow nested containers when type and dimensions fit",
            "City cannot go inside Building or Closet; physical hierarchy cannot contain cycles",
            "Rack/table/shelf mount requires wiring closet",
            "Shelf storage requires a powered-off disconnected device; stored devices cannot be powered on or cabled",
            "Rack and table geometry is visual; no numbered rack units",
            "Grid profiles are saved per container type (intercity/city/building/generic); spacing is in meters using container dimension calibration",
            "GET view includes grid geometry, all grid_profiles and delete_preview (null for intercity)",
            "Deleting a container removes its whole subtree and extracts all devices onto the surviving parent floor, preserving configurations and cables",
            "Physical edits support Undo/Redo; deletion does not require an API confirmation flag",
        ],
    }

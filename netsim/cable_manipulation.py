"""legacy simulator physical cable manipulation: bends, shared group points, colors.

Route geometry is stored as world-meter points and travels with native lab JSON.
Each cable is still a single existing simulated Ethernet link. Routing bends
change its calculated path length, never its endpoint/port connectivity.
"""
from __future__ import annotations
import json,math,re,shlex,uuid
from .model import LabError
from .physical_distance import device_world_position,frame_scale,location_origin_m

COLOR=re.compile(r"^#[0-9a-fA-F]{6}$")
MAX_BENDS=64
MAX_ALL_BENDS=4000
MAX_METERS=10_000_000

def key(link)->str:
    endpoints=sorted(((link.a_device,link.a_if),(link.b_device,link.b_if)))
    return json.dumps(endpoints,separators=(",",":"),ensure_ascii=False)

def link_by_end(lab,device,interface):
    return lab.link_for(device,interface) or (_ for _ in ()).throw(LabError("no cable on that interface"))

def route_for(lab,link):
    return lab.cable_routes.get(key(link),{"color":"#24354b","bends":[]})

def finite_m(value,label):
    if isinstance(value,bool) or not isinstance(value,(float,int)) or not math.isfinite(value):
        raise LabError(label+" must be a finite number")
    value=float(value)
    if abs(value)>MAX_METERS:raise LabError(label+" exceeds supported physical world bounds")
    return round(value,6)

def _all_bends(lab):
    for route_key,route in lab.cable_routes.items():
        for bend in route["bends"]:yield route_key,bend

def _locate_bend(lab,link,bend_id):
    route=lab.cable_routes.get(key(link))
    if not route:raise LabError("cable has no routed bend points")
    for bend in route["bends"]:
        if bend["id"]==bend_id:return route,bend
    raise LabError("bend point does not exist on cable")

def _new_id(prefix):
    return prefix+uuid.uuid4().hex[:16]

def add_bend(lab,device,interface,x_m,y_m,after=None):
    link=link_by_end(lab,device,interface)
    x,y=finite_m(x_m,"x_m"),finite_m(y_m,"y_m")
    route=lab.cable_routes.setdefault(key(link),{"color":"#24354b","bends":[]})
    if len(route["bends"])>=MAX_BENDS or sum(1 for _ in _all_bends(lab))>=MAX_ALL_BENDS:
        raise LabError("maximum cable bend points reached")
    bends=route["bends"]
    if after is None:idx=len(bends)
    elif after=="start":idx=0
    else:
        idx=next((i+1 for i,b in enumerate(bends) if b["id"]==after),-1)
        if idx<0:raise LabError("after bend point not found on cable")
    bend={"id":_new_id("bend_"),"x_m":x,"y_m":y,"group":None}
    bends.insert(idx,bend)
    lab.events.append("cable bend created "+bend["id"])
    if lab.cable_length_effects:lab.recompute_ospf()
    return bend["id"]

def _set_coords(lab,bend,x,y):
    group=bend.get("group")
    if group is not None:
        for _,candidate in _all_bends(lab):
            if candidate["group"]==group:
                candidate["x_m"]=x;candidate["y_m"]=y
    else:
        bend["x_m"]=x;bend["y_m"]=y

def move_bend(lab,device,interface,bend_id,x_m,y_m):
    link=link_by_end(lab,device,interface)
    _,bend=_locate_bend(lab,link,bend_id)
    _set_coords(lab,bend,finite_m(x_m,"x_m"),finite_m(y_m,"y_m"))
    lab.events.append("cable bend moved "+bend_id)
    if lab.cable_length_effects:lab.recompute_ospf()

def group_bends(lab,first_device,first_interface,first_id,second_device,second_interface,second_id):
    first_link=link_by_end(lab,first_device,first_interface)
    second_link=link_by_end(lab,second_device,second_interface)
    if key(first_link)==key(second_link):raise LabError("group points require two different cables")
    _,first=_locate_bend(lab,first_link,first_id)
    _,second=_locate_bend(lab,second_link,second_id)
    g1,g2=first.get("group"),second.get("group")
    if g1 and g2 and g1!=g2:raise LabError("ungroup before merging two existing groups")
    if g1 and g2 and g1==g2:return g1
    ident=g1 or g2 or _new_id("group_")
    first["group"]=ident;second["group"]=ident
    _set_coords(lab,second,second["x_m"],second["y_m"])
    lab.events.append("cables grouped "+ident)
    if lab.cable_length_effects:lab.recompute_ospf()
    return ident

def group_members(lab,group):
    return [(route_key,bend) for route_key,bend in _all_bends(lab) if bend["group"]==group]

def move_group(lab,group,x_m,y_m):
    members=group_members(lab,group)
    if len(members)<2:raise LabError("group point does not exist")
    x,y=finite_m(x_m,"x_m"),finite_m(y_m,"y_m")
    for _,bend in members:bend.update(x_m=x,y_m=y)
    lab.events.append("cable group moved "+group)
    if lab.cable_length_effects:lab.recompute_ospf()

def ungroup(lab,group,device=None,interface=None):
    members=group_members(lab,group)
    if len(members)<2:raise LabError("group point does not exist")
    if device is not None:
        if not interface:raise LabError("device and interface required together")
        target=key(link_by_end(lab,device,interface))
        selected=[bend for route_key,bend in members if route_key==target]
        if not selected:raise LabError("cable is not in this group")
    else:selected=[bend for _,bend in members]
    for bend in selected:bend["group"]=None
    rest=group_members(lab,group)
    if len(rest)<2:
        for _,bend in rest:bend["group"]=None
    lab.events.append("cable group ungrouped "+group)
    return len(selected)

def _prune_groups(lab):
    groups={}
    for _,bend in _all_bends(lab):
        if bend.get("group"):
            groups.setdefault(bend["group"],[]).append(bend)
    for bends in groups.values():
        if len(bends)<2:
            for bend in bends:bend["group"]=None

def delete_bend(lab,device,interface,bend_id):
    link=link_by_end(lab,device,interface)
    route,bend=_locate_bend(lab,link,bend_id)
    route["bends"].remove(bend)
    _prune_groups(lab)
    if not route["bends"] and route["color"]=="#24354b":
        lab.cable_routes.pop(key(link),None)
    lab.events.append("cable bend removed "+bend_id)
    if lab.cable_length_effects:lab.recompute_ospf()

def set_color(lab,device,interface,color):
    link=link_by_end(lab,device,interface)
    if not isinstance(color,str) or not COLOR.fullmatch(color):
        raise LabError("cable color must be #RRGGBB")
    entry=lab.cable_routes.setdefault(key(link),{"color":"#24354b","bends":[]})
    entry["color"]=color.lower()
    if not entry["bends"] and entry["color"]=="#24354b":
        lab.cable_routes.pop(key(link),None)
    lab.events.append("cable colored "+key(link))

def prune_disconnected(lab):
    valid={key(link) for link in lab.links}
    lab.cable_routes={k:v for k,v in lab.cable_routes.items() if k in valid}
    _prune_groups(lab)

def rename_device(lab,old,new):
    modified={}
    for route_key,entry in lab.cable_routes.items():
        endpoints=json.loads(route_key)
        for endpoint in endpoints:
            if endpoint[0]==old:endpoint[0]=new
        updated=json.dumps(sorted(endpoints),separators=(",",":"),ensure_ascii=False)
        modified[updated]=entry
    lab.cable_routes=modified

def points(lab,link):
    a=device_world_position(lab,link.a_device)
    b=device_world_position(lab,link.b_device)
    route=route_for(lab,link)
    return [{"x_m":a["x_m"],"y_m":a["y_m"],"type":"device","device":link.a_device},
            *[dict(bend,type="bend") for bend in route["bends"]],
            {"x_m":b["x_m"],"y_m":b["y_m"],"type":"device","device":link.b_device}]

def segments(lab,link):
    path=points(lab,link)
    segments=[]
    color=route_for(lab,link)["color"]
    for a,b in zip(path,path[1:]):
        length=math.hypot(a["x_m"]-b["x_m"],a["y_m"]-b["y_m"])
        black=bool(a.get("group") and b.get("group"))
        segments.append({"length_m":round(length,4),
                         "type":"routed" if len(path)>2 else "straight_line",
                         "color":"#202020" if black else color,
                         "grouped":black})
    return segments

def total_length_m(lab,link):
    path=points(lab,link)
    return sum(math.hypot(a["x_m"]-b["x_m"],a["y_m"]-b["y_m"])
               for a,b in zip(path,path[1:]))

def view(lab,location="intercity"):
    if location!="intercity":lab._physical_location(location)
    scale=frame_scale(lab,location)
    ox,oy=location_origin_m(lab,location)
    entries=[]
    for link in lab.links:
        a_loc=lab.device_locations.get(link.a_device,"intercity")
        b_loc=lab.device_locations.get(link.b_device,"intercity")
        if a_loc!=location or b_loc!=location:continue
        from .physical_distance import cable_length
        route=route_for(lab,link)
        path=points(lab,link)
        projected=[]
        for p in path:
            projected.append({**p,
              "x":round((p["x_m"]-ox)/scale["meters_per_x"],5),
              "y":round((p["y_m"]-oy)/scale["meters_per_y"],5)})
        entries.append({
            "a_device":link.a_device,"a_if":link.a_if,
            "b_device":link.b_device,"b_if":link.b_if,
            "key":key(link),"color":route["color"],"points":projected,
            "segments":segments(lab,link),"length":cable_length(lab,link),
            "up":lab.link_operational(link),
            "reason":lab.link_status(link)["reason"]})
    return {"ok":True,"location":location,"geometry":scale,
            "world_origin_m":{"x_m":ox,"y_m":oy},
            "cables":entries,"total_cables":len(lab.links),
            "group_count":len({b["group"] for _,b in _all_bends(lab) if b.get("group")}),
            "constraints":{"max_bends_per_cable":MAX_BENDS,
               "coordinate_system":"absolute world metres; UI view projects to current location canvas"}}

def validate_load(lab,routes):
    if not isinstance(routes,dict):raise LabError("cable_routes must be an object")
    if len(routes)>len(lab.links):raise LabError("too many saved cable routes")
    valid={key(l) for l in lab.links}
    saved={};ids=set();groups={}
    for route_key,route in routes.items():
        if route_key not in valid or not isinstance(route,dict) or set(route)!={"color","bends"}:
            raise LabError("invalid saved cable route")
        color=route["color"]
        if not isinstance(color,str) or not COLOR.fullmatch(color):
            raise LabError("invalid saved cable color")
        bends=route["bends"]
        if not isinstance(bends,list) or len(bends)>MAX_BENDS:
            raise LabError("invalid saved bend list")
        recorded=[]
        for bend in bends:
            if not isinstance(bend,dict) or set(bend)!={"id","x_m","y_m","group"}:
                raise LabError("invalid saved bend")
            ident=bend["id"];group=bend["group"]
            if not isinstance(ident,str) or not re.fullmatch(r"bend_[0-9a-f]{16}",ident) or ident in ids:
                raise LabError("invalid or duplicate saved bend ID")
            ids.add(ident)
            x,y=finite_m(bend["x_m"],"x_m"),finite_m(bend["y_m"],"y_m")
            if group is not None:
                if not isinstance(group,str) or not re.fullmatch(r"group_[0-9a-f]{16}",group):
                    raise LabError("invalid saved group ID")
                groups.setdefault(group,[]).append((route_key,x,y))
            recorded.append({"id":ident,"x_m":x,"y_m":y,"group":group})
        saved[route_key]={"color":color.lower(),"bends":recorded}
    if len(ids)>MAX_ALL_BENDS:raise LabError("too many saved cable bends")
    for group,members in groups.items():
        if len(members)<2 or len({row[0] for row in members})<2 or len({(row[1],row[2]) for row in members})>1:
            raise LabError("invalid saved cable group members")
    lab.cable_routes=saved

def action_command(body:dict):
    if not isinstance(body,dict):raise LabError("expected object")
    action=body.get("action")
    if action in {"undo","redo"}:return action
    def word(field):
        value=body.get(field)
        if not isinstance(value,str) or not value or len(value)>99 or any(c.isspace() for c in value):
            raise LabError(field+" must be one non-empty token")
        return shlex.quote(value)
    def coord(field):return str(finite_m(body.get(field),field))
    if action=="add_bend":
        return "cable bend-add "+word("device")+" "+word("interface")+" "+coord("x_m")+" "+coord("y_m")+((" "+word("after")) if body.get("after") else "")
    if action=="move_bend":
        return "cable bend-move "+word("device")+" "+word("interface")+" "+word("bend")+" "+coord("x_m")+" "+coord("y_m")
    if action=="delete_bend":
        return "cable bend-delete "+word("device")+" "+word("interface")+" "+word("bend")
    if action=="set_color":
        color=body.get("color")
        if not isinstance(color,str) or not COLOR.fullmatch(color):raise LabError("color must be #RRGGBB")
        return "cable color "+word("device")+" "+word("interface")+" "+color
    if action=="group_bends":
        return "cable group "+word("device")+" "+word("interface")+" "+word("bend")+" "+word("other_device")+" "+word("other_interface")+" "+word("other_bend")
    if action=="move_group":
        return "cable group-move "+word("group")+" "+coord("x_m")+" "+coord("y_m")
    if action=="ungroup":
        return "cable ungroup "+word("group")+((" "+word("device")+" "+word("interface")) if body.get("device") is not None else "")
    raise LabError("unsupported cable action")

def schema():
    return {"version":1,"read":{"view":"GET /api/physical-cables?location=city0",
                                    "schema":"GET /api/physical-cables/schema",
                                    "all_lengths":"GET /api/physical-distance"},
            "write":{"method":"POST","path":"/api/physical-cables/action",
              "actions":{
                "add_bend":{"device":"R1","interface":"g0/0","x_m":123.0,"y_m":45.0,"after":None},
                "move_bend":{"device":"R1","interface":"g0/0","bend":"bend_<id>","x_m":124.0,"y_m":55.0},
                "delete_bend":{"device":"R1","interface":"g0/0","bend":"bend_<id>"},
                "set_color":{"device":"R1","interface":"g0/0","color":"#cc0000"},
                "group_bends":{"device":"R1","interface":"g0/0","bend":"bend_<id>",
                  "other_device":"R2","other_interface":"g0/1","other_bend":"bend_<id>"},
                "move_group":{"group":"group_<id>","x_m":124.0,"y_m":55.0},
                "ungroup":{"group":"group_<id>","device":"R1","interface":"g0/0"},
                "undo":{},"redo":{},
              }},
            "notes":[
              "Bend coordinates are world metres; use GET /api/physical-cables for calibrated projected UI coordinates.",
              "Bends and groups alter path length and optional 100m copper carrier state.",
              "Group points require bends on two distinct connected cables; drag a bend onto another to create.",
              "Grouping is colour black only between two shared GroupPoints; other cable segments preserve user colour.",
              "No cable is disconnected when bends or GroupPoints are removed.",
              "Routes persist in native lab JSON, supports Undo/Redo and agent API."
            ]}

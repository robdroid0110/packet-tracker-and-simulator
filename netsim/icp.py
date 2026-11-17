"""legacy network simulator Industrial Control Panel (ICP) — section 20.

Physical model only. DIN rails and wire conduits are layout fixtures,
not networking devices or electrical simulation. All actions use the
shared lab command history and saved JSON state.
"""
from __future__ import annotations
import math, re, shlex
from .model import LabError

# Packet Tracker and Simulator visual presets, NOT vendor-certified cabinet dimensions.
PRESETS={"small":(1.2,0.6,1.8),"medium":(1.8,0.8,2.0),"large":(2.4,1.0,2.2)}
GRID=20
ANCHOR_OFFSETS=((0,0),(10,0),(-10,0),(0,10),(0,-10),(10,10))
FIXTURE_KINDS={"din","wic"}
VALID_SIDES={"door","cabinet"}
MAX_FIXTURES=100

def default_panel(size="small"):
    return {"size":size,"door_closed":False,"workspace_mode":False,
            "fixtures":{},"mounts":{},"anchors":{}}

def _panel(lab,location):
    loc=lab._physical_location(location)
    if loc["type"]!="icp":raise LabError("location is not an Industrial Control Panel")
    return lab.icp_panels[location]

def _number(value,label):
    if isinstance(value,bool) or not isinstance(value,(float,int)) or not math.isfinite(value):
        raise LabError(label+" must be a finite number")
    if not 0<=value<=1000:raise LabError(label+" must be within 0..1000 ICP coordinates")
    return float(value)

def _coord(x,y,anchor=0):
    if not isinstance(anchor,int) or isinstance(anchor,bool) or not 0<=anchor<6:
        raise LabError("snap anchor must be an integer from 0 to 5")
    x,y=_number(x,"x"),_number(y,"y")
    ox,oy=ANCHOR_OFFSETS[anchor]
    return (round(max(0,min(1000,round((x+ox)/GRID)*GRID-ox)),4),
            round(max(0,min(1000,round((y+oy)/GRID)*GRID-oy)),4))

def _editable(panel):
    if panel["workspace_mode"]:raise LabError("ICP workspace preview is read-only; exit preview first")

def create(lab,name,parent,size):
    if size not in PRESETS:raise LabError("ICP size must be small, medium or large")
    destination=None if parent in (None,"intercity") else lab._physical_location(parent)
    lab._location_fits("icp",PRESETS[size],destination)
    ident=lab.add_physical_location("icp",name,parent)
    lab.physical_locations[ident].update(zip(("width","length","height"),PRESETS[size]))
    lab.icp_panels[ident]=default_panel(size)
    lab.events.append("ICP "+ident+" created with "+size+" preset")
    return ident

def set_door(lab,location,closed):
    panel=_panel(lab,location)
    if not isinstance(closed,bool):raise LabError("closed must be boolean")
    if not closed:panel["workspace_mode"]=False
    panel["door_closed"]=closed
    lab.events.append("ICP "+location+" door "+("closed" if closed else "open"))

def preview(lab,location,enabled):
    panel=_panel(lab,location)
    if not isinstance(enabled,bool):raise LabError("enabled must be boolean")
    panel["workspace_mode"]=enabled
    if enabled:panel["door_closed"]=True
    lab.events.append("ICP "+location+" workspace preview "+("on" if enabled else "off"))

def _fixture(panel,ident):
    if ident not in panel["fixtures"]:raise LabError("unknown ICP fixture")
    return panel["fixtures"][ident]

def _member_ids(panel,fixture_id):
    fixture=_fixture(panel,fixture_id)
    group=fixture["group"]
    return [k for k,v in panel["fixtures"].items()
            if k==fixture_id or group is not None and v["group"]==group]

def _move_fixture_members(lab,location,panel,members,dx,dy):
    # Prevalidate the entire rigid assembly before modifying any coordinates.
    for ident in members:
        item=panel["fixtures"][ident]
        _number(item["x"]+dx,"fixture x")
        _number(item["y"]+dy,"fixture y")
    affected=[name for name,fid in panel["mounts"].items() if fid in members]
    for name in affected:
        detail=lab.physical_device_details[name]
        _number(detail["x"]+dx,"mounted device x")
        _number(detail["y"]+dy,"mounted device y")
    for ident in members:
        item=panel["fixtures"][ident]
        item["x"]=round(item["x"]+dx,4);item["y"]=round(item["y"]+dy,4)
    for name in affected:
        detail=lab.physical_device_details[name]
        detail["x"]=round(detail["x"]+dx,4);detail["y"]=round(detail["y"]+dy,4)
    if lab.cable_length_effects and affected:lab.recompute_ospf()

def move_device(lab,device,side,x,y,anchor=0,detach=False):
    lab._device(device)
    location=lab.device_locations.get(device)
    panel=_panel(lab,location)
    _editable(panel)
    if side not in VALID_SIDES:raise LabError("ICP device side must be door or cabinet")
    if not isinstance(detach,bool):raise LabError("detach must be boolean")
    x,y=_coord(x,y,anchor)
    detail=lab.physical_device_details[device]
    attached=panel["mounts"].get(device)
    if attached and not detach and side=="cabinet":
        members=_member_ids(panel,attached)
        _move_fixture_members(lab,location,panel,members,x-detail["x"],y-detail["y"])
    else:
        if attached:panel["mounts"].pop(device)
        detail.update(x=x,y=y,surface=side,shelf=None)
        if lab.cable_length_effects:lab.recompute_ospf()
    panel["anchors"][device]=anchor
    lab.events.append("ICP "+location+" moved "+device+" on "+side)

def add_fixture(lab,location,kind,orientation,x,y):
    panel=_panel(lab,location);_editable(panel)
    if kind not in FIXTURE_KINDS:raise LabError("ICP fixture must be din or wic")
    if orientation not in ({"horizontal"} if kind=="din" else {"horizontal","vertical"}):
        raise LabError("DIN must be horizontal; WIC can be horizontal or vertical")
    if len(panel["fixtures"])>=MAX_FIXTURES:raise LabError("ICP fixture limit of 100 reached")
    x,y=_coord(x,y)
    number=0
    while "fixture"+str(number) in panel["fixtures"]:number+=1
    ident="fixture"+str(number)
    panel["fixtures"][ident]={"id":ident,"kind":kind,"orientation":orientation,
                              "x":x,"y":y,"group":None}
    lab.events.append("ICP "+location+" created "+kind+" "+ident)
    return ident

def move_fixture(lab,location,ident,x,y,detach=False):
    panel=_panel(lab,location);_editable(panel)
    if not isinstance(detach,bool):raise LabError("detach must be boolean")
    obj=_fixture(panel,ident)
    x,y=_coord(x,y)
    members=[ident] if detach else _member_ids(panel,ident)
    _move_fixture_members(lab,location,panel,members,x-obj["x"],y-obj["y"])
    if detach:split_fixture(lab,location,ident)
    lab.events.append("ICP "+location+" moved "+ident)

def join_fixtures(lab,location,a,b):
    panel=_panel(lab,location);_editable(panel)
    if a==b:raise LabError("cannot join a fixture to itself")
    first,second=_fixture(panel,a),_fixture(panel,b)
    if first["kind"]!=second["kind"] or first["orientation"]!=second["orientation"]:
        raise LabError("fixtures must have the same kind and orientation")
    left,right=first["group"],second["group"]
    if left and right and left==right:return left
    if left and right and left!=right:raise LabError("split one strip before joining two existing strips")
    idx=0
    groups={v["group"] for v in panel["fixtures"].values()}
    while "strip"+str(idx) in groups:idx+=1
    ident=left or right or "strip"+str(idx)
    for fid in {a,b}:
        panel["fixtures"][fid]["group"]=ident
    lab.events.append("ICP "+location+" joined fixtures "+a+" and "+b)
    return ident

def split_fixture(lab,location,ident):
    panel=_panel(lab,location);_editable(panel)
    fixture=_fixture(panel,ident)
    group=fixture["group"]
    if group is None:return
    fixture["group"]=None
    remaining=[x for x in panel["fixtures"].values() if x["group"]==group]
    if len(remaining)<2:
        for member in remaining:member["group"]=None
    lab.events.append("ICP "+location+" split "+ident+" from "+group)

def delete_fixture(lab,location,ident):
    panel=_panel(lab,location);_editable(panel)
    _fixture(panel,ident)
    for device,mount in list(panel["mounts"].items()):
        if mount==ident:del panel["mounts"][device]
    split_fixture(lab,location,ident)
    del panel["fixtures"][ident]
    lab.events.append("ICP "+location+" deleted "+ident)

def mount(lab,device,fixture_id):
    lab._device(device)
    location=lab.device_locations[device]
    panel=_panel(lab,location);_editable(panel)
    fixture=_fixture(panel,fixture_id)
    if fixture["kind"]!="din":raise LabError("devices can mount only on DIN rails")
    detail=lab.physical_device_details[device]
    if detail["surface"]!="cabinet":raise LabError("move device to cabinet before DIN mounting")
    # A nearby mounting target; explicit snap to the DIN rail centerline.
    attached=sum(1 for n,f in panel["mounts"].items() if f==fixture_id and n!=device)
    x,y=_coord(fixture["x"]+20*attached,fixture["y"])
    changed=(x!=detail["x"] or y!=detail["y"])
    panel["mounts"][device]=fixture_id
    detail.update(x=x,y=y)
    if changed and lab.cable_length_effects:lab.recompute_ospf()
    lab.events.append("ICP "+location+" DIN mounted "+device+" on "+fixture_id)

def unmount(lab,device):
    lab._device(device)
    location=lab.device_locations.get(device)
    panel=_panel(lab,location);_editable(panel)
    if device not in panel["mounts"]:raise LabError("device is not DIN mounted")
    del panel["mounts"][device]
    lab.events.append("ICP "+location+" unmounted "+device)

def forget_device(lab,device):
    for panel in lab.icp_panels.values():
        panel["mounts"].pop(device,None)
        panel["anchors"].pop(device,None)

def rename_device(lab,old,new):
    for panel in lab.icp_panels.values():
        for field in ("mounts","anchors"):
            if old in panel[field]:panel[field][new]=panel[field].pop(old)

def panel_view(lab,location):
    panel=_panel(lab,location)
    devices=[{"device":name,"model":lab.devices[name].model,
              "powered":lab.devices[name].powered,
              "side":lab.physical_device_details[name]["surface"],
              "x":lab.physical_device_details[name]["x"],
              "y":lab.physical_device_details[name]["y"],
              "anchor":panel["anchors"].get(name,0),
              "mount":panel["mounts"].get(name)}
             for name in lab.devices if lab.device_locations.get(name)==location]
    return {"ok":True,"location":location,
            "location_meta":dict(lab.physical_locations[location]),
            "panel":{"size":panel["size"],"door_closed":panel["door_closed"],
                     "workspace_mode":panel["workspace_mode"]},
            "fixtures":[dict(v) for v in panel["fixtures"].values()],
            "devices":devices,
            "grid_step":GRID,"snap_anchor_count":6,
            "limits":{"fixtures":MAX_FIXTURES},
            "notes":["DIN and WIC items are visual only; wires are ordinary network links.",
                     "Workspace mode is a closed-door read-only preview."]}

def validate_load(lab,data):
    if not isinstance(data,dict):raise LabError("invalid saved ICP panels")
    locations={name for name,l in lab.physical_locations.items() if l["type"]=="icp"}
    if set(data)-locations:raise LabError("saved ICP references a non-ICP location")
    panels={}
    for loc in locations:
        raw=data.get(loc,default_panel())
        if not isinstance(raw,dict) or set(raw)!={"size","door_closed","workspace_mode","fixtures","mounts","anchors"}:
            raise LabError("invalid saved ICP panel shape")
        size=raw["size"]
        if size not in PRESETS:raise LabError("invalid saved ICP preset")
        if any(not isinstance(raw[k],bool) for k in ("door_closed","workspace_mode")):
            raise LabError("invalid saved ICP door state")
        if raw["workspace_mode"] and not raw["door_closed"]:raise LabError("preview must have closed door")
        fixtures=raw["fixtures"];mounts=raw["mounts"];anchors=raw["anchors"]
        if not isinstance(fixtures,dict) or len(fixtures)>MAX_FIXTURES or not isinstance(mounts,dict) or not isinstance(anchors,dict):
            raise LabError("invalid saved ICP fixtures")
        groups={}
        stored={}
        for ident,f in fixtures.items():
            if not re.fullmatch(r"fixture[0-9]+",ident) or not isinstance(f,dict) or set(f)!={"id","kind","orientation","x","y","group"} or f["id"]!=ident:
                raise LabError("invalid saved ICP fixture")
            kind,orientation=f["kind"],f["orientation"]
            if kind not in FIXTURE_KINDS or orientation not in ({"horizontal"} if kind=="din" else {"horizontal","vertical"}):
                raise LabError("invalid saved ICP fixture orientation")
            x,y=_number(f["x"],"x"),_number(f["y"],"y")
            group=f["group"]
            if group is not None:
                if not isinstance(group,str) or not re.fullmatch(r"strip[0-9]+",group):raise LabError("invalid saved strip ID")
                groups.setdefault(group,[]).append((kind,orientation))
            stored[ident]=dict(f,x=x,y=y)
        for g,members in groups.items():
            if len(members)<2 or len(set(members))!=1:raise LabError("inconsistent saved ICP fixture strip")
        for device,fixture_id in mounts.items():
            if device not in lab.devices or lab.device_locations.get(device)!=loc or fixture_id not in stored or stored[fixture_id]["kind"]!="din":
                raise LabError("invalid DIN mount reference")
            if lab.physical_device_details[device]["surface"]!="cabinet":raise LabError("DIN mounts require cabinet placement")
        for device,anchor in anchors.items():
            if device not in lab.devices or lab.device_locations.get(device)!=loc or isinstance(anchor,bool) or not isinstance(anchor,int) or not 0<=anchor<6:
                raise LabError("invalid ICP snap anchor")
        for device in lab.devices:
            if lab.device_locations.get(device)==loc and lab.physical_device_details[device]["surface"] not in VALID_SIDES:
                raise LabError("ICP device must be placed on door or cabinet")
        panels[loc]={"size":size,"door_closed":raw["door_closed"],
                     "workspace_mode":raw["workspace_mode"],
                     "fixtures":stored,"mounts":dict(mounts),"anchors":dict(anchors)}
    lab.icp_panels=panels

def action_command(body):
    if not isinstance(body,dict):raise LabError("ICP action expects a JSON object")
    action=body.get("action")
    if action in {"undo","redo"}:return action
    def word(name):
        v=body.get(name)
        if not isinstance(v,str) or not v or len(v)>90 or any(ch.isspace() for ch in v):
            raise LabError(name+" must be a short single token")
        return shlex.quote(v)
    def num(name):return str(_number(body.get(name),name))
    def yes(name):
        v=body.get(name)
        if not isinstance(v,bool):raise LabError(name+" must be boolean")
        return "on" if v else "off"
    if action=="create":
        size=body.get("size")
        if size not in PRESETS:raise LabError("ICP size must be small, medium or large")
        name=body.get("name")
        if not isinstance(name,str) or not name.strip() or len(name)>80 or any(ord(ch)<32 for ch in name):
            raise LabError("invalid ICP name")
        parent=body.get("parent") or "intercity"
        if not isinstance(parent,str) or not parent or len(parent)>80 or any(ch.isspace() for ch in parent):
            raise LabError("invalid ICP parent")
        return "icp create "+shlex.quote(size)+" "+shlex.quote(name)+" "+shlex.quote(parent)
    if action=="door":return "icp door "+word("location")+" "+yes("closed")
    if action=="preview":return "icp preview "+word("location")+" "+yes("enabled")
    if action=="device_move":
        side=body.get("side");anchor=body.get("anchor",0)
        if side not in VALID_SIDES:raise LabError("side must be door or cabinet")
        if isinstance(anchor,bool) or not isinstance(anchor,int) or not 0<=anchor<6:raise LabError("anchor must be 0..5")
        detach=body.get("detach",False)
        if not isinstance(detach,bool):raise LabError("detach must be boolean")
        return "icp device-move "+word("device")+" "+side+" "+num("x")+" "+num("y")+" "+str(anchor)+" "+("detach" if detach else "attached")
    if action=="fixture_add":
        kind=body.get("kind");orient=body.get("orientation")
        if kind not in FIXTURE_KINDS or orient not in {"horizontal","vertical"}:raise LabError("invalid fixture")
        return "icp fixture-add "+word("location")+" "+kind+" "+orient+" "+num("x")+" "+num("y")
    if action=="fixture_move":
        detach=body.get("detach",False)
        if not isinstance(detach,bool):raise LabError("detach must be boolean")
        return "icp fixture-move "+word("location")+" "+word("fixture")+" "+num("x")+" "+num("y")+" "+("detach" if detach else "attached")
    if action=="fixture_join":
        return "icp fixture-join "+word("location")+" "+word("fixture")+" "+word("other")
    if action=="fixture_split":
        return "icp fixture-split "+word("location")+" "+word("fixture")
    if action=="fixture_delete":
        return "icp fixture-delete "+word("location")+" "+word("fixture")
    if action=="mount":return "icp mount "+word("device")+" "+word("fixture")
    if action=="unmount":return "icp unmount "+word("device")
    raise LabError("unsupported ICP action")

def schema():
    return {"version":1,
      "read":{"panel":"GET /api/icp?location=loc0","schema":"GET /api/icp/schema"},
      "write":{"method":"POST","path":"/api/icp/action","actions":{
        "create":{"size":"small|medium|large","name":"Control Panel","parent":"building0"},
        "door":{"location":"loc0","closed":True},
        "preview":{"location":"loc0","enabled":True},
        "device_move":{"device":"R1","side":"door|cabinet","x":200,"y":160,"anchor":0,"detach":False},
        "fixture_add":{"location":"loc0","kind":"din|wic","orientation":"horizontal|vertical","x":200,"y":160},
        "fixture_move":{"location":"loc0","fixture":"fixture0","x":220,"y":180,"detach":False},
        "fixture_join":{"location":"loc0","fixture":"fixture0","other":"fixture1"},
        "fixture_split":{"location":"loc0","fixture":"fixture0"},
        "fixture_delete":{"location":"loc0","fixture":"fixture0"},
        "mount":{"device":"R1","fixture":"fixture0"},
        "unmount":{"device":"R1"},
        "undo":{},"redo":{}
      }},
      "presets":{k:{"width_m":v[0],"length_m":v[1],"height_m":v[2]} for k,v in PRESETS.items()},
      "rules":["Grid step 20, anchor positions 0-5; UI Tab cycles anchors during drag.",
               "Device side changes via Shift-drag; Ctrl-drag detaches mounted device or fixture.",
               "DIN rail horizontal only; WIC horizontal/vertical. WIC is decorative, not electrical.",
               "All ICP layouts persist in native JSON and share shell/agent undo history.",
               "The physical container dimensions are Packet Tracker and Simulator presets, not vendor vendor-certified measurements.",
               "Equipment on an ICP door is visible from the back when the door is open.",
               "Workspace preview is a read-only closed-door display; no simulation of industrial PLC protocols."]}

"""Portable PNG/JPEG visual assets for Packet Tracker and Simulator labs.

Images live INSIDE lab JSON so import/export works across OS/browser sessions.
Strict-size binary validation and content-addressed IDs prevent path traversal,
remote URLs, SVG script content, and arbitrarily large base64 submissions.
"""
from __future__ import annotations
import base64,binascii,hashlib,re,shlex,struct,zlib

from .model import LabError

MAX_ASSET_BYTES=1_000_000
MAX_TOTAL_BYTES=8_000_000
MAX_ASSETS=40
MAX_SIDE=8192
MAX_PIXELS=16_000_000
SHA_RE=re.compile(r"^[0-9a-f]{64}$")
HEX_COLOR=re.compile(r"^#[0-9a-fA-F]{6}$")

def _jpeg_dimensions(data:bytes)->tuple[int,int]:
    if not data.startswith(b"\xff\xd8"):raise LabError("invalid JPEG header")
    pos=2
    while pos+4<len(data):
        if data[pos]!=0xff:raise LabError("invalid JPEG marker")
        while pos<len(data) and data[pos]==0xff:pos+=1
        if pos>=len(data):break
        marker=data[pos];pos+=1
        if marker==0xd9:break
        if marker in {0x01,*range(0xd0,0xd9)}:continue
        if pos+2>len(data):break
        n=int.from_bytes(data[pos:pos+2],"big")
        if n<2 or pos+n>len(data):raise LabError("invalid JPEG segment")
        if marker in {0xc0,0xc1,0xc2,0xc3,0xc5,0xc6,0xc7,0xc9,0xca,0xcb,0xcd,0xce,0xcf}:
            if n<7:raise LabError("invalid JPEG dimensions")
            height=int.from_bytes(data[pos+3:pos+5],"big")
            width=int.from_bytes(data[pos+5:pos+7],"big")
            return width,height
        pos+=n
    raise LabError("JPEG image dimensions missing")

def _gif_dimensions(data):
    if len(data)<14 or data[:6] not in (b'GIF87a',b'GIF89a'):raise LabError('invalid GIF header')
    width,height=struct.unpack('<HH',data[6:10]);packed=data[10]
    pos=13+(3*(2**((packed&7)+1)) if packed&128 else 0)
    frames=0;pixels=0
    def blocks(pos):
        while pos<len(data):
            length=data[pos];pos+=1
            if not length:return pos
            pos+=length
            if pos>len(data):raise LabError('truncated GIF block')
        raise LabError('unterminated GIF blocks')
    while pos<len(data):
        marker=data[pos];pos+=1
        if marker==59:
            if pos!=len(data) or not frames:raise LabError('invalid GIF trailer')
            return width,height
        if marker==33:
            if pos>=len(data):raise LabError('truncated GIF extension')
            pos=blocks(pos+1)
        elif marker==44:
            if pos+9>len(data):raise LabError('truncated GIF frame')
            left,top,w,h=struct.unpack('<HHHH',data[pos:pos+8]);flags=data[pos+8];pos+=9
            if not w or not h or left+w>width or top+h>height:raise LabError('invalid GIF frame bounds')
            if flags&128:pos+=3*(2**((flags&7)+1))
            if pos>=len(data) or not 2<=data[pos]<=8:raise LabError('invalid GIF code size')
            pos=blocks(pos+1);frames+=1;pixels+=w*h
            if pixels>MAX_PIXELS:raise LabError('GIF decoded frame budget exceeds pixel limit')
            if frames>1000:raise LabError('GIF exceeds 1000 frames')
        else:raise LabError('invalid GIF block')
    raise LabError('GIF trailer missing')

def image_info(mime:str,b64:str)->tuple[bytes,int,int,str]:
    if mime not in {"image/png","image/jpeg","image/gif"}:
        raise LabError("custom images must be PNG, JPEG or GIF")
    if not isinstance(b64,str) or not b64 or len(b64)>1_340_000:
        raise LabError("image base64 payload missing or exceeds 1MB limit")
    try:data=base64.b64decode(b64,validate=True)
    except (binascii.Error,ValueError) as exc:raise LabError("invalid base64 image") from exc
    if not 0<len(data)<=MAX_ASSET_BYTES:raise LabError("image must be at most 1MB")
    if mime=="image/png":
        if len(data)<33 or not data.startswith(b"\x89PNG\r\n\x1a\n") or data[12:16]!=b"IHDR" or data[8:12]!=b"\x00\x00\x00\r":
            raise LabError("invalid PNG header")
        width,height=struct.unpack(">II",data[16:24])
        # Validate PNG chunk boundaries/checksums; reject truncated or polyglot files.
        pos=8;ends=0;has_data=False
        while pos<len(data):
            if pos+12>len(data):raise LabError("truncated PNG chunk")
            length=int.from_bytes(data[pos:pos+4],"big")
            kind=data[pos+4:pos+8]
            end=pos+12+length
            if end>len(data):raise LabError("truncated PNG content")
            actual=int.from_bytes(data[pos+8+length:end],"big")
            expected=zlib.crc32(kind+data[pos+8:pos+8+length])&0xffffffff
            if actual!=expected:raise LabError("invalid PNG checksum")
            if pos==8 and (kind!=b"IHDR" or length!=13):
                raise LabError("invalid PNG IHDR")
            if kind==b"IDAT":has_data=True
            if kind==b"IEND":
                ends+=1
                if length!=0 or end!=len(data):raise LabError("invalid PNG ending")
            pos=end
        if not has_data or ends!=1:raise LabError("incomplete PNG file")
    elif mime=="image/gif":width,height=_gif_dimensions(data)
    else:
        if not data.endswith(bytes((0xff,0xd9))):
            raise LabError("JPEG end marker missing")
        width,height=_jpeg_dimensions(data)
    if not (1<=width<=MAX_SIDE and 1<=height<=MAX_SIDE and width*height<=MAX_PIXELS):
        raise LabError("image dimensions exceed safe limits")
    return data,width,height,hashlib.sha256(data).hexdigest()

def public_assets(lab)->dict:
    return {
        "ok":True,
        "assets":[{key:value[key] for key in ("id","mime","bytes","width","height","label")}
                  for value in lab.visual_assets.values()],
        "cluster_icons":dict(lab.cluster_icons),
        "device_icons":{name:dict(m) for name,m in lab.device_icons.items()},
        "location_backgrounds":{name:dict(m) for name,m in lab.location_backgrounds.items()},
        "limits":{"asset_bytes":MAX_ASSET_BYTES,"total_bytes":MAX_TOTAL_BYTES,
                  "max_assets":MAX_ASSETS,"file_types":["image/png","image/jpeg","image/gif"]},
        "storage":"embedded in native lab JSON; images served by content hash",
    }

def check_asset_id(lab,asset_id:str|None):
    if asset_id is None:return
    if not isinstance(asset_id,str) or not SHA_RE.fullmatch(asset_id) or asset_id not in lab.visual_assets:
        raise LabError("unknown or invalid visual asset ID")

def add_asset(lab,mime:str,data_base64:str,label:str="")->str:
    if not isinstance(label,str) or len(label)>80 or any(ord(c)<32 for c in label):
        raise LabError("image label must contain at most 80 printable characters")
    raw,width,height,digest=image_info(mime,data_base64)
    if digest in lab.visual_assets:return digest
    if len(lab.visual_assets)>=MAX_ASSETS:raise LabError("image library reached 40 assets")
    if sum(v["bytes"] for v in lab.visual_assets.values())+len(raw)>MAX_TOTAL_BYTES:
        raise LabError("embedded image library exceeds 8MB limit")
    lab.visual_assets[digest]={
        "id":digest,"mime":mime,"bytes":len(raw),
        "width":width,"height":height,"label":label,
        "data_base64":base64.b64encode(raw).decode("ascii"),
    }
    lab.events.append(f"added visual asset {digest[:12]}")
    return digest

def set_icon(lab,device:str,view:str,asset_id:str|None)->None:
    lab._device(device)
    if view not in {"logical","physical"}:raise LabError("icon view must be logical or physical")
    check_asset_id(lab,asset_id)
    entry=dict(lab.device_icons.get(device,{}))
    if asset_id is None:entry.pop(view,None)
    else:entry[view]=asset_id
    if entry:lab.device_icons[device]=entry
    else:lab.device_icons.pop(device,None)
    lab.events.append(f"icon {device}:{view} {'reset' if asset_id is None else 'customized'}")

def set_cluster_icon(lab,cluster,asset_id):
    if cluster not in lab.clusters:raise LabError("unknown cluster")
    check_asset_id(lab,asset_id)
    if asset_id is None:lab.cluster_icons.pop(cluster,None)
    else:lab.cluster_icons[cluster]=asset_id

def set_background(lab,location:str,asset_id:str|None,tiled:bool=False,color:str="#e7e7e7")->None:
    if location.startswith("logical:"):
        target=location.removeprefix("logical:")
        if target!="root" and target not in lab.clusters:raise LabError("unknown logical background target")
    elif location!="intercity":lab._physical_location(location)
    check_asset_id(lab,asset_id)
    if not isinstance(tiled,bool):raise LabError("tiled must be true or false")
    if not isinstance(color,str) or not HEX_COLOR.fullmatch(color):
        raise LabError("background color must be #RRGGBB")
    if asset_id is None and not tiled and color.lower()=="#e7e7e7":
        lab.location_backgrounds.pop(location,None)
    else:
        lab.location_backgrounds[location]={
            "asset_id":asset_id,"tiled":tiled,"color":color.lower()}
    lab.events.append(f"background {location} {'reset' if asset_id is None else 'customized'}")

def discard_asset(lab,asset_id:str)->None:
    if asset_id is None:raise LabError("asset ID required")
    check_asset_id(lab,asset_id)
    if asset_id in lab.cluster_icons.values():raise LabError("asset is in use as a cluster icon")
    for entry in lab.device_icons.values():
        if asset_id in entry.values():raise LabError("asset is in use as a device icon")
    for entry in lab.location_backgrounds.values():
        if entry["asset_id"]==asset_id:raise LabError("asset is in use as a background")
    del lab.visual_assets[asset_id]
    lab.events.append("deleted unused visual asset "+asset_id[:12])

def load_visuals(lab,raw:dict)->None:
    if not isinstance(raw,dict):raise LabError("invalid saved image library")
    assets={}
    for ident,entry in raw.items():
        if not isinstance(ident,str) or not SHA_RE.fullmatch(ident) or not isinstance(entry,dict):
            raise LabError("invalid saved visual asset")
        data,width,height,digest=image_info(entry.get("mime"),entry.get("data_base64"))
        if digest!=ident or entry.get("id")!=ident:
            raise LabError("saved visual asset hash mismatch")
        if entry.get("bytes")!=len(data) or entry.get("width")!=width or entry.get("height")!=height:
            raise LabError("saved visual asset metadata mismatch")
        label=entry.get("label","")
        if not isinstance(label,str) or len(label)>80 or any(ord(c)<32 for c in label):
            raise LabError("saved visual asset label invalid")
        assets[ident]={"id":ident,"mime":entry["mime"],
                       "bytes":len(data),"width":width,"height":height,
                       "label":label,"data_base64":base64.b64encode(data).decode("ascii")}
    if len(assets)>MAX_ASSETS or sum(x["bytes"] for x in assets.values())>MAX_TOTAL_BYTES:
        raise LabError("saved visual library exceeds limits")
    lab.visual_assets=assets

def load_assignments(lab,icons:dict,backgrounds:dict)->None:
    if not isinstance(icons,dict) or not isinstance(backgrounds,dict):
        raise LabError("invalid saved visual assignments")
    lab.device_icons={}
    for name,views in icons.items():
        if name not in lab.devices or not isinstance(views,dict):
            raise LabError("saved icon references unknown device")
        if set(views)-{"logical","physical"}:
            raise LabError("unknown icon view")
        for view,ident in views.items():set_icon(lab,name,view,ident)
    lab.location_backgrounds={}
    for location,entry in backgrounds.items():
        if not isinstance(entry,dict) or set(entry)-{"asset_id","tiled","color"}:
            raise LabError("invalid saved background")
        set_background(lab,location,entry.get("asset_id"),entry.get("tiled",False),
                       entry.get("color","#e7e7e7"))

def command_from_action(payload:dict)->str:
    if not isinstance(payload,dict):raise LabError("expected JSON object")
    action=payload.get("action")
    def text(key):
        item=payload.get(key)
        if not isinstance(item,str) or not item.strip() or len(item)>90 or any(ord(c)<32 for c in item):
            raise LabError(key+" must be a non-empty string")
        return shlex.quote(item)
    def asset():
        value=payload.get("asset_id")
        if value is None:return "default"
        if not isinstance(value,str) or not SHA_RE.fullmatch(value):
            raise LabError("asset_id must be a full sha256 hex ID or null")
        return value
    if action=="upload_image":
        mime=payload.get("mime")
        encoded=payload.get("data_base64")
        label=payload.get("label","")
        if not isinstance(label,str) or len(label)>80:raise LabError("invalid image label")
        # Validate BEFORE command or server state changes.
        image_info(mime,encoded)
        return "visual upload "+shlex.quote(mime)+" "+encoded+" "+shlex.quote(label or "unnamed")
    if action=="set_cluster_icon":
        return "visual cluster-icon "+text("cluster")+" "+asset()
    if action=="set_device_icon":
        view=payload.get("view")
        if view not in {"logical","physical"}:raise LabError("invalid icon view")
        return "visual icon "+text("device")+" "+view+" "+asset()
    if action=="set_background":
        location=text("location")
        tiled=payload.get("tiled",False)
        color=payload.get("color","#e7e7e7")
        if not isinstance(tiled,bool):raise LabError("tiled must be boolean")
        if not isinstance(color,str) or not HEX_COLOR.fullmatch(color):
            raise LabError("invalid background color")
        return "visual background "+location+" "+asset()+" "+("tile" if tiled else "fit")+" "+color
    if action=="delete_image":
        return "visual delete "+asset()
    if action in {"undo","redo"}:return action
    raise LabError("unsupported visual customization action")

def schema()->dict:
    return {"version":1,
      "read":{"metadata":"GET /api/visuals",
              "image_bytes":"GET /api/visuals/assets/{full_sha256_hex}",
              "schema":"GET /api/visuals/schema",
              "physical_scale":"GET /api/physical-distance?location=city0"},
      "write":{"method":"POST","path":"/api/visuals/action",
               "actions":{
                   "upload_image":{"mime":"image/png","data_base64":"BASE64_BYTES","label":"office.png"},
                   "set_cluster_icon":{"cluster":"Cluster0","asset_id":None},
                   "set_device_icon":{"device":"R1","view":"physical","asset_id":None},
                   "set_background":{"location":"city0","asset_id":None,
                                     "tiled":False,"color":"#e7e7e7"},
                   "delete_image":{"asset_id":"FULL_SHA256"},
                   "undo":{},"redo":{},
               }},
      "limits":{"max_image_bytes":MAX_ASSET_BYTES,"max_total_bytes":MAX_TOTAL_BYTES,
                "max_assets":MAX_ASSETS,"mime":["image/png","image/jpeg","image/gif"],
                "width_px":MAX_SIDE,"height_px":MAX_SIDE,"total_pixels":MAX_PIXELS},
      "notes":["Icons can be independent for Logical and Physical device views.",
               "Background is per physical location (including intercity) and supports tile/fit.",
               "All original images are stored as base64 inside the exported JSON lab.",
               "Reference recommends 45x31 icons; recommended backgrounds: intercity 2226x1382, city 1685x1043, office 3444x2157, generic 200x200.",
               "Physical scale is read-only in the background dialog and comes from the project's Section 17 metric calibration, not exactly the vendor's per-pixel default."]}

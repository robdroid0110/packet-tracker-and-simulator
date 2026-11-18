from __future__ import annotations

from dataclasses import dataclass, field, asdict
from copy import deepcopy
from contextlib import contextmanager
from contextvars import ContextVar
from functools import wraps
from ipaddress import IPv4Address, IPv4Interface, IPv4Network
from urllib.parse import urlsplit
from pathlib import Path
import json
import math
import random
import re
from typing import Dict, Iterable, List, Optional, Set, Tuple
from .modules import MODULE_TYPES, slots_for, interfaces_for


def _mac() -> str:
    b = [0x02, random.randint(0, 255), random.randint(0, 255), random.randint(0, 255), random.randint(0, 255), random.randint(0, 255)]
    return ":".join(f"{x:02x}" for x in b)


@dataclass
class Interface:
    name: str
    admin_up: bool = True
    ip: Optional[str] = None
    ipv6: Optional[str] = None
    ipv6_link_local: Optional[str] = None
    mac: str = field(default_factory=_mac)
    mode: str = "access"  # switch ports: access|trunk
    access_vlan: int = 1
    allowed_vlans: List[int] = field(default_factory=lambda: [1])
    native_vlan: int = 1
    parent: Optional[str] = None
    encapsulation_vlan: Optional[int] = None
    stp_cost: Optional[int] = None
    portfast: bool = False
    channel_group: Optional[int] = None
    channel_mode: Optional[str] = None
    helper_address: Optional[str] = None
    ip_access_group_in: Optional[str] = None
    ip_access_group_out: Optional[str] = None
    nat_role: Optional[str] = None  # inside|outside
    description: str = ""
    bridge_group: Optional[str] = None
    media: str = "copper"
    speed: str = "auto"
    duplex: str = "auto"
    clock_rate: int = 0
    auto_mdix: bool = False
    mtu: int = 1500
    tx_ring_limit: int = 10
    baud: int = 9600
    data_bits: int = 8
    parity: str = "none"
    stop_bits: int = 1

    @property
    def ipv4(self) -> Optional[IPv4Interface]:
        return IPv4Interface(self.ip) if self.ip else None


@dataclass
class Route:
    network: str
    next_hop: Optional[str] = None
    interface: Optional[str] = None
    source: str = "static"
    metric: int = 1


@dataclass
class ACLRule:
    action: str
    protocol: str = "ip"
    src: str = "0.0.0.0/0"
    dst: str = "0.0.0.0/0"
    sequence: int = 10
    source_port: Optional[dict] = None
    destination_port: Optional[dict] = None


@dataclass
class DHCPPool:
    name: str
    network: str
    gateway: str
    start: str
    end: str
    dns: Optional[str] = None
    leases: Dict[str, str] = field(default_factory=dict)


@dataclass
class Device:
    name: str
    kind: str
    model: str = ""
    x: float = 200
    y: float = 160
    interfaces: Dict[str, Interface] = field(default_factory=dict)
    default_gateway: Optional[str] = None
    routes: List[Route] = field(default_factory=list)
    vlans: Set[int] = field(default_factory=lambda: {1})
    ospf_enabled: bool = False
    ospf_networks: List[str] = field(default_factory=list)
    # A legacy shortcut can enable all connected interfaces in area 0.
    ospf_auto: bool = False
    ospf_areas: Dict[str, int] = field(default_factory=dict)
    ospf_process_id: int = 1
    stp_mode: str = "pvst"
    stp_priority: int = 32768
    cdp_enabled: bool = True
    lldp_enabled: bool = False
    dhcp_pools: Dict[str, DHCPPool] = field(default_factory=dict)
    arp_table: Dict[str, str] = field(default_factory=dict)
    mac_table: Dict[str, str] = field(default_factory=dict)
    acls: Dict[str, List[ACLRule]] = field(default_factory=dict)
    nat_static: Dict[str, str] = field(default_factory=dict)  # inside-local -> inside-global
    nat_overload: List[dict] = field(default_factory=list)
    nat_sessions: Dict[str, str] = field(default_factory=dict)
    powered: bool = True
    dns_server: Optional[str] = None
    dns_enabled: bool = False
    dns_records: Dict[str, str] = field(default_factory=dict)
    modules: Dict[str, str] = field(default_factory=dict)  # limited simulated PT expansion slots
    config: Dict[str,dict] = field(default_factory=dict)
    http_enabled: bool = True
    http_pages: Dict[str, str] = field(default_factory=lambda: {"/": "<h1>Packet Tracker and Simulator</h1><p>Welcome to the simulated Web Server.</p>"})


@dataclass
class Link:
    a_device: str
    a_if: str
    b_device: str
    b_if: str
    cable: str = "auto"  # auto, copper-straight, copper-cross

    def endpoints(self) -> Tuple[Tuple[str, str], Tuple[str, str]]:
        return (self.a_device, self.a_if), (self.b_device, self.b_if)


class LabError(RuntimeError):
    pass


# This context is intentionally external to NetworkLab: saved labs, snapshots,
# copies and undo history must never contain a derived topology cache. Server
# operations already hold the server's lab lock throughout each calculation.
_forwarding_context = ContextVar("packet_tracker_forwarding_context", default=None)


def _scoped_forwarding(method):
    """Reuse topology lookups only for the duration of one synchronous call."""
    @wraps(method)
    def wrapped(self, *args, **kwargs):
        with self._forwarding_scope():
            return method(self, *args, **kwargs)
    return wrapped


class NetworkLab:
    def __init__(self) -> None:
        self.devices: Dict[str, Device] = {}
        self.links: List[Link] = []
        self.notes: Dict[str, dict] = {}
        self.events: List[str] = []
        self.packet_events: List[dict] = []
        self.packet_counter: int = 0
        from .simulation import defaults as simulation_defaults
        self.simulation=simulation_defaults()
        self.clusters: Dict[str,dict] = {}
        from .workspace_tools import defaults
        self.workspace_tools=defaults()
        self.activity: dict | None = None
        self.physical_locations: Dict[str,dict] = self._initial_physical_locations()
        self.device_locations: Dict[str,str] = {}
        self.physical_device_details: Dict[str,dict] = {}
        self.physical_shelves: Dict[str,int] = {"closet0":0}
        from .physical_grid import defaults as grid_defaults
        self.physical_grids = grid_defaults()
        self.cable_length_effects: bool = False
        self.radio_ranges: Dict[str,float] = {}
        # Portable visual asset library: image data is embedded in saved lab JSON.
        self.visual_assets: Dict[str,dict] = {}
        self.device_icons: Dict[str,dict] = {}
        self.cluster_icons: Dict[str,str] = {}
        self.location_backgrounds: Dict[str,dict] = {}
        # Per-connected-link routed cable bend points (world-meter coordinates).
        self.cable_routes: Dict[str,dict] = {}
        # Industrial Control Panels: door/cabinet, grid and DIN/WIC fixtures.
        self.icp_panels: Dict[str,dict] = {}

    # ---------- saved logical workspace clusters ----------
    def _refresh_dynamic_routing(self) -> None:
        """Refresh routing after a change that can affect routed reachability."""
        if any(d.kind == 'router' and (d.ospf_enabled or d.config.get('rip') or d.config.get('eigrp'))
               for d in self.devices.values()):
            self.recompute_ospf()

    @staticmethod
    def _routing_transit_device(device: Device) -> bool:
        return (device.kind in {'router', 'switch'} or device.model == '7960'
                or bool(device.config.get('multilayer_switch'))
                or any(port.bridge_group for port in device.interfaces.values()))

    def _routing_link_relevant(self, a: str, b: str) -> bool:
        left, right = self._device(a), self._device(b)
        return (left.kind == 'router' or right.kind == 'router'
                or (self._routing_transit_device(left) and self._routing_transit_device(right)))

    def _refresh_dynamic_port(self, device: str, iface: str) -> None:
        peer = self.peer(device, iface)
        if peer and self._routing_link_relevant(device, peer[0]):
            self._refresh_dynamic_routing()

    def add_cluster(self, name: str, members: List[str], parent: Optional[str]=None) -> str:
        if not isinstance(name,str) or not 1<=len(name.strip())<=64 or any(ord(c)<32 for c in name):
            raise LabError("cluster name must contain 1-64 printable characters")
        if parent is not None and parent not in self.clusters:
            raise LabError("unknown parent cluster")
        if len(set(members))!=len(members):
            raise LabError("duplicate device in cluster selection")
        membership={n:c['id'] for c in self.clusters.values() for n in c['devices']}
        for n in members:
            self._device(n)
            if n in membership and membership[n]!=parent:
                raise LabError(n+" already belongs to a different cluster")
        index=0
        while f"Cluster{index}" in self.clusters:index+=1
        ident=f"Cluster{index}"
        if parent is not None:
            self.clusters[parent]['devices']=[n for n in self.clusters[parent]['devices'] if n not in members]
        self.clusters[ident]={"id":ident,"name":name.strip(),"devices":list(members),"parent":parent}
        self.events.append("cluster "+ident+" created")
        return ident

    def rename_cluster(self, ident: str, name: str) -> None:
        if ident not in self.clusters:raise LabError("unknown cluster")
        if not isinstance(name,str) or not 1<=len(name.strip())<=64 or any(ord(c)<32 for c in name):
            raise LabError("invalid cluster name")
        self.clusters[ident]["name"]=name.strip()

    def place_in_cluster(self, device: str, target: Optional[str]) -> None:
        self._device(device)
        if target is not None and target not in self.clusters:raise LabError("unknown cluster")
        for c in self.clusters.values():
            c["devices"]=[n for n in c["devices"] if n!=device]
        if target is not None:self.clusters[target]["devices"].append(device)
        self.events.append(f"{device} moved to logical cluster {target or 'Root'}")

    def move_cluster(self, ident: str, parent: Optional[str]) -> None:
        if ident not in self.clusters:raise LabError("unknown cluster")
        if parent is not None and parent not in self.clusters:raise LabError("unknown parent cluster")
        if parent==ident:raise LabError("cluster cannot contain itself")
        cursor=parent
        for _ in range(len(self.clusters)+1):
            if cursor is None:break
            if cursor==ident:raise LabError("cluster hierarchy cycle")
            cursor=self.clusters[cursor]["parent"]
        else:raise LabError("cluster hierarchy cycle")
        self.clusters[ident]["parent"]=parent

    def delete_cluster(self, ident: str) -> None:
        if ident not in self.clusters:raise LabError("unknown cluster")
        parent=self.clusters[ident]["parent"]
        for c in self.clusters.values():
            if c["parent"]==ident:c["parent"]=parent
        self.cluster_icons.pop(ident,None)
        self.location_backgrounds.pop("logical:"+ident,None)
        del self.clusters[ident]
        self.events.append("unclustered "+ident)

    # ---------- physical workspace (shared logical/physical lab) ----------
    @staticmethod
    def _initial_physical_locations() -> Dict[str, dict]:
        return {
            "city0": {"id":"city0","type":"city","name":"Home City","parent":None,"x":28.0,"y":24.0,"width":5000.0,"length":5000.0,"height":500.0},
            "building0": {"id":"building0","type":"building","name":"Corporate Office","parent":"city0","x":28.0,"y":24.0,"width":100.0,"length":80.0,"height":15.0},
            "closet0": {"id":"closet0","type":"closet","name":"Main Wiring Closet","parent":"building0","x":28.0,"y":24.0,"width":20.0,"length":15.0,"height":4.0},
        }

    @staticmethod
    def _physical_name(name: str) -> str:
        if not isinstance(name,str) or not name.strip() or len(name.strip())>80 or any(ord(c)<32 for c in name):
            raise LabError("location name must contain 1-80 printable characters")
        return name.strip()

    @staticmethod
    def _physical_coordinates(x: float, y: float) -> Tuple[float,float]:
        x,y=float(x),float(y)
        if not math.isfinite(x) or not math.isfinite(y) or not (0<=x<=10000 and 0<=y<=10000):
            raise LabError("physical coordinates must be finite and within 0..10000")
        return x,y

    def _physical_location(self, location: str) -> dict:
        if location not in self.physical_locations:
            raise LabError("unknown physical location "+str(location))
        return self.physical_locations[location]

    PHYSICAL_DEFAULTS={"city":(5000.0,5000.0,500.0),"building":(100.0,80.0,15.0),
                       "closet":(20.0,15.0,4.0),"generic":(10.0,10.0,3.0),
                       "icp":(1.2,0.6,1.8)}
    PHYSICAL_PARENT_TYPES={
        "city":{"intercity","generic"},
        "building":{"intercity","city","generic"},
        "closet":{"intercity","city","building","generic"},
        "generic":{"intercity","city","building","closet","generic"},
        "icp":{"intercity","city","building","closet","generic"},
    }

    @staticmethod
    def _physical_dimensions(width: float,length: float,height: float) -> tuple[float,float,float]:
        values=(float(width),float(length),float(height))
        if any(not math.isfinite(v) or not 0.1<=v<=1000000 for v in values):
            raise LabError("physical dimensions must be finite, between 0.1 and 1000000 meters")
        return values

    @classmethod
    def _location_fits(cls, kind: str, dimensions: tuple, parent: dict|None) -> None:
        parent_type=parent["type"] if parent else "intercity"
        if parent_type not in cls.PHYSICAL_PARENT_TYPES[kind]:
            raise LabError(f"cannot put {kind} inside {parent_type}")
        if parent and any(dim>parent[key] for dim,key in zip(dimensions,("width","length","height"))):
            raise LabError("location dimensions exceed parent container dimensions")

    def resize_physical_location(self,ident: str,width:float,length:float,height:float)->None:
        loc=self._physical_location(ident)
        dims=self._physical_dimensions(width,length,height)
        parent=self.physical_locations.get(loc["parent"])
        self._location_fits(loc["type"],dims,parent)
        for child in self.physical_locations.values():
            if child["parent"]==ident and any(child[key]>dim for key,dim in zip(("width","length","height"),dims)):
                raise LabError("new dimensions do not fit an existing child container")
        loc.update(zip(("width","length","height"),dims))
        if self.cable_length_effects or any(d.config.get("wireless_client") for d in self.devices.values()):self.recompute_ospf()

    def relocate_physical_location(self,ident:str,parent:str)->None:
        loc=self._physical_location(ident)
        parent_id=None if parent=="intercity" else parent
        other=self._physical_location(parent_id) if parent_id is not None else None
        cursor=parent_id
        for _ in range(len(self.physical_locations)+1):
            if cursor is None:break
            if cursor==ident:raise LabError("cannot move a container into itself or a descendant")
            cursor=self._physical_location(cursor)["parent"]
        else:raise LabError("physical container hierarchy cycle")
        dims=tuple(loc[k] for k in ("width","length","height"))
        self._location_fits(loc["type"],dims,other)
        loc["parent"]=parent_id
        loc["x"],loc["y"]=28.0,24.0
        if self.cable_length_effects or any(d.config.get("wireless_client") for d in self.devices.values()):self.recompute_ospf()

    def physical_device_position(self,device:str,x:float,y:float)->None:
        self._device(device)
        x,y=self._physical_coordinates(x,y)
        current=self.physical_device_details.setdefault(device,{"x":28.0,"y":24.0,"surface":"floor","shelf":None})
        current["x"],current["y"]=x,y
        if self.cable_length_effects or any(d.config.get("wireless_client") for d in self.devices.values()):self.recompute_ospf()

    def physical_shelf_add(self,closet:str)->int:
        if self._physical_location(closet)["type"]!="closet":raise LabError("shelves require a wiring closet")
        count=self.physical_shelves.get(closet,0)
        if count>=20:raise LabError("maximum 20 storage shelves per closet")
        self.physical_shelves[closet]=count+1
        return count

    def physical_mount_device(self,device:str,surface:str,shelf: int|None=None)->None:
        d=self._device(device)
        location=self.device_locations.get(device,"intercity")
        kind=self.physical_locations.get(location,{}).get("type")
        is_closet=kind=="closet"
        if kind=="icp":
            if surface not in {"door","cabinet"}:
                raise LabError("ICP mounting surface must be door or cabinet")
            shelf=None
            self.physical_device_details.setdefault(device,{"x":200.0,"y":160.0,"surface":"cabinet","shelf":None}).update({"surface":surface,"shelf":None})
            self.events.append(f"mounted {device} on ICP {surface}")
            return
        if surface not in {"floor","rack","table","shelf"}:
            raise LabError("surface must be floor, rack, table or shelf")
        if surface!="floor" and not is_closet:
            raise LabError("racks, tables and shelves require a wiring closet")
        if surface=="shelf":
            if isinstance(shelf,bool) or not isinstance(shelf,int) or not 0<=shelf<self.physical_shelves.get(location,0):
                raise LabError("unknown storage shelf")
            if d.powered or any(link.a_device==device or link.b_device==device for link in self.links):
                raise LabError("shelf storage requires a powered-off, disconnected device")
        else:shelf=None
        self.physical_device_details.setdefault(device,{"x":28.0,"y":24.0,"surface":"floor","shelf":None}).update({"surface":surface,"shelf":shelf})
        self.events.append(f"mounted {device} on {surface}")

    def _physical_placement_default(self,kind:str,location:str)->dict:
        in_closet=location in self.physical_locations and self.physical_locations[location]["type"]=="closet"
        in_icp=location in self.physical_locations and self.physical_locations[location]["type"]=="icp"
        count=sum(1 for loc in self.device_locations.values() if loc==location)
        x,y=(28.0,24.0) if in_closet else ((200.0+(count%4)*180.0,160.0+(count//4)*100.0)
              if in_icp else (275.0+(count%5)*120.0,90.0+(count//5)*110.0))
        return {"x":x,"y":y,"surface":("rack" if kind in {"router","switch"} else "table") if in_closet else ("cabinet" if in_icp else "floor"),"shelf":None}

    def add_physical_location(self, kind: str, name: str, parent: Optional[str]="intercity") -> str:
        kind=kind.lower()
        name=self._physical_name(name)
        parent = "intercity" if parent in {None,"intercity"} else parent
        if kind not in self.PHYSICAL_DEFAULTS:
            raise LabError("location kind must be city, building, closet, generic or icp")
        parent_loc = None if parent=="intercity" else self._physical_location(parent)
        dims=self.PHYSICAL_DEFAULTS[kind]
        self._location_fits(kind,dims,parent_loc)
        index=0
        while f"loc{index}" in self.physical_locations:
            index+=1
        key=f"loc{index}"
        self.physical_locations[key]={"id":key,"type":kind,"name":name,"parent":None if parent=="intercity" else parent,
                                      "x":28.0+index*20,"y":24.0+index*20,
                                      "width":dims[0],"length":dims[1],"height":dims[2]}
        if kind=="closet":self.physical_shelves[key]=0
        if kind=="icp":
            from .icp import default_panel
            self.icp_panels[key]=default_panel()
        self.events.append(f"created {kind} {key} ({name})")
        return key

    def physical_delete_preview(self, location: str) -> dict:
        """Describe a container subtree deletion without changing the lab."""
        entry=self._physical_location(location)  # Intercity is never deletable.
        removed={location}
        pending=[location]
        while pending:
            parent=pending.pop()
            for ident,child in self.physical_locations.items():
                if child["parent"]==parent and ident not in removed:
                    removed.add(ident);pending.append(ident)
        return {"location":location,"destination":entry["parent"] or "intercity",
                "removed_locations":sorted(removed),
                "extracted_devices":sorted(name for name,place in self.device_locations.items()
                                           if place in removed)}

    def delete_physical_location(self, location: str) -> dict:
        """Remove a container subtree, extracting every device onto its parent's floor.

        Logical devices, configuration, links, icons and world-coordinate cable
        bends survive. Location-specific furniture, panels and backgrounds go.
        CommandProcessor snapshots make the entire operation undoable.
        """
        preview=self.physical_delete_preview(location)
        destination=preview["destination"]
        for index,name in enumerate(preview["extracted_devices"]):
            self.place_physical_device(name,destination,recompute=False)
            self.physical_device_details[name].update(
                surface="floor",shelf=None,x=28.0+(index%10)*110,y=24.0+((index//10)%90)*100)
        for ident in preview["removed_locations"]:
            del self.physical_locations[ident]
            self.physical_shelves.pop(ident,None)
            self.location_backgrounds.pop(ident,None)
            self.icp_panels.pop(ident,None)
        self.events.append(f"deleted physical location {location}; extracted {len(preview['extracted_devices'])} device(s) to {destination}")
        if self.cable_length_effects or any(d.config.get("wireless_client") for d in self.devices.values()):self.recompute_ospf()
        return preview

    def rename_physical_location(self, location: str, name: str) -> None:
        entry=self._physical_location(location)
        entry["name"]=self._physical_name(name)
        self.events.append(f"renamed physical location {location} to {entry['name']}")

    def move_physical_location(self, location: str, x: float, y: float) -> None:
        entry=self._physical_location(location)
        entry["x"],entry["y"]=self._physical_coordinates(x,y)
        if self.cable_length_effects or any(d.config.get("wireless_client") for d in self.devices.values()):self.recompute_ospf()

    def place_physical_device(self, device: str, location: str, *, recompute: bool=True) -> None:
        self._device(device)
        if location!="intercity":
            self._physical_location(location)
        previous=self.device_locations.get(device,"intercity")
        if previous in self.icp_panels and previous!=location:
            from .icp import forget_device
            forget_device(self,device)
        self.device_locations[device]=location
        self.physical_device_details[device]=self._physical_placement_default(self.devices[device].kind,location)
        self.events.append(f"placed {device} at {location}")
        if recompute and self.cable_length_effects:self.recompute_ospf()

    def move_physical_devices(self, names: List[str], location: str) -> None:
        """Move 1..200 devices as one validated operation.

        Like PT's Move Object workflow, relocated map devices start stacked
        in the upper left. Closet equipment lands in rack/table furniture.
        Physical movement preserves network links and the logical topology.
        """
        if not isinstance(names, list) or not 1 <= len(names) <= 200:
            raise LabError("move requires 1-200 device names")
        if len(set(names)) != len(names):
            raise LabError("duplicate device in physical move selection")
        for name in names:
            self._device(name)
        if location != "intercity":
            self._physical_location(location)
        moved = 0
        for name in names:
            if self.device_locations.get(name) == location:
                continue
            self.place_physical_device(name, location, recompute=False)
            detail = self.physical_device_details[name]
            detail["x"], detail["y"] = 28.0, 24.0
            moved += 1
        self.events.append(f"physically moved {moved} device(s) to {location}")
        if self.cable_length_effects or any(d.config.get("wireless_client") for d in self.devices.values()):self.recompute_ospf()

    def set_cable_length_effects(self,enabled:bool)->None:
        if not isinstance(enabled,bool):raise LabError("cable effects requires on or off")
        if self.cable_length_effects==enabled:return
        self.cable_length_effects=enabled
        self.events.append("cable length effects "+("on" if enabled else "off"))
        self.recompute_ospf()

    def set_radio_range(self,device:str,radius:float)->None:
        from .physical_distance import radio_default
        d=self._device(device)
        if radio_default(d.model or "") is None:
            raise LabError("radio range requires a supported wireless source model")
        try:r=float(radius)
        except (TypeError,ValueError):raise LabError("radio range must be a number")
        if not math.isfinite(r) or not 0.1<=r<=100000:
            raise LabError("radio range must be 0.1 to 100000 meters")
        self.radio_ranges[device]=r
        self.events.append(f"{device} radio radius {r:g}m")

    def physical_path(self, location: str) -> str:
        if location=="intercity":return "Intercity"
        path=[]
        current=location
        for _ in range(len(self.physical_locations)+1):
            if current is None:break
            entry=self._physical_location(current)
            path.append(entry["name"])
            current=entry["parent"]
        else: raise LabError("physical location parent cycle")
        return "Intercity / "+" / ".join(reversed(path))

    def reset(self) -> None:
        self.devices.clear();self.links.clear();self.notes.clear();self.events.clear()
        self.packet_events.clear();self.packet_counter=0
        from .simulation import defaults as simulation_defaults
        self.simulation=simulation_defaults()
        self.physical_locations=self._initial_physical_locations()
        self.device_locations.clear()
        self.physical_device_details.clear()
        self.physical_shelves={"closet0":0}
        from .physical_grid import defaults as grid_defaults
        self.physical_grids=grid_defaults()
        self.cable_length_effects=False
        self.radio_ranges.clear()
        self.visual_assets.clear()
        self.device_icons.clear()
        self.cluster_icons.clear()
        self.location_backgrounds.clear()
        self.cable_routes.clear()
        self.icp_panels.clear()
        self.clusters.clear()
        from .workspace_tools import defaults
        self.workspace_tools=defaults()
        self.activity = None

    # ---------- simplified DNS / HTTP application services ----------
    @staticmethod
    def _valid_dns_name(host: str) -> str:
        host = host.strip().lower().rstrip(".")
        if len(host) > 253 or not host or not re.fullmatch(
            r"[a-z0-9](?:[a-z0-9-]{0,61}[a-z0-9])?(?:\.[a-z0-9](?:[a-z0-9-]{0,61}[a-z0-9])?)*", host
        ):
            raise LabError("invalid DNS hostname")
        return host

    def set_dns_client(self, device: str, ip: Optional[str]) -> None:
        d = self._device(device)
        if d.kind not in {"pc", "server"}:
            raise LabError("DNS client settings require a host")
        if ip is not None:
            IPv4Address(ip)
        d.dns_server = ip

    def dns_service(self, device: str, enabled: bool) -> None:
        d = self._device(device)
        if d.kind != "server":
            raise LabError("DNS service requires a server")
        d.dns_enabled = bool(enabled)

    def dns_record(self, device: str, name: str, ip: str) -> None:
        d = self._device(device)
        if d.kind != "server":
            raise LabError("DNS records require a server")
        name = self._valid_dns_name(name)
        IPv4Address(ip)
        d.dns_records[name] = ip

    def dns_delete(self, device: str, name: str) -> None:
        d = self._device(device)
        name = self._valid_dns_name(name)
        if name not in d.dns_records:
            raise LabError("DNS record not found")
        del d.dns_records[name]

    def http_service(self, device: str, enabled: bool) -> None:
        d = self._device(device)
        if d.kind != "server":
            raise LabError("HTTP service requires a server")
        d.http_enabled = bool(enabled)

    def set_http_page(self, device: str, path: str, content: str) -> None:
        d = self._device(device)
        if d.kind != "server":
            raise LabError("HTTP pages require a server")
        if not isinstance(path, str) or not path.startswith("/") or "?" in path or "#" in path or len(path) > 120:
            raise LabError("HTTP page path must begin with / and contain no query or fragment")
        if not isinstance(content, str) or not 0 < len(content) <= 20000:
            raise LabError("HTTP page must contain 1-20000 characters")
        d.http_pages[path] = content

    def _transit(self, source: str, target_ip: str, protocol: str, source_port: Optional[int] = 1025, destination_port: Optional[int] = None) -> Tuple[bool, List[str], List[str]]:
        d = self._device(source)
        if not d.powered:
            return False, [source, "power-off"], []
        origin_ip = self._source_ip_for_destination(source, target_ip)
        if origin_ip is None:
            return False, [source, "no-route"], []
        meta = {"translated_source": origin_ip, "final_destination": target_ip,"source_port":source_port,"destination_port":destination_port}
        ok, forward = self._forward(source, target_ip, set(), [], origin_ip, protocol, None, meta)
        if not ok:
            return False, forward, []
        receiver = meta.get("final_owner") or (self.owner_of_ip(target_ip) or ("", ""))[0]
        if receiver == source:
            return True, forward, [source]
        reply_src = meta.get("final_destination", target_ip)
        reply_dst = meta.get("translated_source", origin_ip)
        ok_back, backward = self._forward(receiver, reply_dst, set(), [], reply_src, protocol, None, {"source_port":meta.get("destination_port",destination_port),"destination_port":source_port})
        return ok_back, forward, backward

    def _packet_event(self, protocol: str, src: str, dst: str, detail: str, ok: bool = True, capture: bool = True) -> None:
        self.packet_counter += 1
        self.packet_events.append({
            "seq": self.packet_counter, "time": round(self.packet_counter * 0.001, 3),
            "protocol": protocol, "source": src, "destination": dst,
            "detail": detail, "ok": bool(ok),
        })
        self.packet_events = self.packet_events[-256:]
        if capture:
            from .simulation import record_external
            record_external(self,self.packet_events[-1])

    def _trace_packet(self, protocol: str, path: List[str], detail: str, ok: bool = True) -> None:
        if len(path) <= 1:
            name = path[0] if path else ""
            self._packet_event(protocol, name, name, detail, ok)
            return
        for a, b in zip(path, path[1:]):
            self._packet_event(protocol, a, b, detail, ok)

    def send_simple_pdu(self, source: str, destination: str) -> dict:
        self._device(source)
        dst = self._device(destination)
        target = next((str(i.ipv4.ip) for i in dst.interfaces.values() if i.ip), None)
        if not target:
            self._packet_event("ICMP", source, destination, "No destination IP configured", False)
            return {"ok": False, "status": "Failed", "message": "Destination has no IPv4 address"}
        ok, forward, backward = self._transit(source, target, "icmp")
        self._trace_packet("ICMP", forward, "Echo Request", ok)
        if ok:
            self._trace_packet("ICMP", backward, "Echo Reply", True)
        return {"ok": ok, "status": "Successful" if ok else "Failed", "message": "Echo Reply" if ok else "Destination unreachable"}

    def resolve_dns(self, source: str, hostname: str) -> str:
        from .device_services import resolve_dns
        try:return resolve_dns(self,source,hostname)
        except LabError as exc:
            if "Unresolved" in str(exc):raise
            raise LabError("Host Name Unresolved ("+str(exc)+")") from exc

    def http_request(self, source: str, raw_url: str) -> dict:
        client = self._device(source)
        if client.kind not in {"pc", "server"}:
            raise LabError("Web Browser requires a PC or server")
        if not isinstance(raw_url, str) or len(raw_url) > 2048:
            raise LabError("Invalid URL")
        text = raw_url.strip()
        parsed = urlsplit(text if "://" in text else "http://"+text)
        if parsed.scheme not in {"http","https"} or not parsed.hostname or parsed.username or parsed.password:
            raise LabError("Only simulated http:// URLs are supported")
        try:
            if parsed.port is not None and not 1<=parsed.port<=65535:
                raise LabError("Invalid HTTP service port")
        except ValueError:
            raise LabError("Invalid port")
        host = parsed.hostname
        try:
            address = str(IPv4Address(host))
        except ValueError:
            address = self.resolve_dns(source, host)
        target = self.owner_of_ip(address)
        if not target:
            raise LabError("Web Server Unavailable")
        server = self._device(target[0])
        selected_port=parsed.port or (443 if parsed.scheme=="https" else 80)
        expected_port=443 if parsed.scheme=="https" else 80
        if selected_port!=expected_port and not any(r['external_port']==selected_port and r['internal_port']==expected_port and r['protocol'] in ('tcp','both') for r in server.config.get('port_forwards',{}).values()):raise LabError("HTTP service is not listening on that port")
        ok, go, ret = self._transit(source, address, "tcp",destination_port=parsed.port or (443 if parsed.scheme=="https" else 80))
        self._trace_packet("TCP", go, "HTTP connection", ok)
        if not ok:
            raise LabError("Web Server Unreachable")
        if go and go[-1] in self.devices:server=self.devices[go[-1]]
        from .device_services import profile,service
        managed=profile(server) in {'home-router','meraki','controller','wlc','observer','firewall','iox-router'}
        if server.kind != "server" and not managed or not service(server,parsed.scheme).get('enabled'):
            self._packet_event("HTTP", source, server.name, "Service disabled", False)
            raise LabError("HTTP Service Unavailable")
        path = parsed.path or "/"
        if path == "/index.html":
            path = "/"
        for node in go:
            if node not in self.devices:continue
            for blocked in self.devices[node].config.get('url_blocks',[]):
                if blocked['url'] in raw_url and blocked['host'] in ('any',self._source_ip_for_destination(source,address)):
                    self._packet_event('HTTP',source,node,'URL blocked',False);raise LabError('URL blocked by firewall')
        page = server.http_pages.get(path)
        if managed and path=='/':page='<h1>'+profile(server).replace('-',' ').title()+'</h1><p>Use Manage Device to authenticate and configure this simulated appliance.</p>'
        self._trace_packet("HTTP", go, "GET "+path, page is not None)
        self._trace_packet("HTTP", ret, "Response "+("200" if page is not None else "404"), page is not None)
        if page is None:
            return {"ok": False, "status": 404, "url": raw_url, "resolved_ip": address,
                    "html": "<h1>404 Not Found</h1>", "server": server.name}
        return {"ok": True, "status": 200, "url": raw_url, "resolved_ip": address,
                "html": page, "server": server.name,"management":server.name if managed else None}

    # ---------- logical workspace annotations ----------
    @staticmethod
    def _note_position(x: float, y: float) -> tuple[float, float]:
        x, y = float(x), float(y)
        if not all(math.isfinite(v) and -10000 <= v <= 10000 for v in (x, y)):
            raise LabError("note coordinates must be finite and within -10000..10000")
        return x, y

    def add_note(self, x: float, y: float, text: str) -> str:
        x, y = self._note_position(x, y)
        if not isinstance(text, str) or not text.strip() or len(text) > 800:
            raise LabError("note text must contain 1-800 characters")
        number = 0
        while "Note" + str(number) in self.notes:
            number += 1
        ident = "Note" + str(number)
        self.notes[ident] = {"text": text, "x": x, "y": y}
        self.events.append("added note " + ident)
        return ident

    def update_note(self, ident: str, text: str) -> None:
        if ident not in self.notes:
            raise LabError("unknown note " + ident)
        if not isinstance(text, str) or not text.strip() or len(text) > 800:
            raise LabError("note text must contain 1-800 characters")
        self.notes[ident]["text"] = text
        self.events.append("updated note " + ident)

    def move_note(self, ident: str, x: float, y: float) -> None:
        if ident not in self.notes:
            raise LabError("unknown note " + ident)
        x, y = self._note_position(x, y)
        self.notes[ident].update(x=x, y=y)

    def remove_note(self, ident: str) -> None:
        if ident not in self.notes:
            raise LabError("unknown note " + ident)
        del self.notes[ident]
        self.events.append("removed note " + ident)

    # ---------- topology ----------
    def add_device(self, kind: str, name: str, x: float = 200, y: float = 160, model: str = "") -> Device:
        kind = kind.lower()
        if name in self.devices:
            raise LabError(f"device {name} already exists")
        if kind not in {"pc", "switch", "router", "server", "generic"}:
            raise LabError("device type must be pc, server, switch, router, or generic")
        d = Device(name=name, kind=kind, model=model, x=x, y=y)
        if kind in {"pc", "server", "generic"}:
            d.interfaces["eth0"] = Interface("eth0")
        elif kind == "router":
            for n in ("g0/0", "g0/1", "g0/2", "g0/3"):
                d.interfaces[n] = Interface(n)
        else:
            for i in range(1, 13):
                d.interfaces[f"fa0/{i}"] = Interface(f"fa0/{i}")
            for i in range(1, 3):
                d.interfaces[f"g0/{i}"] = Interface(f"g0/{i}")
        self.devices[name] = d
        from .special_devices import initialize_new
        initialize_new(self,d)
        preferred = "closet0" if kind in {"router","switch"} else "building0"
        self.device_locations[name] = preferred if preferred in self.physical_locations else "intercity"
        self.physical_device_details[name]=self._physical_placement_default(kind,self.device_locations[name])
        self.events.append(f"added {kind} {name}")
        return d

    def rename_device(self, old: str, new: str) -> None:
        d = self._device(old)
        if not re.fullmatch(r"[A-Za-z][A-Za-z0-9_-]{0,30}", new):
            raise LabError("device name must start with a letter and contain only letters, numbers, _ or -")
        if new == old:
            return
        if new in self.devices:
            raise LabError(f"device {new} already exists")
        del self.devices[old]
        d.name = new
        self.devices[new] = d
        if old in self.device_locations:
            self.device_locations[new] = self.device_locations.pop(old)
        if old in self.physical_device_details:
            self.physical_device_details[new]=self.physical_device_details.pop(old)
        for link in self.links:
            if link.a_device == old: link.a_device = new
            if link.b_device == old: link.b_device = new
        from .cable_manipulation import rename_device as rename_cable_routes
        rename_cable_routes(self,old,new)
        from .icp import rename_device as rename_icp_device
        rename_icp_device(self,old,new)
        for c in self.clusters.values():
            c["devices"]=[new if n==old else n for n in c["devices"]]
        if old in self.radio_ranges:self.radio_ranges[new]=self.radio_ranges.pop(old)
        if old in self.device_icons:self.device_icons[new]=self.device_icons.pop(old)
        for p in self.simulation["pdus"].values():
            if p["source"]==old:p["source"]=new
            if p["destination"]==old:p["destination"]=new
            task=p.get("task",{})
            payload=task.get("payload",{})
            key="device" if task.get("operation")=="device-config" else "source"
            if payload.get(key)==old:payload[key]=new
        if self.simulation["pending"]:
            from .simulation import reset
            reset(self)
        for g in self.workspace_tools.get("diagram",{}).get("groups",{}).values():
            g["members"]=[new if n==old else n for n in g["members"]]
        self.events.append(f"renamed {old} to {new}")

    def remove_device(self, name: str) -> None:
        device = self._device(name)
        groups=self.workspace_tools.get("diagram",{}).get("groups",{})
        for key,g in list(groups.items()):
            g["members"]=[n for n in g["members"] if n!=name]
            if not g["members"]:del groups[key]
        routing_relevant = (device.kind == 'router' or any(
            self._routing_link_relevant(link.a_device, link.b_device)
            for link in self.links if name in (link.a_device, link.b_device)))
        self.links = [l for l in self.links if l.a_device != name and l.b_device != name]
        from .icp import forget_device as forget_icp_device
        forget_icp_device(self,name)
        from .cable_manipulation import prune_disconnected
        prune_disconnected(self)
        del self.devices[name]
        self.device_locations.pop(name,None)
        self.physical_device_details.pop(name,None)
        self.radio_ranges.pop(name,None)
        self.device_icons.pop(name,None)
        for c in self.clusters.values():
            c["devices"]=[n for n in c["devices"] if n!=name]
        self.simulation["pdus"]={k:p for k,p in self.simulation["pdus"].items() if p["source"]!=name and p["destination"]!=name}
        if self.simulation["pending"]:
            from .simulation import reset
            reset(self)
        self.events.append(f"removed {name}")
        if routing_relevant:self._refresh_dynamic_routing()

    def connect(self, a_device: str, a_if: str, b_device: str, b_if: str, cable: str = "auto") -> None:
        if any(self.physical_device_details.get(n,{}).get("surface")=="shelf" for n in (a_device,b_device)):
            raise LabError("devices stored on shelves cannot be cabled")
        if a_device == b_device:
            raise LabError("cannot connect a device to itself")
        self._iface(a_device, a_if)
        self._iface(b_device, b_if)
        a_device, a_if = self._physical_endpoint(a_device, a_if)
        b_device, b_if = self._physical_endpoint(b_device, b_if)
        if self.link_for(a_device, a_if) or self.link_for(b_device, b_if):
            raise LabError("an interface can only have one cable")
        from .hardware import validate_cable
        cable=validate_cable(self,a_device,a_if,b_device,b_if,cable)
        self.links.append(Link(a_device, a_if, b_device, b_if, cable))
        self.events.append(f"connected {a_device}:{a_if} <-> {b_device}:{b_if} using {cable}")
        if self._routing_link_relevant(a_device, b_device):self._refresh_dynamic_routing()

    def auto_connect(self, a_device: str, b_device: str) -> Link:
        """Connect the first free compatible data ports on two devices."""
        if a_device == b_device:
            raise LabError("cannot connect a device to itself")
        a, b = self._device(a_device), self._device(b_device)
        if any(self.physical_device_details.get(n, {}).get('surface') == 'shelf' for n in (a_device, b_device)):
            raise LabError('devices stored on shelves cannot be cabled')
        # Prefer usable data ports and select an actual cable for the pair.
        priority = ('copper', 'fiber-mm', 'fiber-sm', 'serial', 'modem', 'coax', 'usb', 'ioe')
        def rank(device, port, other):
            phone_penalty = 0
            if device.model == '7960':
                other_is_switch = other.kind == 'switch' or other.config.get('multilayer_switch', False)
                desired = 'eth0' if other_is_switch else 'pc'
                phone_penalty = port.name != desired
            return (phone_penalty, not port.admin_up, not bool(port.ip))
        from .hardware import copper_cable, physical_status, validate_cable
        candidates = []
        for order, media in enumerate(priority):
            left = sorted((p for p in a.interfaces.values() if p.media == media and not p.parent and not self.link_for(a_device, p.name)), key=lambda p: rank(a,p,b))
            right = sorted((p for p in b.interfaces.values() if p.media == media and not p.parent and not self.link_for(b_device, p.name)), key=lambda p: rank(b,p,a))
            for ap in left:
                for bp in right:
                    cable = copper_cable(self,a_device,ap.name,b_device,bp.name) if media == 'copper' else ('serial-dte' if media == 'serial' and bp.clock_rate and not ap.clock_rate else 'auto')
                    try:
                        cable = validate_cable(self,a_device,ap.name,b_device,bp.name,cable)
                        link = Link(a_device,ap.name,b_device,bp.name,cable)
                        operational, _ = physical_status(self,link)
                        candidates.append(((not operational,order,rank(a,ap,b),rank(b,bp,a)),link))
                    except LabError:
                        continue
        for _, link in sorted(candidates,key=lambda item:item[0]):
            try:
                self.connect(link.a_device,link.a_if,link.b_device,link.b_if,link.cable)
                return self.links[-1]
            except LabError:
                continue
        raise LabError('no free compatible interfaces between these devices')

    def duplicate_devices(self, names: List[str], dx: float=120, dy: float=80) -> Dict[str,str]:
        """Clone a selected topology group and internal links atomically.

        Configuration is copied (including IP addressing); fresh interface MACs and
        empty dynamic tables prevent fabricating learned host state.
        External links are not copied because their original ports are occupied.
        """
        if not names or len(names)>512 or len(names)!=len(set(names)):
            raise LabError("duplicate requires 1-512 unique device names")
        for name in names: self._device(name)
        dx,dy=float(dx),float(dy)
        if not math.isfinite(dx) or not math.isfinite(dy):
            raise LabError("duplicate offset must be finite")
        clones={}
        occupied=set(self.devices)
        for name in names:
            base=name[:23]+"_copy"
            candidate=base
            counter=2
            while candidate in occupied:
                candidate=f"{base[:25]}{counter}"
                counter+=1
            src=self.devices[name]
            x,y=src.x+dx,src.y+dy
            if not 0<=x<=10000 or not 0<=y<=10000:
                raise LabError(f"duplicate {name} outside logical workspace")
            d=deepcopy(src)
            d.name=candidate
            d.x,d.y=x,y
            d.arp_table.clear();d.mac_table.clear();d.nat_sessions.clear()
            for iface in d.interfaces.values(): iface.mac=_mac()
            for pool in d.dhcp_pools.values(): pool.leases.clear()
            clones[name]=(candidate,d)
            occupied.add(candidate)
        internal=[deepcopy(link) for link in self.links
                  if link.a_device in clones and link.b_device in clones]
        for name,(new,d) in clones.items():
            self.devices[new]=d
            self.device_locations[new]=self.device_locations.get(name,"intercity")
            physical=deepcopy(self.physical_device_details.get(name,self._physical_placement_default(d.kind,self.device_locations[new])))
            if physical["surface"]=="shelf":
                physical["surface"]="floor";physical["shelf"]=None
            self.physical_device_details[new]=physical
            if name in self.radio_ranges:self.radio_ranges[new]=self.radio_ranges[name]
            if name in self.device_icons:self.device_icons[new]=deepcopy(self.device_icons[name])
        for link in internal:
            link.a_device=clones[link.a_device][0]
            link.b_device=clones[link.b_device][0]
            self.links.append(link)
        for source,(clone,_) in clones.items():
            for c in self.clusters.values():
                if source in c["devices"]:c["devices"].append(clone)
        self.events.append("duplicated "+", ".join(names))
        if any(self._routing_transit_device(clone) for _, clone in clones.values()):
            self._refresh_dynamic_routing()
        return {name:pair[0] for name,pair in clones.items()}

    def remove_group(self, names: List[str]) -> None:
        if not names or len(names)>512 or len(set(names))!=len(names):
            raise LabError("remove-group requires 1-512 distinct device names")
        for n in names: self._device(n)
        for n in names: self.remove_device(n)
        self.events.append("removed group "+", ".join(names))

    def move_device(self, name: str, x: float, y: float) -> None:
        d=self._device(name)
        x,y=float(x),float(y)
        if not all(math.isfinite(v) and 0<=v<=10000 for v in (x,y)):
            raise LabError("logical coordinates must be finite within 0..10000")
        d.x,d.y=x,y
        self.events.append(f"moved {name} to {x},{y}")

    def move_group(self, names: List[str], dx: float, dy: float) -> None:
        if not names or len(names)>512 or len(names)!=len(set(names)):
            raise LabError("move-group requires 1-512 unique device names")
        dx,dy=float(dx),float(dy)
        if not math.isfinite(dx) or not math.isfinite(dy):
            raise LabError("move offset must be finite")
        devices=[self._device(n) for n in names]
        for d in devices:
            if not (0<=d.x+dx<=10000 and 0<=d.y+dy<=10000):
                raise LabError("device would leave logical workspace")
        for d in devices: d.x+=dx;d.y+=dy
        self.events.append("moved group "+", ".join(names))

    def module_slots(self, device: str) -> list[dict]:
        d=self._device(device)
        slots=[]
        for slot in slots_for(d):
            installed=d.modules.get(slot)
            slots.append({
                "slot":slot,"module":installed,"editable":True,
                "available":__import__("netsim.modules",fromlist=["compatible_modules"]).compatible_modules(d),
                "interfaces":interfaces_for(slot,installed) if installed else [],
                "requires_power_off":True,
            })
        return slots

    def set_module(self, device: str, slot: str, module: Optional[str]) -> None:
        d=self._device(device)
        if slot not in slots_for(d):
            raise LabError("unsupported expansion slot; only generic PT device profiles have simulated modules")
        if d.powered:
            raise LabError("switch device power off before changing expansion modules")
        if module in ("none","",None):
            module=None
        elif module not in __import__("netsim.modules",fromlist=["compatible_modules"]).compatible_modules(d):
            raise LabError("unsupported module type for this device")
        existing=d.modules.get(slot)
        if existing==module:return
        if existing:
            names=set(interfaces_for(slot,existing))
            if any((link.a_device==device and link.a_if in names) or
                   (link.b_device==device and link.b_if in names) for link in self.links):
                raise LabError("disconnect attached module cables before removing the module")
            if any(i.parent in names for i in d.interfaces.values()):
                raise LabError("delete module subinterfaces before removing the module")
            for name in names:d.interfaces.pop(name,None)
            d.modules.pop(slot,None)
        if module:
            names=interfaces_for(slot,module)
            if any(name in d.interfaces for name in names):
                raise LabError("module port naming collides with an existing interface")
            d.modules[slot]=module
            for name in names:d.interfaces[name]=Interface(name,media=MODULE_TYPES[module].get("media","copper"))
        self.events.append(f"{device}:{slot} -> {module or 'empty'}")
        self.recompute_ospf()

    def set_power(self, device: str, on: bool) -> None:
        d = self._device(device)
        if d.config.get("passive"):raise LabError("passive cabling device has no power switch")
        if on and self.physical_device_details.get(device,{}).get("surface")=="shelf":
            raise LabError("remove device from storage shelf before powering on")
        if not isinstance(on, bool):
            raise LabError("power state must be on/off")
        if d.powered == on:
            return
        d.powered = on
        if not on:
            d.arp_table.clear()
            d.mac_table.clear()
            d.nat_sessions.clear()
        if on and d.config:
            from .device_config import boot
            boot(self,device)
        self.events.append(f"{device} power {'on' if on else 'off'}")
        self.recompute_ospf()

    def power_cycle_all(self) -> None:
        """Reboot all devices without erasing their configured network parameters."""
        for d in list(self.devices.values()):
            d.powered = self.physical_device_details.get(d.name,{}).get("surface")!="shelf"
            if d.powered and d.config:
                from .device_config import boot
                boot(self,d.name)
                d=self.devices[d.name]
            d.arp_table.clear()
            d.mac_table.clear()
            d.nat_sessions.clear()
        self.packet_events.clear()
        self.packet_counter = 0
        self.events.append("Power cycled all devices; dynamic tables and packet trace cleared")
        self.recompute_ospf()

    def link_operational(self, link: Link) -> bool:
        from .hardware import physical_status
        return physical_status(self,link)[0]

    def link_status(self, link: Link) -> dict:
        from .physical_distance import cable_length
        info=cable_length(self,link)
        up=self.link_operational(link)
        a=self._device(link.a_device)
        b=self._device(link.b_device)
        from .hardware import physical_status
        reason=physical_status(self,link)[1]
        return {"up":up,"cable":link.cable,
                "endpoints":[f"{link.a_device}:{link.a_if}",f"{link.b_device}:{link.b_if}"],
                "reason":reason,**info}

    def _physical_endpoint(self, device: str, iface: str) -> Tuple[str, str]:
        p = self._iface(device, iface)
        return device, (p.parent or iface)

    def disconnect(self, device: str, iface: str) -> None:
        endpoint = self._physical_endpoint(device, iface)
        link = self.link_for(device, iface)
        routing_relevant = bool(link and self._routing_link_relevant(link.a_device, link.b_device))
        before = len(self.links)
        self.links = [l for l in self.links if endpoint not in l.endpoints()]
        if len(self.links) == before:
            raise LabError("no cable on that interface")
        from .cable_manipulation import prune_disconnected
        prune_disconnected(self)
        if routing_relevant:self._refresh_dynamic_routing()

    @contextmanager
    def _forwarding_scope(self):
        """Index one unchanged topology; nested calls on this lab share it.

        Callers must not edit topology while the scope is active. Direct model
        access needs external synchronization, as it did before this cache.
        """
        current = _forwarding_context.get()
        if current is not None and current[0] is self:
            yield
            return
        links = {}
        for link in self.links:
            for endpoint in link.endpoints():
                # Match the original first-link behavior even for malformed labs.
                links.setdefault(endpoint, link)
        token = _forwarding_context.set((self, links, {}))
        try:
            yield
        finally:
            _forwarding_context.reset(token)

    def link_for(self, device: str, iface: str) -> Optional[Link]:
        endpoint = self._physical_endpoint(device, iface)
        current = _forwarding_context.get()
        if current is not None and current[0] is self:
            return current[1].get(endpoint)
        for link in self.links:
            if endpoint in link.endpoints():
                return link
        return None

    def peer(self, device: str, iface: str) -> Optional[Tuple[str, str]]:
        endpoint = self._physical_endpoint(device, iface)
        link = self.link_for(device, iface)
        if not link:
            return None
        a, b = link.endpoints()
        return b if a == endpoint else a

    # ---------- configuration ----------
    def set_ip(self, device: str, iface: str, cidr: str) -> None:
        IPv4Interface(cidr)
        p=self._iface(device,iface)
        if p.media not in {"copper","fiber-mm","fiber-sm","serial","wifi","bridge","modem","coax","vpn"}:raise LabError("IP configuration requires a data interface")
        p.ip = cidr
        self.recompute_ospf()

    def add_subinterface(self, device: str, parent: str, vlan: int, cidr: str) -> Interface:
        d = self._device(device)
        if d.kind != "router":
            raise LabError("subinterfaces are supported on routers")
        parent_if = self._iface(device, parent)
        if parent_if.parent is not None:
            raise LabError("parent must be a physical interface")
        if not 1 <= int(vlan) <= 4094:
            raise LabError("VLAN must be 1-4094")
        IPv4Interface(cidr)
        name = f"{parent}.{int(vlan)}"
        d.interfaces[name] = Interface(name=name, ip=cidr, mac=parent_if.mac, parent=parent, encapsulation_vlan=int(vlan))
        self.recompute_ospf()
        return d.interfaces[name]

    def set_interface_state(self, device: str, iface: str, up: bool) -> None:
        p=self._iface(device,iface)
        changed=p.admin_up!=up;p.admin_up=up
        self.recompute_ospf()
        if changed and self._device(device).config.get("syslog_host"):
            from .device_services import emit_log
            emit_log(self,device,iface+(" up" if up else " down"))

    def set_gateway(self, device: str, gateway: str) -> None:
        IPv4Address(gateway)
        self._device(device).default_gateway = gateway

    def add_vlan(self, switch: str, vlan: int, *, recompute=True) -> None:
        d = self._device(switch)
        if (d.kind != "switch" and not d.config.get("multilayer_switch",False)):
            raise LabError("VLANs can be created on switches")
        if not 1 <= vlan <= 4094:
            raise LabError("VLAN must be 1-4094")
        changed = vlan not in d.vlans
        d.vlans.add(vlan)
        if changed and recompute:self._refresh_dynamic_routing()

    def set_switchport_access(self, switch: str, iface: str, vlan: int) -> None:
        d = self._device(switch)
        if (d.kind != "switch" and not d.config.get("multilayer_switch",False)):
            raise LabError("switchport command requires a switch")
        new_vlan = vlan not in d.vlans
        self.add_vlan(switch, vlan, recompute=False)
        p = self._iface(switch, iface)
        p.mode = "access"
        if d.config.get("multilayer_switch"):
            for name in list(d.interfaces):
                if d.interfaces[name].parent == iface:del d.interfaces[name]
        p.access_vlan = vlan
        if d.config.get("multilayer_switch"):p.bridge_group="vlan"+str(vlan)
        p.allowed_vlans = [vlan]
        if new_vlan:self._refresh_dynamic_routing()
        else:self._refresh_dynamic_port(switch, iface)

    def set_switchport_trunk(self, switch: str, iface: str, vlans: Iterable[int]) -> None:
        d = self._device(switch)
        if (d.kind != "switch" and not d.config.get("multilayer_switch",False)):
            raise LabError("switchport command requires a switch")
        values = sorted(set(int(v) for v in vlans))
        if not values:
            values = sorted(d.vlans)
        for v in values:
            self.add_vlan(switch, v, recompute=False)
        p = self._iface(switch, iface)
        p.mode = "trunk"
        p.allowed_vlans = values
        if d.config.get("multilayer_switch"):
            p.bridge_group = None
            for name in list(d.interfaces):
                if d.interfaces[name].parent == iface:del d.interfaces[name]
            for tag in values:
                name=iface+"."+str(tag)
                d.interfaces[name]=Interface(name,parent=iface,encapsulation_vlan=tag,bridge_group="vlan"+str(tag),media=p.media)
        self._refresh_dynamic_routing()

    def set_native_vlan(self, switch: str, iface: str, vlan: int) -> None:
        d = self._device(switch)
        if (d.kind != "switch" and not d.config.get("multilayer_switch",False)):
            raise LabError("native VLAN requires a switch")
        if not 1 <= int(vlan) <= 4094:
            raise LabError("VLAN must be 1-4094")
        p = self._iface(switch, iface)
        if p.mode != "trunk":
            raise LabError("native VLAN can only be configured on a trunk")
        self.add_vlan(switch, int(vlan), recompute=False)
        p.native_vlan = int(vlan)
        if int(vlan) not in p.allowed_vlans:
            p.allowed_vlans.append(int(vlan)); p.allowed_vlans.sort()
        self._refresh_dynamic_routing()

    def set_stp_mode(self, switch: str, mode: str) -> None:
        d = self._device(switch)
        if (d.kind != "switch" and not d.config.get("multilayer_switch",False)):
            raise LabError("STP mode requires a switch")
        mode = mode.lower()
        aliases = {"rstp": "rapid-pvst", "rapid": "rapid-pvst", "pvst+": "pvst"}
        mode = aliases.get(mode, mode)
        if mode not in {"pvst", "rapid-pvst"}:
            raise LabError("STP mode must be pvst or rapid-pvst")
        d.stp_mode = mode
        self._refresh_dynamic_routing()

    def set_stp_priority(self, switch: str, priority: int) -> None:
        d = self._device(switch)
        if (d.kind != "switch" and not d.config.get("multilayer_switch",False)):
            raise LabError("STP priority requires a switch")
        priority = int(priority)
        if priority < 0 or priority > 61440 or priority % 4096:
            raise LabError("STP priority must be 0-61440 in increments of 4096")
        d.stp_priority = priority
        self._refresh_dynamic_routing()

    def set_portfast(self, switch: str, iface: str, enabled: bool) -> None:
        d = self._device(switch)
        if (d.kind != "switch" and not d.config.get("multilayer_switch",False)):
            raise LabError("PortFast requires a switch")
        self._iface(switch, iface).portfast = bool(enabled)

    def set_channel_group(self, switch: str, iface: str, group: int, mode: str) -> None:
        d = self._device(switch)
        if (d.kind != "switch" and not d.config.get("multilayer_switch",False)):
            raise LabError("EtherChannel requires a switch")
        group = int(group)
        if not 1 <= group <= 64:
            raise LabError("channel group must be 1-64")
        mode = mode.lower()
        if mode not in {"on", "active", "passive", "desirable", "auto"}:
            raise LabError("channel mode must be on, active, passive, desirable, or auto")
        p = self._iface(switch, iface)
        p.channel_group = group
        p.channel_mode = mode
        self._refresh_dynamic_routing()

    def clear_channel_group(self, switch: str, iface: str) -> None:
        p = self._iface(switch, iface)
        p.channel_group = None
        p.channel_mode = None
        self._refresh_dynamic_routing()

    def add_static_route(self, device: str, network: str, next_hop: Optional[str] = None, interface: Optional[str] = None) -> None:
        d = self._device(device)
        if d.kind != "router":
            raise LabError("static routes are supported on routers")
        net = str(IPv4Network(network, strict=False))
        if next_hop:
            IPv4Address(next_hop)
        if interface:
            self._iface(device, interface)
        d.routes = [r for r in d.routes if not (r.network == net and r.source == "static")]
        d.routes.append(Route(network=net, next_hop=next_hop, interface=interface, source="static"))

    def enable_ospf(self, device: str, network: Optional[str] = None,
                    area=0, *, automatic=None, process_id=None) -> None:
        from .ospf import configure
        configure(self, device, network, area, automatic=automatic, process_id=process_id)

    def disable_ospf(self, device: str, *, clear=False) -> None:
        from .ospf import disable
        disable(self, device, clear=clear)

    def remove_ospf_network(self, device: str, network: str, area=None) -> None:
        from .ospf import remove_network
        remove_network(self, device, network, area)

    def ospf_status(self, device: str) -> dict:
        from .ospf import status
        return status(self, device)

    def set_helper_address(self, device: str, iface: str, server: Optional[str]) -> None:
        d = self._device(device)
        if d.kind != "router":
            raise LabError("ip helper-address requires a router")
        if server is not None:
            IPv4Address(server)
        self._iface(device, iface).helper_address = server

    def set_discovery_protocol(self, device: str, protocol: str, enabled: bool) -> None:
        d = self._device(device)
        protocol = protocol.lower()
        if protocol == "cdp": d.cdp_enabled = bool(enabled)
        elif protocol == "lldp": d.lldp_enabled = bool(enabled)
        else: raise LabError("protocol must be cdp or lldp")

    def neighbors(self, device: str, protocol: str = "cdp") -> List[dict]:
        d = self._device(device); protocol = protocol.lower()
        if protocol not in {"cdp", "lldp"}: raise LabError("protocol must be cdp or lldp")
        enabled = d.cdp_enabled if protocol == "cdp" else d.lldp_enabled
        if not enabled: return []
        out = []
        for link in self.links:
            if link.a_device == device: local_if, remote, remote_if = link.a_if, link.b_device, link.b_if
            elif link.b_device == device: local_if, remote, remote_if = link.b_if, link.a_device, link.a_if
            else: continue
            rd = self._device(remote)
            remote_enabled = rd.cdp_enabled if protocol == "cdp" else rd.lldp_enabled
            if not remote_enabled: continue
            if protocol == "cdp" and (d.kind not in {"router","switch"} or rd.kind not in {"router","switch"}): continue
            if not self._iface_effective_up(device, local_if) or not self._iface_effective_up(remote, remote_if): continue
            out.append({"device": remote, "local_interface": local_if, "remote_interface": remote_if, "capability": "R" if rd.kind=="router" else "S" if rd.kind=="switch" else "H", "platform": rd.kind})
        return sorted(out, key=lambda x:(x["local_interface"],x["device"]))

    # ---------- ACL / NAT configuration ----------
    @staticmethod
    def _acl_network(value: str) -> str:
        value = value.strip().lower()
        if value == "any":
            return "0.0.0.0/0"
        return str(IPv4Network(value, strict=False))

    def add_acl_rule(self, device: str, name: str, action: str, protocol: str = "ip", src: str = "any", dst: str = "any", sequence: Optional[int] = None, source_port=None, destination_port=None) -> ACLRule:
        d = self._device(device)
        if d.kind != "router":
            raise LabError("ACLs are currently supported on routers")
        action = action.lower(); protocol = protocol.lower()
        if action not in {"permit", "deny"}: raise LabError("ACL action must be permit or deny")
        if protocol not in {"ip", "icmp", "tcp", "udp"}: raise LabError("ACL protocol must be ip, icmp, tcp, or udp")
        from .acl_ports import normalize
        source_port=normalize(source_port);destination_port=normalize(destination_port)
        if (source_port or destination_port) and protocol not in {"tcp","udp"}:raise LabError("port filters require TCP or UDP")
        rules = d.acls.setdefault(str(name), [])
        seq = int(sequence) if sequence is not None else (max((r.sequence for r in rules), default=0) + 10)
        rule = ACLRule(action=action, protocol=protocol, src=self._acl_network(src), dst=self._acl_network(dst), sequence=seq,source_port=source_port,destination_port=destination_port)
        rules[:] = [r for r in rules if r.sequence != seq]
        rules.append(rule); rules.sort(key=lambda r:r.sequence)
        return rule

    def clear_acl(self, device: str, name: str) -> None:
        self._device(device).acls.pop(str(name), None)
        d=self._device(device)
        for i in d.interfaces.values():
            if i.ip_access_group_in == str(name): i.ip_access_group_in = None
            if i.ip_access_group_out == str(name): i.ip_access_group_out = None

    def set_access_group(self, device: str, iface: str, acl: Optional[str], direction: str) -> None:
        d=self._device(device)
        if d.kind != "router": raise LabError("ip access-group currently requires a router")
        p=self._iface(device,iface); direction=direction.lower()
        if direction not in {"in","out"}: raise LabError("ACL direction must be in or out")
        if acl is not None and str(acl) not in d.acls: raise LabError(f"ACL {acl} does not exist")
        if direction == "in": p.ip_access_group_in = None if acl is None else str(acl)
        else: p.ip_access_group_out = None if acl is None else str(acl)

    def acl_permits(self, device: str, acl: str, src: str, dst: str, protocol: str = "ip", source_port=None, destination_port=None) -> bool:
        d=self._device(device); rules=d.acls.get(str(acl))
        if rules is None: return True
        sip,dip=IPv4Address(src),IPv4Address(dst); protocol=protocol.lower()
        for r in sorted(rules,key=lambda x:x.sequence):
            if r.protocol not in {"ip", protocol}: continue
            if sip not in IPv4Network(r.src) or dip not in IPv4Network(r.dst): continue
            from .acl_ports import matches
            if not matches(r.source_port,source_port) or not matches(r.destination_port,destination_port):continue
            return r.action == "permit"
        return False  # IOS implicit deny

    def _acl_interface_permits(self, device: str, iface: Optional[str], direction: str, src: str, dst: str, protocol: str, source_port=None, destination_port=None) -> bool:
        if not iface: return True
        p=self._iface(device,iface)
        acl=p.ip_access_group_in if direction == "in" else p.ip_access_group_out
        return True if not acl else self.acl_permits(device,acl,src,dst,protocol,source_port,destination_port)

    def set_nat_role(self, device: str, iface: str, role: Optional[str]) -> None:
        d=self._device(device)
        if d.kind != "router": raise LabError("NAT roles require a router")
        if role is not None:
            role=role.lower()
            if role not in {"inside","outside"}: raise LabError("NAT role must be inside or outside")
        self._iface(device,iface).nat_role=role

    def add_nat_static(self, device: str, inside_local: str, inside_global: str) -> None:
        d=self._device(device)
        if d.kind != "router": raise LabError("NAT requires a router")
        IPv4Address(inside_local); IPv4Address(inside_global)
        d.nat_static[str(IPv4Address(inside_local))]=str(IPv4Address(inside_global))

    def add_nat_overload(self, device: str, network: str, outside_iface: str) -> None:
        d=self._device(device)
        if d.kind != "router": raise LabError("PAT requires a router")
        net=str(IPv4Network(network,strict=False)); out=self._iface(device,outside_iface)
        if out.nat_role != "outside": raise LabError("PAT interface must be marked ip nat outside")
        if not out.ip: raise LabError("PAT outside interface needs an IPv4 address")
        d.nat_overload=[r for r in d.nat_overload if not (r.get("network")==net and r.get("outside_iface")==outside_iface)]
        d.nat_overload.append({"network":net,"outside_iface":outside_iface})

    def clear_nat(self, device: str) -> None:
        d=self._device(device); d.nat_static.clear(); d.nat_overload.clear(); d.nat_sessions.clear()

    def _nat_inbound(self, device: str, incoming_iface: Optional[str], src: Optional[str], dst: str, protocol: str) -> str:
        d=self._device(device)
        if d.kind != "router" or not incoming_iface or self._iface(device,incoming_iface).nat_role != "outside": return dst
        for local,global_ip in d.nat_static.items():
            if dst == global_ip: return local
        if src:
            local=d.nat_sessions.get(f"{dst}|{src}|{protocol}")
            if local: return local
        return dst

    def _nat_outbound(self, device: str, incoming_iface: Optional[str], outgoing_iface: Optional[str], src: Optional[str], dst: str, protocol: str) -> Optional[str]:
        d=self._device(device)
        if d.kind != "router" or not src or not incoming_iface or not outgoing_iface: return src
        if self._iface(device,incoming_iface).nat_role != "inside" or self._iface(device,outgoing_iface).nat_role != "outside": return src
        if src in d.nat_static:
            return d.nat_static[src]
        sip=IPv4Address(src)
        for rule in d.nat_overload:
            if outgoing_iface == rule.get("outside_iface") and sip in IPv4Network(rule["network"]):
                out=self._iface(device,outgoing_iface)
                if not out.ip: continue
                global_ip=str(out.ipv4.ip)
                d.nat_sessions[f"{global_ip}|{dst}|{protocol}"]=src
                return global_ip
        return src

    def add_dhcp_pool(self, device: str, name: str, network: str, gateway: str, start: str, end: str, dns: Optional[str] = None) -> DHCPPool:
        d = self._device(device)
        if d.kind not in {"router", "server"}:
            raise LabError("DHCP pools are supported on routers and servers")
        net = IPv4Network(network, strict=False)
        gw, first, last = IPv4Address(gateway), IPv4Address(start), IPv4Address(end)
        if gw not in net or first not in net or last not in net or int(first) > int(last):
            raise LabError("gateway and DHCP range must be valid addresses inside the pool network")
        if dns:
            IPv4Address(dns)
        pool = DHCPPool(name=name, network=str(net), gateway=str(gw), start=str(first), end=str(last), dns=dns)
        d.dhcp_pools[name] = pool
        return pool

    def _allocate_dhcp_lease(self, cd: Device, ci: Interface, pool: DHCPPool) -> str:
        net = IPv4Network(pool.network)
        binding=next((d.config.get("dhcp_bindings",{}).get(ci.mac) for d in self.devices.values() if pool in d.dhcp_pools.values() and ci.mac in d.config.get("dhcp_bindings",{})),None)
        if binding:
            if IPv4Address(binding) not in net:raise LabError("DHCP binding is outside pool network")
            pool.leases[ci.mac]=binding
        if ci.mac in pool.leases:
            addr = IPv4Address(pool.leases[ci.mac])
        else:
            used = {IPv4Address(i.ipv4.ip) for d in self.devices.values() for i in d.interfaces.values() if i.ip}
            used |= {IPv4Address(v) for v in pool.leases.values()}
            addr = None
            for raw in range(int(IPv4Address(pool.start)), int(IPv4Address(pool.end)) + 1):
                candidate = IPv4Address(raw)
                if candidate not in used and str(candidate) != pool.gateway:
                    addr = candidate; break
            if addr is None:
                raise LabError(f"DHCP pool {pool.name} is exhausted")
            pool.leases[ci.mac] = str(addr)
        ci.ip = f"{addr}/{net.prefixlen}"
        cd.default_gateway = pool.gateway
        cd.dns_server = pool.dns
        return ci.ip

    def dhcp_request(self, client: str, iface: str) -> str:
        cd = self._device(client); ci = self._iface(client, iface)
        if cd.kind not in {"pc", "server"}:
            raise LabError("DHCP client must be a PC or server")
        # 1) Normal broadcast-domain DHCP.
        for sd in self.devices.values():
            for pool in sd.dhcp_pools.values():
                net = IPv4Network(pool.network)
                for si in sd.interfaces.values():
                    if not si.ip or si.ipv4.ip not in net or not self._iface_effective_up(sd.name, si.name):
                        continue
                    if not self.l2_reachable((client, iface), (sd.name, si.name)):
                        continue
                    lease = self._allocate_dhcp_lease(cd, ci, pool)
                    self.events.append(f"DHCP {client}:{iface} <- {lease} via {sd.name}/{pool.name}")
                    return lease
        # 2) DHCP relay. The client broadcast reaches a router interface with
        # helper-address; giaddr is represented by that interface's IPv4 address.
        for rd in self.devices.values():
            if rd.kind != "router": continue
            for ri in rd.interfaces.values():
                if not ri.helper_address or not ri.ip or not self._iface_effective_up(rd.name, ri.name): continue
                if not self.l2_reachable((client, iface), (rd.name, ri.name)): continue
                helper_owner = self.owner_of_ip(ri.helper_address)
                if not helper_owner: continue
                ok, _ = self._forward(rd.name, ri.helper_address, set(), [])
                if not ok: continue
                sd = self._device(helper_owner[0])
                if not sd.dhcp_pools: continue
                relay_ip = ri.ipv4.ip
                for pool in sd.dhcp_pools.values():
                    if relay_ip not in IPv4Network(pool.network): continue
                    lease = self._allocate_dhcp_lease(cd, ci, pool)
                    self.events.append(f"DHCP-RELAY {client}:{iface} <- {lease} via {rd.name}:{ri.name} helper {ri.helper_address}")
                    return lease
        raise LabError("no reachable DHCP pool or relay found")

    # ---------- routing ----------
    def connected_routes(self, device: str) -> List[Route]:
        d = self._device(device)
        out: List[Route] = []
        for iface in d.interfaces.values():
            if self._iface_effective_up(d.name, iface.name) and iface.ip:
                ipif = iface.ipv4
                assert ipif
                out.append(Route(str(ipif.network), interface=iface.name, source="connected", metric=0))
        return out

    def routing_table(self, device: str) -> List[Route]:
        d = self._device(device)
        routes = self.connected_routes(device) + list(d.routes)
        if d.kind != "router" and d.default_gateway:
            routes.append(Route("0.0.0.0/0", next_hop=d.default_gateway, source="default", metric=1))
        return sorted(routes, key=lambda r: (-IPv4Network(r.network).prefixlen, r.metric, r.network))

    def route_for(self, device: str, dst: str) -> Optional[Route]:
        ip = IPv4Address(dst)
        for route in self.routing_table(device):
            if ip in IPv4Network(route.network):
                return route
        return None

    def recompute_ospf(self) -> None:
        from .special_devices import refresh_wireless
        refresh_wireless(self)
        from .ospf import recompute
        recompute(self)

        from .device_config import recompute_rip
        recompute_rip(self)
        from .eigrp import recompute as recompute_eigrp
        recompute_eigrp(self)

    # ---------- STP / EtherChannel ----------
    def _switch_capable(self,name):
        d=self._device(name)
        return d.kind=="switch" or bool(d.config.get("multilayer_switch"))

    def _bridge_mac(self, switch: str) -> str:
        d = self._device(switch)
        return min((i.mac for i in d.interfaces.values()), default="ff:ff:ff:ff:ff:ff")

    def _bridge_key(self, switch: str, vlan: int = 1) -> Tuple[int, str, str]:
        d = self._device(switch)
        # PVST bridge ID includes the VLAN system-id extension. Keeping it in the
        # comparison makes root selection deterministic while respecting priority.
        return (d.stp_priority + int(vlan), self._bridge_mac(switch), switch)

    def _default_stp_cost(self, iface: str) -> int:
        name = iface.lower()
        if name.startswith("fa"):
            return 19
        if name.startswith("g") or name.startswith("gi"):
            return 4
        return 19

    @staticmethod
    def _channel_modes_compatible(a: Optional[str], b: Optional[str]) -> bool:
        if not a or not b:
            return False
        a, b = a.lower(), b.lower()
        if a == "on" or b == "on":
            return a == b == "on"
        if a in {"active", "passive"} and b in {"active", "passive"}:
            return "active" in {a, b}
        if a in {"desirable", "auto"} and b in {"desirable", "auto"}:
            return "desirable" in {a, b}
        return False

    def _channel_port_operational(self, switch: str, iface: str) -> bool:
        p = self._iface(switch, iface)
        if p.channel_group is None:
            return True
        peer = self.peer(switch, iface)
        if not peer or not self._switch_capable(peer[0]):
            return False
        pp = self._iface(*peer)
        return pp.channel_group is not None and self._channel_modes_compatible(p.channel_mode, pp.channel_mode)

    def etherchannel_summary(self, switch: str) -> List[dict]:
        d = self._device(switch)
        if (d.kind != "switch" and not d.config.get("multilayer_switch",False)):
            raise LabError("EtherChannel summary requires a switch")
        groups: Dict[int, List[Interface]] = {}
        for p in d.interfaces.values():
            if p.channel_group is not None:
                groups.setdefault(p.channel_group, []).append(p)
        out = []
        for group, ports in sorted(groups.items()):
            peers = []
            protocol = "static"
            operational = True
            for p in ports:
                peer = self.peer(switch, p.name)
                if peer:
                    peers.append(peer[0])
                if p.channel_mode in {"active", "passive"}:
                    protocol = "LACP"
                elif p.channel_mode in {"desirable", "auto"}:
                    protocol = "PAgP"
                if not self._channel_port_operational(switch, p.name):
                    operational = False
            out.append({
                "group": group,
                "name": f"Po{group}",
                "protocol": protocol,
                "ports": [p.name for p in ports],
                "modes": {p.name: p.channel_mode for p in ports},
                "peer": sorted(set(peers)),
                "operational": bool(ports) and operational,
            })
        return out

    def _switch_link_base_allows_vlan(self, switch: str, iface: str, vlan: int) -> bool:
        p = self._iface(switch, iface)
        if vlan not in self._device(switch).vlans:
            return False
        if not self._iface_effective_up(switch, iface):
            return False
        if p.channel_group is not None and not self._channel_port_operational(switch, iface):
            return False
        return (p.mode == "access" and p.access_vlan == vlan) or (p.mode == "trunk" and vlan in p.allowed_vlans)

    def _stp_logical_edges(self, vlan: int) -> List[dict]:
        raw = []
        for idx, link in enumerate(self.links):
            a, b = link.a_device, link.b_device
            if not self._switch_capable(a) or not self._switch_capable(b):
                continue
            if not self._switch_link_base_allows_vlan(a, link.a_if, vlan):
                continue
            if not self._switch_link_base_allows_vlan(b, link.b_if, vlan):
                continue
            pa, pb = self._iface(a, link.a_if), self._iface(b, link.b_if)
            if pa.channel_group is not None and pb.channel_group is not None and self._channel_modes_compatible(pa.channel_mode, pb.channel_mode):
                lo, hi = sorted((a, b))
                if a == lo:
                    key = ("po", lo, pa.channel_group, hi, pb.channel_group)
                else:
                    key = ("po", lo, pb.channel_group, hi, pa.channel_group)
            else:
                key = ("link", idx)
            raw.append((key, link))
        grouped: Dict[tuple, List[Link]] = {}
        for key, link in raw:
            grouped.setdefault(key, []).append(link)
        edges = []
        for key, members in grouped.items():
            first = members[0]
            a, b = first.a_device, first.b_device
            costs = []
            for m in members:
                ia, ib = self._iface(m.a_device, m.a_if), self._iface(m.b_device, m.b_if)
                costs.extend([ia.stp_cost or self._default_stp_cost(ia.name), ib.stp_cost or self._default_stp_cost(ib.name)])
            # Bundling increases bandwidth. Approximate IEEE cost by dividing the
            # slowest member cost by member count, with a minimum cost of 1.
            cost = max(1, max(costs or [19]) // max(1, len(members)))
            edges.append({"id": key, "a": a, "b": b, "members": members, "cost": cost})
        return edges

    def spanning_tree(self, vlan: int = 1) -> dict:
        vlan = int(vlan)
        switches = sorted(name for name, d in self.devices.items() if (d.kind == "switch" or d.config.get("multilayer_switch",False)) and d.powered and vlan in d.vlans)
        if not switches:
            return {"vlan": vlan, "root": None, "ports": {}, "root_costs": {}}
        root = min(switches, key=lambda sw: self._bridge_key(sw, vlan))
        edges = self._stp_logical_edges(vlan)
        adj: Dict[str, List[Tuple[str, dict]]] = {sw: [] for sw in switches}
        for e in edges:
            if e["a"] in adj and e["b"] in adj:
                adj[e["a"]].append((e["b"], e)); adj[e["b"]].append((e["a"], e))

        inf = 10**9
        dist = {sw: inf for sw in switches}; dist[root] = 0
        component_roots = {root: root}
        parent_edge: Dict[str, tuple] = {}
        todo = set(switches)
        while todo:
            cur = min(todo, key=lambda sw: (dist[sw], self._bridge_key(sw, vlan)))
            todo.remove(cur)
            if dist[cur] >= inf:
                dist[cur] = 0
                component_roots[cur] = cur
            for other, e in adj[cur]:
                if other not in todo:
                    continue
                cand = dist[cur] + e["cost"]
                old_parent = parent_edge.get(other)
                old_tie = (self._bridge_key(cur, vlan), str(e["id"]))
                if old_parent is not None:
                    old_edge = next((x for x in edges if x["id"] == old_parent), None)
                    old_neighbor = None
                    if old_edge:
                        old_neighbor = old_edge["b"] if old_edge["a"] == other else old_edge["a"]
                    current_tie = (self._bridge_key(old_neighbor, vlan) if old_neighbor else (inf,"", ""), str(old_parent))
                else:
                    current_tie = ((inf, "", ""), "")
                if cand < dist[other] or (cand == dist[other] and old_tie < current_tie):
                    dist[other] = cand
                    component_roots[other] = component_roots[cur]
                    parent_edge[other] = e["id"]

        tree_edges = set(parent_edge.values())
        ports: Dict[str, dict] = {}
        for sw in switches:
            d = self._device(sw)
            for p in d.interfaces.values():
                if p.parent is not None:
                    continue
                if not self._switch_link_base_allows_vlan(sw, p.name, vlan):
                    continue
                peer = self.peer(sw, p.name)
                if not peer or not self._switch_capable(peer[0]):
                    ports[f"{sw}:{p.name}"] = {"role": "designated", "state": "forwarding", "cost": p.stp_cost or self._default_stp_cost(p.name), "portfast": p.portfast}

        for e in edges:
            a, b = e["a"], e["b"]
            if e["id"] in tree_edges:
                # Child side is the root port; parent side is designated.
                if parent_edge.get(a) == e["id"]:
                    roles = {a: "root", b: "designated"}
                elif parent_edge.get(b) == e["id"]:
                    roles = {b: "root", a: "designated"}
                else:
                    roles = {a: "designated", b: "designated"}
                states = {a: "forwarding", b: "forwarding"}
            else:
                ka = (dist.get(a, inf), self._bridge_key(a, vlan), a)
                kb = (dist.get(b, inf), self._bridge_key(b, vlan), b)
                designated = a if ka <= kb else b
                blocked = b if designated == a else a
                roles = {designated: "designated", blocked: "alternate"}
                states = {designated: "forwarding", blocked: "discarding" if self._device(blocked).stp_mode == "rapid-pvst" else "blocking"}
            for m in e["members"]:
                for sw, ifn in ((m.a_device, m.a_if), (m.b_device, m.b_if)):
                    p = self._iface(sw, ifn)
                    ports[f"{sw}:{ifn}"] = {
                        "role": roles[sw], "state": states[sw],
                        "cost": p.stp_cost or self._default_stp_cost(ifn),
                        "portfast": p.portfast,
                        "channel_group": p.channel_group,
                    }
        return {
            "vlan": vlan,
            "root": root,
            "root_bridge_id": self._bridge_key(root, vlan),
            "component_roots": component_roots,
            "root_costs": {sw: (None if cost >= inf else cost) for sw, cost in dist.items()},
            "ports": ports,
        }

    def stp_port_state(self, switch: str, iface: str, vlan: int) -> str:
        d = self._device(switch)
        if (d.kind != "switch" and not d.config.get("multilayer_switch",False)):
            return "forwarding"
        if not self._switch_link_base_allows_vlan(switch, iface, vlan):
            return "disabled"
        current = _forwarding_context.get()
        if current is not None and current[0] is self:
            trees = current[2]
            if vlan not in trees:
                trees[vlan] = self.spanning_tree(vlan)
            st = trees[vlan]
        else:
            st = self.spanning_tree(vlan)
        return st["ports"].get(f"{switch}:{iface}", {"state": "forwarding"})["state"]

    # ---------- L2 + reachability ----------
    def infer_vlan(self, endpoint: Tuple[str, str]) -> int:
        dev, iface = endpoint
        d = self._device(dev)
        p = self._iface(dev, iface)
        if p.bridge_group and p.bridge_group.startswith("vlan"):return int(p.bridge_group[4:])
        if p.encapsulation_vlan is not None:
            return p.encapsulation_vlan
        if (d.kind == "switch" or d.config.get("multilayer_switch",False)):
            return p.access_vlan if p.mode == "access" else p.native_vlan
        peer = self.peer(dev, iface)
        if peer:
            pd = self._device(peer[0])
            pp = self._iface(*peer)
            if (pd.kind == "switch" or pd.config.get("multilayer_switch",False)) and pp.mode == "access":
                return pp.access_vlan
        return 1

    def _iface_effective_up(self, dev: str, iface: str) -> bool:
        p = self._iface(dev, iface)
        if not p.admin_up:
            return False
        physical = p.parent or iface
        if p.parent is not None and not self._iface(dev, p.parent).admin_up:
            return False
        if p.media=="bridge":
            d=self._device(dev)
            return d.powered and any(other.name!=p.name and other.bridge_group==p.bridge_group and self._iface_effective_up(dev,other.name) for other in d.interfaces.values() if other.media!="bridge")
        if p.media not in {"copper","fiber-mm","fiber-sm","serial","wifi","vpn"} and not (p.media in {"modem","coax"} and (self._device(dev).config.get("cloud") or self._device(dev).config.get("pppoe_pending") or self._device(dev).config.get("pppoe_session") or self._device(dev).config.get("dialup_session") or self._device(dev).config.get("dialup_sessions"))):return False
        # Administrative state and line protocol are separate. Carrier depends
        # on both devices' power, both ports and the physical copper media.
        link = self.link_for(dev, physical)
        return link is not None and self.link_operational(link)

    def _port_allows_vlan(self, dev: str, iface: str, vlan: int) -> bool:
        d, p = self._device(dev), self._iface(dev, iface)
        if not self._iface_effective_up(dev, iface):
            return False
        if p.media=="bridge" and p.bridge_group=="vlan"+str(vlan):return True
        if d.config.get("multilayer_switch") and p.parent is not None and p.encapsulation_vlan==vlan:return self._port_allows_vlan(dev,p.parent,vlan)
        if (d.kind == "switch" or d.config.get("multilayer_switch",False)):
            if not self._switch_link_base_allows_vlan(dev, iface, vlan):
                return False
            if iface in d.config.get("rep_ports",{}):
                from .industrial_switching import rep_forwarding
                return rep_forwarding(self,dev,iface)
            return self.stp_port_state(dev, iface, vlan) in {"forwarding", "learning"}
        if p.encapsulation_vlan is not None:
            return p.encapsulation_vlan == vlan
        if d.kind == "router":
            if any(child.parent == iface and child.encapsulation_vlan == vlan and child.admin_up for child in d.interfaces.values()):
                return True
        return self.infer_vlan((dev, iface)) == vlan

    @_scoped_forwarding
    def l2_path(self, start: Tuple[str, str], goal: Tuple[str, str]) -> Optional[List[Tuple[str, str]]]:
        self._iface(*start); self._iface(*goal)
        vlan = self.infer_vlan(start)
        if self.infer_vlan(goal) != vlan:
            return None
        queue = [start]
        seen = {start}
        previous: Dict[Tuple[str, str], Optional[Tuple[str, str]]] = {start: None}
        while queue:
            cur = queue.pop(0)
            if cur == goal:
                path: List[Tuple[str, str]] = []
                node: Optional[Tuple[str, str]] = cur
                while node is not None:
                    path.append(node); node = previous[node]
                return list(reversed(path))
            dev, iface = cur
            if not self._iface_effective_up(dev, iface):
                continue
            candidates: List[Tuple[str, str]] = []
            peer = self.peer(dev, iface)
            if peer and self._port_allows_vlan(*peer, vlan):
                candidates.append(peer)
            d = self._device(dev)
            if (d.kind == "switch" or d.config.get("multilayer_switch",False)) and self._port_allows_vlan(dev, iface, vlan):
                from .special_devices import cloud_allows
                candidates.extend((dev, other_name) for other_name in d.interfaces if self._port_allows_vlan(dev, other_name, vlan) and cloud_allows(d,iface,other_name))
            elif d.kind == "router" or d.model == "7960":
                p = self._iface(dev, iface)
                if p.bridge_group:
                    candidates.extend((dev,other.name) for other in d.interfaces.values() if other.bridge_group==p.bridge_group and self._port_allows_vlan(dev,other.name,vlan))
                if p.parent is None:
                    candidates.extend((dev, child.name) for child in d.interfaces.values() if child.parent == iface and child.encapsulation_vlan == vlan and self._port_allows_vlan(dev, child.name, vlan))
            for other in candidates:
                if other not in seen:
                    seen.add(other); previous[other] = cur; queue.append(other)
        return None

    def l2_reachable(self, start: Tuple[str, str], goal: Tuple[str, str]) -> bool:
        return self.l2_path(start, goal) is not None

    def _learn_l2_exchange(self, start: Tuple[str, str], goal: Tuple[str, str], source_ip: Optional[str] = None, target_ip: Optional[str] = None) -> None:
        path = self.l2_path(start, goal)
        if not path:
            return
        vlan = self.infer_vlan(start)
        src_if = self._iface(*start); dst_if = self._iface(*goal)
        if source_ip and target_ip:
            self._device(start[0]).arp_table[target_ip] = dst_if.mac
            self._device(goal[0]).arp_table[source_ip] = src_if.mac
        learned_switches: Set[str] = set()
        for dev, iface in path:
            if self._switch_capable(dev) and dev not in learned_switches:
                self._device(dev).mac_table[f"{vlan}:{src_if.mac}"] = iface
                learned_switches.add(dev)
        learned_switches.clear()
        for dev, iface in reversed(path):
            if self._switch_capable(dev) and dev not in learned_switches:
                self._device(dev).mac_table[f"{vlan}:{dst_if.mac}"] = iface
                learned_switches.add(dev)

    def owner_of_ip(self, ip: str) -> Optional[Tuple[str, str]]:
        target = IPv4Address(ip)
        for d in self.devices.values():
            for iface in d.interfaces.values():
                if iface.ip and iface.ipv4.ip == target:
                    return d.name, iface.name
        # Static NAT globals behave like addresses owned by the NAT router on its
        # outside segment, even when they are not configured directly on the port.
        for d in self.devices.values():
            if d.kind != "router" or str(target) not in d.nat_static.values(): continue
            for iface in d.interfaces.values():
                if iface.nat_role == "outside" and iface.ip and target in iface.ipv4.network:
                    return d.name, iface.name
            for iface in d.interfaces.values():
                if iface.nat_role == "outside": return d.name, iface.name
        from .industrial_switching import alias_owner
        return alias_owner(self,target)

    def _source_ip_for_destination(self, source: str, target_ip: str) -> Optional[str]:
        route = self.route_for(source, target_ip)
        if not route:
            return None
        d = self._device(source)
        if route.interface:
            iface = self._iface(source, route.interface)
            if iface.ip:
                return str(iface.ipv4.ip)
        if route.next_hop:
            nh = IPv4Address(route.next_hop)
            for iface in d.interfaces.values():
                if self._iface_effective_up(source, iface.name) and iface.ip and nh in iface.ipv4.network:
                    return str(iface.ipv4.ip)
        for iface in d.interfaces.values():
            if self._iface_effective_up(source, iface.name) and iface.ip:
                return str(iface.ipv4.ip)
        return None

    def ping(self, source: str, target_ip: str) -> Tuple[bool, str]:
        result = self.ping_detailed(source, target_ip)
        # Historically a queued ping is a successfully submitted command.
        return result["status"] != "failed", result["message"]

    @_scoped_forwarding
    def ping_detailed(self, source: str, target_ip: str) -> dict:
        """Run the same ping as the CLI and return its versioned outcome."""
        from .connectivity import ping
        return ping(self, source, target_ip)

    @_scoped_forwarding
    def traceroute(self, source: str, target_ip: str) -> Tuple[bool, str]:
        IPv4Address(target_ip)
        source_ip = self._source_ip_for_destination(source, target_ip)
        if not source_ip:
            return False, f"TRACEROUTE failed\n{source} -> no-route"
        meta={"translated_source":source_ip,"final_destination":target_ip}
        ok, trace = self._forward(source, target_ip, set(), [], source_ip, "icmp", None, meta)
        return ok, "TRACEROUTE " + ("complete" if ok else "failed") + "\n" + " -> ".join(trace)

    def _forward(self, device: str, dst: str, visited: Set[str], trace: List[str], src: Optional[str] = None, protocol: str = "ip", incoming_iface: Optional[str] = None, meta: Optional[dict] = None) -> Tuple[bool, List[str]]:
        if meta is None: meta={}
        diagnostic = meta.get("_diagnostic")
        if diagnostic is not None:
            diagnostic["hops"].append(device)
        def fail(code: str, marker: str, **details) -> Tuple[bool, List[str]]:
            if diagnostic is not None:
                diagnostic["reason"] = {"code": code, "device": device, **details}
            return False, trace + [marker]
        if src is not None: meta.setdefault("translated_source",src)
        if device in visited:
            return fail("routing_loop", f"{device}(routing-loop)")
        visited = set(visited); visited.add(device)
        trace = trace + [device]
        d = self._device(device)
        # Inbound ACL sees the packet as it arrived on the interface.
        if src and incoming_iface and d.kind == "router" and not self._acl_interface_permits(device, incoming_iface, "in", src, dst, protocol,meta.get("source_port"),meta.get("destination_port")):
            return fail("acl_in_denied", f"ACL-in-deny({incoming_iface})", interface=incoming_iface)
        # Translate an outside destination before the route lookup.
        if d.kind == "router":
            from .port_forwarding import inbound
            dst=inbound(self,d,incoming_iface,src,dst,protocol,meta)
            translated_dst=self._nat_inbound(device,incoming_iface,src,dst,protocol)
            if translated_dst != dst:
                dst=translated_dst; meta["final_destination"]=dst
        if src:
            from .access_services import host_permits
            if not host_permits(d,src,dst,protocol):return fail("host_firewall_denied", "host-firewall-deny")
        owner = self.owner_of_ip(dst)
        if owner and owner[0] == device:
            meta["final_owner"]=device; meta["final_destination"]=dst
            return True, trace
        if d.kind=="router" and incoming_iface is not None and "ttl" in meta:
            meta["ttl"]-=1
            if meta["ttl"]<=0:return fail("ttl_expired", "TTL-expired")
        route = self.route_for(device, dst)
        if not route:
            return fail("no_route", "no-route")
        if route.source == "connected":
            out_if = self._iface(device, route.interface)
            if d.kind == "router":
                from .port_forwarding import outbound
                src=outbound(d,src,dst,protocol,meta)
                new_src=self._nat_outbound(device,incoming_iface,out_if.name,src,dst,protocol)
                if new_src != src:
                    src=new_src; meta["translated_source"]=src
            if src and d.kind == "router" and not self._acl_interface_permits(device, out_if.name, "out", src, dst, protocol,meta.get("source_port"),meta.get("destination_port")):
                return fail("acl_out_denied", f"ACL-out-deny({out_if.name})", interface=out_if.name)
            target = self.owner_of_ip(dst)
            if not target:
                return fail("destination_unassigned", "no-host")
            if self._iface_effective_up(device, out_if.name) and self.l2_reachable((device, out_if.name), target):
                self._learn_l2_exchange((device, out_if.name), target, str(out_if.ipv4.ip) if out_if.ip else None, dst)
                if target[0] == device:
                    meta["final_owner"]=device; meta["final_destination"]=dst
                    return True, trace
                from .industrial_switching import translate
                src,dst=translate(self,(device,out_if.name),target,src,dst,meta)
                return self._forward(target[0], dst, visited, trace, src, protocol, target[1], meta)
            return fail("l2_unreachable", "L2-unreachable", interface=out_if.name)
        next_hop = route.next_hop
        if not next_hop:
            return fail("invalid_route", "invalid-route")
        nh_owner = self.owner_of_ip(next_hop)
        if not nh_owner:
            return fail("next_hop_missing", f"next-hop-{next_hop}-missing", next_hop=next_hop)
        for iface in d.interfaces.values():
            if self._iface_effective_up(device, iface.name) and iface.ip and IPv4Address(next_hop) in iface.ipv4.network:
                if self.l2_reachable((device, iface.name), nh_owner):
                    if d.kind == "router":
                        from .port_forwarding import outbound
                        src=outbound(d,src,dst,protocol,meta)
                        new_src=self._nat_outbound(device,incoming_iface,iface.name,src,dst,protocol)
                        if new_src != src:
                            src=new_src; meta["translated_source"]=src
                    if src and d.kind == "router" and not self._acl_interface_permits(device, iface.name, "out", src, dst, protocol,meta.get("source_port"),meta.get("destination_port")):
                        return fail("acl_out_denied", f"ACL-out-deny({iface.name})", interface=iface.name)
                    self._learn_l2_exchange((device, iface.name), nh_owner, str(iface.ipv4.ip), next_hop)
                    return self._forward(nh_owner[0], dst, visited, trace, src, protocol, nh_owner[1], meta)
        return fail("next_hop_unreachable", f"next-hop-{next_hop}-unreachable", next_hop=next_hop)

    # ---------- persistence ----------
    def to_dict(self) -> dict:
        light_cache={}
        return {
            "workspace_tools":deepcopy(self.workspace_tools),
            "activity":deepcopy(self.activity),
            "version": 1,
            "devices": {name: self._device_to_dict(d) for name, d in self.devices.items()},
            "links": [{**asdict(l), "lights":__import__("netsim.hardware",fromlist=["lights"]).lights(self,l,light_cache),"up": self.link_operational(l),
                       "status": self.link_status(l)["reason"]} for l in self.links],
            "notes": {name: dict(note) for name, note in self.notes.items()},
            "clusters": {key: {"id":c["id"],"name":c["name"],"devices":list(c["devices"]),"parent":c["parent"]} for key,c in self.clusters.items()},
            "physical_locations": {key:dict(loc) for key,loc in self.physical_locations.items()},
            "device_locations": dict(self.device_locations),
            "physical_device_details": {key:dict(value) for key,value in self.physical_device_details.items()},
            "physical_shelves":dict(self.physical_shelves),
            "physical_grids":{kind:dict(profile) for kind,profile in self.physical_grids.items()},
            "cable_length_effects":self.cable_length_effects,
            "radio_ranges":dict(self.radio_ranges),
            "visual_assets":{key:dict(value) for key,value in self.visual_assets.items()},
            "cluster_icons":dict(self.cluster_icons),
            "device_icons":{key:dict(value) for key,value in self.device_icons.items()},
            "location_backgrounds":{key:dict(value) for key,value in self.location_backgrounds.items()},
            "cable_routes":{name:{"color":r["color"],"bends":[dict(b) for b in r["bends"]]}
                           for name,r in self.cable_routes.items()},
            "icp_panels":{key:{"size":v["size"],"door_closed":v["door_closed"],"workspace_mode":v["workspace_mode"],
                               "fixtures":{f:dict(item) for f,item in v["fixtures"].items()},
                               "mounts":dict(v["mounts"]),"anchors":dict(v["anchors"])}
                          for key,v in self.icp_panels.items()},
            "events": list(self.events[-200:]),
            "simulation":deepcopy(self.simulation),
            "packet_events": list(self.packet_events), "packet_counter": self.packet_counter,
        }

    def _device_to_dict(self, d: Device) -> dict:
        return {
            "name": d.name, "kind": d.kind, "model": d.model, "x": d.x, "y": d.y, "powered": d.powered,
            "interfaces": {n: asdict(i) for n, i in d.interfaces.items()},
            "config":deepcopy(d.config),
            "modules": dict(d.modules),
            "default_gateway": d.default_gateway, "dns_server": d.dns_server,
            "dns_enabled": d.dns_enabled, "dns_records": dict(d.dns_records),
            "http_enabled": d.http_enabled, "http_pages": dict(d.http_pages),
            "routes": [asdict(r) for r in d.routes if r.source not in {"ospf","rip","eigrp"}],
            "vlans": sorted(d.vlans), "ospf_enabled": d.ospf_enabled,
            "ospf_networks": list(d.ospf_networks), "ospf_auto": d.ospf_auto,
            "ospf_areas": dict(d.ospf_areas), "ospf_process_id": d.ospf_process_id,
            "stp_mode": d.stp_mode, "stp_priority": d.stp_priority,
            "cdp_enabled": d.cdp_enabled, "lldp_enabled": d.lldp_enabled,
            "dhcp_pools": {name: asdict(pool) for name, pool in d.dhcp_pools.items()},
            "arp_table": dict(d.arp_table), "mac_table": dict(d.mac_table),
            "acls": {name: [asdict(r) for r in rules] for name, rules in d.acls.items()},
            "nat_static": dict(d.nat_static), "nat_overload": list(d.nat_overload), "nat_sessions": dict(d.nat_sessions),
        }

    def save(self, path: str) -> None:
        Path(path).write_text(json.dumps(self.to_dict(), indent=2))

    def load(self, path: str) -> None:
        data = json.loads(Path(path).read_text())
        self.devices = {}
        for name, raw in data.get("devices", {}).items():
            d = Device(name=name, kind=raw["kind"], model=raw.get("model", ""), x=raw.get("x", 200), y=raw.get("y", 160))
            d.powered = bool(raw.get("powered", True))
            from .device_config import validate_saved
            d.config=validate_saved(raw.get("config",{}))
            d.interfaces = {n: Interface(**v) for n, v in raw.get("interfaces", {}).items()}
            from .hardware import validate_port
            for p in d.interfaces.values():validate_port(p)
            raw_modules=raw.get("modules",{})
            if not isinstance(raw_modules,dict):raise LabError("modules must be an object")
            d.modules={}
            for slot,module in raw_modules.items():
                if slot not in slots_for(d) or module not in MODULE_TYPES:
                    raise LabError("invalid saved module slot or type")
                names=interfaces_for(slot,module)
                if any(name not in d.interfaces for name in names):
                    raise LabError("saved module ports missing from device")
                d.modules[slot]=module

            d.default_gateway = raw.get("default_gateway")
            d.dns_server = raw.get("dns_server")
            d.dns_enabled = bool(raw.get("dns_enabled", False))
            d.dns_records = dict(raw.get("dns_records", {}))
            d.http_enabled = bool(raw.get("http_enabled", True))
            d.http_pages = dict(raw.get("http_pages", d.http_pages))
            d.routes = [Route(**r) for r in raw.get("routes", [])]
            d.vlans = set(raw.get("vlans", [1]))
            d.ospf_enabled = raw.get("ospf_enabled", False)
            d.ospf_networks = list(raw.get("ospf_networks", []))
            from .ospf import load_config
            load_config(d, raw)
            d.stp_mode = raw.get("stp_mode", "pvst")
            d.stp_priority = int(raw.get("stp_priority", 32768))
            d.cdp_enabled = bool(raw.get("cdp_enabled", True))
            d.lldp_enabled = bool(raw.get("lldp_enabled", False))
            d.dhcp_pools = {n: DHCPPool(**v) for n, v in raw.get("dhcp_pools", {}).items()}
            d.arp_table = dict(raw.get("arp_table", {})); d.mac_table = dict(raw.get("mac_table", {}))
            d.acls = {n: [ACLRule(**r) for r in rules] for n, rules in raw.get("acls", {}).items()}
            d.nat_static = dict(raw.get("nat_static", {})); d.nat_overload = list(raw.get("nat_overload", [])); d.nat_sessions = dict(raw.get("nat_sessions", {}))
            self.devices[name] = d
        self.clusters={}
        raw_clusters=data.get("clusters",{})
        if not isinstance(raw_clusters,dict):raise LabError("clusters must be an object")
        members=set()
        for ident,c in raw_clusters.items():
            if not re.fullmatch(r"Cluster[0-9]+",ident) or not isinstance(c,dict) or c.get("id")!=ident:
                raise LabError("invalid cluster ID")
            devices=c.get("devices",[])
            if not isinstance(devices,list) or any(not isinstance(d,str) or d not in self.devices for d in devices):
                raise LabError("cluster contains unknown device")
            if len(set(devices))!=len(devices) or members.intersection(devices):
                raise LabError("device belongs to multiple clusters")
            members.update(devices)
            name=c.get("name")
            if not isinstance(name,str) or not 1<=len(name.strip())<=64 or any(ord(ch)<32 for ch in name):
                raise LabError("invalid cluster name")
            self.clusters[ident]={"id":ident,"name":name.strip(),"parent":c.get("parent"),"devices":list(devices)}
        for ident in self.clusters:
            visited=set()
            cursor=ident
            while cursor is not None:
                if cursor in visited or cursor not in self.clusters:
                    raise LabError("cluster parent cycle or missing parent")
                visited.add(cursor)
                cursor=self.clusters[cursor]["parent"]
        self.notes = {}
        for ident, raw in data.get("notes", {}).items():
            if not re.fullmatch(r"Note[0-9]+", ident) or not isinstance(raw, dict):
                raise LabError("invalid saved note ID")
            x, y = self._note_position(raw["x"], raw["y"])
            txt = raw["text"]
            if not isinstance(txt, str) or not txt.strip() or len(txt) > 800:
                raise LabError("invalid saved note text")
            self.notes[ident] = {"x": x, "y": y, "text": txt}
        self.links = [Link(**{key: raw[key] for key in ("a_device", "a_if", "b_device", "b_if", "cable") if key in raw})
                      for raw in data.get("links", [])]
        # Older saved labs lacked physical-placement data. Migrate without changing links or addresses.
        raw_locations=data.get("physical_locations")
        if raw_locations is None:
            self.physical_locations=self._initial_physical_locations()
        else:
            if not isinstance(raw_locations,dict):
                raise LabError("physical_locations must be an object")
            locations={}
            for key,raw in raw_locations.items():
                if not re.fullmatch(r"[a-zA-Z][a-zA-Z0-9_-]{0,39}",key) or not isinstance(raw,dict):
                    raise LabError("invalid physical location ID")
                if raw.get("id")!=key or raw.get("type") not in self.PHYSICAL_DEFAULTS:
                    raise LabError("invalid physical location")
                x,y=self._physical_coordinates(raw.get("x",28),raw.get("y",24))
                dims=self._physical_dimensions(*(raw.get(d,v) for d,v in zip(("width","length","height"),self.PHYSICAL_DEFAULTS[raw["type"]])))
                locations[key]={"id":key,"type":raw["type"],"name":self._physical_name(raw.get("name")),
                                "parent":raw.get("parent"),"x":x,"y":y,
                                "width":dims[0],"length":dims[1],"height":dims[2]}
            for key,loc in locations.items():
                parent=loc["parent"]
                parent_kind="intercity" if parent is None else locations.get(parent,{}).get("type")
                self._location_fits(loc["type"],tuple(loc[d] for d in ("width","length","height")),locations.get(parent))
                cursor=parent
                visited={key}
                while cursor is not None:
                    if cursor in visited or cursor not in locations:raise LabError("invalid physical location cycle")
                    visited.add(cursor);cursor=locations[cursor]["parent"]
            self.physical_locations=locations
        from .physical_grid import load_profiles
        self.physical_grids=load_profiles(data.get("physical_grids",{}))
        raw_placements=data.get("device_locations",{})
        if not isinstance(raw_placements,dict):
            raise LabError("device_locations must be an object")
        if any(n not in self.devices for n in raw_placements):
            raise LabError("physical placement references an unknown device")
        self.device_locations={}
        for name,d in self.devices.items():
            default="closet0" if d.kind in {"router","switch"} else "building0"
            if default not in self.physical_locations:default="intercity"
            choice=raw_placements.get(name, default)
            if choice!="intercity" and choice not in self.physical_locations:
                raise LabError(f"invalid physical placement for {name}")
            self.device_locations[name]=choice
        raw_shelves=data.get("physical_shelves",{})
        if not isinstance(raw_shelves,dict):raise LabError("physical shelves must be an object")
        self.physical_shelves={key:0 for key,loc in self.physical_locations.items() if loc["type"]=="closet"}
        for key,count in raw_shelves.items():
            if key not in self.physical_shelves or isinstance(count,bool) or not isinstance(count,int) or not 0<=count<=20:
                raise LabError("invalid shelf count")
            self.physical_shelves[key]=count
        raw_details=data.get("physical_device_details",{})
        if not isinstance(raw_details,dict) or any(name not in self.devices for name in raw_details):
            raise LabError("invalid device physical placement records")
        self.physical_device_details={}
        for name,d in self.devices.items():
            location=self.device_locations[name]
            defaults=self._physical_placement_default(d.kind,location)
            raw=raw_details.get(name,{})
            if not isinstance(raw,dict):raise LabError("invalid device physical placement")
            x,y=self._physical_coordinates(raw.get("x",defaults["x"]),raw.get("y",defaults["y"]))
            surface=raw.get("surface",defaults["surface"]);shelf=raw.get("shelf")
            self.physical_device_details[name]={"x":x,"y":y,"surface":"floor","shelf":None}
            self.physical_mount_device(name,surface,shelf)
        value=data.get("cable_length_effects",False)
        if not isinstance(value,bool):raise LabError("cable_length_effects must be true or false")
        self.cable_length_effects=value
        saved_ranges=data.get("radio_ranges",{})
        if not isinstance(saved_ranges,dict):raise LabError("radio_ranges must be an object")
        from .physical_distance import radio_default
        self.radio_ranges={}
        for name,radius in saved_ranges.items():
            if name not in self.devices or radio_default(self.devices[name].model or "") is None:
                raise LabError("radio range references an unsupported device")
            if isinstance(radius,bool) or not isinstance(radius,(float,int)) or not math.isfinite(radius) or not 0.1<=radius<=100000:
                raise LabError("invalid saved radio range")
            self.radio_ranges[name]=float(radius)
        from .visual_customization import load_visuals,load_assignments
        load_visuals(self,data.get("visual_assets",{}))
        load_assignments(self,data.get("device_icons",{}),
                         data.get("location_backgrounds",{}))
        from .visual_customization import set_cluster_icon
        self.cluster_icons={}
        icons=data.get("cluster_icons",{})
        if not isinstance(icons,dict):raise LabError("invalid cluster icons")
        for ident,asset in icons.items():set_cluster_icon(self,ident,asset)
        from .cable_manipulation import validate_load as load_cable_routes
        load_cable_routes(self,data.get("cable_routes",{}))
        from .icp import validate_load as load_icp
        load_icp(self,data.get("icp_panels",{}))
        from .workspace_tools import validate
        self.workspace_tools=validate(data.get("workspace_tools",{}))
        for group in self.workspace_tools["diagram"]["groups"].values():
            if any(name not in self.devices for name in group["members"]):
                raise LabError("unknown device in diagram group")
        from .activity import validate_activity
        self.activity=validate_activity(data.get("activity"))
        self.events = list(data.get("events", []))[-200:]
        self.packet_events = list(data.get("packet_events", []))[-256:]
        self.packet_counter = int(data.get("packet_counter", len(self.packet_events)))
        from .simulation import load as load_simulation
        self.simulation=load_simulation(self,data.get("simulation"))
        self.recompute_ospf()

    # ---------- helpers ----------
    def _device(self, name: str) -> Device:
        if name not in self.devices:
            raise LabError(f"unknown device {name}")
        return self.devices[name]

    def _iface(self, device: str, iface: str) -> Interface:
        d = self._device(device)
        if iface not in d.interfaces:
            raise LabError(f"unknown interface {device}:{iface}")
        return d.interfaces[iface]

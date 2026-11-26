from __future__ import annotations

import json
import shlex
from copy import deepcopy
from ipaddress import IPv4Network
from .model import LabError, NetworkLab
from .ios import IOSSession
from .capabilities import capability_text
from .device_catalog import CATALOG, MODELS, get_model

HELP = """Commands:
  workspace-tool <JSON-action> (viewport, accessibility, template_capture/import/instantiate/delete)
  visual cluster-icon <cluster> <asset-id|default>
  add <pc|server|switch|router|generic> <name> [x y]
  add-model <model-id> <name> [x y]
  add-in-cluster <model-id|kind> <name> <x> <y> <cluster-id>
  catalog [category|subtype]
  remove <name>
  duplicate <name1,name2,...> <dx> <dy>
  remove-group <name1,name2,...>
  move-group <name1,name2,...> <dx> <dy>
  undo
  redo
  note add <x> <y> <text>\n  note edit <note-id> <text>\n  note move <note-id> <x> <y>\n  note delete <note-id>\n  rename <old-name> <new-name>
  connect <dev1> <if1> <dev2> <if2>
  auto-connect <dev1> <dev2>
  disconnect <device> <iface>
  ip <device> <iface> <address/prefix>
  subif <router> <parent-if> <vlan-id> <address/prefix>
  up|down <device> <iface>
  gateway <device> <ipv4>
  vlan <switch> <vlan-id>
  switchport <switch> <iface> access <vlan-id>
  switchport <switch> <iface> trunk <vlan1,vlan2,...>
  native-vlan <switch> <iface> <vlan-id>
  stp <switch> mode <pvst|rapid-pvst>
  stp <switch> priority <0..61440>
  portfast <switch> <iface> <on|off>
  channel <switch> <iface> <group> <on|active|passive|desirable|auto>
  no-channel <switch> <iface>
  route <router> <prefix> via <next-hop>
  route <router> <prefix> dev <interface>
  ospf <router> enable [network/prefix [area <id>]]
  ospf <router> auto|disable|clear|remove <network/prefix>
  show ospf <router>
  dhcp-pool <router|server> <name> <network> <gateway> <start> <end> [dns]
  dhcp <pc|server> <iface>
  helper <router> <iface> <dhcp-server-ip|none>
  acl <router> <name> <permit|deny> <ip|icmp|tcp|udp> <src-prefix|any> <dst-prefix|any> [sequence]
  no-acl <router> <name>
  access-group <router> <iface> <acl|none> <in|out>
  nat-role <router> <iface> <inside|outside|none>
  nat-static <router> <inside-local> <inside-global>
  nat-overload <router> <inside-network> <outside-iface>
  nat-clear <router>
  cdp <device> <on|off>
  lldp <device> <on|off>
  ping <source-device> <destination-ip>
  traceroute <source-device> <destination-ip>
  ios <device> <ios-command...>
  move <device> <x> <y>
  physical add <city|building|closet|generic> <name> [parent-id]
  physical add-device <model> <name> <logical-x> <logical-y> <location> [physical-x physical-y]
  physical grid <intercity|city|building|generic> <on|off> <spacing-m> <#RRGGBB>
  physical delete-preview <location-id>
  physical delete <location-id>
  physical rename <location-id> <name>
  physical position <location-id> <x> <y>
  physical place <device> <location-id|intercity>
  physical move-devices <device1,device2,...> <destination-id|intercity>
  physical dimensions <location-id> <width-m> <length-m> <height-m>
  physical relocate <location-id> <new-parent-id|intercity>
  physical device-position <device> <x> <y>
  physical shelf-add <closet-id>
  physical mount <device> <rack|table|floor|shelf> [shelf-index]
  physical measure <device1> <device2>
  physical cable-length <device> <interface>
  physical cable-effects <on|off>
  physical radio-range <source-device> <radius-m>
  physical radio-status [location-id|intercity]
  visual upload <image/png|image/jpeg> <base64-bytes> [label]
  visual import <local-png-or-jpg-path> [label]
  visual icon <device> <logical|physical> <asset-sha256|default>
  visual background <location|intercity> <asset-sha256|default> <tile|fit> <#RRGGBB>
  visual delete <asset-sha256>
  cable bend-add <device> <port> <x-m> <y-m> [after-bend-id]
  cable bend-move <device> <port> <bend-id> <x-m> <y-m>
  cable bend-delete <device> <port> <bend-id>
  cable color <device> <port> <#RRGGBB>
  cable group <device> <port> <bend-id> <other-device> <port> <bend-id>
  cable group-move <group-id> <x-m> <y-m>
  cable ungroup <group-id> [device port]
  icp create <small|medium|large> <name> <parent|intercity>
  icp door <location> <on=closed|off=open>
  icp preview <location> <on|off>
  icp device-move <device> <door|cabinet> <x> <y> <anchor-0..5> <attached|detach>
  icp fixture-add <location> <din|wic> <horizontal|vertical> <x> <y>
  icp fixture-move <location> <fixture> <x> <y> <attached|detach>
  icp fixture-join <location> <fixture1> <fixture2>
  icp fixture-split <location> <fixture>
  icp fixture-delete <location> <fixture>
  icp mount <device> <din-fixture>
  icp unmount <device>
  cluster add <name> <device1,device2|none> [parent-id|root]
  cluster place <device> <cluster-id|root>
  cluster move <cluster-id> <parent-id|root>
  cluster rename <cluster-id> <name>
  cluster delete <cluster-id>
  show clusters
  show physical
  show topology
  show interfaces [device]
  show routes <device>
  show arp <device>
  show mac <switch>
  show spanning-tree <switch> [vlan-id]
  show etherchannel <switch>
  show cdp <device>
  show lldp <device>
  show acl <router> [name]
  show nat <router>
  show dhcp <router|server>
  dns-client <pc|server> <DNS-server-ip|none>
  dns-service <server> <on|off>
  dns-add <server> <hostname> <ipv4>
  dns-delete <server> <hostname>
  http-service <server> <on|off>
  http-page <server> <path> "<HTML text>"
  web-get <pc> <http://host/path>
  pdu <source-device> <destination-device>
  show dns <server>
  show http <server>
  show packet-events
  show vlans <switch>
  show links\n  show notes\n  show json
  capabilities [device-type|device-name]
  save <path>
  load <path>
  reset
  help

Agent interface:
  sample load|check <id>       Load an undoable practice lab or check current topology
  simulation '<JSON>'           Authoritative mode/scenario/PDU/capture action
  device-config '<JSON>'        Authoritative device/hardware/service action
  ./netlab exec 'add router R1'
  ./netlab exec 'show json'
  curl -s localhost:8765/api/state
  curl -s -X POST localhost:8765/api/command -H 'content-type: application/json' -d '{"command":"ping PC1 10.0.0.1"}'
"""


class CommandProcessor:
    HISTORY_LIMIT=64
    EDIT_COMMANDS={
        "enterprise","exercise","incident","sample","device-config","ios","simulation","workspace-tool","module","add","add-model","add-in-cluster","duplicate","remove","remove-group","rename","connect","auto-connect","disconnect",
        "move","move-group","physical","visual","cable","icp","note","cluster","ip","subif","up","down","gateway",
        "vlan","switchport","native-vlan","stp","portfast","channel","no-channel",
        "route","ospf","dhcp-pool","dhcp","helper","acl","no-acl","access-group",
        "nat-role","nat-static","nat-overload","nat-clear","cdp","lldp","power",
        "power-cycle","dns-client","dns-service","dns-add","dns-delete",
        "http-service","http-page","reset","load"
    }

    def __init__(self, lab: NetworkLab):
        self.lab = lab
        self.ios_sessions: dict[str, IOSSession] = {}
        self._undo_stack: list[dict] = []
        self._redo_stack: list[dict] = []

    def _restore_snapshot(self,snapshot:dict)->None:
        # Keep the NetworkLab identity: IOS and API clients share this same object.
        self.lab.__dict__.clear()
        self.lab.__dict__.update(deepcopy(snapshot))
        self.ios_sessions.clear()

    def _history_operation(self,cmd:str)->str:
        if cmd=="undo":
            if not self._undo_stack: return "Nothing to undo"
            before=deepcopy(self.lab.__dict__)
            after=self._undo_stack.pop()
            self._redo_stack.append(before)
            self._restore_snapshot(after)
            return "Undo completed"
        if not self._redo_stack: return "Nothing to redo"
        before=deepcopy(self.lab.__dict__)
        after=self._redo_stack.pop()
        self._undo_stack.append(before)
        self._restore_snapshot(after)
        return "Redo completed"

    def execute(self, line: str) -> str:
        line = line.strip()
        if not line:
            return ""
        try:
            argv = shlex.split(line)
        except ValueError as e:
            return f"ERROR: {e}"
        before=None
        try:
            cmd=argv[0].lower()
            if cmd in {"undo","redo"}:
                if len(argv)!=1: raise LabError(f"{cmd} takes no arguments")
                return self._history_operation(cmd)
            tracked=cmd in self.EDIT_COMMANDS
            before=deepcopy(self.lab.__dict__) if tracked else None
            output=self._execute(argv)
            if tracked and before!=self.lab.__dict__:
                if self.lab.simulation["mode"]=="simulation" and cmd in {"add","add-model","remove","remove-group","connect","auto-connect","disconnect","ip","up","down","power","power-cycle","route","ospf","acl","access-group","module","gateway"}:
                    from .simulation import reset
                    reset(self.lab)
                self._undo_stack.append(before)
                self._undo_stack=self._undo_stack[-self.HISTORY_LIMIT:]
                self._redo_stack.clear()
            return output
        except (LabError, ValueError, KeyError) as e:
            if before is not None and before!=self.lab.__dict__:self._restore_snapshot(before)
            return f"ERROR: {e}"
        except Exception as e:
            if before is not None and before!=self.lab.__dict__:self._restore_snapshot(before)
            return f"ERROR: {type(e).__name__}: {e}"

    def _execute(self, a: list[str]) -> str:
        cmd = a[0].lower()
        if cmd in {"help", "?"}:
            return HELP
        if cmd in {"capabilities", "capability", "describe"}:
            return capability_text(a[1] if len(a) > 1 else None, self.lab)
        if cmd=='sample' and len(a)==3:
            from .samples import load,check
            if a[1]=='load':
                output=load(self.lab,a[2]);self.ios_sessions.clear();return output
            if a[1]=='check':return json.dumps(check(self.lab,a[2]))
            raise LabError('sample action must be load or check')
        if cmd=="enterprise" and len(a)==2:
            from .enterprise_training import action
            return json.dumps(action(self.lab,json.loads(a[1])))
        if cmd=="exercise" and len(a)==2:
            from .exercise_runner import action
            return json.dumps(action(self.lab,json.loads(a[1])))
        if cmd=="incident" and len(a)==2:
            from .incident_cases import action
            body=json.loads(a[1])
            if not isinstance(body,dict):raise LabError("incident action must be an object")
            return json.dumps(action(self.lab,body))
        if cmd=="device-config" and len(a)==2:
            from .device_config import action
            return json.dumps(action(self.lab,json.loads(a[1])))
        if cmd=="simulation" and len(a)==2:
            from .simulation import action
            return json.dumps(action(self.lab,json.loads(a[1])))
        if cmd=="workspace-tool" and len(a)==2:
            from .workspace_tools import command
            return json.dumps(command(self.lab,json.loads(a[1])))
        if cmd == "reset":
            self.lab.reset(); self.ios_sessions.clear()
            return "lab reset"
        if cmd == "note":
            if len(a) == 5 and a[1] == "add":
                ident = self.lab.add_note(float(a[2]), float(a[3]), a[4])
                return "added note " + ident
            if len(a) == 4 and a[1] == "edit":
                self.lab.update_note(a[2], a[3]); return "updated note " + a[2]
            if len(a) == 5 and a[1] == "move":
                self.lab.move_note(a[2], float(a[3]), float(a[4])); return "moved note " + a[2]
            if len(a) == 3 and a[1] == "delete":
                self.lab.remove_note(a[2]); return "deleted note " + a[2]
            raise LabError("usage: note add <x> <y> <text> | note edit/move/delete <note-id> ...")
        if cmd == "add-in-cluster" and len(a) == 6:
            spec_name,name,x,y,cluster=a[1],a[2],float(a[3]),float(a[4]),a[5]
            if cluster not in self.lab.clusters:
                raise LabError("unknown logical cluster")
            if spec_name in {"pc","server","switch","router","generic"}:
                d=self.lab.add_device(spec_name,name,x,y)
            else:
                spec=get_model(spec_name)
                d=self.lab.add_device(spec["kind"],name,x,y,model=spec["id"])
            self.lab.place_in_cluster(name,cluster)
            return f"added {d.name} in cluster {cluster}"
        if cmd == "add" and len(a) >= 3:
            x, y = (float(a[3]), float(a[4])) if len(a) >= 5 else (200, 160)
            d = self.lab.add_device(a[1], a[2], x, y)
            return f"added {d.kind} {d.name}"
        if cmd == "add-model" and len(a) >= 3:
            spec = get_model(a[1])
            x, y = (float(a[3]), float(a[4])) if len(a) >= 5 else (200, 160)
            d = self.lab.add_device(spec["kind"], a[2], x, y, model=spec["id"])
            return f"added {spec['label']} as {d.name} ({spec['support']})"
        if cmd == "catalog":
            q = " ".join(a[1:]).strip().lower()
            rows = []
            for spec in MODELS.values():
                if q and q not in spec["category"].lower() and q not in spec["subtype"].lower() and q not in spec["label"].lower():
                    continue
                rows.append(f"{spec['id']:<26} {spec['label']:<28} {spec['subtype']:<20} {spec['support']}")
            return "Model ID                   Label                        Group                Support\n" + "\n".join(rows)
        if cmd=="cluster" and len(a)>=2:
            sub=a[1].lower()
            if sub=="add" and len(a) in {4,5}:
                members=[] if a[3] in {"-","none"} else a[3].split(",")
                parent=None if len(a)==4 or a[4].lower()=="root" else a[4]
                ident=self.lab.add_cluster(a[2],members,parent)
                return f"created cluster {ident}"
            if sub=="rename" and len(a)==4:
                self.lab.rename_cluster(a[2],a[3]);return "cluster renamed"
            if sub=="place" and len(a)==4:
                self.lab.place_in_cluster(a[2],None if a[3].lower()=="root" else a[3])
                return "device moved into cluster"
            if sub=="move" and len(a)==4:
                self.lab.move_cluster(a[2],None if a[3].lower()=="root" else a[3])
                return "cluster moved"
            if sub=="delete" and len(a)==3:
                self.lab.delete_cluster(a[2]);return "cluster deleted (devices preserved)"
            raise LabError("cluster add <name> <device1,device2|none> [parent-id|root] | cluster place <device> <id|root> | cluster move <id> <parent-id|root> | cluster rename <id> <name> | cluster delete <id>")
        if cmd == "visual" and len(a)>=2:
            from .visual_customization import add_asset,set_icon,set_background,discard_asset
            verb=a[1].lower()
            if verb=="import" and len(a) in {3,4}:
                from pathlib import Path
                import base64
                file=Path(a[2])
                if not file.is_file() or file.stat().st_size>1_000_000:
                    raise LabError("image file must exist and be at most 1MB")
                mime={".gif":"image/gif",".png":"image/png",".jpg":"image/jpeg",".jpeg":"image/jpeg"}.get(file.suffix.lower())
                if mime is None:raise LabError("image file must be .png or .jpg")
                ident=add_asset(self.lab,mime,base64.b64encode(file.read_bytes()).decode("ascii"),
                                a[3] if len(a)==4 else file.name)
                return "visual asset uploaded "+ident
            if verb=="upload" and len(a) in {4,5}:
                ident=add_asset(self.lab,a[2],a[3],a[4] if len(a)==5 else "")
                return "visual asset uploaded "+ident
            if verb=="cluster-icon" and len(a)==4:
                from .visual_customization import set_cluster_icon
                set_cluster_icon(self.lab,a[2],None if a[3]=="default" else a[3])
                return "cluster icon updated"
            if verb=="icon" and len(a)==5:
                ident=None if a[4]=="default" else a[4]
                set_icon(self.lab,a[2],a[3],ident)
                return f"visual icon {a[2]} {a[3]} "+("reset" if ident is None else "updated")
            if verb=="background" and len(a)==6:
                if a[4] not in {"tile","fit"}:raise LabError("background mode must be tile or fit")
                ident=None if a[3]=="default" else a[3]
                set_background(self.lab,a[2],ident,a[4]=="tile",a[5])
                return f"background {a[2]} "+("reset" if ident is None else "updated")
            if verb=="delete" and len(a)==3:
                discard_asset(self.lab,a[2])
                return "visual asset deleted "+a[2]
            raise LabError("visual upload|icon|background|delete: see visual help")
        if cmd == "cable" and len(a)>=2:
            from . import cable_manipulation as cables
            verb=a[1].lower()
            if verb=="bend-add" and len(a) in {6,7}:
                ident=cables.add_bend(self.lab,a[2],a[3],float(a[4]),float(a[5]),a[6] if len(a)==7 else None)
                return "cable bend created "+ident
            if verb=="bend-move" and len(a)==7:
                cables.move_bend(self.lab,a[2],a[3],a[4],float(a[5]),float(a[6]))
                return "cable bend moved "+a[4]
            if verb=="bend-delete" and len(a)==5:
                cables.delete_bend(self.lab,a[2],a[3],a[4])
                return "cable bend deleted "+a[4]
            if verb=="color" and len(a)==5:
                cables.set_color(self.lab,a[2],a[3],a[4])
                return "cable colored "+a[4]
            if verb=="group" and len(a)==8:
                ident=cables.group_bends(self.lab,a[2],a[3],a[4],a[5],a[6],a[7])
                return "cable bends grouped "+ident
            if verb=="group-move" and len(a)==5:
                cables.move_group(self.lab,a[2],float(a[3]),float(a[4]))
                return "cable group moved "+a[2]
            if verb=="ungroup" and len(a) in {3,5}:
                removed=cables.ungroup(self.lab,a[2],a[3] if len(a)==5 else None,a[4] if len(a)==5 else None)
                return "ungrouped "+str(removed)+" bend point(s)"
            raise LabError("cable bend-add|bend-move|bend-delete|color|group|group-move|ungroup")
        if cmd == "icp" and len(a)>=2:
            from . import icp
            task=a[1].lower()
            if task=="create" and len(a)==5:
                ident=icp.create(self.lab,a[3],a[4],a[2])
                return "created ICP "+ident
            if task=="door" and len(a)==4:
                if a[3] not in {"on","off"}:raise LabError("door expects on (closed) or off (open)")
                icp.set_door(self.lab,a[2],a[3]=="on")
                return "ICP door "+("closed" if a[3]=="on" else "opened")
            if task=="preview" and len(a)==4:
                if a[3] not in {"on","off"}:raise LabError("preview expects on or off")
                icp.preview(self.lab,a[2],a[3]=="on")
                return "ICP preview "+a[3]
            if task=="device-move" and len(a)==8:
                if a[7] not in {"detach","attached"}:raise LabError("move expects detach or attached")
                icp.move_device(self.lab,a[2],a[3],float(a[4]),float(a[5]),int(a[6]),a[7]=="detach")
                return "ICP device moved "+a[2]
            if task=="fixture-add" and len(a)==7:
                ident=icp.add_fixture(self.lab,a[2],a[3],a[4],float(a[5]),float(a[6]))
                return "ICP fixture added "+ident
            if task=="fixture-move" and len(a)==7:
                if a[6] not in {"detach","attached"}:raise LabError("fixture move expects detach or attached")
                icp.move_fixture(self.lab,a[2],a[3],float(a[4]),float(a[5]),a[6]=="detach")
                return "ICP fixture moved "+a[3]
            if task=="fixture-join" and len(a)==5:
                group=icp.join_fixtures(self.lab,a[2],a[3],a[4])
                return "ICP fixture strip "+group
            if task=="fixture-split" and len(a)==4:
                icp.split_fixture(self.lab,a[2],a[3])
                return "ICP fixture split "+a[3]
            if task=="fixture-delete" and len(a)==4:
                icp.delete_fixture(self.lab,a[2],a[3])
                return "ICP fixture deleted "+a[3]
            if task=="mount" and len(a)==4:
                icp.mount(self.lab,a[2],a[3])
                return "ICP device DIN mounted "+a[2]
            if task=="unmount" and len(a)==3:
                icp.unmount(self.lab,a[2])
                return "ICP device unmounted "+a[2]
            raise LabError("icp create|door|preview|device-move|fixture-add|fixture-move|fixture-join|fixture-split|fixture-delete|mount|unmount")
        if cmd == "physical" and len(a)>=2:
            action=a[1].lower()
            if action=="grid" and len(a)==6:
                from .physical_grid import set_profile
                if a[3] not in {"on","off"}:raise LabError("grid requires on or off")
                set_profile(self.lab,a[2],a[3]=="on",float(a[4]),a[5])
                return f"updated {a[2]} grid"
            if action=="delete-preview" and len(a)==3:
                return json.dumps(self.lab.physical_delete_preview(a[2]))
            if action=="delete" and len(a)==3:
                preview=self.lab.delete_physical_location(a[2])
                return f"deleted {a[2]}; extracted {len(preview['extracted_devices'])} device(s) to {preview['destination']}"
            if action=="add-device" and len(a) in {7,9}:
                model,name=a[2],a[3]
                x,y=self.lab._physical_coordinates(float(a[4]),float(a[5]))
                location=a[6]
                if location!="intercity":self.lab._physical_location(location)
                if name in self.lab.devices:raise LabError("device already exists")
                px,py=(self.lab._physical_coordinates(float(a[7]),float(a[8])) if len(a)==9 else (None,None))
                if model in {"pc","server","switch","router","generic"}:
                    d=self.lab.add_device(model,name,x,y)
                else:
                    spec=get_model(model)
                    d=self.lab.add_device(spec["kind"],name,x,y,model=spec["id"])
                self.lab.place_physical_device(name,location)
                if px is not None:self.lab.physical_device_position(name,px,py)
                return f"created {d.name} at {self.lab.physical_path(location)}"
            if action=="add" and len(a) in {4,5}:
                ident=self.lab.add_physical_location(a[2],a[3],a[4] if len(a)==5 else "intercity")
                return f"created physical location {ident}: {self.lab.physical_path(ident)}"
            if action=="rename" and len(a)==4:
                self.lab.rename_physical_location(a[2],a[3])
                return f"renamed {a[2]} to {a[3]}"
            if action=="position" and len(a)==5:
                self.lab.move_physical_location(a[2],float(a[3]),float(a[4]))
                return f"moved location {a[2]} to {a[3]},{a[4]}"
            if action=="place" and len(a)==4:
                self.lab.place_physical_device(a[2],a[3])
                return f"placed {a[2]} at {self.lab.physical_path(a[3])}"
            if action=="move-devices" and len(a)==4:
                names=a[2].split(",")
                self.lab.move_physical_devices(names,a[3])
                return f"moved {len(names)} physical device(s) to {self.lab.physical_path(a[3])}"
            if action=="dimensions" and len(a)==6:
                self.lab.resize_physical_location(a[2],float(a[3]),float(a[4]),float(a[5]))
                return f"resized physical location {a[2]}"
            if action=="relocate" and len(a)==4:
                self.lab.relocate_physical_location(a[2],a[3])
                return f"relocated physical location {a[2]}"
            if action=="device-position" and len(a)==5:
                self.lab.physical_device_position(a[2],float(a[3]),float(a[4]))
                return f"positioned physical device {a[2]}"
            if action=="shelf-add" and len(a)==3:
                ident=self.lab.physical_shelf_add(a[2])
                return f"created shelf {ident} in {a[2]}"
            if action=="mount" and len(a) in {4,5}:
                self.lab.physical_mount_device(a[2],a[3],int(a[4]) if len(a)==5 else None)
                return f"mounted {a[2]} on {a[3]}"
            if action=="cable-effects" and len(a)==3:
                if a[2] not in {"on","off"}:raise LabError("cable-effects expects on or off")
                self.lab.set_cable_length_effects(a[2]=="on")
                return "cable length effects "+a[2]
            if action=="radio-range" and len(a)==4:
                self.lab.set_radio_range(a[2],float(a[3]))
                return f"radio range for {a[2]} set to {float(a[3]):g}m"
            if action=="measure" and len(a)==4:
                from .physical_distance import distance_m
                return f"straight-line distance {a[2]} to {a[3]}: {distance_m(self.lab,a[2],a[3]):.4f} meters"
            if action=="cable-length" and len(a)==4:
                from .physical_distance import cable_length
                link=self.lab.link_for(a[2],a[3])
                if link is None:raise LabError("no cable on that interface")
                value=cable_length(self.lab,link)
                return f"{link.a_device}:{link.a_if} to {link.b_device}:{link.b_if}: {value['total_length_m']:.4f}m; 100m max; effects {'on' if value['enforced'] else 'off'}"
            if action=="radio-status" and len(a) in {2,3}:
                from .physical_distance import physics_status
                return json.dumps(physics_status(self.lab,a[2] if len(a)==3 else "intercity"))
            raise LabError("physical add <city|building|closet|generic> <name> [parent-id] | physical rename/position/relocate/dimensions | physical place/device-position/mount/shelf-add")
        if cmd == "rename" and len(a) == 3:
            self.lab.rename_device(a[1], a[2])
            if a[1] in self.ios_sessions:
                session = self.ios_sessions.pop(a[1]); session.device = a[2]
                self.ios_sessions[a[2]] = session
            return f"renamed {a[1]} to {a[2]}"
        if cmd=="duplicate" and len(a)==4:
            mapping=self.lab.duplicate_devices(a[1].split(","),float(a[2]),float(a[3]))
            return "duplicated "+", ".join(f"{a} -> {b}" for a,b in mapping.items())
        if cmd=="remove-group" and len(a)==2:
            self.lab.remove_group(a[1].split(","))
            return "group removed"
        if cmd=="move-group" and len(a)==4:
            self.lab.move_group(a[1].split(","),float(a[2]),float(a[3]))
            return "group moved"
        if cmd == "remove" and len(a) == 2:
            self.lab.remove_device(a[1]); return f"removed {a[1]}"
        if cmd == "connect" and len(a) in {5, 6}:
            self.lab.connect(a[1], a[2], a[3], a[4], a[5] if len(a) == 6 else "auto")
            return "link created"
        if cmd == "auto-connect" and len(a) == 3:
            link = self.lab.auto_connect(a[1], a[2])
            return f"link created: {link.a_device}:{link.a_if} <-> {link.b_device}:{link.b_if} ({link.cable})"
        if cmd == "power-cycle" and len(a) == 1:
            self.lab.power_cycle_all()
            return "All devices restarted; dynamic tables cleared"
        if cmd=="module" and len(a)==4:
            self.lab.set_module(a[1],a[2],None if a[3].lower()=="none" else a[3])
            return f"module {a[1]}:{a[2]} set to {a[3]}"
        if cmd == "power" and len(a) == 3:
            if a[2].lower() not in {"on", "off"}:
                raise LabError("power value must be on or off")
            self.lab.set_power(a[1], a[2].lower() == "on")
            return f"{a[1]} powered {a[2].lower()}"
        if cmd == "disconnect" and len(a) == 3:
            self.lab.disconnect(a[1], a[2]); return "link removed"
        if cmd == "ip" and len(a) == 4:
            self.lab.set_ip(a[1], a[2], a[3]); self.lab.recompute_ospf(); return f"{a[1]}:{a[2]} = {a[3]}"
        if cmd == "subif" and len(a) == 5:
            i = self.lab.add_subinterface(a[1], a[2], int(a[3]), a[4]); return f"{a[1]}:{i.name} dot1q {a[3]} = {a[4]}"
        if cmd in {"up", "down"} and len(a) == 3:
            self.lab.set_interface_state(a[1], a[2], cmd == "up"); self.lab.recompute_ospf(); return f"{a[1]}:{a[2]} {cmd}"
        if cmd == "gateway" and len(a) == 3:
            self.lab.set_gateway(a[1], a[2]); return f"default gateway {a[2]}"
        if cmd == "vlan" and len(a) == 3:
            self.lab.add_vlan(a[1], int(a[2])); return f"VLAN {a[2]} created on {a[1]}"
        if cmd == "switchport" and len(a) >= 5:
            if a[3] == "access":
                self.lab.set_switchport_access(a[1], a[2], int(a[4])); return f"{a[1]}:{a[2]} access vlan {a[4]}"
            if a[3] == "trunk":
                vlans = [int(x) for x in a[4].split(",") if x]
                self.lab.set_switchport_trunk(a[1], a[2], vlans); return f"{a[1]}:{a[2]} trunk {','.join(map(str, vlans))}"
        if cmd == "native-vlan" and len(a) == 4:
            self.lab.set_native_vlan(a[1], a[2], int(a[3])); return f"{a[1]}:{a[2]} native vlan {a[3]}"
        if cmd == "stp" and len(a) == 4:
            if a[2] == "mode":
                self.lab.set_stp_mode(a[1], a[3]); return f"{a[1]} STP mode {self.lab._device(a[1]).stp_mode}"
            if a[2] == "priority":
                self.lab.set_stp_priority(a[1], int(a[3])); return f"{a[1]} STP priority {a[3]}"
        if cmd == "portfast" and len(a) == 4:
            enabled = a[3].lower() in {"on", "enable", "enabled", "true", "1"}
            if a[3].lower() not in {"on", "off", "enable", "disable", "enabled", "disabled", "true", "false", "1", "0"}:
                raise LabError("portfast value must be on or off")
            self.lab.set_portfast(a[1], a[2], enabled); return f"{a[1]}:{a[2]} PortFast {'on' if enabled else 'off'}"
        if cmd == "channel" and len(a) == 5:
            self.lab.set_channel_group(a[1], a[2], int(a[3]), a[4]); return f"{a[1]}:{a[2]} channel-group {a[3]} mode {a[4]}"
        if cmd == "no-channel" and len(a) == 3:
            self.lab.clear_channel_group(a[1], a[2]); return f"{a[1]}:{a[2]} removed from EtherChannel"
        if cmd == "route" and len(a) == 5:
            IPv4Network(a[2], strict=False)
            if a[3] == "via":
                self.lab.add_static_route(a[1], a[2], next_hop=a[4]); return "static route added"
            if a[3] == "dev":
                self.lab.add_static_route(a[1], a[2], interface=a[4]); return "static route added"
        if cmd == "ospf":
            if len(a) in (3, 4, 6) and a[2] == "enable":
                if len(a) == 6 and a[4].lower() != "area":
                    raise LabError("usage: ospf <router> enable [network/prefix [area <id>]]")
                self.lab.enable_ospf(a[1], a[3] if len(a) >= 4 else None,
                                     a[5] if len(a) == 6 else 0)
                return f"OSPF enabled on {a[1]}"
            if len(a) == 3 and a[2] == "auto":
                self.lab.enable_ospf(a[1], automatic=True)
                return f"OSPF automatic area 0 enabled on {a[1]}"
            if len(a) == 3 and a[2] in ("disable", "clear"):
                self.lab.disable_ospf(a[1], clear=a[2] == "clear")
                return f"OSPF {'disabled' if a[2] == 'disable' else 'cleared'} on {a[1]}"
            if len(a) == 4 and a[2] == "remove":
                self.lab.remove_ospf_network(a[1], a[3])
                return f"OSPF network removed from {a[1]}"
            raise LabError("usage: ospf <router> enable [network/prefix [area <id>]] | auto | disable | clear | remove <network/prefix>")
        if cmd == "dhcp-pool" and len(a) in {7, 8}:
            p = self.lab.add_dhcp_pool(a[1], a[2], a[3], a[4], a[5], a[6], a[7] if len(a) == 8 else None); return f"DHCP pool {p.name} {p.network} range {p.start}-{p.end}"
        if cmd == "dns-client" and len(a) == 3:
            self.lab.set_dns_client(a[1], None if a[2].lower() in {"none","off"} else a[2])
            return f"{a[1]} DNS server {self.lab._device(a[1]).dns_server or 'unset'}"
        if cmd == "dns-service" and len(a) == 3:
            if a[2].lower() not in {"on", "off"}: raise LabError("DNS service value must be on or off")
            self.lab.dns_service(a[1], a[2].lower() == "on")
            return f"{a[1]} DNS {a[2].lower()}"
        if cmd == "dns-add" and len(a) == 4:
            self.lab.dns_record(a[1], a[2], a[3])
            return f"DNS A {a[2]} -> {a[3]} on {a[1]}"
        if cmd == "dns-delete" and len(a) == 3:
            self.lab.dns_delete(a[1], a[2])
            return "DNS record deleted"
        if cmd == "http-service" and len(a) == 3:
            if a[2].lower() not in {"on", "off"}: raise LabError("HTTP service value must be on or off")
            self.lab.http_service(a[1], a[2].lower() == "on")
            return f"{a[1]} HTTP {a[2].lower()}"
        if cmd == "http-page" and len(a) == 4:
            self.lab.set_http_page(a[1], a[2], a[3])
            return f"HTTP page {a[2]} updated on {a[1]}"
        if cmd == "web-get" and len(a) == 3:
            result = self.lab.http_request(a[1], a[2])
            return f"HTTP {result['status']} {result['resolved_ip']} from {result['server']}\n{result['html']}"
        if cmd == "pdu" and len(a) == 3:
            result = self.lab.send_simple_pdu(a[1], a[2])
            return f"ICMP PDU {result['status']}: {result['message']}"
        if cmd == "dhcp" and len(a) == 3:
            addr = self.lab.dhcp_request(a[1], a[2]); return f"DHCP lease {a[1]}:{a[2]} = {addr}"
        if cmd == "helper" and len(a) == 4:
            value = None if a[3].lower() in {"none", "off", "remove"} else a[3]
            self.lab.set_helper_address(a[1], a[2], value); return f"{a[1]}:{a[2]} helper {value or 'removed'}"
        if cmd == "acl" and len(a) in {7, 8}:
            rule = self.lab.add_acl_rule(a[1], a[2], a[3], a[4], a[5], a[6], int(a[7]) if len(a) == 8 else None)
            return f"ACL {a[2]} seq {rule.sequence} {rule.action} {rule.protocol} {rule.src} {rule.dst}"
        if cmd == "no-acl" and len(a) == 3:
            self.lab.clear_acl(a[1], a[2]); return f"ACL {a[2]} removed"
        if cmd == "access-group" and len(a) == 5:
            acl = None if a[3].lower() in {"none","remove","off"} else a[3]
            self.lab.set_access_group(a[1], a[2], acl, a[4]); return f"{a[1]}:{a[2]} access-group {acl or 'none'} {a[4]}"
        if cmd == "nat-role" and len(a) == 4:
            role=None if a[3].lower() in {"none","off","remove"} else a[3]
            self.lab.set_nat_role(a[1],a[2],role); return f"{a[1]}:{a[2]} NAT role {role or 'none'}"
        if cmd == "nat-static" and len(a) == 4:
            self.lab.add_nat_static(a[1],a[2],a[3]); return f"static NAT {a[2]} -> {a[3]}"
        if cmd == "nat-overload" and len(a) == 4:
            self.lab.add_nat_overload(a[1],a[2],a[3]); return f"PAT {a[2]} overload {a[3]}"
        if cmd == "nat-clear" and len(a) == 2:
            self.lab.clear_nat(a[1]); return f"NAT cleared on {a[1]}"
        if cmd in {"cdp", "lldp"} and len(a) == 3:
            if a[2].lower() not in {"on", "off"}: raise LabError(f"{cmd} value must be on or off")
            self.lab.set_discovery_protocol(a[1], cmd, a[2].lower() == "on"); return f"{cmd.upper()} {'enabled' if a[2].lower() == 'on' else 'disabled'} on {a[1]}"
        if cmd == "ping" and len(a) == 3:
            ok, text = self.lab.ping(a[1], a[2]); return text
        if cmd == "traceroute" and len(a) == 3:
            ok, text = self.lab.traceroute(a[1], a[2]); return text
        if cmd == "ios" and len(a) >= 3:
            dev = a[1]
            self.lab._device(dev)
            session = self.ios_sessions.get(dev)
            if session is None:
                session = self.ios_sessions[dev] = IOSSession(self.lab, dev)
            return session.execute(" ".join(a[2:]))
        if cmd == "move" and len(a) == 4:
            self.lab.move_device(a[1], float(a[2]), float(a[3]))
            return "moved"
        if cmd == "save" and len(a) == 2:
            self.lab.save(a[1]); return f"saved {a[1]}"
        if cmd == "load" and len(a) == 2:
            self.lab.load(a[1]); return f"loaded {a[1]}"
        if cmd == "show":
            return self._show(a[1:])
        raise LabError("unknown or malformed command; run 'help'")

    def _show(self, a: list[str]) -> str:
        if not a:
            raise LabError("show requires an object")
        what = a[0].lower()
        if what == "ospf" and len(a) == 2:
            return json.dumps(self.lab.ospf_status(a[1]), indent=2)
        if what=="clusters" and len(a)==1:
            if not self.lab.clusters:return "(no logical workspace clusters)"
            return "\n".join(f"{id}: {c['name']} | parent={c['parent'] or 'Root'} | devices={','.join(c['devices']) or '-'}"
                               for id,c in self.lab.clusters.items())
        if what=="physical" and len(a)==1:
            out=["PHYSICAL WORKSPACE (placements are informational; links are logical)"]
            for ident,loc in self.lab.physical_locations.items():
                out.append(f"  {ident:<12} {loc['type']:<9} {self.lab.physical_path(ident)}")
            out.append("DEVICES")
            for name in sorted(self.lab.devices):
                out.append(f"  {name:<12} {self.lab.device_locations.get(name,'intercity'):<12} {self.lab.physical_path(self.lab.device_locations.get(name,'intercity'))}")
            return "\n".join(out)
        if what == "notes" and len(a) == 1:
            return "\\n".join(f"{name}: ({n['x']}, {n['y']}) {n['text']}" for name,n in sorted(self.lab.notes.items())) or "(no notes)"
        if what == "json":
            return json.dumps(self.lab.to_dict(), indent=2)
        if what == "topology":
            if not self.lab.devices:
                return "(empty lab)"
            lines = ["DEVICES"]
            for d in self.lab.devices.values():
                ips = [f"{i.name}={i.ip}" for i in d.interfaces.values() if i.ip]
                lines.append(f"  {d.name:<10} {d.kind:<7} {(d.model or '-'):<24} {' '.join(ips)}")
            lines.append("LINKS")
            lines.extend(f"  {l.a_device}:{l.a_if} <-> {l.b_device}:{l.b_if}" for l in self.lab.links)
            return "\n".join(lines)
        if what == "links":
            return "\n".join(f"{l.a_device}:{l.a_if} <-> {l.b_device}:{l.b_if} [{l.cable} {'up' if self.lab.link_operational(l) else 'down'}]" for l in self.lab.links) or "(no links)"
        if what == "interfaces":
            names = [a[1]] if len(a) > 1 else list(self.lab.devices)
            out = []
            for name in names:
                d = self.lab._device(name)
                out.append(f"{name} ({d.kind})")
                out.append("Interface      State  IPv4                 Mode/VLAN")
                for i in d.interfaces.values():
                    extra = f"{i.mode}/{i.access_vlan if i.mode == 'access' else ','.join(map(str, i.allowed_vlans))}" if d.kind == "switch" else "-"
                    out.append(f"{i.name:<14} {'up' if i.admin_up else 'down':<6} {(i.ip or '-'):20} {extra}")
            return "\n".join(out)
        if what in {"routes", "route"} and len(a) == 2:
            out = [f"Routing table for {a[1]}", "Code  Prefix              Next-hop           Interface  Metric"]
            codes = {"connected":"C", "static":"S", "default":"S*", "ospf":"O"}
            for r in self.lab.routing_table(a[1]):
                out.append(f"{codes.get(r.source,'?'):<5} {r.network:<19} {(r.next_hop or '-'):18} {(r.interface or '-'):10} {r.metric}")
            return "\n".join(out)
        if what == "arp" and len(a) == 2:
            d = self.lab._device(a[1])
            if not d.arp_table: return "(ARP table empty)"
            return "\n".join([f"ARP table for {d.name}", "IPv4             MAC"] + [f"{ip:<16} {mac}" for ip, mac in sorted(d.arp_table.items())])
        if what == "mac" and len(a) == 2:
            d = self.lab._device(a[1])
            if d.kind != "switch": raise LabError("show mac requires a switch")
            if not d.mac_table: return "(MAC address table empty)"
            rows=[f"MAC table for {d.name}", "VLAN  MAC                Port"]
            for key, port in sorted(d.mac_table.items()):
                vlan, mac = key.split(':', 1); rows.append(f"{vlan:<5} {mac:<18} {port}")
            return "\n".join(rows)
        if what in {"spanning-tree", "stp"} and len(a) in {2, 3}:
            sw = a[1]; vlan = int(a[2]) if len(a) == 3 else 1
            d = self.lab._device(sw)
            if d.kind != "switch": raise LabError("show spanning-tree requires a switch")
            st = self.lab.spanning_tree(vlan)
            if st["root"] is None: return f"VLAN {vlan}: no spanning-tree instance"
            root_cost = st["root_costs"].get(sw)
            out = [f"Spanning tree for {sw} VLAN {vlan}", f"Mode: {d.stp_mode}", f"Root: {st.get('component_roots', {}).get(sw, st['root'])}  Root cost: {root_cost if root_cost is not None else '-'}", f"Bridge priority: {d.stp_priority}", "Interface      Role        State        Cost  Channel  PortFast"]
            for key, info in sorted(st["ports"].items()):
                dev, ifn = key.split(':',1)
                if dev != sw: continue
                ch = f"Po{info.get('channel_group')}" if info.get('channel_group') else "-"
                out.append(f"{ifn:<14} {info['role']:<11} {info['state']:<12} {info.get('cost','-')!s:<5} {ch:<8} {'yes' if info.get('portfast') else 'no'}")
            return "\n".join(out)
        if what == "etherchannel" and len(a) == 2:
            groups = self.lab.etherchannel_summary(a[1])
            if not groups: return "(no EtherChannel groups)"
            out=[f"EtherChannel summary for {a[1]}", "Group  Port-channel  Protocol  State  Ports"]
            for g in groups:
                state = "SU" if g['operational'] else "SD"
                ports = ','.join(f"{p}({g['modes'].get(p)})" for p in g['ports'])
                out.append(f"{g['group']:<6} {g['name']:<13} {g['protocol']:<9} {state:<5} {ports}")
            return "\n".join(out)
        if what in {"acl", "acls", "access-lists"} and len(a) in {2,3}:
            d=self.lab._device(a[1])
            if d.kind != "router": raise LabError("show acl requires a router")
            names=[a[2]] if len(a)==3 else sorted(d.acls)
            if not names: return "(no access lists)"
            out=[]
            for name in names:
                rules=d.acls.get(name,[])
                out.append(f"Access list {name}")
                for r in rules: out.append(f"  {r.sequence:<5} {r.action:<6} {r.protocol:<5} {r.src:<18} {r.dst}")
            return "\n".join(out)
        if what == "nat" and len(a) == 2:
            d=self.lab._device(a[1])
            if d.kind != "router": raise LabError("show nat requires a router")
            out=[f"NAT on {d.name}"]
            roles=[f"  {i.name}: {i.nat_role}" for i in d.interfaces.values() if i.nat_role]
            out.extend(roles or ["  (no inside/outside interfaces)"])
            for local,glob in sorted(d.nat_static.items()): out.append(f"  static {local} -> {glob}")
            for rule in d.nat_overload: out.append(f"  overload {rule['network']} -> interface {rule['outside_iface']}")
            for key,local in sorted(d.nat_sessions.items()): out.append(f"  dynamic {local} -> {key.split('|',1)[0]} ({key})")
            return "\n".join(out)
        if what in {"cdp", "lldp"} and len(a) == 2:
            proto=what.upper(); rows=[f"{proto} neighbors for {a[1]}", "Device       Local Intf   Capability  Platform  Port ID"]
            for n in self.lab.neighbors(a[1], what): rows.append(f"{n['device']:<12} {n['local_interface']:<12} {n['capability']:<11} {n['platform']:<9} {n['remote_interface']}")
            return "\n".join(rows) if len(rows)>2 else f"(no {proto} neighbors)"
        if what == "dns" and len(a) == 2:
            d=self.lab._device(a[1])
            return ("DNS " + ("enabled" if d.dns_enabled else "disabled") + "\n" +
                    "\n".join(f"  {name} A {ip}" for name,ip in sorted(d.dns_records.items())))
        if what == "http" and len(a) == 2:
            d=self.lab._device(a[1])
            return f"HTTP {'enabled' if d.http_enabled else 'disabled'} on {d.name}\n" + "\n".join(sorted(d.http_pages))
        if what == "packet-events" and len(a) == 1:
            return "\n".join(f"{e['seq']:>5} {e['protocol']:<5} {e['source']} -> {e['destination']} {e['detail']}" for e in self.lab.packet_events) or "(no packet events)"
        if what == "dhcp" and len(a) == 2:
            d = self.lab._device(a[1])
            if not d.dhcp_pools: return "(no DHCP pools)"
            out = [f"DHCP pools on {d.name}"]
            for p in d.dhcp_pools.values():
                out.append(f"  {p.name}: {p.network} gw {p.gateway} range {p.start}-{p.end}")
                for mac, ip in p.leases.items(): out.append(f"    {ip:<15} {mac}")
            return "\n".join(out)
        if what == "vlans" and len(a) == 2:
            d = self.lab._device(a[1])
            if d.kind != "switch": raise LabError("show vlans requires a switch")
            out = [f"VLANs on {d.name}: {', '.join(map(str, sorted(d.vlans)))}"]
            for i in d.interfaces.values():
                if i.mode == "access": out.append(f"  {i.name:<8} access vlan {i.access_vlan}")
                else:
                    ch = f" Po{i.channel_group}/{i.channel_mode}" if i.channel_group else ""
                    out.append(f"  {i.name:<8} trunk native {i.native_vlan} allowed {','.join(map(str, i.allowed_vlans))}{ch}")
            return "\n".join(out)
        raise LabError("unsupported show command")

#!/usr/bin/env python3
from __future__ import annotations

from http.server import ThreadingHTTPServer, SimpleHTTPRequestHandler
from pathlib import Path
from urllib.parse import unquote, urlparse, parse_qs
import argparse
import json
import mimetypes
import os
import shlex
import threading
from copy import deepcopy

from netsim.model import NetworkLab, LabError
from netsim.cli import CommandProcessor
from netsim.capabilities import PRODUCT, CONTROL_PLANE_VERSION, registry
from netsim.device_catalog import CATALOG
from netsim.original_icons import icon_svg
from netsim.workspace_list import workspace_list, action_to_command, workspace_list_schema
from netsim.physical_workspace import physical_view, physical_tree, physical_schema, action_command as physical_action_command
from netsim.physical_distance import (
    physics_status, schema as distance_schema, distance_m,
    device_world_position, cable_length,
    action_command as distance_action_command
)
from netsim.backups import create_snapshot, list_snapshots, resolve_snapshot
from netsim.icp import panel_view as icp_view, schema as icp_schema, action_command as icp_action_command
from netsim.physical_accessibility import (
    view as accessibility_view, schema as accessibility_schema,
    command as accessibility_command
)
from netsim.cable_manipulation import (
    view as cable_view, schema as cable_schema,
    action_command as cable_action_command
)
from netsim.visual_customization import (
    public_assets, schema as visual_schema,
    command_from_action as visual_action_command,
    SHA_RE as VISUAL_SHA_RE
)
import base64

ROOT = Path(__file__).resolve().parent
WEB = ROOT / "web"
STATE = Path(os.environ.get("PACKETTRACKER_STATE", str(ROOT / "labs" / "autosave.json")))
BACKUPS = Path(os.environ.get("PACKETTRACKER_BACKUPS", str(ROOT / "labs" / "backups")))
# Self-contained project help is served from web/help.
LAB = NetworkLab()
LOCK = threading.RLock()
PROC = CommandProcessor(LAB)

if STATE.exists():
    try:
        LAB.load(str(STATE))
    except Exception as e:
        print(f"warning: could not load autosave: {e}")


def save_state():
    STATE.parent.mkdir(parents=True, exist_ok=True)
    LAB.save(str(STATE))


def command_ok(output):
    return not output.startswith(('ERROR:', '% '))


class Handler(SimpleHTTPRequestHandler):
    server_version = "PacketTrackerSimulator/0.2"

    def log_message(self, fmt, *args):
        print("[http]", fmt % args)

    def _json(self, obj, status=200):
        raw = json.dumps(obj).encode()
        self.send_response(status)
        self.send_header("content-type", "application/json")
        self.send_header("content-length", str(len(raw)))
        self.send_header("cache-control", "no-store")
        self.end_headers()
        self.wfile.write(raw)

    def _reject_large_request(self, size: int, message):
        # For a moderately oversized upload, consume at most 4 MB before
        # replying. Otherwise a fast client can receive BrokenPipe while
        # still sending and miss the useful 413 JSON response. Larger bodies
        # are rejected without draining to avoid an unbounded upload DoS.
        if 0 < size <= 4_000_000:
            old_timeout = self.connection.gettimeout()
            try:
                self.connection.settimeout(1.5)
                remaining = size
                while remaining:
                    chunk = self.rfile.read(min(remaining, 65536))
                    if not chunk: break
                    remaining -= len(chunk)
            except (OSError, TimeoutError):
                pass
            finally:
                self.connection.settimeout(old_timeout)
        self._json({'ok': False, 'error': message}, 413)

    def do_GET(self):
        path = unquote(urlparse(self.path).path)
        if path.startswith("/assets/icons/"):
            identifier = path.removeprefix("/assets/icons/")
            if not identifier or len(identifier)>250 or ".." in identifier or "\\" in identifier:
                self.send_error(404);return
            raw = icon_svg(identifier)
            self.send_response(200)
            self.send_header("content-type","image/svg+xml; charset=utf-8")
            self.send_header("content-length",str(len(raw)))
            self.send_header("cache-control","public, max-age=86400")
            self.end_headers();self.wfile.write(raw)
            return
        if path in {"/api/cyber-range/enterprise/archive","/api/cyber-range/enterprise/report"}:
            from netsim.enterprise_archive import progress, report
            try:
                q=parse_qs(urlparse(self.path).query,keep_blank_values=True)
                with LOCK:
                    if path.endswith("/archive"):
                        if q:raise LabError("archive takes no filters")
                        self._json(progress(LAB))
                    else:
                        if set(q)!={"run_id"} or len(q["run_id"])!=1:raise LabError("one run_id is required")
                        self._json(report(LAB,q["run_id"][0]))
            except LabError as exc:self._json({"ok":False,"error":str(exc)},400)
            return
        if path in {"/api/cyber-range/enterprise","/api/cyber-range/enterprise/schema"}:
            from netsim.enterprise_training import view, schema
            if urlparse(self.path).query:
                self._json({"ok":False,"error":"enterprise endpoint takes no filters"},400);return
            with LOCK:self._json(schema() if path.endswith("/schema") else view(LAB))
            return
        if path == "/api/cyber-range/exercises/report":
            from netsim.exercise_runner import archived_report
            try:
                q=parse_qs(urlparse(self.path).query,keep_blank_values=True)
                if set(q)!={"run_id"} or len(q["run_id"])!=1:raise LabError("one run_id is required")
                with LOCK:self._json(archived_report(LAB,q["run_id"][0]))
            except LabError as exc:self._json({"ok":False,"error":str(exc)},400)
            return
        if path in {"/api/cyber-range/exercises", "/api/cyber-range/exercises/schema"}:
            from netsim.exercise_runner import view, schema
            if urlparse(self.path).query:
                self._json({"ok":False,"error":"exercise endpoint takes no filters"},400);return
            with LOCK:self._json(schema() if path.endswith("/schema") else view(LAB))
            return
        if path in {"/api/cyber-range/incidents", "/api/cyber-range/incidents/schema"}:
            from netsim.incident_cases import view, schema
            if urlparse(self.path).query:
                self._json({"ok":False,"error":"incident endpoint takes no filters"},400);return
            with LOCK:self._json(schema() if path.endswith("/schema") else view(LAB))
            return
        if path in {"/api/cyber-range/soc", "/api/cyber-range/soc/schema"}:
            from netsim.defensive_soc import view, schema
            try:
                query=parse_qs(urlparse(self.path).query,keep_blank_values=True)
                if set(query)-{"kind","outcome"} or any(len(v)!=1 for v in query.values()):
                    raise LabError("invalid SOC filters")
                if path.endswith("/schema"):
                    if query:raise LabError("schema takes no filters")
                    self._json(schema())
                else:
                    with LOCK:self._json(view(LAB,query.get("kind",[None])[0],query.get("outcome",[None])[0]))
            except LabError as exc:self._json({"ok":False,"error":str(exc)},400)
            return
        if path == "/api/cyber-range/schema":
            from netsim.cyber_range import schema
            self._json(schema());return
        if path == '/api/v1/connectivity/schema':
            from netsim.connectivity import schema
            self._json(schema());return
        if path == '/api/topology-layout':
            from netsim.topology_presentation import layout
            try:
                q=parse_qs(urlparse(self.path).query)
                names=json.loads(q['names'][0]) if 'names' in q else None
                with LOCK:self._json(layout(LAB,names))
            except (LabError,ValueError,TypeError) as exc:self._json({'ok':False,'error':str(exc)},400)
            return
        if path in {"/api/workspace-tools","/api/workspace-tools/schema"}:
            from netsim.workspace_tools import view,schema
            try:
                q=parse_qs(urlparse(self.path).query)
                with LOCK:self._json(schema() if path.endswith('/schema') else view(LAB,q.get('workspace',['logical'])[0],q.get('location',['root'])[0],q.get('mode',['contents'])[0]))
            except (LabError,ValueError,TypeError) as exc:self._json({'ok':False,'error':str(exc)},400)
            return
        if path == '/api/samples/translation-template':
            from netsim.samples import translation_template
            self._json({'ok':True,'template':translation_template()});return
        if path == '/api/samples':
            from netsim.samples import catalog
            try:self._json(catalog(parse_qs(urlparse(self.path).query).get('language',['eng'])[0]))
            except LabError as exc:self._json({'ok':False,'error':str(exc)},400)
            return
        if path == '/api/command-reference':
            from netsim.command_reference import view
            try:self._json(view(parse_qs(urlparse(self.path).query).get('profile',[None])[0]))
            except LabError as exc:self._json({'ok':False,'error':str(exc)},400)
            return
        if path in {"/api/device-config","/api/device-config/schema"}:
            from netsim.device_config import view,schema
            try:
                with LOCK:self._json(schema() if path.endswith('/schema') else view(LAB,parse_qs(urlparse(self.path).query).get('device',[None])[0]))
            except (LabError,ValueError,TypeError,KeyError) as exc:self._json({'ok':False,'error':str(exc)},400)
            return
        if path in {"/api/simulation","/api/simulation/schema"}:
            from netsim.simulation import view,schema
            try:
                with LOCK:self._json(schema() if path.endswith('/schema') else view(LAB))
            except (LabError,ValueError,TypeError) as exc:self._json({'ok':False,'error':str(exc)},400)
            return
        if path == "/api/activity":
            from netsim.activity import progress
            with LOCK:
                self._json({"ok": True, "activity": progress(LAB)})
            return
        if path == "/api/state":
            with LOCK:
                self._json(LAB.to_dict())
            return
        if path == "/api/ospf":
            name = parse_qs(urlparse(self.path).query).get('device', [None])[0]
            try:
                with LOCK:
                    self._json({'ok': True, **LAB.ospf_status(name)})
            except (LabError, ValueError, TypeError) as exc:
                self._json({'ok': False, 'error': str(exc)}, 400)
            return
        if path == "/api/physical-accessibility/schema":
            self._json({"ok":True,**accessibility_schema()})
            return
        if path == "/api/physical-accessibility":
            params=parse_qs(urlparse(self.path).query)
            location=params.get("location",["intercity"])[0]
            try:
                with LOCK:self._json(accessibility_view(LAB,location))
            except (LabError,ValueError,TypeError) as exc:
                self._json({"ok":False,"error":str(exc)},400)
            return
        if path == "/api/icp/schema":
            self._json({"ok":True,**icp_schema()})
            return
        if path == "/api/icp":
            params=parse_qs(urlparse(self.path).query)
            location=params.get("location",[None])[0]
            try:
                if location is None:raise LabError("location is required")
                with LOCK:self._json(icp_view(LAB,location))
            except (LabError,ValueError,TypeError) as exc:
                self._json({"ok":False,"error":str(exc)},400)
            return
        if path == "/api/physical-cables/schema":
            self._json({"ok":True,**cable_schema()})
            return
        if path == "/api/physical-cables":
            params=parse_qs(urlparse(self.path).query)
            location=params.get("location",["intercity"])[0]
            try:
                with LOCK:self._json(cable_view(LAB,location))
            except (LabError,ValueError) as exc:
                self._json({"ok":False,"error":str(exc)},400)
            return
        if path == "/api/visuals/schema":
            self._json({"ok":True,**visual_schema()})
            return
        if path == "/api/visuals":
            with LOCK:self._json(public_assets(LAB))
            return
        if path.startswith("/api/visuals/assets/"):
            ident=path.removeprefix("/api/visuals/assets/")
            if not VISUAL_SHA_RE.fullmatch(ident):
                self._json({"ok":False,"error":"invalid asset ID"},404);return
            with LOCK:entry=LAB.visual_assets.get(ident)
            if entry is None:
                self._json({"ok":False,"error":"asset not found"},404);return
            content=base64.b64decode(entry["data_base64"])
            self.send_response(200)
            self.send_header("content-type",entry["mime"])
            self.send_header("x-content-type-options","nosniff")
            self.send_header("cache-control","private, max-age=31536000, immutable")
            self.send_header("content-length",str(len(content)))
            self.end_headers()
            self.wfile.write(content)
            return

        if path == "/api/physical-distance/schema":
            self._json({"ok":True,**distance_schema()})
            return
        if path == "/api/physical-distance":
            params=parse_qs(urlparse(self.path).query)
            source=params.get("source",[None])[0]
            target=params.get("target",[None])[0]
            device=params.get("device",[None])[0]
            iface=params.get("interface",[None])[0]
            location=params.get("location",["intercity"])[0]
            try:
                with LOCK:
                    if source is not None or target is not None:
                        if not source or not target or device is not None or iface is not None:
                            raise LabError("source and target device names are required together")
                        distance=distance_m(LAB,source,target)
                        result={"ok":True,"source":device_world_position(LAB,source),
                                "target":device_world_position(LAB,target),
                                "distance_m":round(distance,4),"unit":"meters",
                                "model":"2d-straight-line"}
                    elif device is not None or iface is not None:
                        if not device or not iface:raise LabError("device and interface are required together")
                        LAB._iface(device,iface)
                        cable=LAB.link_for(device,iface)
                        if cable is None:raise LabError("interface has no connected cable")
                        result={"ok":True,"a_device":cable.a_device,"a_if":cable.a_if,
                                "b_device":cable.b_device,"b_if":cable.b_if,
                                **LAB.link_status(cable)}
                    else:
                        result=physics_status(LAB,location)
                    self._json(result)
            except (LabError,ValueError,TypeError) as exc:
                self._json({"ok":False,"error":str(exc)},400)
            return
        if path == "/api/physical-workspace/tree":
            with LOCK:self._json(physical_tree(LAB))
            return
        if path == "/api/physical-workspace/schema":
            self._json({"ok":True,**physical_schema()})
            return
        if path == "/api/physical-workspace":
            params=parse_qs(urlparse(self.path).query)
            location=params.get("location",["intercity"])[0]
            try:
                with LOCK:self._json({"ok":True,**physical_view(LAB,location)})
            except (LabError,ValueError) as exc:
                self._json({"ok":False,"error":str(exc)},400)
            return
        if path == "/api/workspace-list/schema":
            self._json({"ok":True,**workspace_list_schema()})
            return
        if path == "/api/workspace-list":
            params=parse_qs(urlparse(self.path).query)
            cluster=params.get("cluster",["root"])[0]
            device=params.get("device",[None])[0]
            try:
                with LOCK:
                    result=workspace_list(LAB,cluster,device)
                    self._json({"ok":True,**result})
            except LabError as exc:
                self._json({"ok":False,"error":str(exc)},400)
            return
        if path == "/api/backups":
            with LOCK:
                self._json({"ok": True, "backups": list_snapshots(BACKUPS)})
            return
        if path == "/api/health":
            self._json({"ok": True, "service": "packet-tracker", "product": PRODUCT, "version": CONTROL_PLANE_VERSION})
            return
        if path == "/api/capabilities":
            with LOCK:
                self._json(registry(LAB))
            return
        if path == "/api/catalog":
            self._json(CATALOG)
            return
        if path == "/api/help-status":
            self._json({"available": True, "index": "/help/index.html"})
            return
        rel = "index.html" if path == "/" else path.lstrip("/")
        target = (WEB / rel).resolve()
        if not target.is_relative_to(WEB.resolve()) or not target.is_file():
            self.send_error(404);return
        raw = target.read_bytes()
        self.send_response(200)
        self.send_header("content-type", mimetypes.guess_type(str(target))[0] or "application/octet-stream")
        self.send_header("content-length", str(len(raw)))
        self.end_headers(); self.wfile.write(raw)

    def do_POST(self):
        # Browser requests carry Origin; non-browser agents without one remain supported.
        origin = self.headers.get("Origin")
        host = self.headers.get("Host", "")
        if origin is not None and origin.lower() != ("http://" + host).lower():
            self._json({"ok": False, "error": "cross-origin requests are not allowed"}, 403)
            return
        path = unquote(urlparse(self.path).path)
        if path.startswith("/assets/icons/"):
            identifier = path.removeprefix("/assets/icons/")
            if not identifier or len(identifier)>250 or ".." in identifier or "\\" in identifier:
                self.send_error(404);return
            raw = icon_svg(identifier)
            self.send_response(200)
            self.send_header("content-type","image/svg+xml; charset=utf-8")
            self.send_header("content-length",str(len(raw)))
            self.send_header("cache-control","public, max-age=86400")
            self.end_headers();self.wfile.write(raw)
            return
        try:
            n = int(self.headers.get("content-length", "0"))
            if n < 0 or n > 17_000_000:
                error={'code':'request_too_large','message':'request exceeds the 17 MB limit'} if path == '/api/v1/connectivity/ping' else 'request exceeds the 17 MB limit'
                self._reject_large_request(n,error);return
            if path == "/api/visuals/action" and (n<2 or n>1_500_000):
                self._reject_large_request(n,'image upload request exceeds 1.5 MB');return
            if path == "/api/workspace-tools/action" and (n<2 or n>17_000_000):
                self._reject_large_request(n,'workspace request exceeds 17 MB');return
            if path == "/api/lab/import" and (n<2 or n>11_000_000):
                self._reject_large_request(n,'lab import request exceeds size limit');return
            body = json.loads(self.rfile.read(n) or b"{}")
            if not isinstance(body,dict):
                error={'code':'invalid_request','message':'request body must be a JSON object'} if path == '/api/v1/connectivity/ping' else 'request body must be a JSON object'
                self._json({'ok':False,'error':error},400);return
        except Exception as e:
            error={'code':'invalid_request','message':str(e)} if path == '/api/v1/connectivity/ping' else str(e)
            self._json({"ok": False, "error": error}, 400); return
        if path == "/api/cyber-range/enterprise/action":
            from netsim.enterprise_training import view
            with LOCK:
                output=PROC.execute("enterprise "+shlex.quote(json.dumps(body)))
                ok=command_ok(output)
                if ok:save_state()
                self._json({"ok":ok,"output":output,"enterprise":view(LAB)},200 if ok else 400)
            return
        if path == "/api/cyber-range/exercises/action":
            from netsim.exercise_runner import view
            with LOCK:
                output=PROC.execute("exercise "+shlex.quote(json.dumps(body)))
                ok=command_ok(output)
                if ok:save_state()
                self._json({"ok":ok,"output":output,"exercise":view(LAB)},200 if ok else 400)
            return
        if path == "/api/cyber-range/incidents/action":
            from netsim.incident_cases import view
            with LOCK:
                output=PROC.execute("incident "+shlex.quote(json.dumps(body)))
                ok=command_ok(output)
                if ok:save_state()
                self._json({"ok":ok,"output":output,"incidents":view(LAB)},200 if ok else 400)
            return
        if path == "/api/cyber-range/generate":
            from netsim.cyber_range import generate
            try:
                self._json(generate(body))
            except (LabError, ValueError, TypeError) as exc:
                self._json({"ok":False,"error":str(exc)},400)
            return
        if path == '/api/v1/connectivity/ping':
            from ipaddress import ip_address
            def invalid(code, message):
                self._json({'ok':False,'error':{'code':code,'message':message}},400)
            source, destination = body.get('source'), body.get('destination_ip')
            if set(body) != {'source','destination_ip'} or not isinstance(source,str) or not source or not isinstance(destination,str) or not destination:
                invalid('invalid_request','source and destination_ip must be nonempty strings; no other fields are supported');return
            try:
                address=ip_address(destination)
                if getattr(address,'scope_id',None) is not None:raise ValueError('IPv6 scope identifiers are not supported')
            except ValueError as exc:
                invalid('invalid_request',str(exc));return
            with LOCK:
                if source not in LAB.devices:
                    invalid('unknown_source','unknown source device: '+source);return
                try:
                    verification=LAB.ping_detailed(source,str(address))
                except (LabError,ValueError) as exc:
                    invalid('operation_rejected',str(exc));return
                save_state()
            self._json({'ok':True,'result':verification},202 if verification['status']=='queued' else 200)
            return
        if path == "/api/ios/complete":
            from netsim.ios import IOSSession
            from netsim.ios_completion import complete
            try:
                if set(body) != {"device", "text", "cursor"}:
                    raise ValueError("Expected device, text, and cursor")
                device, text, cursor = body["device"], body["text"], body["cursor"]
                if not isinstance(device, str) or not 1 <= len(device) <= 128:
                    raise ValueError("Invalid device name")
                with LOCK:
                    target = LAB._device(device)
                    if target.kind not in ("router", "switch"):
                        raise ValueError("IOS CLI is only available for simulated routers/switches")
                    session = PROC.ios_sessions.get(device)
                    if session is None:
                        session = IOSSession(LAB, device)
                    result = complete(session, text, cursor)
                self._json({"ok": True, **result})
            except (LabError, ValueError) as exc:
                self._json({"ok": False, "error": str(exc)}, 400)
            return
        if path == "/api/activity/action":
            from netsim.activity import progress
            try:
                with LOCK:
                    if not LAB.activity:
                        raise ValueError("No learning activity is loaded")
                    action = body.get("action")
                    if action == "mark_page":
                        page = body.get("page")
                        reviewed = body.get("reviewed")
                        if type(page) is not int or not 0 <= page < len(LAB.activity["pages"]) or type(reviewed) is not bool:
                            raise ValueError("Invalid activity page or review state")
                        completed = set(LAB.activity["completed_pages"])
                        if reviewed: completed.add(page)
                        else: completed.discard(page)
                        LAB.activity["completed_pages"] = sorted(completed)
                        save_state()
                    elif action != "check_work":
                        raise ValueError("Unsupported learning activity operation")
                    self._json({"ok": True, "activity": progress(LAB)})
            except ValueError as exc:
                self._json({"ok":False,"error":str(exc)},400)
            return
        if path == "/api/lab/export":
            import base64
            from netsim.pkt_export import export_pkt
            try:
                if body.get("format") != "pkt":
                    raise ValueError("Only the experimental network-only PKT exporter is supported")
                with LOCK:
                    encoded, warnings = export_pkt(LAB)
                self._json({"ok":True,"format":"pkt",
                            "data":base64.b64encode(encoded).decode("ascii"),
                            "warnings":warnings})
            except (LabError,ValueError) as exc:
                self._json({"ok":False,"error":str(exc)},400)
            return
        if path == "/api/lab/import":
            from netsim.lab_import import decode_file
            try:
                candidate, warnings = decode_file(body.get('data'), body.get('filename'))
                if body.get('commit') is True:
                    with LOCK:
                        safety = create_snapshot(LAB, BACKUPS)
                        old = LAB.__dict__.copy()
                        try:
                            LAB.__dict__.clear(); LAB.__dict__.update(candidate.__dict__)
                            save_state()
                        except Exception:
                            LAB.__dict__.clear(); LAB.__dict__.update(old)
                            raise
                        PROC.ios_sessions.clear()
                        PROC._undo_stack.append(deepcopy(old))
                        PROC._undo_stack=PROC._undo_stack[-PROC.HISTORY_LIMIT:]
                        PROC._redo_stack.clear()
                        self._json({'ok':True,'warnings':warnings,'safety_backup':safety,'state':LAB.to_dict()})
                else:
                    self._json({'ok':True,'warnings':warnings,'devices':len(candidate.devices),'links':len(candidate.links)})
            except (ValueError, OSError) as exc:
                self._json({'ok':False,'error':str(exc)},400)
            return
        if path == "/api/backups":
            with LOCK:
                name = create_snapshot(LAB, BACKUPS)
                self._json({"ok": True, "backup": name})
            return
        if path == "/api/backups/restore":
            try:
                filename = body.get("name")
                with LOCK:
                    selected = resolve_snapshot(BACKUPS, filename)
                    safety = create_snapshot(LAB, BACKUPS, max_count=25)  # retain requested restore point
                    LAB.load(str(selected))
                    PROC.ios_sessions.clear()
                    save_state()
                    self._json({"ok": True, "restored": selected.name, "safety_backup": safety, "state": LAB.to_dict()})
            except (ValueError, FileNotFoundError) as exc:
                self._json({"ok": False, "error": str(exc)}, 400)
            return
        if path == "/api/http-page":
            server, page, html = body.get("server"), body.get("path"), body.get("html")
            if not all(isinstance(x, str) for x in (server, page, html)):
                self._json({"ok": False, "error": "server, path and HTML text required"}, 400); return
            with LOCK:
                try:
                    LAB.set_http_page(server, page, html)
                    save_state()
                    self._json({"ok": True, "state": LAB.to_dict()})
                except (ValueError, RuntimeError) as exc:
                    self._json({"ok": False, "error": str(exc)}, 400)
            return
        if path == "/api/web":
            source, url = body.get("source"), body.get("url")
            if not isinstance(source, str) or not isinstance(url, str):
                self._json({"ok": False, "error": "source and URL required"}, 400); return
            with LOCK:
                try:
                    if LAB.simulation['mode']=='simulation':
                        from netsim.simulation import enqueue_task
                        ident=enqueue_task(LAB,'http',{'source':source,'url':url})
                        save_state();self._json({'ok':True,'pending':True,'job':ident,'state':LAB.to_dict()},202);return
                    response = LAB.http_request(source, url)
                    save_state()
                    self._json({**response, "state": LAB.to_dict()})
                except (ValueError, RuntimeError) as exc:
                    save_state()
                    self._json({"ok": False, "error": str(exc), "state": LAB.to_dict()}, 400)
            return
        if path == '/api/samples/validate-translation':
            from netsim.samples import validate_translation
            try:self._json({'ok':True,'translation':validate_translation(body)})
            except (LabError,ValueError,TypeError) as exc:self._json({'ok':False,'error':str(exc)},400)
            return
        if path == '/api/samples/action':
            kind=body.get('action');ident=body.get('id')
            if kind not in ('load','check') or not isinstance(ident,str):self._json({'ok':False,'error':'sample action and id required'},400);return
            with LOCK:
                output=PROC.execute('sample '+kind+' '+shlex.quote(ident));ok=command_ok(output)
                if ok and kind=='load':save_state()
                self._json({'ok':ok,'output':output,'state':LAB.to_dict()},200 if ok else 400)
            return
        if path == "/api/device-config/action":
            with LOCK:
                output=PROC.execute('device-config '+shlex.quote(json.dumps(body)))
                ok=command_ok(output)
                if ok:save_state()
                self._json({'ok':ok,'output':output,'state':LAB.to_dict()},200 if ok else 400)
            return
        if path == "/api/simulation/action":
            with LOCK:
                output=PROC.execute('simulation '+shlex.quote(json.dumps(body)))
                ok=command_ok(output)
                if ok:save_state()
                self._json({'ok':ok,'output':output,'simulation':__import__('netsim.simulation',fromlist=['view']).view(LAB,synchronize=False),'state':LAB.to_dict()},200 if ok else 400)
            return
        if path == "/api/workspace-tools/action":
            command=body.get('action') if isinstance(body,dict) else None
            with LOCK:
                output=PROC.execute(command if command in ('undo','redo') else 'workspace-tool '+shlex.quote(json.dumps(body)))
                ok=command_ok(output)
                if ok:save_state()
                self._json({'ok':ok,'output':output,'state':LAB.to_dict()},200 if ok else 400)
            return
        if path == "/api/physical-accessibility/action":
            try:cmd=accessibility_command(body)
            except (LabError,ValueError,TypeError) as exc:
                self._json({"ok":False,"error":str(exc)},400);return
            with LOCK:
                output=PROC.execute(cmd)
                ok=command_ok(output)
                if ok:save_state()
                self._json({"ok":ok,"output":output,"state":LAB.to_dict()},200 if ok else 400)
            return
        if path == "/api/icp/action":
            try:cmd=icp_action_command(body)
            except (LabError,ValueError,TypeError) as exc:
                self._json({"ok":False,"error":str(exc)},400);return
            with LOCK:
                output=PROC.execute(cmd)
                ok=command_ok(output)
                if ok:save_state()
                self._json({"ok":ok,"output":output,"state":LAB.to_dict()},200 if ok else 400)
            return
        if path == "/api/physical-cables/action":
            try:cmd=cable_action_command(body)
            except (LabError,TypeError,ValueError) as exc:
                self._json({"ok":False,"error":str(exc)},400);return
            with LOCK:
                output=PROC.execute(cmd)
                ok=command_ok(output)
                if ok:save_state()
                self._json({"ok":ok,"output":output,"state":LAB.to_dict()},
                           200 if ok else 400)
            return
        if path == "/api/visuals/action":
            try:
                cmd=visual_action_command(body)
            except (LabError,ValueError,TypeError) as exc:
                self._json({"ok":False,"error":str(exc)},400);return
            with LOCK:
                output=PROC.execute(cmd)
                ok=command_ok(output)
                if ok:save_state()
                response={"ok":ok,"output":output,
                          "visuals":public_assets(LAB),
                          "state":LAB.to_dict()}
                if ok and body.get("action")=="upload_image":
                    response["asset_id"]=output.split()[-1]
                self._json(response,200 if ok else 400)
            return
        if path == "/api/physical-distance/action":
            try:
                cmd=distance_action_command(body)
            except (ValueError,TypeError,LabError) as exc:
                self._json({"ok":False,"error":str(exc)},400);return
            with LOCK:
                output=PROC.execute(cmd)
                ok=command_ok(output)
                if ok:save_state()
                self._json({"ok":ok,"output":output,
                            "cable_length_effects":LAB.cable_length_effects,
                            "radio_ranges":dict(LAB.radio_ranges),
                            "state":LAB.to_dict()},200 if ok else 400)
            return
        if path == "/api/physical-workspace/action":
            try:
                cmd=physical_action_command(body)
                location=body.get("view_location","intercity")
                if not isinstance(location,str):raise LabError("view_location must be a string")
            except (LabError,ValueError,TypeError) as exc:
                self._json({"ok":False,"error":str(exc)},400);return
            with LOCK:
                try:
                    physical_view(LAB,location)
                except LabError as exc:
                    self._json({"ok":False,"error":str(exc)},400);return
                output=PROC.execute(cmd)
                ok=command_ok(output)
                if ok:save_state()
                result={"ok":ok,"output":output,"state":LAB.to_dict()}
                # A location move may invalidate the currently displayed parent;
                # always return a usable projection.
                try:result["workspace"]=physical_view(LAB,location)
                except LabError:result["workspace"]=physical_view(LAB)
                self._json(result,200 if ok else 400)
            return
        if path == "/api/workspace-list/action":
            try:
                cmd=action_to_command(body)
                target_cluster=body.get("cluster","root")
                if not isinstance(target_cluster,str):raise LabError("cluster must be a string")
            except (LabError,TypeError,ValueError) as exc:
                self._json({"ok":False,"error":str(exc)},400);return
            with LOCK:
                if target_cluster!="root" and target_cluster not in LAB.clusters:
                    self._json({"ok":False,"error":"unknown logical cluster"},400);return
                output=PROC.execute(cmd)
                ok=command_ok(output)
                if ok:save_state()
                try:
                    selection=body.get("selected_device")
                    if not isinstance(selection,str):selection=None
                    projection=workspace_list(LAB,target_cluster,selection)
                except LabError:
                    projection=workspace_list(LAB)
                response={"ok":ok,"output":output,"workspace":projection,"state":LAB.to_dict()}
            self._json(response,200 if ok else 400)
            return
        if path == "/api/command":
            command = body.get("command")
            if not isinstance(command,str):
                self._json({'ok':False,'error':'command must be a string'},400);return
            with LOCK:
                output = PROC.execute(command)
                save_state()
                state = LAB.to_dict()
            self._json({"ok": command_ok(output), "output": output, "state": state})
            return
        if path == "/api/batch":
            commands = body.get("commands")
            if not isinstance(commands, list) or any(not isinstance(x, str) for x in commands):
                self._json({"ok": False, "error": "commands must be an array of strings"}, 400); return
            if len(commands) > 10000:
                self._json({"ok": False, "error": "batch limit is 10000 commands"}, 400); return
            stop_on_error = bool(body.get("stop_on_error", True))
            if not isinstance(body.get('stop_on_error',True),bool):
                self._json({'ok':False,'error':'stop_on_error must be a boolean'},400);return
            results = []
            all_ok = True
            with LOCK:
                for index, command in enumerate(commands):
                    output = PROC.execute(command)
                    ok = command_ok(output)
                    results.append({"index": index, "command": command, "ok": ok, "output": output})
                    if not ok:
                        all_ok = False
                        if stop_on_error:
                            break
                save_state()
                state = LAB.to_dict()
            self._json({"ok": all_ok, "requested": len(commands), "executed": len(results), "results": results, "state": state})
            return
        if path == "/api/state":
            # direct UI position updates; intentionally narrow instead of arbitrary JSON mutation
            name = body.get("device")
            if not isinstance(name, str):
                self._json({"ok": False, "error": "device required"}, 400); return
            with LOCK:
                try:
                    d=LAB._device(name)
                    x,y=body.get("x",d.x),body.get("y",d.y)
                    output=PROC.execute(f"move {shlex.quote(name)} {x} {y}")
                    if output.startswith("ERROR:"):
                        self._json({"ok":False,"error":output},400)
                    else:
                        save_state()
                        self._json({"ok":True,"state":LAB.to_dict()})
                except Exception as e:
                    self._json({"ok": False, "error": str(e)}, 400)
            return
        self.send_error(404)


def main():
    p = argparse.ArgumentParser(description="Packet Tracker and Simulator local network simulator")
    p.add_argument("--host", default="127.0.0.1")
    p.add_argument("--port", type=int, default=8765)
    args = p.parse_args()
    httpd = ThreadingHTTPServer((args.host, args.port), Handler)
    print(f"{PRODUCT} running at http://{args.host}:{args.port}")
    print("Agent API: GET /api/state, GET /api/workspace-list, POST /api/workspace-list/action, POST /api/command, POST /api/batch")
    try:
        httpd.serve_forever()
    except KeyboardInterrupt:
        pass
    finally:
        save_state()


if __name__ == "__main__":
    main()

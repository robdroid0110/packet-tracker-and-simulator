# Packet Tracker and Simulator Agent Manual

Packet Tracker and Simulator is designed around one rule: **anything the GUI can do must also be controllable by an agent through the same simulator state**.

## Control-plane contract

A feature is not considered complete until it has all of these:

1. simulation/model behavior;
2. GUI control or visualization where appropriate;
3. agent command/API operation;
4. capability-registry entry;
5. state/query output so an agent can verify the result;
6. automated behavior test where the feature affects networking.

This prevents GUI-only features and prevents the agent shell from becoming a second, inconsistent simulator.

## Discovery

```bash
./netlab capabilities
./netlab capabilities pc
./netlab capabilities switch
./netlab capabilities R1
./netlab manual
```

HTTP discovery:

```text
GET /api/capabilities
GET /api/catalog
GET /api/state
```

`/api/capabilities` is machine-readable and reports device types, tabs, implemented/planned features, action IDs, syntax, and current device instances. `/api/catalog` exposes legacy network simulator-compatible model metadata separately from behavioral support, so agents can distinguish “placeable model” from “fully simulated device.”

## Execution

Single operation:

```bash
./netlab exec 'add router R1 400 250'
./netlab exec 'catalog Routers'
./netlab exec 'add-model isr4331 R2 520 250'
```

Batch/world build:

```bash
./netlab batch labs/mini-city.netlab
```

HTTP:

```text
GET /api/v1/connectivity/schema
POST /api/v1/connectivity/ping
{"source":"PC1","destination_ip":"10.0.0.1"}

POST /api/command
{"command":"ping PC1 10.0.0.1"}

POST /api/batch
{"commands":["add router R1","add switch SW1","connect R1 g0/0 SW1 g0/1"],"stop_on_error":true}
```

The batch endpoint accepts up to 10,000 ordered simulator commands and returns an individual result for every executed command plus the final simulator state.

Browser POST requests with an `Origin` header must match the server origin; cross-origin requests are rejected with HTTP 403. Agent clients that do not send an Origin header remain supported. This check does not authenticate local processes or prevent DNS rebinding.

Request bodies must be JSON objects. `/api/command` requires a string `command`;
`/api/batch` requires a list of strings and a Boolean `stop_on_error` if supplied.
Invalid request shapes/types return HTTP 400 with `ok: false`. Command-level IOS
errors beginning with `% ` also return `ok: false`; the command endpoint retains
HTTP 200 for executed commands, so check the JSON result. A legacy ping that runs but
cannot reach its target is an executed command. Prefer the versioned connectivity
API and inspect `result.reachable` and `result.reason` for typed verification.
Simulation Mode returns HTTP 202 with a job ID and `reachable: null` until the
job completes; see [structured connectivity verification](CONNECTIVITY_VERIFICATION.md).
Batches may partially execute; inspect individual results and `executed`.
Successful `/api/lab/import` commits now support undo/redo through the same
command endpoint and retain the pre-import safety backup.

See [feature coverage](HELP_COVERAGE.md) for original projects built and checked
through these APIs, including deliberate outages and malformed requests.

Area-aware OSPF can be configured with `ospf R1 enable 10.0.0.0/30 area 7` and inspected through `GET /api/ospf?device=R1` or `show ospf R1`. The [OSPF reference](OSPF_AREAS_REFERENCE.md) documents legacy compatibility, all commands and simulator limits.

## Current device families

- `pc` — Physical / Config / Desktop / Programming / Attributes
- `server` — host networking and DHCP server behavior; richer service UI is still being expanded
- `switch` — VLANs, trunks, native VLAN, PVST/Rapid-PVST, EtherChannel, CDP/LLDP, MAC learning
- `router` — IPv4, static routing, router-on-a-stick, simplified OSPF, DHCP server/relay, CDP/LLDP
- `generic` — catalog/placement/cabling surface for specialized legacy network simulator models whose protocol-specific engine is not implemented yet

The catalog covers 151 conventional and IoT-style legacy network simulator entries. `support: engine` means the model is backed by an existing simulator engine; `support: catalog` means it is intentionally visible/placeable without pretending unsupported behavior works.

The capability registry is authoritative for what is actually implemented. UI placeholders are explicitly marked `planned` in discovery data rather than being presented to agents as working features.

## Agent workflow

For an unfamiliar lab, an agent should:

1. call `GET /api/capabilities`;
2. call `GET /api/state`;
3. generate an ordered command plan;
4. execute it with `/api/batch`;
5. inspect the returned state;
6. verify with `show`, `ping`, `traceroute`, IOS `show` commands, or later protocol-specific diagnostics;
7. correct only the failed portion instead of rebuilding the lab blindly.

## Example world

`labs/mini-city.netlab` creates a small routed city with a core network plus Hospital, School, and Office zones. It is intentionally generated entirely through the agent control plane, with no GUI clicking.

## Architectural direction

Future devices—wireless APs, multilayer switches, firewalls, phones, IoT devices, clouds, WAN devices, etc.—must register their capabilities in `netsim/capabilities.py` as they are implemented. The long-term goal is for an AI agent to discover the complete simulator vocabulary and construct large network worlds deterministically from a natural-language request.

## Logical workspace annotations (help-guided)

Agents can create/update/reposition/delete legacy network simulator-style sticky notes directly:
- note add <x> <y> "<text>" — allocates Note0, Note1, and so forth
- note edit <note-id> "<text>"
- note move <note-id> <x> <y>
- note delete <note-id>
- show notes / show json to inspect

They persist through normal save/load. The GUI Place Note tool edits the same NetworkLab.notes state. Note text is limited to 800 characters; coordinates must be finite. This is topology annotation, not a simulated protocol.

## Physical connectivity and power

Use `connect PC1 eth0 SRV1 eth0 copper-cross` or `connect PC1 eth0 SW1 fa0/1 copper-straight`. If type is omitted or `auto`, the simulator chooses an operational Ethernet connection for compatibility with existing labs. An explicit incompatible copper type creates a connected but carrier-down interface. `show links` and `GET /api/state` expose type and live status. `power PC1 off` and `power PC1 on` change runtime power state without erasing IP configuration. Unsupported cable types (e.g., console, serial and fiber without modules) return errors instead of false positives.

## DNS / HTTP and My First PT Lab

Agent commands:
  dns-client Client 192.168.0.105
  dns-service WebServer on
  dns-add WebServer www.firstlab.com 192.168.0.105
  http-service WebServer on
  http-page WebServer / "<h1>Simulated</h1>"
  web-get Client http://www.firstlab.com/
  show dns WebServer
  show http WebServer
  pdu Client WebServer
  show packet-events
  power-cycle

Programmatic Web Browser: POST /api/web with JSON source and URL yields HTTP-like status, resolved IP, server, HTML and state. POST /api/http-page with server/path/html updates a page without shell-quoting issues. Neither endpoint accesses the real Internet.

GET /api/state packet_events is bounded to 256 synthetic hop events with seq, time, protocol, source, destination, detail and ok. This is not real packet serialization or an exact protocol-timing emulator.

Power-cycle clears transient ARP/MAC/NAT and packet trace, preserving configuration. Use labs/my-first-pt-lab.netlab only against an empty or disposable lab, not the user's active network.

## Workspace Basics physical geography

GET /api/state returns physical_locations (city/building/closet objects keyed by stable ID) and device_locations (name -> location ID or intercity). Both persist inside normal lab JSON. New/legacy labs have city0 / building0 / closet0 by default.

Commands:
- physical add city Jaipur intercity
- physical add building School city0
- physical add closet Lab building0
- physical rename loc0 "New Name"
- physical position loc0 345 125
- physical place PC1 closet0
- show physical

The simulator validates location type, hierarchy, name, coordinates and device references. Move PC1 200 300 changes logical placement ONLY. Physical assignment does not modify links or routing behavior. Geographic cable/wireless effects are future work.

## Logical Workspace agents and grouped editing

The same POST /api/command and ./netlab exec interface offers:
- duplicate PC1,SW1 120 80: clone 1-512 devices, configuration and internal links. Generate fresh MACs, clear dynamic tables, preserve device physical assignment; copied IP addresses may conflict.
- move-group PC1,SW1 40 50: atomic logical coordinate change.
- remove-group PC1,SW1: atomic removal with undo.
- undo / redo: restore one change from bounded in-memory 64-snapshot command-driven history; server restart clears history.
- cluster add Campus PC1,SW1 [parent-id]: add named saved cluster and selected devices. Parent ID enables nesting; pass none to create an empty group.
- cluster place PC1 Cluster0 (or root), cluster move Cluster1 Cluster0 (or root): move devices or nested cluster locations.
- cluster rename Cluster0 "Campus A", cluster delete Cluster0: rename or uncluster while preserving devices and links.
- show clusters: list saved logical groups.

GET /api/state includes clusters keyed by Cluster0, Cluster1 etc with id, name, parent and devices fields. Load validates membership and parent cycles. Lab files lacking clusters load with an empty group list.

## Workspace List: typed API for agents (Help section 14)

Read: GET /api/workspace-list?cluster=root or GET /api/workspace-list?cluster=Cluster0&device=PC1. This returns the currently visible devices, child clusters, links and selected-device module slots.
Discover: GET /api/workspace-list/schema (JSON action types and examples) and GET /api/capabilities.
Mutate: POST /api/workspace-list/action accepts typed JSON with action add_device, remove_device, move_device, power_device, add_link, remove_link, set_module, undo or redo. All edits use the existing command processor and shared persisted lab.

Agent shell also supports module <device> <slot> <PT-ETH-1|PT-ETH-4|none> to install/remove SIMULATED Ethernet modules in PT/generic profiles. Device power must be off; attached ports must be disconnected first. Other chassis show fixed onboard interfaces but do not pretend to have supported slots.

Example call:
curl -s -X POST http://127.0.0.1:8765/api/workspace-list/action -H 'Content-Type: application/json' -d '{"action":"move_device","device":"PC1","x":280,"y":220}'

Security: no HTTP authentication is implemented. Keep binding to loopback until remote authentication/access control is added. Project API-first rule: API_FEATURE_CONTRACT.md.

## Section 14 Workspace List: typed API

GET /api/workspace-list?cluster=root (or Cluster0 etc) retrieves the currently visible logical devices and links. Add &device=R1 to receive physical module slot layout for that device. GET /api/workspace-list/schema supplies supported action payloads and module types.

POST /api/workspace-list/action accepts typed JSON such as:
  {"action":"add_device","model":"pc-pt","name":"PC2","x":180,"y":200}
  {"action":"add_device","model":"pc-pt","name":"PC3","x":320,"y":220,"cluster":"Cluster0"}
  {"action":"move_device","device":"PC2","x":330,"y":220}
  {"action":"power_device","device":"R1","powered":false}
  {"action":"set_module","device":"R1","slot":"slot0","module":"PT-ETH-4"}
  {"action":"add_link","a_device":"R1","a_if":"g0/0","b_device":"SW1","b_if":"fa0/1","cable":"auto"}
  {"action":"remove_link","device":"R1","iface":"g0/0"}
  {"action":"undo"}

All actions share the CommandProcessor undo stack, persist to saved labs and validate before mutation. Invalid input responds with HTTP 400 JSON {ok:false,error:...}. Expansion slots are intentionally virtual generic PT profiles only, requiring device power-off; connected module ports cannot be removed. Serial, fiber, console and vendor-specific modules are not yet supported. New add-in-cluster command is the atomic CLI counterpart for adding directly inside logical nested clusters.

GET /api/capabilities includes workspace_list.read, workspace_list.schema, workspace_list.edit, workspace_list.add_in_cluster, and device.module. Remote deployment requires authentication/access control (server binds loopback by default).

## Section 15 Physical Workspace agent access

The authoritative saved lab includes physical_locations (type/name/parent/x/y/width/length/height in meters), device_locations, physical_device_details (position and floor/rack/table/shelf), and physical_shelves (closet shelf count).

GET /api/physical-workspace?location=closet0 returns current container metadata, immediate children, devices, their surfaces, shelf count, and links. GET /api/physical-workspace/schema advertises the typed JSON action contract. POST /api/physical-workspace/action accepts:
- add_location, rename_location, move_location, relocate_location, resize_location
- add_device: create and place a device in one atomic undoable operation
- place_device, position_device, add_shelf, mount_device
- undo, redo

CLI equivalents: physical add generic Storage closet0; physical dimensions loc0 8 7 2; physical relocate loc0 building0; physical add-device pc-pt PC3 200 160 city0 350 230; physical shelf-add closet0; physical mount R1 rack; physical mount R1 shelf 0; show physical.

Restrictions are enforced in NetworkLab, not just GUI. Child dimensions cannot exceed parent; parent hierarchy must be acyclic. Shelves require powered-off, disconnected hardware and prevent power-on and new cables until removed. Physical motion does not change existing IP or logical cabling. Cable distance and wireless range are currently not simulated. Do not expose the unauthenticated API outside loopback.

## Physical Move Object and Navigation Tree (Section 16)

GET /api/physical-workspace/tree exposes the complete hierarchy of all locations and physical devices. The tree is independent from the visual current location and can be used to plan relocations.

POST /api/physical-workspace/action with {"action":"move_devices","devices":["R1","R2"],"location":"loc0"} moves 1-200 unique valid names atomically to a known location. Existing network links and logical geometry do not change. The destination physical coordinates become (28,24) for moved devices; in closets their default rack/table mount is assigned. Existing container moves remain {"action":"relocate_location","location":"building0","parent":"loc0"}. Undo and Redo operate on both.

GET /api/physical-workspace?location=intercity returns boundary_links with source/destination visible child IDs, counts of all logical links, and counts of operational links for cross-city map connections. These link counts do not imply physical cable length: distance effects remain unsupported.

Both capabilities are discoverable in GET /api/capabilities (physical_workspace.tree, workspace.physical_move_devices). The HTTP server is unauthenticated and must remain loopback-only unless separately secured.

## Section 17 — Physical distance agent capabilities

GET /api/physical-distance?source=R1&target=R2 returns metric 2D straight-line distance and global positions. GET /api/physical-distance?device=R1&interface=g0/0 returns connected cable segment and total metres, 100m copper limit, operational flag and reason. GET /api/physical-distance?location=city0 includes all cable distances, projection units, wireless source circles, configured radii and geometric client range checks. GET /api/physical-distance/schema documents arguments and limits.

POST /api/physical-distance/action accepts {"action":"cable_effects","enabled":true}, {"action":"radio_range","device":"AP1","radius_m":180}, undo or redo. CLI equivalents: physical cable-effects on|off, physical measure A B, physical cable-length R1 g0/0, physical radio-range AP1 180, physical radio-status city0. All model writes share undo/redo and lab save. Copper limit is 100m and effects default OFF. Wireless pairing, association and RF forwarding are NOT implemented; geometric in-range checks are not real connectivity. See PHYSICAL_DISTANCE_REFERENCE.md.

## Section 18 — portable visual customization

Use visual import /path/to/map.png to upload a PNG/JPEG from the local host (1MB maximum); the command prints its SHA-256 asset ID. Agent commands: visual upload image/png BASE64 [label], visual icon R1 physical SHA256, visual icon R1 logical default, visual background city0 SHA256 tile #aabbcc, visual background intercity default fit #e7e7e7, visual delete SHA256. Asset references, color, tile and separate Logical/Physical device icons persist with labs and support undo/redo.

HTTP: GET /api/visuals for metadata and saved assignments, GET /api/visuals/schema for contract, GET /api/visuals/assets/<sha256> for binary PNG/JPEG, POST /api/visuals/action for upload_image, set_device_icon, set_background, delete_image, undo, redo. See PHYSICAL_CUSTOMIZATION_REFERENCE.md for JSON fields and safety quotas. No executable SVG, remote URL assets or browser-only copies.

## Physical Cable Manipulation — BendPoints and GroupPoints (Section 19)

GET /api/physical-cables?location=city0 returns cable routes in a given location: source/destination ports, ordered endpoints, bend IDs, shared group IDs, 2D world-meter coordinates and canvas projections, segment colour/length, total length and real operational status. GET /api/physical-cables/schema provides typed action definitions.

POST /api/physical-cables/action supports:
- add_bend {device,interface,x_m,y_m,after?:"start"|bend-id}; move_bend {device,interface,bend,x_m,y_m}; delete_bend {device,interface,bend}
- set_color {device,interface,color:"#ff1133"}
- group_bends {device,interface,bend,other_device,other_interface,other_bend}; move_group {group,x_m,y_m}; ungroup {group,device?,interface?}; undo or redo.

CLI equivalents: cable bend-add R1 g0/0 300 500 start; cable bend-move R1 g0/0 bend_ID 320 510; cable color R1 g0/0 #aa2200; cable group R1 g0/0 bend_ID R2 g0/1 bend_ID; cable group-move group_ID 320 520; cable ungroup group_ID. Units are **absolute world metres**. Physical-cables GET gives coordinate origins/scales. The full polyline length now drives the opt-in 100m Ethernet limit rather than endpoint distance alone. Paths and groups persist in lab JSON with the same Undo history. See PHYSICAL_CABLE_MANIPULATION_REFERENCE.md.

## Section 20 — Industrial Control Panel agent API and CLI

GET /api/icp/schema discovers ICP presets, actions and bounds. GET /api/icp?location=loc0 reports the cabinet state (door, preview, devices, snap anchors, mounted DIN fixtures, grouped DIN/WIC strips). POST /api/icp/action controls create, door, preview, device_move, fixture_add/move/join/split/delete, mount, unmount, undo, redo. Example JSON bodies: {"action":"create","name":"Factory","size":"medium","parent":"building0"}; {"action":"device_move","device":"R1","side":"cabinet","x":240,"y":160,"anchor":0,"detach":false}; {"action":"fixture_add","location":"loc0","kind":"din","orientation":"horizontal","x":200,"y":180}; {"action":"mount","device":"R1","fixture":"fixture0"}. All positions are local 0-1000 ICP canvas units, grid snapped every 20 units, with six anchor offsets.

CLI equivalents: icp create medium "Factory Panel" building0; icp door loc0 on|off; icp preview loc0 on|off; icp device-move R1 cabinet 240 160 0 attached; icp fixture-add loc0 din horizontal 200 180; icp fixture-join loc0 fixture0 fixture1; icp fixture-move loc0 fixture0 400 220 attached; icp fixture-split loc0 fixture0; icp mount R1 fixture0; icp unmount R1. Complete CLI/JSON examples: ICP_REFERENCE.md. ICP layout never simulates power wiring or industrial PLC behavior.

ICP network connections use the existing common agent interface: connect PC1 eth0 R1 g0/0 auto, disconnect PC1 eth0, or POST /api/command with {"command":"connect PC1 eth0 R1 g0/0 auto"}. GET /api/state and GET /api/icp?location=loc0 show state and placement. The ICP GUI is a thin API client for the same commands; DIN/WIC do not route Ethernet.

## Section 21 — Physical Accessibility API

GET /api/physical-accessibility?location=closet0 returns screen-reader-friendly tree/breadcrumbs, current location surfaces, equipment, actual ports and UP/DOWN status, module slots, and associated cables. GET /api/physical-accessibility/schema enumerates typed controls and keyboard navigation.

POST /api/physical-accessibility/action accepts add_device (model, name, location), move_device (device, location), mount_device (device, surface, optional shelf), place_icp_device (device, side, x, y), connect (a_device, a_if, b_device, b_if, cable), disconnect (device, interface), power (device, enabled bool), set_module (device, slot, module), add_shelf (location), undo, redo. Actions route through the same CommandProcessor as the existing shell and remain saved in native lab JSON. This is the accessible *view* of the existing engine, not a new simulation. See PHYSICAL_ACCESSIBILITY_REFERENCE.md.

## Section 22 — Physical grids and container deletion

GET /api/physical-workspace?location=building0 includes grid (metric/projected spacing, colour, visibility, support), grid_profiles and delete_preview (affected subtree, extracted devices, destination). POST /api/physical-workspace/action accepts {"action":"set_grid","container_type":"city","enabled":true,"spacing_m":125,"color":"#cc2244"} and {"action":"delete_location","location":"closet0"}. Schema version 2 and capability IDs workspace.physical_grid / workspace.physical_delete advertise these operations.

CLI: physical grid city on 125 #cc2244; physical delete-preview building0; physical delete closet0. All mutations share Undo/Redo and autosave. Deletion extracts equipment to the parent floor, preserving logical configuration and cables; it removes nested containers and their furniture/background assignments. Intercity cannot be deleted. Grid settings persist per type, with legacy defaults. Read previews before deleting when evaluating impact. With cable effects enabled, extraction can change carrier as positions change. See PHYSICAL_SPECIAL_NOTES_REFERENCE.md.

## Workspace and Accessibility — Sections 23–32

Added portable logical/cluster artwork (including GIF), shared Logical/Physical viewports, configured device/cluster/container template management and JSON portability, accessible event inspection, keyboard/menu/tab controls, terminal focus exit, saved contrast and application scaling. All durable operations are authoritative API/CLI actions with history, validation and saved-state compatibility. Discovery: GET /api/workspace-tools/schema; read: GET /api/workspace-tools; write: POST /api/workspace-tools/action or workspace-tool '<JSON>'. Existing /api/visuals now supports logical backgrounds and cluster icons.

259 Python tests pass, including 200-device template capture/creation and isolated HTTP atomicity. Isolated Chromium checks real controls, templates, viewport pan, artwork, accessible names, contrast, 4K and persistence without touching the active lab. Defined browser scope is complete through Section 32; native vendor file formats and OS screen-reader certification remain outside the verified scope. Details, shortcuts and limits: [WORKSPACE_ACCESSIBILITY_REFERENCE.md](WORKSPACE_ACCESSIBILITY_REFERENCE.md). Next sequential phase: Section 33.

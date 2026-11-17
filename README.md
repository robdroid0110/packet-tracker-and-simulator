# Packet Tracker and Simulator

Packet Tracker and Simulator is an open-source, local networking laboratory for Linux and Windows. Create virtual topologies in a graphical workspace or control the same deterministic network simulator through its agent API.

The primary command is ./packet-tracker-simulator. The legacy netlab CLI remains available for backward compatibility. Supported features are documented below; some devices and protocols intentionally use simplified models.

## Why this exists

Packet Tracker and Simulator is a local environment for learning and testing virtual network topology configurations without physical networking hardware. A visual interface and an agent API share the same simulation state.

## Platforms

The source is a Python-based application for Linux; the optional GUI needs Qt dependencies. Windows builds are made on Windows and are not included in this source repository.

## Privacy and security

The simulator runs locally, not as an authenticated public cloud service. Its HTTP API must not be exposed to untrusted networks or port-forwarded; lab data remains on the local machine. Read SECURITY.md before network exposure.

## Contributing and licence

Contributions can be submitted through issues and pull requests. See CONTRIBUTING.md, LICENSE and THIRD_PARTY_NOTICES.md. Desktop binary redistribution carries separate third-party licence obligations.

## Quick start

From the project checkout, run `./launch.sh` to start the simulator and open the web UI. Alternatively, run `./packet-tracker-simulator serve` and visit `http://127.0.0.1:8765`. No proprietary network simulator, bundled vendor artwork or external help installation is required.

For desktop integration, run `python3 tools/install_linux_desktop.py` and see [Desktop applications](DESKTOP_APPLICATIONS.md). The agent API is available from the same local server at `/api/capabilities`.

## Desktop applications

Packet Tracker and Simulator can also run in a Linux desktop window or as a Windows executable, using the same simulator and API as the web app. See [Desktop applications](DESKTOP_APPLICATIONS.md) for installation, saved labs, available builds, and platform limitations.

**File → Open** selects a local Packet Tracker and Simulator JSON lab or imports a supported legacy network simulator `.pkt` file. The `.pkt` importer is partial and displays a warning before replacing the current lab. See [File import](FILE_IMPORT.md) for what is preserved, the API and the limitations.

In **Connections**, choose **Automatically Choose Connection Type**, then click two devices to connect compatible free data ports. The simulator chooses the matching cable type, preferring a working connection and copper when alternatives are equivalent. Hold Ctrl while choosing the tool to make multiple connections; press Escape to finish. The same operation is available to agents as `auto-connect PC1 SW1` through `POST /api/command`, with undo support. Unsupported devices or devices with no compatible free ports cannot be connected automatically.

On the logical canvas, **Shift+D** focuses a device. Arrow keys navigate; **Shift+Arrow** moves the focused device, and **Enter** opens it or uses the chosen connection tool. See [keyboard and accessibility controls](WORKSPACE_ACCESSIBILITY_REFERENCE.md#logical-canvas-keyboard-controls) for cycling overlapping devices, larger moves, manual port selection and limitations.

For verified network features and limitations, see [feature coverage](HELP_COVERAGE.md). The later [feature coverage](HELP_COVERAGE.md) includes reproducible measurements, [feature coverage](HELP_COVERAGE.md), and [feature coverage](HELP_COVERAGE.md).

## Core design rule

**Every completed feature must be controllable from both the GUI and the agent control plane.**

A feature is not considered complete until its simulator behavior, GUI surface, agent command/API, capability-registry entry, verification/query output, and relevant tests exist.

## Current working network features

- built-in catalogue with 152 network/end/IoT/component/cabling entries
- engine-backed hosts, routers, switches and specialized wireless/security/controller/cloud/industrial models; remaining catalog-only items are identified explicitly
- typed copper/fibre/serial/console/phone/coax cabling, powered modules and interface administrative/carrier state
- IPv4 addressing and host default gateways
- access VLANs, 802.1Q trunks, allowed VLAN lists and native VLANs
- router-on-a-stick / 802.1Q subinterfaces
- connected/static IPv4 routing
- simplified area-aware OSPF routing and neighbor inspection ([details](OSPF_AREAS_REFERENCE.md))
- DHCP pools, client leasing and routed DHCP relay (`ip helper-address`)
- dynamic ARP and switch MAC learning
- simulated DNS records, client resolver, HTTP webpages, Web Browser and DNS/TCP/HTTP event traces
- authoritative Realtime/Simulation scheduler, saved scenarios, complex periodic PDUs, captured headers/OSI views and deferred network clients (not wire-accurate)
- PVST/Rapid-PVST-style root election, port roles and redundant-link blocking
- EtherChannel: static, LACP and PAgP modes
- CDP and LLDP neighbor discovery
- stateful IOS-like router/switch CLI
- IPv4 ACLs with inbound/outbound interface binding and implicit deny
- stateful static NAT and interface PAT/overload with return translation tracking
- bidirectional ping validation and traceroute
- JSON lab save/load and automatic state persistence

Sections **33–73** now have shared simulation/device APIs, native configuration forms and behavioural tests. Services include FTP/TFTP, mail, AAA, NTP/PTP, syslog and SNMP; device models include wireless/WLC, home-router forwarding, controllers, IOx lifecycle, industrial switching/PLC/historian and observer checks. IPv6 supports static routing, SLAAC and local DHCPv6. See [the implementation/API reference](OPERATING_MODES_DEVICES_REFERENCE.md) for examples, testing instructions and exact limitations.

**File → Open Samples** provides original concept, DHCP skill, design and troubleshooting labs with copy-based checks and undoable loading. English/Spanish sample instructions, API access and contributor translation-pack guidance are described in [SAMPLES_TRANSLATION_REFERENCE.md](SAMPLES_TRANSLATION_REFERENCE.md).

## Feature coverage

See the feature and implementation notes in the documentation for tested capabilities and known limitations. The Help button opens original, self-contained application documentation from web/help/index.html; no other simulator installation is required.

The first pass includes **Options → Preferences** (Ctrl+R): visible device labels/link lights, configurable port labels, animation and interface/CLI font preferences, and a local user profile. Settings live in browser storage.

The **Place Note** tool now creates editable, movable, persistent logical-workspace annotations. Notes use the same simulator/control-plane state as topology devices. Example agent commands:

    note add 250 100 "Hospital distribution"
    note edit Note0 "Core distribution"
    note move Note0 300 145
    show notes
    note delete Note0

Unsupported legacy network simulator UI settings and protocol behaviors are explicitly marked as pending.

## Application help

The Help toolbar button and per-device help controls open this project's own help page. All documentation is shipped with the source and desktop builds; there is no external vendor-help service.

The first help-driven parity pass provides documented hierarchical **Global / Routing / Switching / Interface** Config navigation, an **Equivalent IOS Commands** preview, a device-name change tied to the simulator, router static routes and OSPF, switch VLAN database, server DHCP service setup, the PC IP Configuration screen with DHCP/static IPv4, and model-appropriate hardware images in Physical views. The UI retains planned/disabled controls for features without a simulator engine.

Implementation and remaining gaps are tracked in `HELP_COVERAGE.md`.

## Current UI direction

The GUI includes these networking workflow areas:

- top menu and two tool rows
- Logical / Physical workspace strip
- large central topology workspace
- topology-oriented resizable bottom dock with main categories, subcategories, search/filter, horizontal device tray and selected-device status
- draggable left/right column splitters plus a draggable dock-height splitter; sizes persist locally
- bottom Play Controls, Event List, Realtime/Simulation controls, Scenario/PDU region and full PDU table columns
- Realtime / Simulation area and PDU panel
- per-device windows with device-specific tabs
- PC window: Physical / Config / Desktop / Programming / Attributes

Packet Tracker and Simulator renders generic, original SVG network icons in both source and packaged versions. The interface controls, placement, saved layouts and network operations do not require external artwork or another simulator installation.

## Agent control plane

Discovery:

```bash
./netlab capabilities
./netlab capabilities pc
./netlab capabilities switch
./netlab capabilities R1
./netlab manual
./netlab state
```

Single command:

```bash
./netlab exec 'add router R1 400 250'
./netlab exec 'show interfaces R1'
./netlab exec 'catalog Routers'
./netlab exec 'add-model isr4331 R2 520 250'
```

Batch/world build:

```bash
./netlab batch labs/mini-city.netlab
```

Interactive shell:

```bash
./netlab shell
```

HTTP:

```text
GET  /api/health
GET  /api/state
GET  /api/capabilities
GET  /api/catalog
GET  /api/v1/connectivity/schema
POST /api/v1/connectivity/ping
POST /api/command
POST /api/batch
```

The batch endpoint accepts up to 10,000 ordered simulator commands and returns per-command results plus final state. The [connectivity verification API](CONNECTIVITY_VERIFICATION.md) reports typed IPv4/IPv6 reachability, failure reasons and simulation jobs without parsing command output.

See `AGENT_MANUAL.md` for the control-plane contract and discovery model.

## Bundled icons and help

The simulator includes its own SVG icons and user help. Proprietary third-party art, help files and executable binaries must not be added to the project or its releases.

## Run

```bash
cd /path/to/packet-tracker-and-simulator
./netlab serve
```

Open:

```text
http://127.0.0.1:8765
```

or:

```bash
./netlab open
```

## Example generated world

`labs/mini-city.netlab` creates a routed mini-city with a core network and Hospital, School, and Office zones entirely through the agent control plane. Cross-zone ping/traceroute is used to verify the generated topology.

## Major remaining work

- IPv6, NDP, SLAAC and DHCPv6
- HSRP
- DHCP snooping and DAI
- DTP and VTP
- richer OSPF neighbor/LSDB/cost/passive-interface behavior
- multilayer switching and SVIs
- DNS/HTTP/FTP/TFTP/email service simulation
- wireless networking and specialized WLC/AP behavior
- IoT/Home/Smart City/Industrial/Power Grid/Boards/Actuators/Sensors catalog parity and behavior
- frame/PDU animation and filtering
- deeper packet-accurate Simulation mode timeline semantics (the matching Event List/filters/play-control UI is now present)
- scenario grading and fault injection
- optional Linux namespaces/FRRouting backend

The long-term target is for an AI agent to receive a natural-language request such as “build a small city network,” discover all available devices/features, generate the complete topology/configuration, execute it, and verify that the network behaves correctly.

## Physical link behavior

other simulators' *My First PT Lab* demonstrates a direct PC-to-server Ethernet cable mismatch. Packet Tracker and Simulator models this legacy cabling case using the same deterministic network state:

```text
add pc PC1
add server SRV1
connect PC1 eth0 SRV1 eth0 copper-straight
show links                 # carrier down
disconnect PC1 eth0
connect PC1 eth0 SRV1 eth0 copper-cross
show links                 # carrier up
power SRV1 off             # carrier down; configuration preserved
power SRV1 on              # carrier up
```

`connect` without an explicit type still means `auto` for backward compatibility. `auto` keeps the link up whenever devices/ports are powered and administratively enabled, as before. Non-copper media remain marked as not implemented. The GUI's cable selector, power controls, line state colors, persistence and agent commands share this behavior.

## My First legacy network simulator Lab

This tutorial now has a reproducible example: labs/my-first-pt-lab.netlab. Run it ONLY against a disposable/empty simulator lab, because it adds devices and cables to the active network. The setup tests a failed straight-through PC-server link, replaces it with crossover, configures IPv4/DNS, and downloads the server's simulated HTTP webpage.

In GUI, use Server > Services > DNS/HTTP and Client > Desktop > IP Configuration/Web Browser. In Simulation mode, a web-page request waits for five DNS/TCP/HTTP events to be replayed with Capture/Forward before displaying the page. The Inspect tool displays ARP/MAC/route/interface tables. Power Cycle Devices clears learned tables and packet history but retains network configuration.

The Font/4K pass makes Preferences > Font > Global Size scale menus, toolbars, icons and palette controls, while preserving topology coordinate sizes. Browser validation confirmed 31px toolbar controls at size 12 and 46.5px at size 18.

All network services are simulated: no public Internet requests, no actual server listening on port 80, no packet serialization or true event-driven TCP implementation.

## Workspace Basics — linked Logical and Physical views

The Physical workspace now uses authoritative saved lab state, rather than maintaining a separate browser-only location list. Device creation in either workspace adds the same underlying device. Intercity contains the default Home City, Corporate Office and Main Wiring Closet.

Create cities, buildings or closets; rename or reposition physical location cards; drop a device from the model palette into a physical container; or use Move Object to relocate devices. Right-click a physical device to move it. Locations and device assignments persist through autosave and ordinary save/load, including migration from older lab files.

Agent examples (execute against an appropriate lab): physical add city Jaipur intercity; physical add building School city0; physical place PC1 loc0; physical rename loc0 "Jaipur Campus"; physical position loc0 240 150; show physical.

Physical placement does NOT change logical coordinates, IP addresses, cables or reachability. Physical cable-length effects, radio range, rack-slot behavior and generic physical containers are not implemented yet.

## Logical Workspace (Help section 13)

Click to select; Ctrl/Cmd-click or draw a marquee to select multiple devices. Drag the selection together, or Ctrl/Cmd-drag to duplicate. Copy/Paste/Undo/Redo work from the toolbar, Edit menu or standard keyboard shortcuts. Delete removes a selected group and its links after confirmation, as a single undoable edit.

Ctrl/Cmd-click a device or cable type in the palette to lock repeated placement, while normal clicking places once. Esc cancels. Options > Preferences > Interface enables alignment guides and snap-to-device. Fit Workspace is based on actual topology bounds; Viewport is a clickable topology mini-map.

Logical clusters and nested clusters are now included in saved lab JSON. You can cluster multiple selected devices, open a cluster, create subclusters, rename by double-clicking its label, or use Delete to uncluster without deleting network hardware. A cluster can be managed through the agent shell.

Example commands:
  duplicate PC1,SW1 120 80
  move-group PC1,SW1 40 50
  remove-group PC1,SW1
  undo
  redo
  cluster add Campus PC1,SW1
  cluster add Floor1 PC1 Cluster0
  cluster place PC2 Cluster0
  cluster rename Cluster0 "Main Campus"
  cluster move Cluster1 root
  cluster delete Cluster1
  show clusters

Cloning keeps configuration (including IP addresses, which can conflict), regenerates interface MAC addresses and recreates links only between cloned members. Undo/Redo retains at most 64 in-memory snapshots during the current server session. Hardware slots, full canvas panning, advanced docking and custom device templates remain incomplete.

## Workspace List (third-party vendor Help section 14)

Open Workspace List from View menu or workspace toolbar. It shows currently visible logical devices and immediate child clusters, model, power, x/y coordinates, links with cable endpoints and operational link-light status, and physical module layout for a selected device. Navigate clusters using the row or Show Parent Cluster. Add/remove devices and links, edit coordinates, toggle power and install/remove supported virtual expansion modules from the table.

API-first: GET /api/workspace-list, GET /api/workspace-list/schema, POST /api/workspace-list/action. Agent operations use the same NetworkLab, command processor, undo/redo and autosave. See API_FEATURE_CONTRACT.md for mandatory API exposure and testing of every future feature.

Expansion modules PT-ETH-1 and PT-ETH-4 are SYNTHETIC Ethernet modules for generic PT simulation profiles; real third-party vendor model slot compatibility is not claimed. Module edits require device power off and disconnected module ports. Fiber, serial and console cabling are not yet modeled. The HTTP API has no authentication; keep the service bound to 127.0.0.1.

## Workspace List (Help section 14)

From View > Workspace List or the Workspace List button beside Logical/Physical tabs, open the keyboard-accessible table dialog. It displays only devices and links visible in the current logical cluster, with parent-cluster navigation, device model, powered status, editable X/Y position and a live link status indicator.

Select a device to inspect onboard interfaces and modeled expansion slots. Add/remove devices, power them on/off, change coordinates, create/remove auto/straight/crossover copper links and manage supported simulated modules through the same backend as the agent. Module insertion/removal requires power-off; removing a cabled module is refused. third-party vendor-specific hardware SKUs, serial and fibre link types are not yet modeled and are not presented as supported.

REST API:
- GET /api/workspace-list?cluster=root&device=R1 — visible devices, clusters, links and selected module slots.
- GET /api/workspace-list/schema — machine-readable action examples and explicit limitations.
- POST /api/workspace-list/action — typed JSON actions (add_device, remove_device, move_device, power_device, add_link, remove_link, set_module, undo, redo).
- GET /api/capabilities — agent capability registry.

Example (against your own selected lab): curl -X POST http://127.0.0.1:8765/api/workspace-list/action -H 'content-type: application/json' -d '{"action":"move_device","device":"R1","x":260,"y":300}'.

Pass cluster=Cluster0 to add_device to create the device directly inside that cluster as one undoable action, rather than creating an invisible root device. CLI equivalent: add-in-cluster pc-pt PC2 200 180 Cluster0.

The localhost API is unauthenticated. Do not expose it directly to other hosts; use an authenticated proxy or add access control before remote or multiuser deployment.

## Physical Workspace (third-party vendor Help section 15)

Open the Physical tab for the Intercity / City / Building / Wiring Closet hierarchy. Create and nest Generic Containers, change their metric dimensions, rename or relocate them, and drag their cards. The model validates container types, dimension fit and parent cycles. Devices placed here are the same simulation devices visible in Logical view. Device creation+placement is one atomic Undo action; physical device positions are persisted separately from logical coordinates.

Within a Wiring Closet, the view now exposes Rack, Table, Floor and user-created Storage Shelves, with equipment movement and basic link lights. A device must be powered OFF and disconnected before storage on a shelf, and cannot be powered on or cabled while stored. Rack/table slots and front/back hardware layouts remain visual-only.

All behavioural controls have a documented agent-facing API: GET /api/physical-workspace?location=closet0, GET /api/physical-workspace/schema, and POST /api/physical-workspace/action. CLI actions include physical add generic, physical add-device, physical dimensions, physical relocate, physical device-position, physical shelf-add and physical mount. See PHYSICAL_WORKSPACE_REFERENCE.md for full coverage and explicit gaps; distance effects and pegboards remain unimplemented.

## Physical Moving Devices and Navigation (third-party vendor Help section 16)

Switch to Physical and choose **Navigation** to browse the complete Intercity/City/Building/Wiring Closet hierarchy and all devices. Check several devices, then choose **Move here** on a destination, or drag devices/containers onto a destination row. **Move Object** in the Physical toolbar arms a click-to-select mode on a map device or location; it opens the tree with that object selected. Moving several devices is one undoable API operation. Cross-city cables appear as map lines with operational status and aggregate link counts. Destination map objects start stacked at top-left; rack/table devices use their respective furniture surfaces.

API: GET /api/physical-workspace/tree, GET /api/physical-workspace?location=intercity (boundary_links), POST /api/physical-workspace/action action=move_devices. CLI: physical move-devices R1,R2 loc0. Read PHYSICAL_MOVING_REFERENCE.md for exact implementation limits and reference mapping.

## Physical Distance Measurements (third-party vendor Help section 17)

Physical map dimensions now calibrate a 2D metric world across intercity, cities, buildings, closets and nested containers. A new Distances panel in Physical view lists cable endpoints, estimated straight-line length and live carrier status. In **Options > Preferences > Interface**, enable Cable Length Effects to apply the documented 100m copper limit; this setting is saved and off by default. Show Wireless Grid draws Wi-Fi/cellular/Bluetooth coverage estimates; radio radii can be edited in metres. Geometric RF coverage is **not** wireless association or packet forwarding.

Agent commands: physical measure PC1 PC2; physical cable-length R1 g0/0; physical cable-effects on; physical radio-range AP1 180. Read via GET /api/physical-distance?location=city0, /api/physical-distance?source=PC1&target=PC2, or /api/physical-distance/schema; write through POST /api/physical-distance/action. Detailed assumptions/limitations in PHYSICAL_DISTANCE_REFERENCE.md.

## Section 18: Portable Icons and Backgrounds

The Physical Workspace Background button now opens a working PNG/JPEG chooser with Browse, Apply, Reset, optional tiling, colour and a read-only calibrated metric scale. Different physical locations can have independent backgrounds. In a device's Physical tab, both Customize Icon in Physical View and Customize Icon in Logical View are functional and independent. Uploaded images are validated and embedded in the native saved lab JSON, not only the browser cache; images and assignments survive lab save/load across OSes. Images are deduplicated by SHA-256. Supported operations are discoverable at GET /api/visuals/schema and writable through POST /api/visuals/action; the agent shell can import local image files. Details, limits and gaps: PHYSICAL_CUSTOMIZATION_REFERENCE.md.

## Physical Cable Manipulation (third-party vendor Help §19)

In Physical Workspace, click any visible cable to create a BendPoint or choose its colour. Drag black BendPoints to route cables; drag one onto another cable's BendPoint to create a shared yellow GroupPoint. Move the GroupPoint to move grouped cable routes together. Click points to ungroup or delete bends without removing connections. The Cable Manipulation panel provides a list and Undo/Redo. Routed 2D cable total length now affects Ethernet carrier when opt-in cable-length effects are enabled; direct distance remains available separately. CLI: cable bend-add, bend-move, bend-delete, group, group-move, ungroup, color. API: GET /api/physical-cables, /schema; POST /api/physical-cables/action. All persistent changes share the lab JSON and agent history. See PHYSICAL_CABLE_MANIPULATION_REFERENCE.md for examples and UI/3D limitations.

## Industrial Control Panel (third-party vendor Help §20)

The Physical Workspace has a **New ICP** tool with Small/Medium/Large control cabinets. Enter an ICP to view its door and cabinet: open/close using the handle, Shift-click the location icon for a read-only closed-door preview, and add DIN rails or horizontal/vertical Wire Conduits. Shift-drag transfers devices between door and cabinet; Ctrl-drag detaches DIN-mounted devices or rail segments. Tab cycles six snap anchors during drag. Device positions, fixtures, groups and DIN attachments persist with native lab JSON and have full CLI/REST agent controls. API: GET /api/icp?location=loc0, GET /api/icp/schema and POST /api/icp/action. This is a physical layout model, **not a functional industrial control/PLC/electrical simulator**. Details in ICP_REFERENCE.md.

ICP cabinets also include a network connection pane: choose two devices and unused Ethernet ports to create a real cable using the same shared Link engine as the Logical Workspace. Connected port states are displayed even in read-only closed-door preview. DIN/WIC remain purely decorative.

## Section 21: Accessible Physical Navigation

Click **Accessible** on the Physical Workspace toolbar (or use **Alt+Shift+A**) to open a focus-managed, screen-reader-ready dialog. Use Tab, Arrow keys and Enter to navigate the physical location tree, inspect ports/link status and equipment surfaces, take/place devices, mount on Rack/Table/Floor/Shelf, add core devices, connect/disconnect Ethernet links, change power or install modules when powered off. GET /api/physical-accessibility, /schema, and POST /api/physical-accessibility/action provide the same agent controls; all writes use the saved authoritative lab. This is not yet an audited WCAG-compliant application; OS screen readers need manual testing. Details: PHYSICAL_ACCESSIBILITY_REFERENCE.md.

## Physical Workspace Special Notes (Section 22)

Physical toolbar Grid now saves metre spacing, colour and visibility per map container type through the backend. Delete tool and Delete Location preview subtree removal, then extract all equipment onto the parent floor while preserving network configuration/cables. Undo/Redo restores the complete edit. Creating devices still works after deleting the original building/closet. GET /api/physical-workspace adds grid geometry/profiles and deletion previews; POST actions add set_grid and delete_location. See [PHYSICAL_SPECIAL_NOTES_REFERENCE.md](PHYSICAL_SPECIAL_NOTES_REFERENCE.md) for API examples, limits and isolated browser verification.

## Workspace and Accessibility — Sections 23–32

Added portable logical/cluster artwork (including GIF), shared Logical/Physical viewports, configured device/cluster/container template management and JSON portability, accessible event inspection, keyboard/menu/tab controls, terminal focus exit, saved contrast and application scaling. All durable operations are authoritative API/CLI actions with history, validation and saved-state compatibility. Discovery: GET /api/workspace-tools/schema; read: GET /api/workspace-tools; write: POST /api/workspace-tools/action or workspace-tool '<JSON>'. Existing /api/visuals now supports logical backgrounds and cluster icons.

259 Python tests pass, including 200-device template capture/creation and isolated HTTP atomicity. Isolated Chromium checks real controls, templates, viewport pan, artwork, accessible names, contrast, 4K and persistence without touching the active lab. Defined browser scope is complete through Section 32; native third-party vendor file formats and OS screen-reader certification remain outside the verified scope. Details, shortcuts and limits: [WORKSPACE_ACCESSIBILITY_REFERENCE.md](WORKSPACE_ACCESSIBILITY_REFERENCE.md). Next sequential phase: Section 33.

### Topology clarity

Use **Topology display** in the upper toolbar for separated straight cables, smart labels,
neighbor highlighting, zoom-aware detail, collapsible groups and an undoable
Tidy Layout preview. [Usage, agent API and measured limits](TOPOLOGY_PRESENTATION.md).

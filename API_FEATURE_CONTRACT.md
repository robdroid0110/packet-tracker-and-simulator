# Packet Tracker and Simulator API-First Feature Contract

This file is a standing project rule. Apply it to every future implementation,
including device engines, networking protocols, workspaces, simulation, accessibility,
IoT, automation, file handling and mobile interfaces.

## Definition of done for a feature

1. **One authoritative model.** No browser-only copy of simulation state. UI and agents
   must read and mutate the same NetworkLab through a shared command processor.
   UI-specific preferences (font, local presentation) are the only exceptions.
2. **Agent control is mandatory.** Every new operation has documented CLI access and/or
   a typed JSON HTTP endpoint; retrieval has a corresponding read endpoint. New
   interface elements must never be clickable demos with no underlying behavior
   unless explicitly labelled unsupported and disabled.
3. **Discoverable capabilities.** Publish machine-readable actions in
   GET /api/capabilities, and for structured workflows expose an endpoint-specific
   schema (GET /api/workspace-list/schema is the current example).
4. **Validation, atomicity and isolation.** Validate types, ranges, names, references,
   media compatibility and power state in the model or shared service. Return meaningful
   errors, never silently succeed. Write operations use the shared lock, saved state
   and command-history mechanics. Never touch an active user's saved lab during tests.
5. **Persistent state.** Durable features must survive save/load/autosave, load older
   lab versions where feasible and reject corrupt data. Explain limitations and
   migration behavior.
6. **Tests at three levels.** Verify model/CLI unit tests, HTTP API contract tests
   with isolated temporary state, and browser interactions for GUI workflows.
   Include negative tests and representative 100-200-device scaling checks.
7. **Explicit simulation limits.** Implemented, simplified, catalog-only, and
   unsupported behavior must be distinguishable in the GUI, API schema and docs.
8. **Security boundary.** Default server bind is 127.0.0.1. Current HTTP edit
   endpoints have no authentication; DO NOT expose the server directly to an
   untrusted LAN or the Internet. Add authentication, access control and transport
   security before deploying remote or multi-user control.

## Connectivity verification

For typed IPv4/IPv6 ping verification, use `GET /api/v1/connectivity/schema` and
`POST /api/v1/connectivity/ping`; the shared backend, queued simulation result,
side effects, and current limitations are described in [the connectivity reference](CONNECTIVITY_VERIFICATION.md).

## Workspace List: implemented API

Read the currently visible logical workspace:

~~~http
GET /api/workspace-list?cluster=root
GET /api/workspace-list?cluster=Cluster0&device=PC1
GET /api/workspace-list/schema
GET /api/capabilities
~~~

The JSON projection includes only directly visible devices and links, the
current cluster's immediate children, current location path, and optional
selected device module slots. Parent/Root navigation is read-only.

Modify from UI or agent using a typed action:

~~~http
POST /api/workspace-list/action
Content-Type: application/json

{"action":"add_device","model":"router-pt","name":"R1","x":180,"y":140}
{"action":"add_device","model":"pc-pt","name":"PC2","x":220,"y":180,"cluster":"Cluster0"}
~~~

Available actions: add_device, remove_device, move_device, power_device,
add_link, remove_link, set_module, undo, redo. Refer to
GET /api/workspace-list/schema for validated JSON examples and supported
cables/module types. Every action goes through the authoritative command
processor and shares undo/redo history.

Current module support is an intentionally limited virtual expansion:
PT-ETH-1 and PT-ETH-4 on generic Router-PT, Switch-PT, PC-PT,
Laptop-PT, Server-PT and base generic-class simulated devices.
Real vendor SKU/slot compatibility is NOT claimed. Power off devices to
change modules and disconnect module links before removal.
Other vendor-specific module slots are read-only/unsupported.

## Future work gate

Before merging any future UI feature, verify there is a concrete API
or shell action for its operation, a machine-readable capability entry,
persistence where required, and tests proving both UI and agent semantics.
If any requirement cannot be implemented, label the control unsupported
rather than inventing a successful simulation.

## Physical Workspace implementation contract (section 15)

Authoritative operations are read by GET /api/physical-workspace, described at GET /api/physical-workspace/schema and changed via POST /api/physical-workspace/action. Individual actions also have CLI equivalents through the shared CommandProcessor. Physical map coordinates, container dimensions, placement and shelf state persist in saved lab JSON. API creates a device in a chosen physical container atomically. The API deliberately marks distance effects, wireless propagation, rack-unit geometry and pegboards as unsupported until the relevant protocol/physics engines exist. See PHYSICAL_WORKSPACE_REFERENCE.md.

## Physical Moving Devices API requirement (Section 16)

The Physical hierarchy is queryable as GET /api/physical-workspace/tree. A relocation batch uses POST /api/physical-workspace/action with action move_devices and a list of 1–200 validated unique device names. The same command processor provides one Undo step and persisted physical state. Cross-location link-line data is calculated server-side as boundary_links in GET /api/physical-workspace?location=... rather than invented browser geometry. The browser provides keyboard move buttons as well as drag/drop.

## Section 17 — Distance API contract

The physical world metric projection, cable length/100m enforcement and radio range source properties live in the shared Python model. All edits are undoable via typed POST /api/physical-distance/action and CLI, while GET /api/physical-distance and /schema expose source values. Preferences uses this same API; its wireless grid toggle is browser presentation only. No UI-only carrier simulation or fake wireless association. Documentation: PHYSICAL_DISTANCE_REFERENCE.md.

## Section 18 — portable asset API

Native visual asset storage is in the shared NetworkLab: visual_assets (SHA-256, validated PNG/JPEG data and metadata), device_icons (view-specific hashes), location_backgrounds (location-specific image/tile/color). Browser actions always go through POST /api/visuals/action and are discoverable from /api/visuals/schema and /api/capabilities. Original bytes are served at GET /api/visuals/assets/<sha256>. The JSON lab save/load includes all assignments and image data. No PNG/JPEG path traversal, remote URL loading or HTML/SVG payload support; uploads are limited. See PHYSICAL_CUSTOMIZATION_REFERENCE.md.

## Section 19 — cable geometry API contract

Persistent cable routing is exclusively authoritative in NetworkLab.cable_routes (keyed by canonical network port endpoints): ordered 2D world-meter BendPoints, shared GroupPoint IDs, and per-cable colour. GET /api/physical-cables and /schema expose readings, units and action contracts; POST /api/physical-cables/action delegates every mutation to CommandProcessor for common undo/autosave. Optional copper-length carrier checks consume the **routed** cable total, not the direct device distance. Browser SVG is only a presentation. Deleting bends/groups must never disconnect the existing link; disconnecting the link discards orphaned cable geometry. See PHYSICAL_CABLE_MANIPULATION_REFERENCE.md.

## Section 20 — ICP API contract

Native physical location type icp and model-backed icp_panels state: size preset, door_closed, workspace_mode, keyed DIN/WIC fixtures and shared strip IDs, per-device mounts and six-position snap anchors. Physical device surfaces are cabinet/door, distinct from closet rack/table. GET /api/icp /schema and POST /api/icp/action delegate to the same CommandProcessor/NetworkLab and saved JSON as all other agent actions, including Undo/Redo. The browser is a presentation and gesture layer only. A closed-door workspace preview is read-only for layout edits; it is not a PLC/electrical network mode. Full semantics and limits: ICP_REFERENCE.md.

- ICP's cabinet cable form is intentionally wired through existing POST /api/command connect/disconnect operations, rather than inventing a separate networking API. Cabinet placement updates never silently alter existing network links; only explicit connection actions do.

## Section 21 — Physical Accessibility

GET /api/physical-accessibility?location=closet0 exposes an accessible, authoritative physical hierarchy, equipment mount surfaces, port connection status and module slots. GET /api/physical-accessibility/schema advertises the command contract. POST /api/physical-accessibility/action translates typed actions into existing CLI commands via CommandProcessor with Undo/Redo, link and power validation, and autosave. Browser navigation, Take selection and source cable port selection are nonpersistent and do not mutate the lab. See PHYSICAL_ACCESSIBILITY_REFERENCE.md for coverage and screen-reader test limitations.

## Section 22 — Physical Special Notes

Physical Workspace schema v2 adds set_grid (container_type, enabled boolean, spacing_m, color) and delete_location (location). The existing GET view includes authoritative grid geometry/profiles and a read-only delete_preview. Both new GUI workflows call POST /api/physical-workspace/action, sharing CommandProcessor, locking, history and saved state. Container deletion removes its subtree and extracts devices onto the surviving parent floor, preserving network configuration/links. Grid settings are additive native JSON state; older labs receive defaults. Model/HTTP tests include invalid-input atomicity, save/load, 200-device preservation and working ping; a reproducible isolated Chromium harness tests actual controls. See PHYSICAL_SPECIAL_NOTES_REFERENCE.md.

## Workspace and Accessibility — Sections 23–32

Added portable logical/cluster artwork (including GIF), shared Logical/Physical viewports, configured device/cluster/container template management and JSON portability, accessible event inspection, keyboard/menu/tab controls, terminal focus exit, saved contrast and application scaling. All durable operations are authoritative API/CLI actions with history, validation and saved-state compatibility. Discovery: GET /api/workspace-tools/schema; read: GET /api/workspace-tools; write: POST /api/workspace-tools/action or workspace-tool '<JSON>'. Existing /api/visuals now supports logical backgrounds and cluster icons.

259 Python tests pass, including 200-device template capture/creation and isolated HTTP atomicity. Isolated Chromium checks real controls, templates, viewport pan, artwork, accessible names, contrast, 4K and persistence without touching the active lab. Defined browser scope is complete through Section 32; native vendor file formats and OS screen-reader certification remain outside the verified scope. Details, shortcuts and limits: [WORKSPACE_ACCESSIBILITY_REFERENCE.md](WORKSPACE_ACCESSIBILITY_REFERENCE.md). Next sequential phase: Section 33.

## Topology presentation

Saved diagram preferences, collapsible groups and signed layout preview/apply use
`/api/workspace-tools/action` and `/api/topology-layout`; see
[Topology presentation](TOPOLOGY_PRESENTATION.md) for the GUI, API, limits and benchmarks.

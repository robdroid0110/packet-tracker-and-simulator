# vendor Help Section 20 — Industrial Control Panel (ICP)

Reference: /reference/ot_icp.htm from locally installed legacy network simulator 9 help.
Implementation: 2026-11-04.

## Working functionality

- Physical toolbar New ICP creates a named Small, Medium, or Large ICP, fitted to an existing physical container. Panel appears as a Physical Workspace icon, and can be entered like a Wiring Closet.
- Shift-click the ICP location icon to enter a closed-door, read-only Workspace preview. The door handle opens/closes it and exits preview. Equipment on the door shows in the front or back-side presentation; double-click an item to open its device window.
- Any device model can be placed inside ICP without adding hardware restrictions. Door and cabinet are independent, persistent device mounting surfaces. Shift-drag transfers a device between door and cabinet. Ctrl-drag detaches a DIN-mounted device.
- Every device/fixture position is snapped to a 20-unit dot grid. Tab during device dragging cycles six snap anchor offsets. Anchors persist with each device.
- Add, move, group, split and delete layout fixtures: DIN (horizontal only) and Wire Conduit/WIC (horizontal or vertical). Joined same-type/same-orientation strips move together; Ctrl-drag separates a fixture.
- Devices can be mounted on DIN rails; dragging a rail or one of its attached devices moves the rigid assembly. Removing a fixture unmounts its devices but never deletes them or their existing network cables.
- All ICP state is authoritative in the shared Python NetworkLab; GUI, agent API and CLI use CommandProcessor Undo/Redo and lab autosave. Presets, door/preview state, fixtures and groups, mounting assignments and snap anchor positions survive native JSON save/load.
- Native normal network ports, physical link statuses and already implemented cable routing continue to work. ICP layout does not itself implement industrial electronics.

## Preset sizes and coordinate conventions

The inspected vendor text names predefined ICP sizes but does not provide exact numerical dimensions. Packet Tracker and Simulator approximations (metres), not vendor-certified measurements:

| Preset | Width | Depth/Length | Height |
|---|---:|---:|---:|
| Small | 1.2 | 0.6 | 1.8 |
| Medium | 1.8 | 0.8 | 2.0 |
| Large | 2.4 | 1.0 | 2.2 |

ICP devices and fixtures use local 0..1000 x/y coordinates (20-unit grid), distinct from Section 17's world metres. The cabinet fits within its parent geographic container; ICP cannot contain nested physical location types.

## Agent shell

    icp create medium "Factory Panel" building0
    icp door loc0 on                  # on = closed
    icp preview loc0 on               # closed-door read-only preview
    icp device-move R1 cabinet 260 160 0 attached
    icp device-move R1 door 400 280 3 detach
    icp fixture-add loc0 din horizontal 200 160
    icp fixture-add loc0 wic vertical 320 160
    icp fixture-join loc0 fixture0 fixture1
    icp fixture-move loc0 fixture0 400 220 attached
    icp fixture-move loc0 fixture0 430 260 detach
    icp fixture-split loc0 fixture0
    icp fixture-delete loc0 fixture1
    icp mount R1 fixture0
    icp unmount R1
    undo
    redo

Location and fixture IDs are returned by create/add responses. An agent can discover the entire ICP through GET /api/icp?location=loc0.

## Agent REST API

GET /api/icp?location=loc0
GET /api/icp/schema
POST /api/icp/action
GET /api/capabilities

The view reports location geometry, size preset, door/preview state, all fixture positions/orientations/strip groups, devices, mounting side, snap anchor and attached DIN fixture.

POST JSON examples (one action at a time):

    {"action":"create","size":"medium","name":"Factory Panel","parent":"building0"}
    {"action":"door","location":"loc0","closed":true}
    {"action":"preview","location":"loc0","enabled":true}
    {"action":"device_move","device":"R1","side":"door","x":400,"y":280,"anchor":2,"detach":false}
    {"action":"fixture_add","location":"loc0","kind":"din","orientation":"horizontal","x":200,"y":160}
    {"action":"fixture_add","location":"loc0","kind":"wic","orientation":"vertical","x":300,"y":200}
    {"action":"fixture_move","location":"loc0","fixture":"fixture0","x":450,"y":220,"detach":true}
    {"action":"fixture_join","location":"loc0","fixture":"fixture0","other":"fixture1"}
    {"action":"fixture_split","location":"loc0","fixture":"fixture0"}
    {"action":"fixture_delete","location":"loc0","fixture":"fixture0"}
    {"action":"mount","device":"R1","fixture":"fixture0"}
    {"action":"unmount","device":"R1"}
    {"action":"undo"}
    {"action":"redo"}

The API is localhost-only and has no built-in authentication. Do not expose it directly to the public Internet.

## Explicit limitations

- ICP is a 2D physical panel editor, NOT a full industrial control/electrical engine. No PLC scan logic, motor controllers, overload relays, circuit breaker behavior, electrical power circuits, true DIN clamp geometry or 3D physical collision.
- Wire conduits are aesthetic and are not electrically connected (consistent with the vendor's help description). Normal network cabling uses the existing Link model; no conduit signal routing.
- Strip grouping and snap targets approximate the vendor's physical assembly behavior, not pixel-perfect factory geometry. Door-back rendering uses a label indicator rather than distinct back-facing 3D equipment models. The preview does not reproduce the vendor's exact door-flip animation.
- The parent Packet Tracker and Simulator application still has broader mobile-width navigation/workspace limitations; this phase constrains the ICP editor itself to the viewport.
- vendor PKT/PKA native import/export remains unsupported. ICPs survive Packet Tracker and Simulator native JSON lab save/load.

## Verification

- 215 Python tests passed including real isolated HTTP tests, invalid-action rejection, cabinet hierarchy and dimensions, anchor snapping, rigid DIN movement, WIC nonconductive rules, read-only preview, undo/redo, legacy JSON, 200-device queries and device rename/move cleanup.
- Headless Chromium isolated GUI test: New ICP toolbar, create/enter, door toggle, DIN/WIC menu, DIN mounting, Shift-drag to door + Tab anchor, preview read-only, Shift-click icon preview, Ctrl-drag DIN detach, viewport at 1600/1024/390px, zero JavaScript exceptions. The 390px ICP editor panel was measured at ~372px after responsive fix.
- Production lab is backed up before service restart.

## ICP cabinet network connections (Section 20)

A Cabinet Network Connections pane now lists the real simulated links attached to devices inside the ICP, including exact endpoint interfaces and UP/DOWN reasons. If two or more devices are inside the cabinet, a select-port form enables Connect Auto Ethernet using POST /api/command and the existing normal Ethernet engine. The same pane supports explicit confirmed disconnection. Closed-door Workspace preview shows these link states read-only, without connect/disconnect actions. This is a real logical/physical Ethernet connection, *not* DIN/WIC electrical wiring. The corresponding agent API already exists via /api/command, the CLI connect/disconnect verbs and /api/workspace-list/action. Isolated Chromium connected PC1:eth0 to R1:g0/0 and verified an operational UP link, then verified edit actions disappeared in preview; zero JS errors.

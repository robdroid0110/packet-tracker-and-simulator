# vendor Help Section 16 — Physical Workspace: Moving Devices

Reference: /reference/workspace_physical_movingDevices.htm (bundled legacy network simulator 9 help).

## Implemented (Nov 4, 2026)

Physical navigation tree:
- Physical workspace toolbar -> Navigation opens a hierarchical window containing Intercity, cities, buildings, wiring closets, generic containers and all their devices.
- Expand/Collapse, Open destination, checkbox-based multi-device selection, and drag-and-drop moves between location rows.
- Select a container in the tree and move it to another container, or drag it onto a location. Type/size/cycle restrictions remain enforced in NetworkLab. Invalid attempts show the engine error, not success.
- Undo/Redo buttons affect the same command history as the Agent Shell and rest of the app.
- Keyboard-operated buttons and checkboxes provide an alternative to mouse drag-and-drop. Escape closes the navigation window.

Move Object toolbar:
- Physical -> Move Object arms the selection cursor. Clicking a device (in a wiring closet or map) opens Navigation with that device selected; clicking a container opens it with the container selected.
- Moving 1–200 selected devices is one atomic, validated, persisted action and one Undo entry. Moving a group to a geographic map places all devices at the destination's upper-left (28,24); these overlap, matching the reference initial-placement behaviour. In wiring closets, router/switch objects go to racks and end devices to tables. Existing logical coordinates, IPs and links are preserved.
- Relocating a building or closet changes its parent without recreating its descendants, so its devices and existing cables remain intact.
- Working Closet and Back buttons are still available from the Physical Workspace bar.

Connection indicators:
- Intercity and other map levels show a line for any operational logical cable connecting devices in separate visible child locations. The line is based on aggregated GET /api/physical-workspace?location=... boundary_links, not on invented "city links".
- Multiple cables are counted and indicated by a label. A down link is dashed, an operational link solid. Moving both ends into the same city removes the intercity line.

## Agent API: required parity

- GET /api/physical-workspace/tree : nested location/device hierarchy, including model, status and surface.
- GET /api/physical-workspace?location=intercity : boundary_links aggregated between separate visible locations and the other Section-15 data.
- GET /api/physical-workspace/schema : typed action definitions.
- POST /api/physical-workspace/action : JSON move_devices and existing relocate_location, undo, redo, place_device, position_device.
- GET /api/capabilities advertises physical_workspace.tree and workspace.physical_move_devices.

Examples:
  ./netlab exec 'physical move-devices R1,R2 loc0'
  ./netlab exec 'physical relocate building0 loc0'
  ./netlab exec 'undo'

POST /api/physical-workspace/action body:
  {"action":"move_devices","devices":["R1","R2"],"location":"loc0"}
  {"action":"relocate_location","location":"building0","parent":"loc0"}

All writes are through the same NetworkLab and CommandProcessor used by the GUI. Lab autosave and JSON export/import retain placement and hierarchy state. The API binds to localhost by default and does not authenticate remote callers: do not expose it to untrusted networks.

## Gaps relative to Cisco

- No true drag-to-reorder equipment in individual rack slots; rack unit physical dimensions and front/rear chassis are not modeled.
- Multi-device selection by drawing a rectangle around overlapping map icons is not available; use the Navigation tree checkboxes or drag an already-selected group instead.
- Cables have logical reachability but not physically measured length or wireless range. Section 17 covers distance physics.
- The Navigation tree is a working accessibility-oriented alternative, not a pixel-perfect reproduction of the vendor's panel.

## Verification

- 143 Python automated tests, including isolated real HTTP API tests and validation failures, pass.
- Isolated headless Chromium: moving R1 between cities; Undo/Redo; container reparenting; Move Object click selection; tree navigation; responsive 1600/1024/390px dialog; no JavaScript exceptions.
- Second browser test: a solid black line appeared between separated connected cities with correctly different icon positions; 202 device rows rendered successfully after creating 200 devices in the isolated test lab (~1.1 s combined batch + UI on this machine).
- The active user lab was not used for testing.

# vendor Physical Workspace — Cable Manipulation (Section 19)

Reference: /reference/workspace_physical_cableManipulation.htm from the locally installed legacy network simulator 9 help.

## Implemented — 2026-11-04

- Clicking a visible physical cable opens Create BendPoint / Color Cable options. A black circular BendPoint can be dragged to route a cable along a polyline. Creating, moving or deleting BendPoints never disconnects the Ethernet link. Add Bend buttons also exist in the Physical workspace Cable Manipulation panel.
- BendPoints use **world coordinates in metres**, not browser pixels, and are projected into the current physical location using the existing Section 17 metric frame. They remain stable when switching cities, changing backgrounds, or editing through an agent.
- Grouping: drag a BendPoint onto a BendPoint belonging to another cable to form a shared **yellow GroupPoint**. Moving the yellow square moves both/all member bends together. Explicit GroupPoint API can attach additional cables. Multiple separate GroupPoints can appear on the same cable; the cable segment between two group points renders black, regardless of that cable's normal colour.
- Colour Cable supports an RGB colour picker with Apply and Reset. Individual non-grouped cable segments retain their specified colour, default #24354b. A single cross-location link also reflects its custom colour in the intercity map overview.
- Clicking a BendPoint offers Delete BendPoint (keep cable); clicking a GroupPoint offers Ungroup this cable, Ungroup all cables, or Delete BendPoint. Deleting any point never deletes a connected link. The Delete tool exposes the same point-editing menu.
- Routed cable **total length** now sums every straight segment between its endpoints and ordered bends. GET /api/physical-distance reports each segment, direct endpoint distance, total routed cable length and link operational status. With Section 17's optional cable-length effects ON, Ethernet exceeds the 100m limit if the **routed total** exceeds 100m, even when direct endpoint distance is less. Cable routing changes trigger OSPF recomputation where enabled.
- Port addresses, router configurations, and logical topology geometry are preserved. All geometry/colours/groups persist in the **same native JSON lab**, with Undo/Redo.
- Per-cable limits: 64 bends; across lab, 4000 bends, with bounded world coordinates. Invalid routes, duplicate bend identifiers, dangling links, broken group membership and inconsistent saved group coordinates are rejected during load.

## Agent shell commands

    cable bend-add R1 g0/0 1234 5678 [after-bend-id|start]
    cable bend-move R1 g0/0 bend_<id> 1340 5720
    cable bend-delete R1 g0/0 bend_<id>
    cable color R1 g0/0 #ff3300
    cable group R1 g0/0 bend_<id> R2 g0/1 bend_<id>
    cable group-move group_<id> 1340 5720
    cable ungroup group_<id> [R1 g0/0]
    undo
    redo

Bend positions are world **metres**, not physical canvas pixels. GET /api/physical-cables?location=city0 returns the world origin, metres-per-canvas-unit scale, projected path coordinates, endpoints, bend IDs, GroupPoint IDs, lengths and colours for that location.

## Typed API

    GET /api/physical-cables?location=city0
    GET /api/physical-cables/schema
    POST /api/physical-cables/action
    GET /api/physical-distance?device=R1&interface=g0/0
    GET /api/capabilities

POST JSON examples:
- {"action":"add_bend","device":"R1","interface":"g0/0","x_m":1234.0,"y_m":5678.0,"after":"start"}
- {"action":"move_bend","device":"R1","interface":"g0/0","bend":"bend_<id>","x_m":1334.0,"y_m":5678.0}
- {"action":"delete_bend","device":"R1","interface":"g0/0","bend":"bend_<id>"}
- {"action":"set_color","device":"R1","interface":"g0/0","color":"#fa0044"}
- {"action":"group_bends","device":"R1","interface":"g0/0","bend":"bend_<id>","other_device":"R2","other_interface":"g0/1","other_bend":"bend_<id>"}
- {"action":"move_group","group":"group_<id>","x_m":1334.0,"y_m":5678.0}
- {"action":"ungroup","group":"group_<id>","device":"R1","interface":"g0/0"} — omit device/interface to ungroup all.
- {"action":"undo"} / {"action":"redo"}

The API is built on the same NetworkLab and CommandProcessor as the GUI and shell. No alternate browser-only state is used for cable routing.

## Explicit limits / future parity

- Cable manipulation on the GUI canvas is available when both endpoints are directly visible in the **same current physical location**; cable groups spanning hidden descendant locations can still be queried/edited through the agent shell and API. Between cities, the existing aggregated link line remains, not a bendable multi-city cable canvas.
- Wiring-closet racks use device/port lists. The Cable Manipulation panel can add/delete/colour/edit local cable routes but not draw all 3D wiring across rack front/back views.
- This is 2D polyline geometry, not rack-unit routing, floor-to-floor conduit, real-world slack, pegboards/patch panels, collision detection, 3D path bends, cable occupancy or RF attenuation. Copper cable types remain auto, straight and crossover (not unimplemented fiber/console).
- The diagram and mini panel approximate vendor UI; they are not pixel-perfect reproductions. Undo/Redo share the general lab history, including other device changes.

## Verification

- 198 Python tests, including isolated real HTTP tests, pass. Tests cover 100m carrier status vs routed path, multiple bends, group creation/movement/ungroup, black group segments, independent cable colours, Undo/Redo, rename/disconnect cleanup, persistence and validation.
- Isolated Chromium run: click cable to open menu, Create BendPoint, Color Cable, drag one dot onto another to create GroupPoint, ungroup and delete bend without deleting cables, move yellow GroupPoint as a unit, desktop/tablet/390px UI. No JavaScript runtime errors.
- Live lab must be backed up before restarting production.

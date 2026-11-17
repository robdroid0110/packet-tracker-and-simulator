# Physical Workspace — legacy network simulator Help Section 15

Reference: /reference/workspace_physical.htm (installed legacy network simulator 9 help).
Implemented as a deterministic lab model, not a separate browser-only physical world.

## Verified first-pass functionality

- Shared Intercity / City / Building / Wiring Closet hierarchy. Default: Home City / Corporate Office / Main Wiring Closet. Opening and backing out is available in Physical view.
- Create generic containers within supported parents, including nested generic containers. Parent-type restrictions and metric width/length/height containment are validated. Cities cannot be placed inside buildings/closets; containers cannot be parented to themselves or descendants.
- Edit and save physical dimensions. Move and rename physical locations. Physical map card coordinates are separate from logical positions.
- Create a network device directly in a physical container with ONE atomic API/CLI action (undo rolls back both creation and placement). Physical device map cards are movable and their coordinates persist separately from logical coordinates and cabling.
- Wiring closets display distinct rack, table, floor and user-created shelves. Devices can be moved via Move... or drag/drop. Rack/table units and equipment depths are visual only. Simple per-device Ethernet cable lights are shown.
- Storage shelves enforce power OFF and disconnected before placement. Equipment on a shelf cannot be powered on or connected; power cycle leaves it powered off. Up to 20 shelves per wiring closet.
- Moving a device physically DOES NOT silently rewrite its logical topology, IP configuration, or existing links. Changes are undoable, persist in autosave and exported lab JSON and load older labs with migration defaults.

## Agent APIs (required for all new features)

Read and discover:
- GET /api/physical-workspace?location=intercity
- GET /api/physical-workspace?location=closet0
- GET /api/physical-workspace/schema
- GET /api/capabilities

Write:
- POST /api/physical-workspace/action with typed JSON, action:
  - add_location (kind, name, parent)
  - rename_location (location, name)
  - move_location (location, x, y)
  - relocate_location (location, parent)
  - resize_location (location, width, length, height) in meters
  - add_device (model, name, x, y, location, optional physical_x, physical_y)
  - place_device (device, location)
  - position_device (device, x, y)
  - add_shelf (closet)
  - mount_device (device, surface: rack/table/floor/shelf; optional shelf index)
  - undo, redo.

All actions validate using the same NetworkLab/CommandProcessor, persist to the current lab, and use the in-memory Undo history. Binding remains localhost with no authentication, not safe for untrusted network exposure.

CLI equivalents:
- physical add generic Storage closet0
- physical dimensions loc0 8 7 2
- physical relocate loc0 building0
- physical add-device pc-pt PC3 200 160 city0 350 230
- physical place R1 closet0
- physical device-position R1 220 100
- physical shelf-add closet0
- power R1 off
- physical mount R1 shelf 0
- show physical
- undo

## Explicitly not yet implemented

- Accurate physical cable length calculations and optional Ethernet 100-meter enforcement; wireless radio propagation, Bluetooth/cellular range, building attenuation. These belong to Section 17: Distance Measurements.
- Cable pegboards, cable segment paths, hands-on front/rear device cabling, cable-color rules. These belong to Section 19: Cable Manipulation.
- Rack unit heights, server hardware geometry and true front/rear hardware bays.
- Full physical Move Object tree panel, physical multi-object drag/stacking, custom container templates, arbitrary custom graphics/background packages. Later sections cover these details.
- Do not imply that coordinates are actual meter distances until distance calibration and link behavior are implemented.

## Acceptance evidence

- 130 passing automated Python tests, including real HTTP route tests, malformed payload validation, volume/type/cycle constraints, old saved lab migration, atomic create+Undo, 200-device read projection, shelf/power/cable restrictions.
- Isolated Chromium browser checks: new generic container, nested navigation, rack/table/floor/shelf rendering, rejected powered router shelf mount, successful powered-off mount, stored state read back via API, return to Logical view. No JavaScript exceptions.
- Original active user's lab stays untouched until a verified backup and controlled server restart.

## Section 16 progression

The next help page (workspace_physical_movingDevices.htm) has a dedicated verified implementation in PHYSICAL_MOVING_REFERENCE.md. The Move Object and hierarchical Navigation controls, device-group relocations and city-to-city cable line indicators are now functional through the typed API. True rack slots, physical cable length and wireless propagation remain unimplemented.

## Section 17 progression

Metric 2D distance estimates, opt-in 100m copper carrier effects, the cable measurement panel, visual RF circles and radio range API were added in the next documentation phase. Refer to PHYSICAL_DISTANCE_REFERENCE.md for exact calibration, limits and unsupported 3D/RF behaviour.

## Section 18 progression

The Physical Workspace now supports independent device Logical/Physical icons and saved per-container custom backgrounds with tile/fit/colour, with an asset API. All image data is embedded in native lab JSON and remains portable without local browser cache. Details and current gaps: PHYSICAL_CUSTOMIZATION_REFERENCE.md.

## Section 19 progression

Per-cable 2D routed BendPoints, shared GroupPoints and colour coding now have model-backed GUI and API controls. Cable routing/colour is saved and affects the Section 17 copper length limit. This is **not** 3D rack cabling or patch-panel conduit; see PHYSICAL_CABLE_MANIPULATION_REFERENCE.md.

## Section 20 progression — ICP

Physical locations may now be type icp. The Physical Workspace toolbar creates industrial control cabinets; the ICP view has saved door/cabinet equipment, the closed-door preview, DIN/WIC layout strips and agent-readable mounting state. It uses a 20-unit panel grid with six anchor choices and native lab Undo/Redo. For the functional model/API and explicit non-electrical scope, see ICP_REFERENCE.md.

## Section 21 — Accessibility

Screen-reader-friendly, keyboard-driven physical tree and equipment dialog available from Physical toolbar. Same read/write agent API exposes location/equipment/port/module/surface data and real operations without separate state. See PHYSICAL_ACCESSIBILITY_REFERENCE.md.

## Section 22 — Special Notes

Metric grids are now configured and saved per map container type, with authoritative geometry and agent actions. The Delete tool and Delete Location preview removal of container subtrees and extraction of equipment onto the surviving parent floor, preserving logical network state and cable routing. Undo/Redo restores all removed placement/furniture state. New devices fall back to Intercity after default containers are removed. See PHYSICAL_SPECIAL_NOTES_REFERENCE.md for tests and limits.

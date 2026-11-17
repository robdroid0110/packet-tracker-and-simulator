# Section 22 — Physical Workspace Special Notes

Reference: vendor official help, also available from the installed help at `/reference/workspace_physical_specialNotes.htm`.
Implemented 2026-11-04. Defined scope complete; this is not a claim of complete legacy network simulator parity.

## Implemented behaviour

**Navigation and device creation:** existing Navigation and Accessible Physical Navigation controls expose the complete physical tree and shared device movement. Palette placement and the typed `add_device` action create equipment directly in the chosen physical location. These use the same network model as Logical Workspace.

**Grid:** Physical toolbar → Grid opens a keyboard-accessible native dialog. Configure visibility, spacing in metres and line colour independently for Intercity, City, Building and Generic container types. Settings apply to every container of that type and persist in native lab JSON, autosave and Undo/Redo. The map grid is separate from radio coverage and the ICP's existing 20-unit layout grid.

Spacing uses the Section 17 backend calibration: container width / 1000 canvas units and length / 700 canvas units. A 125 m city grid with dimensions 5000 × 5000 m projects to 25 × 17.5 canvas units. Resizing the city to 2500 × 1250 m produces 50 × 70 units without changing the saved metre spacing. Background images share that map coordinate frame; image tile/fit changes presentation, while container dimensions control metric scale. There is no separate image scaling factor editor.

Defaults preserve the previous visible grid: enabled, colour `#d4dbe2`; spacings Intercity 2500 m, City 100 m, Building 5 m, Generic 1 m. Valid spacing is 0.01–1,000,000 m; colours are `#RRGGBB`. Very dense grids (less than 4 canvas units in either dimension) retain exact saved settings/API geometry but hide their lines in the GUI. Closets use furniture and ICPs use their own panel view; the metric map grid does not apply there. Grid configuration has no networking or placement side effects.

**Delete containers:** use the common Delete tool on a physical container card, or enter a location and choose Delete Location. The dialog previews all affected containers, equipment and the surviving destination. Cancel changes nothing. Confirm removes the selected container and its entire nested subtree, extracting every contained device onto the surviving parent's floor. This includes closet shelf equipment and ICP cabinet/door equipment. Deleting Intercity is rejected.

Device objects, logical positions, IP/routing/service configuration, power, modules, icons, Ethernet links, cable colours and world-coordinate cable bends survive extraction. Location-specific shelves, ICP fixtures/mounts and background assignments are removed; portable image assets remain in the library. Extracted equipment receives deterministic floor positions and no shelf assignment. New Logical devices fall back to Intercity when their original default building or closet no longer exists.

**Undo/Redo:** supported for all these edits, including restoring complete container subtrees, furniture, backgrounds and equipment placements. This intentionally retains Packet Tracker and Simulator's undo support beyond the historical vendor help restriction. Deletion is reversible and does not need an extra agent confirmation token. If cable length effects are enabled, extraction changes physical coordinates and can change carrier/recomputed OSPF routes; disabling cable effects preserves the prior distance-independent carrier behaviour.

## Agent API and CLI

Existing endpoint extended, schema version 2 (native JSON lab version remains 1 with an additive field):

```text
GET /api/physical-workspace?location=building0
GET /api/physical-workspace/schema
GET /api/physical-workspace/tree
GET /api/capabilities
POST /api/physical-workspace/action
```

Read responses now include `grid` (support, enabled, type, spacing, colour, backend geometry and projected x/y spacing), `grid_profiles` and `delete_preview` (location, destination, removed_locations, extracted_devices; null for Intercity). No mutation or autosave occurs on GET.

```json
{"action":"set_grid","container_type":"city","enabled":true,"spacing_m":125,"color":"#cc2244"}
{"action":"delete_location","location":"closet0"}
{"action":"undo"}
{"action":"redo"}
```

Optional `view_location` requests a workspace projection in the action response. If deletion removes that view, the response falls back to Intercity. Validation failure returns HTTP 400 with `ok:false`, preserving state and autosave bytes. All writes use the existing lock, CommandProcessor, history and autosave.

```text
physical grid city on 125 #cc2244
physical grid building off 5 #d4dbe2
physical delete-preview building0
physical delete closet0
undo
redo
```

Registry IDs: `workspace.physical_grid`, `workspace.physical_delete`; the existing `physical_workspace.edit` schema advertises both new actions. `GET /api/state` and exported JSON contain `physical_grids`, keyed by container type. Older files without this field receive defaults. Malformed saved profiles are rejected.

## Verification

- Full Python suite: **246 tests pass**, including 19 new Section 22 model/CLI and isolated HTTP cases. Checks cover invalid requests without mutation, metre scaling, shared profiles, save/load, legacy files, extraction cleanup, default-location fallback, exact Undo/Redo, real ping across extraction, optional 100 m carrier effects and preservation of all configurations in a 200-device lab.
- JavaScript syntax and Python compilation pass; Git whitespace check passes.
- Real isolated Chromium: visible grid configuration, metric SVG dimensions/colour, resizing through API, Delete tool preview/Cancel, delete-current extraction, successful ping, Undo/Redo, dense and disabled grids, reload persistence, 390 px dialog, Escape and focus restoration, and palette creation after deleting the original locations. No browser runtime exceptions. Screenshots inspected. Browser harness checks the user's autosave SHA-256 is unchanged.
- Reproduce: `python3 -m unittest discover -s tests -q`. Browser: `python3 tools/verify_physical_special_notes.py --artifacts /tmp/packet-tracker-section22-evidence` (Chromium and Python `websockets` required). All browser state, server and profile data are temporary; artifacts stay only in the supplied directory.

## Remaining limits

The grid is visual and does not snap objects. Metric scale follows container dimensions rather than a separate vendor background-image scale control. Container subtree removal is an explicit Packet Tracker and Simulator rule for nested containers; the source specifically describes closet/building extraction but does not fully specify arbitrary nested generic/ICP deletion. True numbered rack units, 3D geometry, wireless packet association and external PKT/PKZ compatibility remain outside this phase. The overall application is a desktop-oriented interface; only the new modal was verified at 390 px, not the entire app's mobile usability.

Next sequential phase: **Section 23 — Logical Workspace Customizing Icons & Background**.

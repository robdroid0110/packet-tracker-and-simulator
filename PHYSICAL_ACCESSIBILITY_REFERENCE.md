# legacy network simulator Section 21 — Physical Workspace Accessibility

Reference: /reference/workspace_physical_accessibility.htm from locally installed legacy network simulator 9 help.
Implemented: 2026-11-04.

## User-visible functionality

Open the Physical Workspace and choose **Accessible Physical Navigation** from its toolbar, or use Alt+Shift+A to toggle the accessible dialog.

The dialog uses native HTML buttons, accessible list content, labelled form inputs, visible focus, role=dialog with aria-modal/aria-labelledby/aria-describedby, polite live status announcements and Escape to close. Background controls are inert while it is open. It returns focus to the original or replacement toolbar button when closed.

**Navigation:** Tab/Shift+Tab advances through controls. Arrow Up/Down changes the focused item in the list of locations or equipment. Arrow Right enters the focused location. Arrow Left or Backspace returns to the parent, when a location is focused. Enter activates the focused native button. Escape closes the dialog.

The reader-friendly location tree includes Intercity, cities, buildings, wiring closets, generic containers and ICPs. The equipment view lists the current location, mounting surfaces, device model/power state, expansion slots, all simulated Ethernet ports, their peer/occupancy, and UP/DOWN link status. This information comes from the authoritative Python NetworkLab state.

**Take and Place:** Choose Take on an existing device; this is transient UI selection and does not move it until an explicit Place action. Navigate to another container, then Place. In a Wiring Closet you can also place on Rack, Table, Floor or a Storage Shelf (power-off/disconnected rules remain enforced). A rack is a mounting *area*, not a numbered physical rack-unit grid in Packet Tracker and Simulator. ICPs offer Cabinet and Door placements.

**Component box:** Add a supported PC, Router, Switch or Server with a name in the current location. Other models exist in the general catalog, but are not advertised here as fully supported network engines.

**Connect:** Pick an unused source port, navigate to an unused destination port (in the same or another physical location), and activate Connect. Choosing the source alone does not create any link. Connections use existing real network link logic, display peer/operational status, and offer explicit Disconnect.

**Module slots:** Model-backed device module slots are exposed in a details list. Editable slots have a labelled module picker and Apply button. Editing a module is blocked while the device is powered on, following the existing module engine. Powered-off router accepted PT-ETH-1 in isolated Chromium.

## Typed agent API

Read:
    GET /api/physical-accessibility?location=closet0
    GET /api/physical-accessibility/schema
    GET /api/physical-workspace/tree
    GET /api/capabilities

Write:
    POST /api/physical-accessibility/action

JSON examples:
    {"action":"add_device","model":"pc","name":"PC7","location":"closet0"}
    {"action":"move_device","device":"PC7","location":"building0"}
    {"action":"mount_device","device":"R1","surface":"rack"}
    {"action":"mount_device","device":"PC7","surface":"shelf","shelf":0}
    {"action":"place_icp_device","device":"R1","side":"cabinet","x":200,"y":160}
    {"action":"connect","a_device":"PC7","a_if":"eth0","b_device":"R1","b_if":"g0/0","cable":"auto"}
    {"action":"disconnect","device":"PC7","interface":"eth0"}
    {"action":"power","device":"R1","enabled":false}
    {"action":"set_module","device":"R1","slot":"slot0","module":"PT-ETH-1"}
    {"action":"add_shelf","location":"closet0"}
    {"action":"undo"}
    {"action":"redo"}

Each mutation delegates to the existing CommandProcessor, runs on the normal saved NetworkLab, returns the authoritative state and uses existing Undo/Redo/autosave. Navigation, Take selection, focus and choosing a source port are client selections only and require no saved mutation.

## Verification

- 227 automated Python tests pass, including dedicated model checks and isolated real HTTP API tests for add/place/mount/connect, invalid input, Undo/Redo and saved lab state.
- An isolated Chromium browser was used to open the dialog, navigate the physical tree, create PC/router, select a source with no side effects, connect two devices, take/mount a device on rack, and move a device between locations while preserving its network cable.
- Arrow-key navigation and Escape/focus restoration were checked. The modal has a labelled dialog and live announcements. At screen widths of 1600, 1024 and 390px the dialog stayed within the viewport (384px at 390px).
- Module picker: a powered-on router disallowed edits; after powering it off, the dialog installed PT-ETH-1, preserved its link, and returned focus.

## Explicit limitations

- This is a **first-pass accessible workflow, not a WCAG compliance certification**. Actual OS screen readers (NVDA/Narrator, VoiceOver, Orca) have NOT yet been manually verified against it. Native controls and ARIA are implemented, but actual screen reader behaviour must be audited on each platform.
- The rest of the app, including the Logical Workspace, menus, dock, simulation canvas and vendor widgets, has NOT been exhaustively audited for accessibility.
- This does not implement browser speech synthesis; users employ their screen reader of choice.
- True numbered rack-unit slot occupancy, chassis-back hardware manipulation and console/fibre port attachment are not supported by the engine; accessible placement is by Rack/Table/Floor/Shelf and normal Ethernet ports.
- The add-device form only exposes fully supported core engine types; it is not the entire legacy network simulator device catalog.
- The localhost HTTP service does not yet authenticate users; do not expose it directly to untrusted networks.

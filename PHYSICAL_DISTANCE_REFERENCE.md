# Physical Distance Measurements — vendor Help Section 17

Reference: /reference/workspace_physical_distanceMeasurements.htm (bundled legacy network simulator 9 Help).
Implementation date: 2026-11-04. This is a documented 2D approximation, not
the vendor's full three-dimensional/RF physical environment.

## Implemented

- Physical locations and devices have a calibrated **metric 2D projection**.
  Each location's saved width/length in meters maps to a 1000 × 700 unit
  physical canvas. Intercity uses a fixed 100 km × 70 km base frame.
  Nested locations project into one consistent world coordinate system.
  Height is used for size-fitting only; not vertical distance.
- Agent query and GUI measurement panel display straight-line distance,
  cable endpoints, one simplified segment, total length, carrier status,
  and 100-meter copper limit. Cable curves, patch panels and slack do not
  contribute to these estimates.
- Opt-in **Enable Cable Length Effects** under Options > Preferences > Interface
  gates copper links against 100m. At 100m the link can operate, beyond 100m
  it is down. Device power/interface admin state and copper polarity remain
  separately enforced. Cable effects default OFF so existing labs are safe.
- Cable-effect setting persists in lab JSON, is undoable and can be changed
  by any authenticated-local-trust agent/API client (HTTP has NO authentication).
- Wireless source profiles are identified from catalog models. Starter
  Packet Tracker and Simulator geometry: access points/wireless routers 140m (the Cisco
  tutorial illustrates a manually configured 140m AP, not a universal PT
  hardware default); Cell Tower 1000m per tutorial; Bluetooth 10m simplified.
- Source radio radius is user-configurable per device and persisted in JSON.
  Show Wireless Grid is a local browser preference: it draws translucent,
  geometrically calibrated ellipses from the same engine data.
- Geometric source/client within-range checks are reported to agents,
  including power state. They do NOT imply Wi-Fi association, Bluetooth
  pairing, cellular handoff or actual RF packet forwarding.

## Agent shell

    physical measure PC1 PC2
    physical cable-length R1 g0/0
    physical cable-effects on
    physical cable-effects off
    physical radio-range AP1 180
    physical radio-status city0

## Typed API

    GET /api/physical-distance?source=PC1&target=PC2
    GET /api/physical-distance?device=R1&interface=g0/0
    GET /api/physical-distance?location=city0
    GET /api/physical-distance/schema
    POST /api/physical-distance/action

POST body examples (JSON):
    {"action":"cable_effects","enabled":true}
    {"action":"radio_range","device":"AP1","radius_m":180}
    {"action":"undo"}

All changes use the same NetworkLab, CommandProcessor undo/redo history and
autosave. Capability discovery is available at GET /api/capabilities.

## Explicitly not simulated

- Real cable routes, bends, cable slack, pegboards, patch-panel jumps or 3D
  lengths (height/floor separation).
- RF propagation physics, fading, walls, attenuation, interference,
  signal strength, throughput, channels, roaming or cellular towers'
  protocol/control-plane functions.
- Real wireless/Bluetooth client association or wireless packet forwarding.
  Catalog devices are not silently upgraded to working protocol engines.
- vendor background-specific distance calibration; fixed canvas geometry is
  a Packet Tracker and Simulator engineering convention. Root intercity scaling is fixed.

## Verification

- 162 automated Python tests pass, including isolated HTTP API contract tests,
  100m boundary, 105m link failure, Undo/Redo, metric geometry, radio source
  defaults, range edits, save/load migration, invalid data and 200-device read.
- Headless Chromium browser test: real Preferences controls enabled/disabled
  carrier effects and restored the link, Physical measurement UI displayed
  cable distance/reason and wireless coverage, radio radius was changed
  through GUI API, and 1600/1024/390px layouts worked with no JS errors.
- Do not expose the unauthenticated localhost HTTP control API to untrusted
  machines or the public internet.

## Section 19 progression (overrides Section 17 straight-line-only note)

Cable paths now support ordered BendPoints and grouped points. Direct endpoint distance remains a separate reported metric, but **total cable length is the sum of 2D routed segments**; when optional cable effects are on, total length controls the 100m copper carrier. Original straight-line-only cable route caveat in this Section 17 checkpoint has therefore been superseded by the Section 19 implementation. See PHYSICAL_CABLE_MANIPULATION_REFERENCE.md.

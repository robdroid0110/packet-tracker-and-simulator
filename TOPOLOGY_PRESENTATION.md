# Topology clarity controls

Open **Topology display** in the upper tools row. The surrounding UI and the
existing placement, click-to-configure, drag, pan, zoom and connection tools stay
in place. These controls apply to the Logical workspace.

- **Separate parallel cables:** restores direct straight connections. Multiple
  cables between the same visible endpoints get separate parallel lanes, including
  cables created in opposite directions and external links of collapsed groups.
  Status colors and crossover dashes remain visible; endpoint lights appear when a link is inspected. Hover or
  keyboard-focus a cable to inspect its interfaces and status. Turn this setting
  off for coincident straight connections. The existing API key `routing` now
  controls lane separation; saved `true` values use this corrected display.
- **Smart interface labels:** endpoint labels choose among available positions;
  labels with no clear position are suppressed until the connection is inspected. In the default Smart mode, interface labels stay hidden at ordinary zoom and become visible on link/device inspection; clear labels also appear from 160% zoom.
  All/None are available. Existing Preferences label visibility still takes priority.
- **Highlight related connections:** hovering, keyboard focusing or selecting a
  device emphasizes its incident links and neighbors. Selecting a cable highlights
  both endpoints. Unrelated devices are dimmed without altering their hit areas.
- **Preview tidy layout:** selected devices, or all devices visible in the current
  workspace when nothing is selected, receive a deterministic layered layout.
  Router/switch roots, graph distance, spacing and stationary-device avoidance
  determine positions. Preview does not save changes. Apply saves one undoable
  operation; Cancel or Escape restores the original view. Canvas editing is blocked
  during preview. An obsolete preview is rejected rather than overwriting edits.
- **Named groups:** Ctrl-click or marquee-select devices, then Group selected
  devices. Expanded groups have a named outline and collapse control. Collapsed
  groups show device count, external link count and down-link count. Internal links
  are hidden; every external connection remains represented individually. Click the
  group to expand it, or use the manager to expand/collapse/ungroup. This is a visual
  grouping operation: all devices continue simulating and retain configurations.
- **Zoom-aware detail:** keep icons and device names in overview; show collision-free
  interface labels at 160% zoom and above (or on hover/focus), and model/IP subtitles at 110% and above.
  Inspecting a connection reveals its labels at any zoom unless explicitly hidden.
  Disable the setting to keep full detail independently of zoom.

Preferences, groups and applied positions live in the authoritative saved lab.
Older labs gain defaults; their existing positions are never automatically moved.
Rename/delete updates group membership. Undo/Redo applies to preferences, groups
and applied layouts. Physical workspace cables and their physical distances are
unchanged. Existing logical clusters remain separate navigation containers.

## Icon-attached cables

Logical topology cables now anchor to the visible icon perimeter instead of the surrounding device name/label rectangle. The geometry is measured in canvas coordinates and remains attached through zoom, dragging and parallel cables. Connection lights are displayed only while a cable is inspected, keeping dense diagrams uncluttered; down links still use their error colour. The underlying interfaces, cable types and simulation state are unchanged.

Test the geometry explicitly with:

```sh
PLAYWRIGHT_MODULE=/path/to/playwright-core node tools/check_canvas_geometry.cjs
```

## Agent API

Discover via `GET /api/capabilities` and `GET /api/workspace-tools/schema`.
Read saved settings at `GET /api/workspace-tools` → `settings.diagram` or in
`GET /api/state` → `workspace_tools.diagram`.

Read-only layout preview:

```http
GET /api/topology-layout
GET /api/topology-layout?names=%5B%22R1%22%2C%22SW1%22%5D
```

Omitting `names` means all devices; `[]` means an empty layout. The result has
`ok`, `names`, `positions: {device: {x, y}}`, and `signature`. No save or history
entry is made. The signature covers the selection, current device geometry/kinds
and selected graph adjacency. Apply recomputes the plan on the backend and verifies
that the topology still matches. It does not accept arbitrary client positions.

POST these JSON bodies to `/api/workspace-tools/action`:

```json
{"action":"diagram_preferences","routing":true,"labels":"smart","focus":true,"semantic_zoom":true}
{"action":"diagram_group","name":"Office A","members":["PC1","PC2"]}
{"action":"diagram_collapse","name":"Office A","collapsed":true}
{"action":"diagram_ungroup","name":"Office A"}
{"action":"layout_apply","names":["R1","SW1"],"signature":"<from preview>"}
{"action":"undo"}
{"action":"redo"}
```

Preference keys can be updated independently. `labels` accepts `smart`, `all`, or
`none`. Groups have unique nonempty names up to 64 characters, disjoint nonempty
member lists and a boolean `collapsed`; at most 100 groups are allowed. Invalid
requests return HTTP 400 and preserve state. The same writes are available through
`workspace-tool '<JSON>'`; CLI `undo` / `redo` work as usual. Hover, temporary focus,
preview display and cable geometry are presentation state, not network mutations.

## Validation and measured limits

New unit/HTTP tests cover read-only and deterministic preview, apply/undo/redo,
stale preview rejection, partial-layout obstacle avoidance, configuration/link
preservation, invalid requests, saved preferences/groups, rename/delete cleanup,
legacy defaults and a nonoverlapping layout for 500 disconnected devices.
`tools/check_topology_presentation.cjs` exercises real GUI controls against an
isolated backend, reloads groups, verifies live cable dragging and checks controls
at 1440, 1024 and 768px widths. Existing pointer and keyboard regressions also pass.

On this Linux host (Intel i9-13900H, headless Chromium, 1440×900), six samples per
case measured the following **JavaScript execution times**, not end-to-end frame
latency or a guarantee for other hardware:

| Generated lab | Cached full canvas render | Rerouting after geometry changes | Incident cable update during drag |
| --- | --- | --- | --- |
| 200 switches, 379 links (grid plus chain) | 45–49 ms | 175–271 ms | 0.2–0.8 ms |
| 500 switches, 499 links (chain) | 89–110 ms | 319–407 ms | 0.2–0.7 ms |

The figures above describe the earlier orthogonal-routing implementation and are
retained as historical measurements, not benchmarks of the current straight display.
Current straight geometry is cached until geometry, connectivity or separation preferences change.
During a drag, only attached cables/end labels move using their parallel offsets;
label placement is recalculated on release. These timings
cover the diagram update only; existing state serialization, node positioning,
browser paint and backend save costs remain additional. Raw samples are in
[research/performance/topology_presentation.json](research/performance/topology_presentation.json).

Reproduce with an isolated generated fixture:

```sh
python3 tools/generate_diagram_fixture.py --count 200 --grid
# Use the temporary path printed above:
PLAYWRIGHT_MODULE=/path/to/playwright-core PT_CANVAS_FIXTURE=/tmp/.../lab.json node tools/benchmark_diagram.cjs
PLAYWRIGHT_MODULE=/path/to/playwright-core node tools/check_topology_presentation.cjs
```

Direct lines can still cross unrelated cables or pass behind devices. Parallel lanes
separate repeated connections but cannot guarantee a crossing-free dense mesh.
Forced All labels can overlap; label widths are estimated. Tidy Layout may reject
very deep graphs exceeding the 10,000-unit canvas; select a smaller portion then.
Groups do not nest, are not VLANs, and do not move members into logical clusters.
A group spanning clusters shows only members visible in the current workspace.
Expanded outlines may overlap for interleaved member positions. Full canvas rendering in large labs can still cause a pause; the fast drag path
updates only incident cables. No network protocol, cable length or forwarding calculation
has been changed by these presentation features.

## Loading the update

The Linux executable is rebuilt at `dist/linux/PacketTracker`. The existing desktop
launcher uses the updated source checkout. A backend process that was already
running before this update must be restarted before using the new API actions;
then reload the application. Tests used isolated servers and did not restart the
active lab server or change saved user topologies.

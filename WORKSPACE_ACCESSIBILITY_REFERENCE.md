# Workspace and Accessibility — Sections 23–32

Implemented against the official help index, in order after Section 22. The rows below define the tested browser implementation; they do not claim binary-format, native desktop or certified screen-reader parity with legacy network simulator.

| Section | Functionality | Verification / limits |
|---|---|---|
| 23 — Logical Icons & Backgrounds | Independent device icons remain available; new per-cluster icons and root/cluster backgrounds with tile/fit/colour/reset. PNG, JPEG and GIF upload, library, protected deletion and embedded portable JSON. | Browser uploads/applies/renders cluster icon; HTTP/model test background scope, cleanup and save/load. GIF structural validation checks blocks, bounds and trailer; maximum 1000 frames and 16 million cumulative decoded frame pixels. vendor PKT/PKA/PKZ output is not supported. |
| 24 — Viewport | Logical and Physical viewport panels, Contents/Workspace bounds, device/cluster/container markers, background in Workspace mode, visible-area rectangle, click-to-centre and arrow-key pan. View > Show Viewport, toolbar and Shift+V. | Backend projects visible items and bounds; saved mode/visibility/centre are queryable. Browser pans and switches workspace/mode. Physical furniture is represented by equipment markers, not miniature 3D racks. Physical radio coverage estimates are included when Show Wireless Grid is enabled; association/propagation remains unmodeled. |
| 25 — Templates | Workspace Tools / Tools > Device Template Manager / Ctrl+Shift+D captures configured devices, nested logical clusters or physical subtrees. Create, remove, export and import native JSON templates. | Copies supported modules, static configuration, internal links, placements, shelves, ICPs, icons/backgrounds and cable routes. Fresh names/MACs and cleared learned tables/leases/NAT sessions. External cables excluded. Duplicate static IPs are deliberately retained and must be adjusted before joining instances. Custom Templates in the component palette supports click placement and drag/drop. Manager source selectors replace the vendor's canvas Select workflow; native vendor template files are not supported. |
| 26 — Accessibility | Logical Workspace List, accessible Physical Navigation and new native-dialog textual packet-event inspector. Source/destination/protocol and expandable complete event details. | Same authoritative network and packet trace as GUI/API. Events require a recorded PDU (`pdu A B`); ordinary ping output is separate. No new protocol/timing claims. |
| 27 — Screen Reader Basics | Button/input names, menu/region/tab semantics, labelled device dialog, live status and terminal output logs; textual alternatives to graphical workspaces. | Chromium accessibility tree and accessible button names checked. Actual Narrator/JAWS, VoiceOver and Orca speech output remain a manual platform audit. No synthetic speech is added. |
| 28 — Shortcuts | Existing edit shortcuts plus supported navigation, template manager, file/zoom, menu mnemonics and physical creation shortcuts listed below. | Browser checks Shift+N and Ctrl+F6. vendor shortcuts for unimplemented Multiuser/IPC, Activity Wizard, native application exit and specialized desktop apps are not advertised as implemented. Browser-reserved shortcuts may be intercepted by the browser/OS. |
| 29 — Tab Navigation | Native Tab/Shift+Tab, Enter/Space buttons, keyboard-accessible logical canvas devices, arrow menu/category/tab navigation, modal Tab wrapping for existing role dialogs and native focus containment for new dialogs, Ctrl/Cmd+F6 terminal exit. | Browser checks cover direct keyboard navigation, moving, opening and connecting devices; existing physical accessibility tests cover its focus handling. Section 22 Escape focus restoration is synchronous on dialog cancellation. This is not a complete third-party widget or WCAG audit. |
| 30 — High Contrast | CSS forced-colors support for OS/browser contrast; explicit Auto/High/Normal choice in Workspace Tools. High uses black/white controls and removes background images. | Saved backend settings plus Chromium forced-colors emulation and rendered colours. Hardware photos are images, not recoloured vector art. |
| 31 — High DPI | Existing Preferences > Font sizing plus saved application-scale multiplier 1–2 in Workspace Tools. Scale composes with the existing font-size preference. | Chromium 3840×2160 at device scale 2; settings and contrast survive reload. Native OS compositor scaling remains browser/OS owned. |
| 32 — Web View Accessibility | Labelled sandboxed simulated-browser iframe; native HTML fields, links and headings retain browser accessibility semantics. Device terminals expose log names and a focus exit shortcut. | Browser checks labelled sandbox/content and terminal focus exit. vendor login/instruction native WebEngine dialogs are absent from this local simulator. Accessibility of arbitrary user-authored HTTP HTML depends on that HTML. |

## Controls and shortcuts

Open **Workspace Tools** in the secondary toolbar. It contains Accessibility and Device Template Manager controls, plus Accessible simulation events. Capture uses source type and source selectors; imported templates require a new unique name. Removal is undoable; export downloads the selected template's self-contained JSON.

Implemented bindings include existing Ctrl/Cmd+C/V/Z/Shift+Z/Y/A editing; Ctrl/Cmd+N/O/S and I/T/U for supported file/zoom controls; Ctrl/Cmd+Shift+D manager; Shift+L/P workspace; Shift+R/S realtime/simulation; Shift+W logical list; Shift+N accessible physical navigator; Shift+V viewport; Shift+G physical grid; Shift+C/B/F/J/H physical city/building/generic/closet/working-closet controls; Shift+U/M/I logical cluster/move/background controls; Alt+F/E/O/V/T/X/H menus; Ctrl/Cmd+F6 terminal exit. Arrow keys traverse menus, tabs and palette category buttons. Modal controls retain native typing behaviour; global tool shortcuts are suppressed while typing or in a dialog. Ctrl+F6 chooses a device-dialog control when invoked from that device's terminal.

### Logical canvas keyboard controls

Press **Shift+D** outside a text field or dialog to focus the last visited device on the current logical canvas. The canvas has one Tab stop even in a large lab. Arrow keys choose a device in that direction; **Ctrl/Cmd+Arrow** cycles through all visible devices, including devices in the same position. Focus pans the view when necessary. Hidden devices in other clusters are skipped.

With the Select tool active, **Shift+Arrow** moves the focused device 10 logical units; **Ctrl/Cmd+Shift+Arrow** moves it 50. The position is saved through the same undoable `move` command used by agents, bounded to coordinates 0–10,000. Rapid key repeats may be combined into an undoable move. Only the focused device moves, even when a group is selected. Ctrl/Cmd+Z and Ctrl/Cmd+Y undo and redo as before.

**Enter** or **Space** activates the focused device with the currently selected tool. In Select mode this opens its separate device window. To connect devices, choose a cable from the Connections palette using the keyboard; focus moves to the device canvas. Activate a source and destination. Automatic connections select compatible ports through the existing `auto-connect` backend operation. Manual cables open a keyboard-accessible interface picker; choose an interface on each device with Tab and Enter. Escape cancels the connection and restores device focus. **Shift+W** opens Workspace List, which provides keyboard-accessible device creation and explicit connection forms.

Focus and panning are local presentation state; device moves and links are authoritative backend edits and persist in saved labs. The controls have accessible names, descriptions, one roving Tab stop, and visible focus indicators including high-contrast/forced-colors modes. Screen-reader users may need focus mode for arrow navigation. Actual Orca, Narrator, JAWS and VoiceOver speech output has not been tested, and this is not a WCAG certification. Small 320–375 px layouts still have known clipping; direct keyboard group movement and placement directly on the canvas remain unsupported.

## Authoritative APIs

### Artwork

Existing `GET /api/visuals`, `GET /api/visuals/schema`, `POST /api/visuals/action` now include GIF and cluster icons. Set a logical background through `set_background` with `location: "logical:root"` or `"logical:Cluster0"`; choose a cluster icon with `set_cluster_icon` (`cluster`, `asset_id`). Null asset resets the image; default colour/untiled resets the background assignment. Deleting a cluster removes its own icon/background assignment, preserving image library and child clusters. Device icon assignments remain independent for Logical/Physical.

```json
{"action":"set_background","location":"logical:root","asset_id":null,"tiled":false,"color":"#112233"}
{"action":"set_cluster_icon","cluster":"Cluster0","asset_id":"FULL_SHA256_ID"}
```

CLI: `visual cluster-icon Cluster0 ASSET_ID` (or `default`), and existing `visual background logical:root ASSET_ID tile #112233`. Image library limits remain 40 images, 1MB each, 8MB total, 8192 pixels per side and 16 million pixels per image.

### Viewports, templates and accessibility

```text
GET /api/workspace-tools/schema
GET /api/workspace-tools?workspace=logical&location=root&mode=contents
GET /api/workspace-tools?workspace=physical&location=city0&mode=workspace
POST /api/workspace-tools/action
```

Read returns `settings`, scoped `items`, `bounds`, workspace/location and mode. `settings.templates[name]` is the complete export object; no extra export mutation is necessary. The schema enumerates actions. CLI accepts the same JSON: `workspace-tool '{"action":"accessibility","contrast":"high","scale":1.5}'`.

```json
{"action":"viewport","visible":true,"mode":"workspace","workspace":"logical","location":"root","x":1200,"y":900}
{"action":"accessibility","contrast":"auto","scale":1.5}
{"action":"template_capture","name":"My Router","kind":"device","source":"R1","description":"Configured lab router"}
{"action":"template_capture","name":"Office","kind":"cluster","source":"Cluster0"}
{"action":"template_capture","name":"Closet","kind":"physical","source":"closet0"}
{"action":"template_instantiate","name":"My Router","location":"closet0","cluster":"root","x":200,"y":160}
{"action":"template_delete","name":"My Router"}
{"action":"template_import","name":"Imported Router","template":{"kind":"device","root":"R1","description":"...","lab":{}}}
{"action":"undo"}
{"action":"redo"}
```

The import example's `lab` must be a complete valid exported template lab, not an empty placeholder. Import validates referenced devices, cluster/container scope, image data and engine state. A template supports at most 200 devices; libraries have at most 40 templates and 16MB serialized content. Source deletion does not delete the captured template. Only used images are embedded in templates. Cable groups are unique per instance. Physical-template cable bends translate by the container world-origin offset, preserving routed lengths at the new destination. Physical instantiation enforces destination type and size rules. Unsupported modules/media cannot be introduced through templates.

Writes are validated and applied to an isolated candidate NetworkLab before publishing one undoable operation under the existing HTTP lock and autosave. Invalid requests return HTTP 400 without changing state or saved bytes. The 17MB request-body cap permits portable template imports. Capability registry advertises `workspace_tools` and extended `visuals.edit`. Graphical navigation and accessibility are projections of existing lab state; they do not create another simulation authority.

## Persistence and verification

Native JSON remains version 1 with additive `cluster_icons` and `workspace_tools` fields. Older labs receive empty template libraries, hidden Contents viewport, Auto contrast and scale 1. Existing physical/background/device assignments remain valid. Settings are lab-scoped and thus shared by clients reading that lab; keyboard focus and temporary dialog selection are browser-local.

- Original Sections 23–32 Python suite: 259 passing tests, including 13 new model/CLI and isolated HTTP cases. Cases include template source removal, nested clusters/internal links, shelves/container fit, module configuration, fresh MACs, atomic failure, save/load, invalid images/settings and a 200-device capture/creation producing 400 configured devices.
- `python3 tools/verify_workspace_accessibility.py --artifacts /tmp/packet-tracker-sections23-32-evidence` runs isolated Chromium and server instances using temporary labs/profiles. It checks actual template controls and component-palette placement, contrast/scaling, viewport mode and pan, Shift+N, logical background, browsed cluster icon upload/apply/render, accessible packet details, terminal focus exit, embedded web-view title/sandbox, named buttons, accessibility tree, forced-colors, 4K layout and reload persistence. Screenshots are retained only in the requested directory. The active user's autosave SHA-256 must stay unchanged.
- `python3 -m unittest discover -s tests -q`, Node syntax checks, Python compilation and `git diff --check` pass.
- Later canvas checks: `PLAYWRIGHT_MODULE=/path/to/playwright-core node tools/check_canvas_keyboard.cjs` and `PLAYWRIGHT_MODULE=/path/to/playwright-core node tools/check_canvas_scale.cjs` use temporary servers and labs. The latter defaults to the generated 214-device fixture and accepts `PT_CANVAS_FIXTURE`; both accept `PACKET_TRACKER_EXECUTABLE` for the packaged Linux build. They cover keyboard and pointer interaction, focus, links, saved positions, clusters, high contrast and Chromium's accessibility tree.
- The canvas update passed the 388-test Python suite, existing pointer/layout/connectivity browser checks, and packaged Linux keyboard, 214-device and three-lab GUI checks. The packaged native Qt workspace startup check passed on 2026-11-13. Screen-reader speech output and native Qt keyboard interaction remain unverified.
- A 214-device before/after measurement measured redraw medians of 62.8 ms and 51.9 ms, and complete pointer drag times of 382.44 ms and 384.29 ms. Redraw samples include two frame waits; each version has one run and five redraw samples. These measurements do not establish a performance improvement or p95 bound, but did not expose a large redraw/drag regression in that run.

Sections 23–32 are verified for this defined native-browser scope. The next sequential phase is **33 — Operating Modes**. Remaining native-vendor and OS-screen-reader limitations are explicit above and are not completion claims.

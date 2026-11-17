# Physical Customization — legacy network simulator Help Section 18

Reference: /reference/workspace_physical_customIconsAndBG.htm (bundled PT9 help).

## Working functionality

- Per-device independent custom Logical and Physical icons. The device Physical tab now has working Customize Icon in Physical View and Customize Icon in Logical View buttons. Logical changes update topology icons; Physical changes update physical map and rack/table icons. The hardware chassis image stays unchanged.
- Browser Browse accepts PNG/JPEG; images can be chosen from the uploaded library, applied and reset individually. Per-location backgrounds can be selected for Intercity, City, Building, Generic Container, and Wiring Closet.
- Physical Set Background supports per-location background image, tile/fit, background colour, Apply and Reset, with a read-only meter scale from our Section 17 geometry.
- All uploaded image bytes and assignments are stored in the saved native lab JSON, not browser localStorage. Images are SHA-256 content-addressed and deduplicated across devices/locations; exporting and importing JSON preserves them.
- Delete Unused Image is available in the chooser and an agent command; a referenced asset cannot be deleted.

## Reference image sizes and differences

vendor recommends 45x31 px custom device icons, and backgrounds of 2226x1382 (Intercity), 1685x1043 (City), 3444x2157 (Office), and 200x200 (Generic Container).
Our background-dialog scale is metres per calibrated canvas unit, not the exact vendor background-image pixel defaults. Background changes do not change geometry, cabling distance, or wireless range. Device physical positions and container dimensions remain authoritative.

## Safety limits

- Only real PNG and JPEG payloads; validate MIME, signature, dimensions, PNG chunk CRC and IEND, JPEG end marker and basic segment structure. Not a complete raster decoder.
- Maximum 1,000,000 bytes per image, 8192 per image side, 16 million pixels, 40 images and 8MB total image library.
- Upload JSON POST body capped at 1.5MB. Reject oversize/invalid base64, wrong MIME, corrupt metadata and dangling references on load.
- Asset endpoint includes Content-Type image/png or image/jpeg, X-Content-Type-Options nosniff. No SVG/HTML/remote URLs through this workflow.
- HTTP API is localhost-bound and unauthenticated: do not expose to untrusted networks.

## Agent API and CLI

Read:
- GET /api/visuals — images metadata without base64, device icons and backgrounds.
- GET /api/visuals/schema — discovery and schema.
- GET /api/visuals/assets/<sha256> — original image bytes.
- GET /api/physical-distance?location=city0 — geometry scale.

Write:
- POST /api/visuals/action with action upload_image and mime / data_base64 / label.
- action set_device_icon with device / view (logical or physical) / asset_id (sha256 or null).
- action set_background with location / asset_id (sha256 or null) / tiled (bool) / color (#RRGGBB).
- action delete_image with asset_id (only unused images).
- action undo or redo.

Agent Shell:
- visual import /path/to/office.png
- visual upload image/png <base64> [label]
- visual icon R1 physical <sha256>
- visual icon R1 logical default
- visual background city0 <sha256> tile #aabbcc
- visual background intercity default fit #e7e7e7
- visual delete <sha256>

All mutations use NetworkLab + CommandProcessor, with bounded Undo/Redo history and autosave. APIs are discoverable at GET /api/capabilities.

## Not yet implemented

- vendor PKT/PKA/PKZ import/export; images are portable in Packet Tracker and Simulator JSON instead. Current general Save/Open uses host lab-file paths, not a browser-native whole-lab upload/download picker.
- Full vendor bundled-image gallery in picker, vector/SVG/GIF support, cropping and per-device resizing beyond CSS fit.
- Actual background pixels controlling the distance scale (our metric frame is unchanged); exact vendor palette/pixel parity.

## Verification

- 180 automated Python tests, including isolated real HTTP tests, icon independence, per-location BG, Undo/Redo, save/load, hostile/oversized images, reference protection, duplicate asset hashes and 200-device shared images.
- Headless Chromium: file picker PNG upload, tiled city background and separate Intercity, Physical rack icon, Logical topology icon, reset one view without altering other, reset BG, 1600/1024/390px layouts. Zero JS runtime exceptions.
- A backup of the active lab is required before controlled production restart.

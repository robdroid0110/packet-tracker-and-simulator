# Activity (PKA) and network export (PKT): current interoperability status

This is an interoperability prototype, not a replacement for Packet Tracer's complete activity system. Keep native Packet Tracker JSON as the authoritative project. Do not submit exported PKT files as official Packet Tracer labs without verifying them in Packet Tracer first.

## Implemented

- Open PKA activities from the desktop file picker.
- Decode the encrypted container using the existing independently implemented codec.
- Read the legacy XML. If it contains invalid XML attribute characters, an optional non-networking lxml recovery parser can extract the readable data and warns about recovery. DTD and external entities are rejected.
- Import the CURRENT working network, not the instructor's answer snapshot. Preserve supported devices, logical coordinates, supported IP/IOS fields and cable endpoints.
- Present activity instructions as inert plain text, with chapter navigation and a saved "reviewed" flag for each chapter. The local activity state survives native JSON save/reload.
- Compare a limited supported set of IP/interface/routing fields to SHA-256 fingerprints from the answer network, without retaining the plaintext answer configuration or vendor comparison tree. The result is NOT an official grade.
- Display semantic link status in the desktop topology: green = up/forwarding, amber = STP blocked/discarding, red = down, black = console. Cable patterns distinguish copper/fibre/serial/crossover where supported.
- Experimental PKT network export via a desktop button. The codec output is self-consistent and can be decoded by our importer, but vendor compatibility is NOT established.

## Private-file interoperability verification

A third-party, user-authorized activity file was examined locally to validate encrypted container decoding, nonstandard XML recovery, the current working network, instructions, and supported-field checks. The source file, embedded media, instructor answer data, activity title and other identifying details are not redistributed or documented here. Synthetic tests are used in this repository instead.

## Known limitations

- Cisco/Packet Tracer firmware, device internals, unsupported IOS commands, WLC and wireless behaviour, physical-power model and multi-layer switch feature parity.
- Official activity grading, teacher scoring weights, locking, timers, scripts, hidden comparisons and original Check Results.
- Embedded activity images and exact rich-text page layout. The content is readable text, but not pixel-perfect.
- Complete saving back to PKA or reliable vendor-compatible PKT exports. The current PKT writer omits proprietary device subtrees and may be rejected by official Packet Tracer.
- The XML recovery stage is necessarily lossy for invalid attribute bytes. Never overwrite the source activity.

These are distinct large subsystems. Import success is not evidence of full simulation or grading compatibility.

## Verified desktop functionality

The desktop is PyQt6/QWebEngine, not the browser-only test harness. Using an isolated state file outside the Git repository, native desktop testing loaded a private activity, displayed its instruction pages, marked and unmarked review progress, rendered state-derived link symbols, resized into a narrow split-screen layout, and saved an experimental PKT container. The container passed internal decode/import; official Packet Tracer acceptance remains unproven.

The repository's test_activity_interoperability.py uses original synthetic fixtures, with no proprietary lesson data. A private file can optionally be tested locally by setting PTS_TEST_PKA to its path.

For safety, import the source PKA into a separate simulator instance. Never overwrite the original activity.

## Native desktop file-picker acceptance (private opt-in)

To validate a legally obtained activity without committing its contents, run an isolated desktop server with an empty state file outside the repository:

```sh
python3 desktop.py --server --port 8769 --state /tmp/pts-private-test.json
# In another terminal, select an activity you are authorized to use:
PTS_TEST_PKA=/path/to/your/private/activity.pka PTS_TEST_BASE=http://127.0.0.1:8769 \
  python3 tools/check_native_pka_file_picker.py
```

The Qt WebEngine test uses a native mouse event and file chooser, confirms import, instruction pages and status markers, and leaves source content outside the Git repository. Never commit the activity file or generated converted JSON.

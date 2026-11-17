# Desktop applications

Packet Tracker and Simulator uses the same local simulator, web interface and agent API in its desktop and browser versions. The server listens on the local machine only.

## Linux

Run `python3 tools/install_linux_desktop.py` from this checkout to install a **Packet Tracker and Simulator** application-menu entry for the current user. The entry runs `desktop.py` from this checkout, so keep the checkout in place. Python 3, PyQt6 and Qt WebEngine must be installed for the desktop window; without Qt the launcher opens the web interface in the default browser. The installed entry uses the bundled original SVG icons and project help.

After rebuilding the current release, the `dist/linux/PacketTrackerSimulator` is a standalone x86-64 executable. It was built and tested on the current Linux system; compatibility with older distributions and their system libraries is not guaranteed. Run it directly, or copy it to a suitable executable location. The standalone build uses generic artwork and does not include any third-party proprietary assets.

When a Packet Tracker and Simulator server is already running on port 8765, the desktop app connects to it. Thus the installed launcher and browser show and modify the same current lab. When the source launcher starts a new server, it uses the checkout's existing `labs/autosave.json`, if present. The standalone build stores a new lab under `$XDG_DATA_HOME/PacketTracker/autosave.json` (normally `~/.local/share/PacketTracker/autosave.json`). Backups are stored beside that file in `backups/`. Use `--state PATH` to select a lab and start a separate local server rather than attaching to the server on the default port. Alternatively, `PACKETTRACKER_STATE` sets the default for a newly started server; it does not change the lab of an already running server.

## Windows

After rebuilding on Windows, run the x86-64 `dist/windows/PacketTrackerSimulator.exe` on Windows. It opens the interface in a Microsoft Edge app window when Edge is installed, otherwise in the default browser. The executable starts the local server automatically and provides the same API as the web app. Its default saved lab is `%LOCALAPPDATA%\PacketTracker\autosave.json`, with backups in the adjacent `backups` folder. It does not automatically import labs from another computer. The Windows executable has been exercised under Wine, including its backend API and saved state; it has not yet been tested on a native Windows installation. All packaged icons and user help are original to this project.

## Web access and lifecycle

With the default port available, open <http://127.0.0.1:8765> in a browser to use the same running lab. If another service occupies that port, the desktop launcher selects a free port instead. Closing the Linux desktop main window asks whether to save a separate JSON project, discard that export, or cancel closing; simulator mutations are already autosaved. The local server remains running so browser and API clients continue to work, and can be stopped through the operating system's process manager.

Select the hand tool or use the horizontal and vertical scrollbars to pan the logical workspace without moving devices. Clicking a device opens a device-only window, and multiple device windows can be open at once; they all use the same local simulator. In a browser, pop-ups must be allowed for the local Packet Tracker and Simulator site. The device CLI keeps its input at the prompt for successive commands.

A normal click opens a device; to move it, keep the primary mouse button pressed and drag at least 6 screen pixels. There is no waiting period before movement starts. A drag release is consumed so it cannot open a device. Ctrl/Shift-click supports selection. Idle simulation controls are updated only when their contents change, and device windows do not run their own simulation polling loop.

The interaction regression can be run with Playwright installed: `PLAYWRIGHT_MODULE=/path/to/playwright-core node tools/check_workspace_interactions.cjs`. It creates an isolated simulator and checks click jitter, deliberate dragging, the next click, device-only windows and stable idle controls.
Set `PACKET_TRACKER_EXECUTABLE` to an absolute executable path to run the same checks against a packaged build.

The simulation control strip wraps on narrow windows instead of overlapping the mode buttons. Device tabs scroll horizontally when needed, and the CLI fills the available device window with its input at the prompt. Toolbar and palette controls have text/symbol fallbacks when original icons is unavailable. Native device-window titles identify the device.

Run `PLAYWRIGHT_MODULE=/path/to/playwright-core node tools/check_ui_layout.cjs` for responsive layout, terminal sizing/focus and missing-artwork checks. It also accepts `PACKET_TRACKER_EXECUTABLE`.

The time/simulation strip uses a navy gradient, cyan active-mode highlights, rounded buttons and bundled SVG icons. Its clock has a fixed width, so time changes do not move adjacent controls. At narrower desktop widths the groups wrap and all labels remain available. Playback and mode indicators reflect the existing simulation backend; power cycling retains its confirmation. There are no saved-lab or API-format changes.

Run `PLAYWRIGHT_MODULE=/path/to/playwright-core node tools/check_time_controls.cjs` to verify the strip at 800, 1024, 1440 and 1920 pixels, fixed clock geometry, playback/mode requests, Event List, and power-cycle confirmation against an isolated temporary lab. Set `PACKET_TRACKER_EXECUTABLE` to test the Linux package.

The device palette, scenario controls, PDU table and status bar share the same navy/cyan appearance. Common device and category icons use bundled vector artwork in both source and standalone builds. Device and PDU lists scroll horizontally; the dock uses proportional columns with bounded saved widths, and stacks the PDU panel below the palette at widths of 740 pixels or less. The simulation strip is 42 pixels high at the default UI scale on wide desktop windows (previously 64–76 pixels). Playback buttons stay together when wrapping.

Dock sizing responds to window height, wrapped controls and the existing global UI scale, while keeping canvas space available. In very small windows or at enlarged UI scale, the dock itself scrolls vertically so both sections remain reachable. Dragging its splitters starts from the actual displayed size, including when an old saved width has been clamped for a smaller window. Existing saved layout preferences are retained.

Legacy event/PDU display code now yields to the authoritative simulation renderer, preventing backend PDU results from disappearing after a state refresh. No API or saved-lab formats change.

Run `PLAYWRIGHT_MODULE=/path/to/playwright-core node tools/check_bottom_dock.cjs` for 320–2172 pixel layouts at 1x/1.5x UI scale, short windows, restored sizes and resizing, filtering and device placement, cable/category selection, PDU/scenario operations, result persistence across refresh, and PDU undocking/redocking. It uses an isolated temporary lab and accepts `PACKET_TRACKER_EXECUTABLE`. These checks cover the bottom dock; the rest of the application still has some narrow-screen limitations.

The top menu, toolbars and workspace tabs now share the navy/cyan styling of the lower dock, with their existing row heights and UI scale retained. The Simulation Panel has separate event, playback and filter cards, bundled high-contrast playback icons, a full-width colour legend button, a backend-derived protocol summary, and an explicit empty state. The panel fits within the workspace width; in short windows it scrolls vertically so the close button, filters and legend remain reachable.

Playback, speed, constant delay, reset and protocol checkboxes continue to use the authoritative simulation actions. The panel's Play/Pause icon and accessible label follow backend state. Edit Filters exposes the protocol checkboxes and reports its expanded state; filtering affects visibility, not packet delivery. Legacy replay rendering now yields to backend capture state, so refreshing the lab no longer clears the authoritative event list.

Run `PLAYWRIGHT_MODULE=/path/to/playwright-core node tools/check_simulation_panel.cjs` to check 320–1969 pixel widths at 1x/1.5x scale, unchanged top row heights, panel clipping/scrolling, ICMP capture and inspection, capture-row text contrast, filter selection, playback, speed/constant-delay preferences, reset, refresh persistence and the colour legend. It uses an isolated temporary lab and accepts `PACKET_TRACKER_EXECUTABLE` for packaged Linux verification. Saved lab and API formats are unchanged.

## Building

Build on the target operating system with Python and PyInstaller installed. Linux builds additionally require PyQt6 and PyQt6-WebEngine. Run `python tools/build_desktop.py --dist dist/linux` on Linux or `python tools/build_desktop.py --dist dist/windows` on Windows. Build output is ignored by Git; no saved labs or proprietary third-party assets are included. Windows and Linux have different executable formats, so each must be built for its target platform.

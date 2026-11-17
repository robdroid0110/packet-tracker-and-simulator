# Responsive workspace design

Packet Tracker and Simulator supports desktop, split-screen, short-window, and narrow portrait viewports without altering the network simulation or existing desktop presentation.

## Layout modes

- **Desktop:** Above 1060 CSS pixels wide and 640 CSS pixels high, retain the multicolumn device dock, PDU panels, resizable splitters, and stored panel sizes.
- **Compact:** At widths up to 1060 CSS pixels or heights up to 640 CSS pixels, prioritize canvas space. Playback controls scroll horizontally instead of wrapping. The device palette stays in a single row.
- **Short window:** At 440 CSS pixels tall or less, default to canvas-first display, unless the user has manually selected a mode in this session.
- **Narrow portrait:** At widths up to 520 pixels, show Canvas, Devices, PDU and Fit on a dedicated toolbar row.
- **Canvas button:** Temporarily hides the dock, while Devices restores the palette.
- **PDU button:** Opens the existing scenario and packet event panels in a closable overlay rather than stacking them beneath the device palette.
- **Fit button:** Automatically adjusts read-only canvas zoom for the available viewport; once the user adjusts zoom manually, that choice remains in effect until Fit is selected.

Escape closes the PDU overlay. Controls remain accessible through keyboard navigation and horizontal scrolling. Existing global UI-scale preferences are supported. Saved device coordinates and network state remain unchanged.

The compact layout respects the existing Hide bottom dock preference. Other stored desktop dock widths and heights are not overwritten; they resume when the viewport becomes large enough.

## Verification

The dedicated test covers sixteen window sizes, including 675x750 split-screen, 375x667 and 320x568 narrow portrait, 840x360 short window, large desktop, and UI scaling at 1x, 1.25x, and 1.5x. It also verifies panel toggles, device palette, PDU overlay, keyboard Escape, Fit, hide-dock behaviour and desktop restoration.

Use these commands in the project root:

    node tools/check_responsive_layout.cjs
    node tools/check_bottom_dock.cjs
    node tools/check_simulation_panel.cjs
    node tools/check_time_controls.cjs
    node tools/check_topology_presentation.cjs
    python3 -m unittest discover -s tests -q

Browser tests require Chromium and Playwright. If Playwright is installed elsewhere, set PLAYWRIGHT_MODULE to its module path.

The changes affect browser presentation only. They do not change routing, simulation state, command APIs, file formats, or physical workspace behaviour.

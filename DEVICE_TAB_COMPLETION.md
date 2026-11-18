# Device console Tab completion

The native Linux desktop and browser-backed Packet Tracker interface capture **Tab** when a simulated command input is focused. This assists typing only: the simulator does not execute a command until the user presses Enter.

## Supported command surfaces

- Router and switch CLI tabs: mode-aware IOS keywords, including commands such as show ip interface brief, configure terminal, interface, switchport mode trunk, shutdown and no shutdown.
- Interface names come from the selected device. Both short names (g0/0, fa0/1) and full names (GigabitEthernet0/0, FastEthernet0/1) can be completed.
- PC/server Desktop > Command Prompt: ipconfig, arp -a, ping, tracert, traceroute and help.
- Built-in Agent Shell: supported verbs and device-name arguments.

Tab expands the current token when unambiguous or extends its shared prefix. If more than one option remains, the console displays a compact, non-executable list of matches. The input retains keyboard focus. Cursor position and text after the cursor remain intact. Shift+Tab still navigates to another control.

The IOS endpoint is POST /api/ios/complete, accepting a JSON object with device, text and cursor. It returns a replacement span and candidate tokens. The endpoint respects the existing IOSSession mode and does not execute any command, create a persistent session or change the saved network. It will not complete passwords. Input lengths, device kinds and cursor bounds are validated.

Catalog-only devices and placeholder desktop tools do not gain simulated command interpreters from this feature.

## Testing

Mode-aware unit tests:

    python3 -m unittest discover -s tests -p test_ios_tab_completion.py -v

Native PyQt6 / QtWebEngine acceptance with actual Qt Tab key events:

    QT_QPA_PLATFORM=wayland python3 tools/check_native_tab_completion.py

The native test starts its own temporary localhost simulator with four synthetic devices, uses an ephemeral port, and never modifies existing user labs. An X11 environment can use a working xcb display. A functional desktop display is required for this test.

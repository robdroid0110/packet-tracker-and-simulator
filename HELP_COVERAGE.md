# Feature coverage and limitations

This report describes Packet Tracker and Simulator's implemented behaviour. It is based on the project's code, documentation and regression suite, not on the documentation layout or menu hierarchy of another application.

A feature is **supported** when its simulator engine, GUI, agent API and automated checks agree. **Simplified** means intentionally limited networking behaviour. **Catalogue-only** means a model may be placed without full protocol simulation.

| System area | Implemented scope | Details |
| --- | --- | --- |
| Topology editing | Device placement, movement, grouping, annotation and linking | README.md |
| Physical workspace | Locations, equipment containers, racks and saved positions | PHYSICAL_WORKSPACE_REFERENCE.md |
| Cables | Typed connections, basic media constraints and routed lengths | PHYSICAL_CABLE_MANIPULATION_REFERENCE.md |
| Catalogue | Network/end/IoT/industrial devices labelled by support level | OPERATING_MODES_DEVICES_REFERENCE.md |
| Device setup | Interfaces, power, modules and network configuration | OPERATING_MODES_DEVICES_REFERENCE.md |
| IPv4 | Connected/static routing, gateway resolution and diagnostics | CONNECTIVITY_VERIFICATION.md |
| IPv6 | Selected static routing, SLAAC and DHCPv6 support | OPERATING_MODES_DEVICES_REFERENCE.md |
| Routing protocols | Simplified OSPF and RIP | OSPF_AREAS_REFERENCE.md |
| Switching | VLANs, trunks, MAC learning, STP and EtherChannel | OPERATING_MODES_DEVICES_REFERENCE.md |
| Services | DNS, HTTP, DHCP, FTP/TFTP, mail, AAA, NTP/PTP, syslog and SNMP | OPERATING_MODES_DEVICES_REFERENCE.md |
| Wireless | AP, WLAN and selected controller workflows | OPERATING_MODES_DEVICES_REFERENCE.md |
| Security | Selected ACL, NAT/PAT, administration and firewall operations | OPERATING_MODES_DEVICES_REFERENCE.md |
| Industrial/IoT | Limited PLC, sensor, historian and industrial network behaviour | INDUSTRIAL_PROTOCOLS_REFERENCE.md |
| Simulation | Event queue, packet tracing, scenario operations and filters | OPERATING_MODES_DEVICES_REFERENCE.md |
| Device CLI | Stateful command subset with explicit unsupported responses | COMMAND_REFERENCE_IMPLEMENTATION.md |
| Agent control | Capability discovery and JSON/command API | API_FEATURE_CONTRACT.md |
| Files | JSON projects, backups, sample labs and partial legacy .pkt import | FILE_IMPORT.md |
| Accessibility | Keyboard support, contrast, scale and workspace navigation | WORKSPACE_ACCESSIBILITY_REFERENCE.md |
| Desktop | Linux/Windows entry points and separate target-platform builds | DESKTOP_APPLICATIONS.md |
| Help and icons | Original self-contained help and dynamically generated SVGs | web/help/index.html |

## Explicit limitations

The model does not execute real network firmware or reproduce wire-accurate packet timings. Some catalogue models cannot be configured with full device-specific protocol logic. Partial legacy .pkt import does not support .pka activity execution or .pkz export. A similar-looking interface does not imply production-hardware equivalence.

## Verification

Run the Python unittest suite with python3 -m unittest discover -s tests -q. Browser layout and interaction checks in tools/check_*.cjs require Chromium and Playwright. See GITHUB_RELEASE.md for distribution requirements.

This is an independent feature matrix. More detail, examples and verification contracts are documented in the linked source files.

# Operating modes, connections and device configuration — help sections 33–73

Packet Tracker and Simulator implements independent, deterministic protocol/device models. This document defines the implemented scope; it does **not** claim vendor binary, wire-format, hardware, or screen-for-screen parity.

Scope: project-owned simulator models and independently verified user workflows.

## Shared authority and API

All new durable GUI controls use `NetworkLab` through the following interfaces. No browser-local scenario, device, service, or module configuration is authoritative.

| Interface | Purpose |
|---|---|
| `GET /api/simulation/schema` | Operations, applications, limits and time semantics |
| `GET /api/simulation` | Current scenario, PDUs, captured events, visible events, legend and clock; advances realtime/playing work using wall time |
| `POST /api/simulation/action` | Mode, scenario/PDU CRUD, fire, capture, back, reset, advance, playback and filters |
| `GET /api/device-config/schema` | Typed device, hardware, service and specialized operations |
| `GET /api/device-config?device=NAME` | Profile, interfaces, modules, running/startup configurations and routes |
| `POST /api/device-config/action` | Atomic hardware/configuration/service/device-family operation |
| `POST /api/web` | Simulated HTTP(S); returns **202** plus a `job` in Simulation Mode |
| `GET /api/state` | Complete saved-lab representation, including pending simulation traffic |
| `GET /api/capabilities` | Machine-readable discovery of these interfaces and existing topology/IOS APIs |

Write responses contain `ok`, JSON-encoded `output`, and the full authoritative `state`. Bad action requests return 400 without changing the lab or saved file. Successful writes autosave and participate in shared undo history. A simulation read can process scheduled traffic; saving after reads records that progress. Schema and device-configuration reads do not dispatch packets.

The same operations are available in the Agent Shell and `netlab`:

```text
simulation '{"action":"mode","mode":"simulation"}'
simulation '{"action":"pdu_add","source":"PC1","destination":"Server1","protocol":"HTTP","start":1,"interval":5,"ttl":32,"size":512}'
simulation '{"action":"step"}'
simulation '{"action":"advance","seconds":12}'
device-config '{"device":"Server1","action":"service","service":"tftp","enabled":true}'
device-config '{"device":"PC1","action":"transfer","server":"Server1","protocol":"tftp","operation":"get","file":"example.txt"}'
device-config '{"device":"R1","action":"save_startup"}'
```

Get the live schema before constructing action payloads: it is the exhaustive field/action reference. Existing `connect`, `module`, `ios`, VLAN/routing/DHCP/NAT and physical-workspace APIs continue to work.

## Sections 33–40: operating modes

Realtime requests execute immediately. Future and periodic PDUs run when simulation reads synchronize wall time, or when agents explicitly advance time. There is no background process advancing a lab while no requests occur.

Simulation Mode queues IPv4/IPv6 ping, browser HTTP and network client utilities. Queuing does not learn ARP/MAC/NDP, transfer files or deliver HTTP content. Capture evaluates forwarding on an isolated candidate and publishes captured effects; queued service changes become visible on the final captured event. Port and power changes remain immediate and invalidate the old capture.

- Capture/Forward processes the next event. Play uses the same scheduler with saved speed/delay preferences.
- Back changes the inspection cursor. It does not undo master time or learned network state. Forward after Back inspects the existing capture first.
- Reset clears the current capture and transient client jobs, retains user PDU definitions, and preserves monotonically increasing master time.
- Scenario CRUD/selection saves names, descriptions and independent PDU definitions. Selecting a scenario resets its capture.
- Complex PDUs have source/destination/device/IP/interface, application, TTL, ToS, length, ports, sequence, send time, period, URL and colour. Source address/interface membership is checked. TTL and TCP/UDP ACL ports affect delivery.
- Filters affect visibility, not forwarding. PDU Information exposes OSI, inbound, outbound and full event panels; the legend explains default protocol colours.
- The UCPW shows user PDUs, status, runs and editing/deletion/fire actions. Transient CLI/browser/client jobs remain inspectable through the API.

Limits: 500 PDUs, 100 scenarios, 2,000 retained events and bounded dispatch work. A request exceeding its work budget fails atomically. Saved pending events resume after load; automatic playback is paused after loading.

Headers and timing are derived model data, not encoded Ethernet/IP packets. Outbound details include forwarding context; packet buffers, TCP congestion/retransmission, real protocol timers and full OSI implementations are outside this model. Generic TCP/UDP success denotes transport reachability; `application_status: transport-only` identifies applications without an application handshake engine.

## Section 41: links

Typed ports/cables support copper straight/crossover with auto-MDIX, single/multimode fibre, serial DCE/DTE with DCE clock, RS232/console framing, phone/modem, coax, octal, USB and IoE. `auto` chooses compatible data media. Wrong port media, serial clocks, mismatched fixed speed/duplex, power/admin state and configured copper distance affect carrier/forwarding.

Each link exposes endpoint `lights`: green, red, STP/REP amber or operational console black, plus DCE identity. The GUI draws those indicators. Console commands require a connected, powered endpoint and matching framing. Console/USB/IoE cables never masquerade as Ethernet links.

Serial and phone paths use simplified packet forwarding. There is no USB peripheral stack, physical electrical model, RF interference, analogue signal/collision simulation, or per-bit serialization.

## Sections 42–47: inventory and modules

Module installation/removal requires power off and disconnected module ports. Generic PT and selected vendor-labelled media cards create stable `mN/P` interfaces; existing saved names are retained. Slot compatibility is a simulator profile, not an exact vendor chassis matrix. Fixed inventories are retained on load; new model defaults add appropriate console/RS232/media/industrial ports.

Router/switch families reuse the routing, bridging and IOS engines. AP/home/WLC/controller/firewall/cloud/industrial models have specialized configuration engines. Passive patch panels and wall mounts forward only between matching front/back pairs. Bridges, hubs, repeaters and DSL/cable modems use simplified relay paths. Clouds relay only explicitly paired ports. Coax splitters provide three typed coax ports. Phones model registration/call state. The wider IoT/cellular catalog remains partly catalog-only; a placeable item is not proof of a completed protocol engine.

## Sections 48–59: global, IOS, switch and security configuration

The native **Device Configuration** dialog is available in device windows. It offers the same typed operations as the agent API, current inventory and running/startup exports. RIP is also available in the existing Config navigation. Existing Config/CLI views continue to configure the common model.

- Independent display/IOS hostname, local users, enable secret, IPv6 forwarding, interface IPv4/IPv6/link-local/gateway/DNS, status, speed, duplex, MAC, MTU, TX-ring limit and auto-MDIX.
- Running configuration merge and startup import from supported IOS text or lossless native JSON; running/startup export. IOS text represents the supported IOS subset; use complete JSON for all services, media and specialized settings.
- Save/erase startup, reload/power, simulated flash files and boot-image selection. Missing/invalid simulated images enter ROMMON with directory/environment/config-register/boot commands. Flash is retained across managed startup restore.
- Legacy labs preserve running configuration on power cycle until save/erase startup enables managed NVRAM behaviour. Once enabled, unsaved running edits are discarded on boot.
- Connected/static routes, simplified OSPF and RIP, VLANs/trunks and multilayer SVIs. RIP advertises configured networks, has a 15-hop bound and withdraws routes on link loss. SVI trunk/access edits rebuild their bridge membership.
- IE industrial switching: deterministic REP ring protection/recovery, bidirectional L2 NAT and DHCP MAC reservations; PTP clock synchronization.
- IPv4 ACLs support named/numeric TCP/UDP ports with eq/neq/lt/gt/range matching and interface binding. Firewall forms add ordered source/destination/application-port/URL/host rules. Existing NAT/PAT remains authoritative.
- Authenticated SSH/Telnet and physical console terminals retain IOS modes between commands. Enable-secret prompts cannot be bypassed with reload/end. IOx application lifecycle uses simulated files and state; licenses use issued, consumed simulated tokens and controller reachability.
- ASA/ISA clientless HTTPS portal: local-user authentication, saved bookmarks and network-gated HTTP(S) proxy access, with expiring client sessions.

All IOS families share a supported command subset. Full IOS/ASA grammar, vendor image execution, industrial DPI, real licensing and arbitrary IOx application execution are outside scope. SSH/TLS/IPsec/WEP/WPA labels model access policy and credentials; cryptographic algorithms are not executed. TX-ring/MTU values are configurable/persistent but there is no byte-buffer performance emulator.

## Sections 60–64: home routers and Meraki

Home routers provide a bridged LAN, WAN, LAN DHCP, routing/NAT, radio settings, MAC filters and authenticated management. Port forwarding translates external/internal TCP/UDP ports and handles return traffic; DMZ forwards otherwise unmatched inbound traffic. Disabling DHCP/NAT removes the corresponding home-generated configuration.

PC Web Browser can open a simulated management page and launch **Manage Device**, authenticate and edit through a network-gated session. Default home credentials are admin/admin until configured. Meraki uses a persistent simulated serial for initial local access and supports controller management. There is no vendor cloud account or Internet dependency.

Wireless association selects the nearest powered, in-range compatible AP, matching SSID, security, PSK/WEP key or RADIUS credentials and MAC filters. Radio links are rebuilt from authoritative physical placement and current configuration. These are deterministic coverage circles, without RF interference or realistic roaming timing. APs currently expose one active WLAN; applying a WLC group selects its first WLAN. vendor multi-band/multi-SSID UI parity is not claimed.

## Sections 65–66: PCs and servers

Desktop tools launch native operations for modem dial-up, console, wireless, VPN, traffic generation, SNMP/MIB, FTP/TFTP, mail, host firewalls, SSH/Telnet, files, IOx lifecycle and industrial supervision. Command Prompt supports address/ARP inspection, ping/tracert, DNS, files, session inspection and service clients; `help` gives its explicit syntax. Password-bearing commands should be entered with the same care as any CLI history.

- IPv6 supports static/link-local addresses, NDP, routed ping, static routes, SLAAC /64 and same-VLAN DHCPv6 pools with stable MAC leases, gateway and DNS settings. Link-local traffic is not routed. IPv6 app transport/DNS resolution, scoped link-local syntax, dynamic IPv6 routing and DHCPv6 relay are not implemented.
- DHCPv4 pools/client/relay and MAC reservations remain on the existing model.
- DNS A/CNAME/NS/SOA metadata, delegation/loop detection, TTL cache inspection/clear. Local authoritative record edits invalidate that server's cache.
- Editable HTTP(S) pages, sandboxed browser rendering and management links; HTTP/HTTPS are simulated services, not host listeners.
- FTP user permissions (read/write/delete/rename/list), TFTP, virtual files, image/configuration transfer.
- SMTP/POP3 accounts, cross-domain routed delivery and mailbox reception; deleting an account removes both protocol credentials.
- RADIUS/TACACS users, client IP/shared secrets; NTP/PTP synchronization; syslog records; SNMP sysName/sysLocation/interface status and administrative writes.
- PPPoE authentication/address leasing and disconnect restore. Modem dial-up uses phone-cloud numbering, credentials and carrier; IP addressing remains manual. VPN uses authenticated split routing and checks its underlying path; it does not encrypt traffic.

Files are virtual: no configuration operation executes a host shell. Supported files are limited to 200 KB each, 100 locally created files and 4 MB per device configuration; transfers and imports are checked before publish. Historian import adds its own 1 MB CSV/request bound. Some legacy unimplemented desktop icons (for example Bluetooth/NetFlow) remain outside this chapter's documented utilities.

## Sections 67–73: specialized devices

| Family | Working configuration/behaviour |
|---|---|
| Network/Meraki controller | Administrator setup, reachable IP-range discovery, optional credential checks, inventory, provisioning and simulated license token lifecycle |
| Cloud | Serial/DSL/coax/phone pair mappings, DLCI identifiers, provider/LMI metadata and phone numbers; carrier-gated forwarding and modem calls |
| WLC | WLAN credentials/VLAN settings, AP groups, reachable CAPWAP configuration push, authenticated clients |
| Historian | Industrial tags, authenticated network collection/query, validated UTC CSV import and bounded records |
| Cyber Observer | Reachability discovery and findings for plaintext services and weak simulated credentials |
| PLC | Six digital/ten analogue tags, copy/boolean/comparator/arithmetic/latch/timer/counter blocks, deterministic scans and linked IoE outputs |
| Other devices | Basic interfaces, bridge/relay/patch paths, AP authentication/coverage, printer/host addressing, phone registration/dial/answer/hangup/C–D–E note events and power state |

Cloud DLCIs/LMI are metadata over paired paths, not a full Frame Relay/ATM implementation. Controller endpoints implement this simulator's API, not the vendor's external REST API. Observer checks are a small explicit ruleset, not packet-capture-based security analytics. PLC uses a safe block interpreter, not IEC binaries. Historian defaults to 10,000 records and remains bounded by per-device storage even when a larger retention limit is requested. Telephone notes are events, without OS audio. TV image galleries, editable/password-locked generic device HTML, cellular services and full rack electrical dependencies remain unsupported.

## Verification

Final run: **310 Python tests passed**, including **51 new tests**. Chromium interaction checks, Python compilation, JavaScript syntax and `git diff --check` passed. The existing 6-device/2-link lab matched its normalized saved state on the updated server and its original file bytes were preserved. Machine-readable evidence is under `research/sections33-73-verification.json`.

Run:

```sh
python3 -m unittest discover -s tests -q
python3 tools/verify_modes_devices.py --artifacts /tmp/packet-tracker-sections33-73-evidence
node --check web/simulation-engine.js
node --check web/device-config-engine.js
```

The Chromium harness starts temporary servers/labs, checks actual controls and responses, captures screenshots and verifies that `labs/autosave.json` bytes did not change. It exercises frozen PDU creation, capture/inspector/Back, scenarios, complex periodic PDUs, realtime return, interface forms, startup restoration, fibre modules, FTP transfer, pending browser completion, PLC timer, controller discovery/provision and WLC group push. HTTP tests use a temporary autosave and assert that failed writes preserve both memory and bytes.

Focused regressions cover old JSON labs, pending-queue restart, invalid load rollback, source TTL, ACL ports, typed media/console/serial, IP service authentication/permissions, wireless range/security, IPv6/SLAAC/DHCPv6, PPPoE/VPN underlay loss, patch pairing, REP recovery, L2 NAT, SVI VLAN edits, RIP withdrawal, terminal/enable state, DNS cache, phone calls, observer findings, clientless portal and port forwarding/DMZ.

The next ordered topic after this implemented scope is **74, Router-rom**, beginning the exhaustive CLI command-reference series. Remaining differences above are retained explicitly rather than represented as full vendor parity.

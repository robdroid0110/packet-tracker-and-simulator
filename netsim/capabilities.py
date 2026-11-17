from __future__ import annotations

from .device_catalog import CATALOG

PRODUCT = "Packet Tracker and Simulator"
CONTROL_PLANE_VERSION = 1

# Machine-readable capability registry. Keep this authoritative: GUI controls,
# shell commands, docs and agent integrations should all map back to these IDs.
ACTIONS = [
    {"id":"network.verify_ping","kinds":["pc","server","router","switch","generic"],"syntax":"GET /api/v1/connectivity/schema; POST /api/v1/connectivity/ping {source,destination_ip}","description":"Versioned IPv4/IPv6 ping results with reachability, failure reason, routed hops and Simulation Mode job tracking."},
    {"id":"samples.library","kinds":["pc","server","router","switch","generic"],"syntax":"GET /api/samples?language=eng|spa; POST /api/samples/action; sample load|check ID","description":"Original concept, skill, design and troubleshooting examples with isolated connectivity checks and undoable loading."},
    {"id":"cli.reference","kinds":["pc","server","router","switch","generic"],"syntax":"GET /api/command-reference[?profile=NAME]; ios DEVICE COMMAND; device-config <host_command JSON>","description":"Audited reference vocabulary for sections 74–138 and shared IOS/host execution; unsupported grammar is explicitly rejected."},
    {"id":"device.configuration","kinds":["pc","server","router","switch","generic"],"syntax":"GET /api/device-config?device=R1; GET /api/device-config/schema; POST /api/device-config/action; device-config <json>","description":"Atomic device/hardware configuration, startup/running lifecycle, network-gated services and specialized device controllers."},
    {"id":"simulation.scheduler","kinds":["pc","server","router","switch","generic"],"syntax":"GET /api/simulation; GET /api/simulation/schema; POST /api/simulation/action; simulation <json>","description":"Authoritative operating modes, scheduled/periodic PDUs, scenarios, capture/back/reset, protocol filters, header/OSI inspection and master time."},
    {"id":"workspace_tools","kinds":[],"syntax":"GET /api/workspace-tools; GET /api/topology-layout; GET /api/workspace-tools/schema; POST /api/workspace-tools/action; workspace-tool <json>","description":"Authoritative logical/physical viewport, diagram routing/labels/focus/zoom preferences, named collapsible groups and signed preview/apply layout, accessibility contrast/scaling, portable device/cluster/container template capture/import/export/instantiate/delete with undo."},
    {"id":"physical_accessibility.view","kinds":[],"syntax":"GET /api/physical-accessibility?location=closet0","description":"Screen-reader-ready physical navigation, child locations, rack surfaces, devices, interface/port occupancy, link statuses and model module slots."},
    {"id":"physical_accessibility.schema","kinds":[],"syntax":"GET /api/physical-accessibility/schema","description":"Discover keyboard/screen-reader interaction contract and typed physical accessibility actions."},
    {"id":"physical_accessibility.edit","kinds":[],"syntax":"POST /api/physical-accessibility/action {action:move_device|mount_device|add_device|connect|disconnect|power|add_shelf|set_module|place_icp_device|undo|redo}","description":"Place/take devices, mount racks, connect cable endpoints, change power/modules and shelves through the shared lab model and accessible UI."},
    {"id":"icp.view","kinds":[],"syntax":"GET /api/icp?location=loc0","description":"Inspect an Industrial Control Panel door/cabinet, DIN/WIC fixtures and device mounts, anchors and read-only preview mode."},
    {"id":"icp.schema","kinds":[],"syntax":"GET /api/icp/schema","description":"Discover ICP preset sizes, fixtures, snapped coordinates and supported actions."},
    {"id":"icp.edit","kinds":[],"syntax":"POST /api/icp/action {action:create|door|preview|device_move|fixture_add|fixture_move|fixture_join|fixture_split|fixture_delete|mount|unmount|undo|redo}","description":"Control industrial cabinet physical layout, doors, fixtures and DIN mounts with shared lab state and undo."},
    {"id":"physical_cables.view","kinds":[],"syntax":"GET /api/physical-cables?location=city0","description":"Read all connected cables within a physical environment with metre-calibrated projected BendPoints, GroupPoints, segments, colours and actual path lengths."},
    {"id":"physical_cables.schema","kinds":[],"syntax":"GET /api/physical-cables/schema","description":"Discover physical cable bend/group/color API contracts and units."},
    {"id":"physical_cables.edit","kinds":[],"syntax":"POST /api/physical-cables/action {action:add_bend|move_bend|delete_bend|set_color|group_bends|move_group|ungroup|undo|redo}","description":"Persist and modify physical cable routing, shared grouped bends and cable colors with one undoable command."},
    {"id":"visuals.assets","kinds":[],"syntax":"GET /api/visuals","description":"Read portable image metadata and per-device Logical/Physical icons and per-location background assignments."},
    {"id":"visuals.image","kinds":[],"syntax":"GET /api/visuals/assets/{sha256}","description":"Read validated image/png or image/jpeg asset by content ID; contents embedded in native saved lab."},
    {"id":"visuals.schema","kinds":[],"syntax":"GET /api/visuals/schema","description":"Discover image type/size limits, CSS tile/fit and supported customization actions."},
    {"id":"visuals.edit","kinds":[],"syntax":"POST /api/visuals/action {action:upload_image|set_cluster_icon|set_device_icon|set_background|delete_image|undo|redo}","description":"Upload/reset device icons independently for Logical/Physical views and manage per-location portable backgrounds with undo."},
    {"id":"physical_distance.measure","kinds":[],"syntax":"GET /api/physical-distance?source=R1&target=R2; physical measure <a> <b>","description":"Calibrated straight-line physical distance between devices in meters, including nested containers."},
    {"id":"physical_distance.link","kinds":[],"syntax":"GET /api/physical-distance?device=R1&interface=g0/0; physical cable-length <device> <interface>","description":"Retrieve cable segment/total straight-line distance, 100m Ethernet limit and carrier status."},
    {"id":"physical_distance.coverage","kinds":[],"syntax":"GET /api/physical-distance?location=city0; physical radio-status [location]","description":"Get wireless coverage circles and geometric in-range pairs; association/authentication is configured through device.configuration."},
    {"id":"physical_distance.schema","kinds":[],"syntax":"GET /api/physical-distance/schema","description":"Discover API payloads, units, limits and current unsupported distance effects."},
    {"id":"physical_distance.config","kinds":[],"syntax":"POST /api/physical-distance/action {action:cable_effects|radio_range|undo|redo}","description":"Enable/disable opt-in 100m cable effects or set source radio range with undo and saved lab."},
    {"id":"workspace.physical_grid","kinds":[],"syntax":"physical grid <intercity|city|building|generic> <on|off> <spacing-m> <#RRGGBB>","description":"Saved metric grid visibility, spacing and color per map container type; read projected spacing through physical workspace API."},
    {"id":"workspace.physical_delete","kinds":[],"syntax":"physical delete-preview <location>; physical delete <location>","description":"Preview or undoably delete a physical subtree, extracting all equipment onto the parent floor with logical devices and cables preserved."},
    {"id":"physical_workspace.read","kinds":[],"syntax":"GET /api/physical-workspace?location=closet0","description":"Read physical container hierarchy, dimensions, shelf inventory, device mount details and connections."},
    {"id":"physical_workspace.schema","kinds":[],"syntax":"GET /api/physical-workspace/schema","description":"Discover typed Physical Workspace actions and constraints."},
    {"id":"physical_workspace.edit","kinds":[], "syntax":"POST /api/physical-workspace/action {action:set_grid|delete_location|add_device|add_location|rename_location|move_location|relocate_location|resize_location|place_device|move_devices|position_device|mount_device|add_shelf|undo|redo}","description":"Validated physical container, placement and storage edits via shared engine and undo history."},

    {"id":"workspace_list.add_in_cluster","kinds":[],"syntax":"add-in-cluster <model-id|kind> <name> <x> <y> <cluster-id>","description":"Atomically add a device directly into a logical cluster through CLI or typed Workspace List API."},
    {"id":"workspace_list.read","kinds":[],"syntax":"GET /api/workspace-list?cluster=root&device=R1","description":"Accessible, cluster-scoped device and link list with module slots, status and coordinates."},
    {"id":"workspace_list.schema","kinds":[],"syntax":"GET /api/workspace-list/schema","description":"Discover typed Workspace List actions, constraints and API payload examples."},
    {"id":"workspace_list.edit","kinds":[],"syntax":"POST /api/workspace-list/action {action: add_device|remove_device|move_device|power_device|add_link|remove_link|set_module|undo|redo}","description":"Typed JSON edit API routed through the shared command processor and undo history."},
    {"id":"workspace.cluster_add","kinds":[],"syntax":"cluster add <name> <device1,device2|none> [parent-id|root]","description":"Create persistent logical cluster, optionally nested."},
    {"id":"workspace.cluster_place","kinds":[],"syntax":"cluster place <device> <cluster-id|root>","description":"Move device into or out of a persistent cluster."},
    {"id":"workspace.cluster_move","kinds":[],"syntax":"cluster move <cluster-id> <parent-id|root>","description":"Nest a cluster with cycle protection."},
    {"id":"workspace.cluster_rename","kinds":[],"syntax":"cluster rename <id> <name>","description":"Rename logical cluster."},
    {"id":"workspace.cluster_delete","kinds":[],"syntax":"cluster delete <id>","description":"Uncluster a group, preserve its network devices."},
    {"id":"workspace.duplicate","kinds":[],"syntax":"duplicate <device1,device2,...> <dx> <dy>","description":"Clone selected devices, configuration and links within the selected group; unique MACs; does not copy outside connections."},
    {"id":"workspace.remove_group","kinds":[],"syntax":"remove-group <device1,device2,...>","description":"Delete selected devices and their attached links in one undoable operation."},
    {"id":"workspace.move_group","kinds":[],"syntax":"move-group <device1,device2,...> <dx> <dy>","description":"Move several logical workspace devices atomically."},
    {"id":"workspace.undo","kinds":[],"syntax":"undo","description":"Undo previous command-driven topology edit (bounded in-process history)."},
    {"id":"workspace.redo","kinds":[],"syntax":"redo","description":"Redo last undone command-driven edit."},
    {"id":"workspace.physical_add","kinds":[],"syntax":"physical add <city|building|closet|generic> <name> [parent-id]","description":"Add a physical geographic location to saved lab state."},
    {"id":"workspace.physical_dimensions","kinds":[],"syntax":"physical dimensions <location> <width-m> <length-m> <height-m>","description":"Set persistent physical container meter dimensions with parent/child fitting checks."},
    {"id":"workspace.physical_relocate","kinds":[],"syntax":"physical relocate <location> <parent|intercity>","description":"Move a physical location across the hierarchy with cycle/type/size checks."},
    {"id":"workspace.physical_move_devices","kinds":[],"syntax":"physical move-devices <device1,device2,...> <location|intercity>","description":"Atomically move 1-200 physical devices into another location, preserving logical links, stacked at map upper-left."},
    {"id":"physical_workspace.tree","kinds":[],"syntax":"GET /api/physical-workspace/tree","description":"Discover entire expandable physical location/device navigation hierarchy and cross-container links."},
    {"id":"workspace.physical_device_position","kinds":[],"syntax":"physical device-position <device> <x> <y>","description":"Persist device position inside its physical location, independent of logical topology."},
    {"id":"workspace.physical_shelf_add","kinds":[],"syntax":"physical shelf-add <closet>","description":"Create a storage shelf inside a wiring closet."},
    {"id":"workspace.physical_mount","kinds":[],"syntax":"physical mount <device> <floor|rack|table|shelf> [shelf-index]","description":"Assign wiring closet rack/table/shelf placement; shelf requires powered-off and disconnected device."},
    {"id":"workspace.physical_rename","kinds":[],"syntax":"physical rename <location-id> <name>","description":"Rename a location without changing connectivity."},
    {"id":"workspace.physical_position","kinds":[],"syntax":"physical position <location-id> <x> <y>","description":"Move a physical map thumbnail."},
    {"id":"workspace.physical_place","kinds":["pc","server","switch","router","generic"],"syntax":"physical place <device> <location-id|intercity>","description":"Place a device in a physical container while preserving logical topology and configuration."},
    {"id":"topology.add","kinds":["pc","server","switch","router","generic"],"syntax":"add <pc|server|switch|router|generic> <name> [x y]","description":"Create a base device in the logical workspace."},
    {"id":"workspace.note_add","kinds":[],"syntax":"note add <x> <y> <text>","description":"Place a persistent logical-workspace note."},
    {"id":"workspace.note_edit","kinds":[],"syntax":"note edit <note-id> <text>","description":"Edit logical-workspace note content."},
    {"id":"workspace.note_move","kinds":[],"syntax":"note move <note-id> <x> <y>","description":"Reposition an annotation."},
    {"id":"workspace.note_delete","kinds":[],"syntax":"note delete <note-id>","description":"Remove a note from the logical workspace."},
    {"id":"device.module","kinds":["router","switch","pc","server"],"syntax":"module <device> <slot> <PT-ETH-1|PT-ETH-4|none>","description":"Simulated PT expansion modules (generic profiles only); device must be powered off; connected ports cannot be removed."},
    {"id":"topology.add_model","kinds":["pc","server","switch","router","generic"],"syntax":"add-model <model-id> <name> [x y]","description":"Create a device from the legacy network simulator 9.0 model catalog."},
    {"id":"topology.rename","kinds":["pc","server","switch","router","generic"],"syntax":"rename <old-name> <new-name>","description":"Change a device display name while preserving links and configuration."},
    {"id":"topology.remove","kinds":["pc","server","switch","router","generic"],"syntax":"remove <name>","description":"Remove a device and its links."},
    {"id":"topology.move","kinds":["pc","server","switch","router","generic"],"syntax":"move <device> <x> <y>","description":"Move a device on the logical workspace."},
    {"id":"link.connect","kinds":["pc","server","switch","router","generic"],"syntax":"connect <dev1> <if1> <dev2> <if2> [auto|copper-straight|copper-cross]","description":"Cable two physical interfaces. Legacy copper polarity and power determine live link status."},
    {"id":"link.auto_connect","kinds":["pc","server","switch","router","generic"],"syntax":"auto-connect <device1> <device2>","description":"Select available compatible data ports and connect two devices automatically."},
    {"id":"lab.power_cycle","kinds":[],"syntax":"power-cycle","description":"Restart devices, restore managed startup configurations, and clear learned tables and packet trace."},
    {"id":"device.power","kinds":["pc","server","switch","router","generic"],"syntax":"power <device> <on|off>","description":"Change power/carrier and apply managed startup on boot; legacy unmanaged labs preserve running configuration."},
    {"id":"link.disconnect","kinds":["pc","server","switch","router","generic"],"syntax":"disconnect <device> <iface>","description":"Disconnect the cable on an interface."},
    {"id":"interface.ipv4","kinds":["pc","server","router"],"syntax":"ip <device> <iface> <address/prefix>","description":"Assign IPv4 address/prefix."},
    {"id":"interface.admin_state","kinds":["pc","server","switch","router","generic"],"syntax":"up|down <device> <iface>","description":"Change interface administrative state."},
    {"id":"host.gateway","kinds":["pc","server"],"syntax":"gateway <device> <ipv4>","description":"Set host default gateway."},
    {"id":"router.subinterface","kinds":["router"],"syntax":"subif <router> <parent-if> <vlan-id> <address/prefix>","description":"Create an 802.1Q router subinterface."},
    {"id":"router.static_route","kinds":["router"],"syntax":"route <router> <prefix> via <next-hop> | route <router> <prefix> dev <interface>","description":"Install a static IPv4 route."},
    {"id":"router.ospf","kinds":["router"],"syntax":"ospf <router> enable [network/prefix [area <id>]] | auto | disable | clear | remove <network/prefix>; show ospf <router>","description":"Configure area-aware, hop-based OSPF and inspect modeled interfaces and neighbors."},
    {"id":"router.dhcp_relay","kinds":["router"],"syntax":"helper <router> <iface> <dhcp-server-ip|none>","description":"Configure/remove DHCP relay helper address."},
    {"id":"router.acl","kinds":["router"],"syntax":"acl <router> <name> <permit|deny> <ip|icmp|tcp|udp> <src> <dst> [sequence] ; access-group <router> <iface> <acl|none> <in|out>","description":"Create IPv4 ACL rules and bind them inbound/outbound on router interfaces."},
    {"id":"router.nat_static","kinds":["router"],"syntax":"nat-role <router> <iface> <inside|outside|none> ; nat-static <router> <inside-local> <inside-global>","description":"Configure stateful static IPv4 NAT."},
    {"id":"router.nat_pat","kinds":["router"],"syntax":"nat-overload <router> <inside-network> <outside-iface>","description":"Configure stateful interface PAT/overload with return translation tracking."},
    {"id":"switch.vlan","kinds":["switch"],"syntax":"vlan <switch> <vlan-id>","description":"Create a VLAN."},
    {"id":"switch.access_port","kinds":["switch"],"syntax":"switchport <switch> <iface> access <vlan-id>","description":"Configure access port VLAN."},
    {"id":"switch.trunk","kinds":["switch"],"syntax":"switchport <switch> <iface> trunk <vlan1,vlan2,...>","description":"Configure 802.1Q trunk allowed VLANs."},
    {"id":"switch.native_vlan","kinds":["switch"],"syntax":"native-vlan <switch> <iface> <vlan-id>","description":"Set trunk native VLAN."},
    {"id":"switch.stp","kinds":["switch"],"syntax":"stp <switch> mode <pvst|rapid-pvst> | stp <switch> priority <0..61440>","description":"Configure spanning-tree mode or bridge priority."},
    {"id":"switch.portfast","kinds":["switch"],"syntax":"portfast <switch> <iface> <on|off>","description":"Toggle PortFast."},
    {"id":"switch.etherchannel","kinds":["switch"],"syntax":"channel <switch> <iface> <group> <on|active|passive|desirable|auto>","description":"Configure static, LACP or PAgP EtherChannel."},
    {"id":"dns.client","kinds":["pc","server"],"syntax":"dns-client <host> <ipv4|none>","description":"Set host's simulated DNS resolver."},
    {"id":"dns.service","kinds":["server"],"syntax":"dns-service <server> on|off","description":"Enable or disable an authoritative local DNS service."},
    {"id":"dns.record","kinds":["server"],"syntax":"dns-add <server> <hostname> <ipv4>","description":"Add a simulated DNS A record."},
    {"id":"http.service","kinds":["server"],"syntax":"http-service <server> on|off","description":"Enable simulated HTTP service."},
    {"id":"http.page","kinds":["server"],"syntax":"http-page <server> <path> <HTML>","description":"Set a simulated HTTP page (served inside a sandboxed preview)."},
    {"id":"http.client","kinds":["pc","server"],"syntax":"web-get <pc> <url>","description":"Resolve a host and issue a simulated HTTP GET; never accesses the real Internet."},
    {"id":"pdu.icmp","kinds":["pc","server","router"],"syntax":"pdu <source> <destination>","description":"Send a simple ICMP PDU and record a synthetic packet event trace."},
    {"id":"dhcp.server_pool","kinds":["router","server"],"syntax":"dhcp-pool <router|server> <name> <network> <gateway> <start> <end> [dns]","description":"Create a DHCP pool."},
    {"id":"dhcp.client","kinds":["pc","server"],"syntax":"dhcp <pc|server> <iface>","description":"Request a DHCP lease."},
    {"id":"discovery.cdp","kinds":["router","switch"],"syntax":"cdp <device> <on|off>","description":"Toggle CDP."},
    {"id":"discovery.lldp","kinds":["router","switch","pc","server"],"syntax":"lldp <device> <on|off>","description":"Toggle LLDP."},
    {"id":"diagnostic.ping","kinds":["pc","server","router","switch"],"syntax":"ping <source-device> <destination-ip>","description":"Test bidirectional IPv4 reachability."},
    {"id":"diagnostic.traceroute","kinds":["pc","server","router","switch"],"syntax":"traceroute <source-device> <destination-ip>","description":"Trace routed forwarding path."},
    {"id":"device.ios_cli","kinds":["router","switch"],"syntax":"ios <device> <ios-command...>","description":"Execute a stateful IOS-like CLI command."},
    {"id":"lab.save","kinds":[],"syntax":"save <path>","description":"Save complete lab state."},
    {"id":"lab.load","kinds":[],"syntax":"load <path>","description":"Load complete lab state."},
]

DEVICE_TYPES = {
    "generic": {
        "display_name": "Catalog Device",
        "tabs": ["Physical", "Config", "Attributes"],
        "default_interfaces": ["eth0"],
        "features": {"placement":"implemented", "cabling":"implemented", "protocol_engine":"not-yet-implemented"},
    },
    "pc": {
        "display_name": "PC",
        "tabs": ["Physical", "Config", "Desktop", "Programming", "Attributes"],
        "default_interfaces": ["eth0"],
        "desktop_tools": {
            "IP Configuration":"implemented", "Command Prompt":"implemented",
            "Terminal":"implemented-simplified", "Web Browser":"implemented-simplified", "PC Wireless":"implemented-simplified",
            "VPN":"implemented-simplified", "Traffic Generator":"implemented-simplified", "MIB Browser":"implemented-simplified",
            "IP Communicator":"implemented-simplified", "IPv6 Firewall":"implemented-simplified",
            "Firewall":"implemented-simplified", "Text Editor":"implemented-simplified", "PPPoE Dialer":"implemented-simplified",
            "Email":"implemented-simplified", "NetFlow Collector":"planned", "IOX IDE":"implemented-simplified",
            "TFTP Service":"implemented-simplified", "Telnet / SSH":"implemented-simplified", "Bluetooth":"planned",
            "User App Manager":"implemented-simplified", "Supervisory Workstation":"implemented-simplified",
            "IoT Editor":"implemented-simplified", "IoT Monitor":"implemented-simplified", "Dial-up":"implemented-simplified",
        },
    },
    "server": {
        "display_name": "Server",
        "tabs": ["Physical", "Config", "Services", "Desktop", "Programming", "Attributes"],
        "default_interfaces": ["eth0"],
        "services": {"DHCP":"implemented", "DNS":"implemented-simplified", "HTTP":"implemented-simplified", "FTP":"planned", "TFTP":"planned", "Email":"implemented-simplified"},
    },
    "switch": {
        "display_name": "Layer-2 Switch",
        "tabs": ["Physical", "Config", "CLI", "Attributes"],
        "default_interfaces": ["fa0/1..fa0/12", "g0/1..g0/2"],
        "features": {"VLAN":"implemented", "802.1Q trunk":"implemented", "PVST":"implemented", "Rapid-PVST":"implemented", "EtherChannel":"implemented", "CDP":"implemented", "LLDP":"implemented", "DHCP snooping":"planned", "DAI":"planned", "DTP":"planned", "VTP":"planned"},
    },
    "router": {
        "display_name": "Router",
        "tabs": ["Physical", "Config", "CLI", "Attributes"],
        "default_interfaces": ["g0/0..g0/3"],
        "features": {"IPv4":"implemented", "static routing":"implemented", "router-on-a-stick":"implemented", "OSPF":"implemented-simplified", "DHCP server":"implemented", "DHCP relay":"implemented", "CDP":"implemented", "LLDP":"implemented", "ACL":"implemented", "NAT/PAT":"implemented-stateful", "IPv6":"implemented-static-slaac", "HSRP":"planned"},
    },
}


def registry(lab=None) -> dict:
    actions = [dict(a, implemented=True) for a in ACTIONS]
    by_kind = {kind: [a["id"] for a in actions if kind in a.get("kinds", [])] for kind in DEVICE_TYPES}
    devices = {}
    for kind, spec in DEVICE_TYPES.items():
        devices[kind] = {**spec, "actions": by_kind[kind]}
    out = {
        "product": PRODUCT,
        "control_plane_version": CONTROL_PLANE_VERSION,
        "principle": "GUI and agents operate the same simulator state through one authoritative control plane.",
        "device_types": devices,
        "actions": actions,
        "device_catalog": CATALOG,
        "agent_endpoints": {
            "state": "GET /api/state",
            "capabilities": "GET /api/capabilities",
            "single_command": "POST /api/command {command}",
            "batch": "POST /api/batch {commands:[...], stop_on_error:true}",
            "connectivity_schema":"GET /api/v1/connectivity/schema",
            "verify_ping":"POST /api/v1/connectivity/ping {source,destination_ip}",
            "simulation_schema":"GET /api/simulation/schema",
            "simulation":"GET /api/simulation; POST /api/simulation/action",
            "device_configuration_schema":"GET /api/device-config/schema",
            "device_configuration":"GET /api/device-config?device=NAME; POST /api/device-config/action",
            "ospf_status":"GET /api/ospf?device=NAME",
        },
    }
    if lab is not None:
        out["instances"] = {name: {"kind": d.kind, "model": d.model, "interfaces": list(d.interfaces)} for name, d in lab.devices.items()}
    return out


def capability_text(target: str | None = None, lab=None) -> str:
    reg = registry(lab)
    if not target:
        lines = [f"{PRODUCT} agent capabilities v{CONTROL_PLANE_VERSION}", "Device types: " + ", ".join(DEVICE_TYPES)]
        lines.append("Use: capabilities <device-type|device-name> or GET /api/capabilities")
        lines.append(f"Implemented agent actions: {len(ACTIONS)}")
        return "\n".join(lines)
    kind = target.lower()
    if lab is not None and target in lab.devices:
        kind = lab.devices[target].kind
    if kind not in DEVICE_TYPES:
        return f"Unknown device type or instance: {target}"
    spec = reg["device_types"][kind]
    lines = [f"{target} -> {spec['display_name']} ({kind})", "Tabs: " + " / ".join(spec.get("tabs", [])), "Actions:"]
    action_map = {a["id"]: a for a in ACTIONS}
    for aid in spec["actions"]:
        a = action_map[aid]
        lines.append(f"  {aid:<26} {a['syntax']}")
    return "\n".join(lines)

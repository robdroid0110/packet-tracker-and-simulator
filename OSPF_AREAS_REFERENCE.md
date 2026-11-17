# Area-aware OSPF

Packet Tracker and Simulator models a simplified IPv4 OSPF control plane. An interface participates only when it has an IP address selected by a network statement (or by the legacy automatic shortcut), its link is operational, and the router is enabled. Two routers are modeled as neighbors only when their selected interfaces share a subnet and area and can reach one another at Layer 2. Only selected active networks are advertised.

The model propagates intra-area routes and simplified inter-area routes through a router with an active backbone-area interface. It does not use a non-backbone area as a transit path to reconnect a partitioned backbone. This is a deterministic hop-based model, not an IOS or RFC-complete OSPF implementation: interface cost, actual Hello packets, neighbor states, DR/BDR election, LSAs, authentication, route summarization, redistribution and virtual links are not simulated. Administrative distance and mixed-protocol route selection are not consistently modeled as IOS would choose them. Use a real routing stack when those details matter. vendor describes the relationship between areas and the backbone in its OSPF configuration guide.

## GUI

Open a router, select **Config → OSPF**, and enter a network/prefix and an area ID. The panel lists configured statements and modeled neighbors. It supports removing a statement, enabling the area-0 shortcut for all other interfaces, and disabling the process while retaining its statements. Use the device's CLI tab for an IOS-style process ID and commands.

## Agent and HTTP access

The following commands can be sent to `POST /api/command` or used through the `netlab` CLI:

```text
ospf R1 enable 10.0.0.0/30 area 7
ospf R1 enable 192.168.1.0/24 area 7
show ospf R1
ospf R1 remove 10.0.0.0/30
ospf R1 disable
ospf R1 enable
ospf R1 auto
ospf R1 clear
```

`enable <prefix>` replaces the automatic all-interfaces shortcut with explicit selection. If multiple configured prefixes match an address, the most-specific prefix is used. A missing area defaults to 0; area IDs accept decimal values from 0 to 4294967295 or dotted IPv4 notation. `disable` retains the statements; `enable` restores a disabled process with existing statements. `auto` enables area 0 on interfaces not covered by an explicit statement. `clear` removes the process configuration.

For compatibility, `ospf R1 enable` on a fresh router enables the original all-interfaces area-0 shortcut. In contrast, IOS `router ospf <process-id>` starts an explicit process with **no selected interfaces** until `network ... area ...` is configured. Re-entering an existing IOS process does not switch its selection mode. Only one process per router is modeled; attempting a different concurrent process returns an error. IOS network statements currently accept contiguous wildcard masks (equivalent to a CIDR prefix); non-contiguous wildcards are not supported.

`GET /api/ospf?device=R1` returns JSON including `enabled`, `process_id`, `automatic`, configured `networks` and their `area` values, selected `interfaces`, and modeled `neighbors` with local/remote interfaces, peer IP and area. An unknown or missing router returns HTTP 400. These neighbors represent the model's reachable adjacency; the API does not claim real OSPF Hello/Full state. The same data are available through `show ospf R1`. IOS-style `show ip ospf neighbor`, `show ip ospf interface`, `show ip protocols`, `show running-config`, `network ... area ...`, `no network ... area ...`, and `no router ospf <process-id>` are supported within the documented subset.

## Saved-lab compatibility

Native lab JSON now records `ospf_auto`, `ospf_areas`, and `ospf_process_id` alongside the existing `ospf_enabled` and `ospf_networks` fields. Legacy labs without these fields load with area 0 for each saved network; an enabled process with no saved networks retains the old automatic area-0 behavior. Existing explicit network statements are now **enforced**, whereas older versions recorded but ignored them, so a previously working topology can correctly lose a route if its saved statements do not cover the necessary interfaces. Review the statements in that case; the saved configuration itself is retained.

Native startup snapshots made before these fields existed receive the same compatibility defaults. vendor PKT import remains partial; when the importer encounters supported OSPF process and network statements, it now preserves their process ID and area. Unsupported configuration still follows the importer's existing warning and original-text preservation behavior.

## Verification

`tests/test_ospf_areas.py` covers network matching, area mismatch, selected advertisements, multiple links, backbone transitions, a partitioned backbone, cable/VLAN changes, deleting/restoring a trunk VLAN, interface failure, IOS process and area commands, undo, startup and legacy JSON. `tests/test_ospf_http.py` exercises the live HTTP API. `tools/check_ospf_ui.cjs` configures both routers through the GUI/API, tests ping and neighbor withdrawal, and checks undo and IOS output. All tests use isolated labs. The current suite passed 370 tests; the GUI integration and three mixed-network lab checks also passed against the rebuilt Linux executable.

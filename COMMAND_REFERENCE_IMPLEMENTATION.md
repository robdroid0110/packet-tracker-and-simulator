# Command Reference: Router through End Device (74–138)

This range contains 65 vendor help profiles, 3,713 mode entries and 307 distinct root command names. Those roots include large nested grammars. **The range is partially implemented.** Browsing all profiles does not mean that all their commands execute.

## Reference discovery

The native **Command Reference** toolbar dialog lists every profile/mode from Router-rom through PC1.0, links to the official syntax and runs commands on a selected device through the authoritative backend. Hosts use `device-config` / `host_command`; network devices use the existing stateful `ios` command. Unknown commands return errors.

`GET /api/command-reference` returns the full index; `?profile=PC1.0` (or another listed profile) selects a profile. Unknown profiles return 400. The index contains factual command names, mode labels and source links, not copied command explanations or vendor HTML. It remains available without the local vendor installation.

`python3 tools/audit_command_reference.py --reference-root PATH` regenerates the index from locally installed help. Repeated mode definitions are interned in the data file and expanded by the read API. This is a reference vocabulary audit, not an automated assertion of engine support.

## Newly working commands

- Named standard/extended ACL modes: sequence-numbered permit/deny rules, source/destination port predicates, sequence deletion and normal exit/end navigation. Rules affect real forwarding.
- Simplified IPv4 EIGRP: AS/network configuration, matching-AS neighbor discovery, hop-based routes, link-failure withdrawal and saved-state restoration. This does not implement DUAL, EIGRP packets or the vendor composite metric.
- DHCP pool mode: network, default-router, DNS server, pool removal and binding/pool inspection. Complete pool settings create actual lease pools.
- Long interface aliases such as GigabitEthernet0/0, alongside stable simulator names.
- Interface DHCP/SLAAC/DHCPv6 configuration, MTU, TX-ring, MAC, auto-MDIX and description removal.
- `do` execution retains configuration context; clear ARP/MAC/NAT operates on learned state and requires privileged EXEC.
- Additional IPv6 interface/route/neighbour, IPv4 protocol/DHCP, individual-interface and clock inspection; default gateway/DNS and static-route removal/interface routes.
- ROMMON help, environment inspection/unset, explicit boot file, configuration-register inspection and network-gated TFTP image download using ROMMON address/server/file variables.
- Host static IPv4/IPv6 configuration and interface index, release/renew, ARP deletion, alternate DNS server queries, route/NDP inspection and bounded ping options. Continuous ping creates a scheduled PDU that can be stopped using the existing PDU controls; it never blocks in an infinite host loop.
- Interactive FTP username/password/operations and SSH/Telnet login/session forwarding, in addition to the previous explicit service-client syntax.
- Supported running-config text exports preserve ACL port predicates, IPv6 addresses, descriptions, media settings, RIP and DHCP definitions. Native JSON remains the lossless format for all specialized configuration and exact DHCP allocation ranges.

Failed IOS commands restore model and parser context, rather than leaving partial changes. Physical-console and remote sessions persist named-mode context. Existing GUI CLI/Command Prompt and the reference dialog use the same engines as agents.

## Validation

324 Python tests pass, including EIGRP model and HTTP coverage. New checks prove actual ACL blocking/permit, DHCP lease issuance, interface controls, interactive FTP file transfer, ROMMON TFTP recovery, configuration replay and rollback. Isolated HTTP tests validate reference discovery/errors. Chromium checks all 65 profiles, actual command execution and existing simulation/device workflows; the active autosave hash is checked before/after. Run `tools/verify_modes_devices.py --artifacts /tmp/packet-tracker-command-reference-evidence` to reproduce browser evidence.

## Outstanding work — do not mark this range complete

BGP, full EIGRP/DUAL, HSRP, QoS queues/policies, full IPv6 dynamic protocols, IPsec/crypto, full native ASA object/NAT grammar, cellular, voice dial-plan grammar, full line/AAA authentication, all ROMMON variants and embedded JS/Python application runtimes are not implemented by this pass. Many switches/AP/security IOS command families and abbreviated/context-sensitive grammars remain incomplete. Generic root names such as `ip`, `show` and `no` have only supported subcommands, not full tree coverage.

End Device syntax is also partial: complete virtual directory management, SNMP CLI option grammar, scripting runtimes and all netsh/ISATAP commands remain outstanding. Unsupported commands must continue to fail explicitly. `HELP_COVERAGE.md` therefore keeps **74–138 Partial**; topic 139 is not the next unfinished implementation phase.

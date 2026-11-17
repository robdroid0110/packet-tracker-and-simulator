# Structured connectivity verification

Packet Tracker and Simulator provides a versioned ping result for agents and scripts. The existing GUI command prompts, IOS-like `ping`, `POST /api/command`, and `NetworkLab.ping()` still use the same forwarding engine and retain their existing human-readable output. The new API does not parse that output to determine success or failure.

## Discovery and request

- `GET /api/v1/connectivity/schema` describes request fields, statuses, failure codes and HTTP responses.
- `GET /api/capabilities` advertises `network.verify_ping` and both endpoint addresses.
- `POST /api/v1/connectivity/ping` accepts exactly `source` and `destination_ip`, both strings. Destinations must be IPv4 or IPv6 addresses; DNS names and IPv6 scope identifiers are not accepted.

```sh
curl -s http://127.0.0.1:8765/api/v1/connectivity/ping \
  -H 'content-type: application/json' \
  -d '{"source":"PC1","destination_ip":"172.16.3.20"}'
```

An example completed result is:

```json
{
  "ok": true,
  "result": {
    "version": 1,
    "operation": "ping",
    "source": "PC1",
    "destination_ip": "172.16.3.20",
    "ip_version": 4,
    "status": "success",
    "reachable": true,
    "reason": null,
    "paths": {"forward": ["PC1", "R1", "R3", "WEB"], "reply": ["WEB", "R3", "R1", "PC1"]},
    "job_id": null,
    "message": "PING success\nforward: PC1 -> R1 -> R3 -> WEB\nreply:   WEB -> R3 -> R1 -> PC1"
  }
}
```

`ok` means the verification request was accepted, not that the target was reachable. Inspect `result.status` and `result.reachable`. A completed but unsuccessful ping returns HTTP 200, `status: "failed"`, `reachable: false`, and a `reason` object. For example, a return packet blocked by a router ACL can report:

```json
{"code":"acl_out_denied","stage":"reply","device":"R1","interface":"g0/0.10"}
```

`reason.stage` identifies `source`, `target`, `forward`, or `reply`; `device`, `interface`, and `next_hop` appear when relevant. Failure codes are discoverable in the schema. The paths list routed device names in traversal order, including a repeated device if the model detects a loop. They do not claim to list all switch ports or real packets. `message` is for people; agents should use the structured fields.

Invalid request fields, addresses, or source devices return HTTP 400 with `ok: false` and `error: {"code": ..., "message": ...}`. An oversized request returns HTTP 413. Browser origin protection also applies and can reject a cross-origin request with the server's standard HTTP 403 response. This endpoint does not add authentication; keep the control plane on a trusted local interface.

## Simulation Mode

In Simulation Mode the same request returns HTTP 202 and `status: "queued"`. `reachable` and `reason` are `null`; `job_id` is the simulation PDU ID. No completed connectivity result is implied. Step, play, or advance the simulation with `POST /api/simulation/action`, then inspect:

```text
GET /api/simulation
pdus[job_id].result.output.verification
```

For a ping that reaches the forwarding engine, that field is populated when it finishes, with a version-1 `success` or `failed` result. A pending job has a null `result`. A task rejected before forwarding can instead finish with its existing error `message` and no `output.verification`; inspect the enclosing PDU status and result too. The task is evaluated against the modeled topology when dispatched, which may differ from the topology at queue time. Simulation reset can remove pending client tasks. Existing saved labs can still be loaded; newly completed ping tasks add the structured verification alongside their existing `ok` and `message` fields.

## Python and side effects

`NetworkLab.ping_detailed(source, destination_ip)` returns the same result object as the HTTP API. Like existing ping operations, it can update modeled ARP/MAC/NAT or IPv6 neighbor state and packet events. In Simulation Mode it queues a task instead. The HTTP endpoint saves these changes under the existing server lock; it does not include the complete lab in its response. Use `GET /api/state` when the complete state is needed.

The result describes Packet Tracker and Simulator's simulated forwarding, not a real ICMP probe, packet capture, timing measurement, or guarantee of vendor IOS fidelity. It does not provide typed traceroute, batch execution, external network reachability, or detailed Layer 2 hop information.

Tests: `python3 -m unittest discover -s tests -p 'test_connectivity_verification.py' -v`. GUI/agent parity can be checked with `PLAYWRIGHT_MODULE=/path/to/playwright-core node tools/check_connectivity_ui.cjs`; it uses a temporary server and an isolated copy of the campus lab. Set `PACKET_TRACKER_EXECUTABLE` to exercise a packaged Linux build.

The 2026-11-07 validation passed the full 388-test Python suite, source and packaged GUI/agent parity, the three sample-lab GUI checks, and a native Qt smoke test. A separate comparison with the preceding revision matched legacy output and modeled state across ten IPv4, IPv6, ACL, NAT, and queued-ping scenarios. These checks do not establish support for every topology or protocol.

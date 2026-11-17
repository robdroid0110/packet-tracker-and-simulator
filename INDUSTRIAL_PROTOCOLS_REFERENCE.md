# Industrial/OT implementation progress

the vendor's Industrial/OT overview describes Modbus, PROFINET, OPC UA, CIP, PRP, PTP and IEC 61850. Section 139 remains **partial**: Packet Tracker and Simulator currently has the PLC/industrial, REP, L2 NAT and PTP features described in `OPERATING_MODES_DEVICES_REFERENCE.md`, plus the Modbus and CIP subset below. PROFINET, OPC UA, PRP, IEC 61850 and their scripting APIs remain unfinished.

## Modbus TCP

Configure `service` with `service: modbus, enabled: true` on a simulated device. `modbus_send` delivers a JSON value to a named/IP server over the simulator's TCP/502 forwarding path. The server calls `modbus_receive` to remove the next message. Messages include the source device; the inbox holds at most 200 entries, each at most 8 KiB. Service state, power, links, routing and interface ACLs affect delivery. Pending messages are saved in the lab.

The simulated transport provides a bounded message exchange. It does not implement wire-format Modbus/TCP, RTU or standard function/register semantics. This follows the legacy network simulator help's documented programmable-payload scope, but does not yet include its JavaScript callbacks.

## CIP

`cip_identity` stores a device identity and enables CIP. `cip_object` creates/removes a JSON object by numeric class and instance, with up to 128 objects per device. A client uses `cip_request` with `identity`, `get` or `set` over the existing TCP/44818 forwarding model. Objects and identity persist with the lab. Individual attributes, implicit I/O, forward-open/close and the legacy network simulator script API are still pending.

## Shared UI and APIs

All five operations are available through **Device Configuration** and `POST /api/device-config/action`; `GET /api/device-config/schema` lists their fields. Examples:

```json
{"device":"PLC","action":"service","service":"modbus","enabled":true}
{"device":"Client","action":"modbus_send","server":"PLC","data":{"temperature":24}}
{"device":"PLC","action":"cip_identity","identity":{"vendor":939,"name":"Lab PLC"}}
{"device":"PLC","action":"cip_object","class_id":3000,"instance_id":1,"data":{"value":5}}
{"device":"Client","action":"cip_request","server":"PLC","operation":"get","class_id":3000,"instance_id":1}
```

In Simulation Mode, network sends/requests are queued and their results and target-device changes are published on final capture. Captured traces are available in the normal event inspector. No host sockets or user scripts are executed.

## Verification

`python3 -m unittest discover -s tests -q` passes 329 tests. New model tests cover service-disabled/disconnected failures, data transfer, object writes, atomic bad input, Simulation Mode freeze/capture and saved-lab reload. The isolated HTTP test exercises both protocols through the agent API. The Chromium harness `tools/verify_modes_devices.py` checks both operations through the native forms and confirms the active autosave bytes remain unchanged.

Other requested sections 140–181 and any previously partial command references remain tracked in `HELP_COVERAGE.md`. They must not be interpreted as completed by this change.

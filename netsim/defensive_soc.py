"""Bounded, simulated defensive telemetry. Never executes network or host actions."""
from copy import deepcopy
import math
from .model import LabError

LIMIT = 256
KINDS = {"packet", "connectivity", "scheduled", "health", "service"}
OUTCOMES = {"success", "failure"}
FIELDS = {"id", "sim_time", "kind", "protocol", "source", "destination", "outcome",
          "reason", "packet_seq", "job_id"}
GENERIC_REASON = {"modeled_operation_failed", "modeled_packet_failed", "modeled_interface_down", "modeled_service_disabled"}

def defaults():
    return {"version": 1, "next_id": 1, "dropped": 0, "logs": []}

def text(value, limit=128):
    # Store only short identifiers, never packet payloads, command text or credentials.
    return "".join(c for c in str(value or "") if c.isprintable())[:limit]

def append(lab, kind, protocol, source, destination, ok, reason=None, packet_seq=None, job_id=None):
    journal = lab.defensive_soc
    entry = {"id": journal["next_id"], "sim_time": lab.simulation["master_time"],
             "kind": kind, "protocol": text(protocol, 32), "source": text(source),
             "destination": text(destination), "outcome": "success" if ok else "failure",
             "reason": reason, "packet_seq": packet_seq, "job_id": text(job_id) if job_id else None}
    journal["next_id"] += 1
    journal["logs"].append(entry)
    if len(journal["logs"]) > LIMIT:
        journal["logs"].pop(0)
        journal["dropped"] += 1
    from .incident_cases import observe
    observe(lab,entry)

def packet(lab, event):
    append(lab, "packet", event["protocol"], event["source"], event["destination"],
           event["ok"], None if event["ok"] else "modeled_packet_failed",
           packet_seq=event["seq"], job_id=event.get("pdu"))

def reason_code(verification):
    from .connectivity import FAILURE_CODES
    reason = verification.get("reason")
    code = reason.get("code") if isinstance(reason, dict) else None
    return code if isinstance(code, str) and code in FAILURE_CODES else "modeled_operation_failed"

def connectivity(lab, result):
    if result["status"] == "queued":
        return
    ok = result["status"] == "success"
    append(lab, "connectivity", "ICMPv6" if result["ip_version"] == 6 else "ICMP",
           result["source"], result["destination_ip"], ok, None if ok else reason_code(result))

def scheduled(lab, pdu, result, event):
    if not isinstance(result, dict) or type(result.get("ok")) is not bool:
        return
    verification = result.get("output")
    verification = verification.get("verification") if isinstance(verification, dict) else None
    ok = result["ok"]
    if (isinstance(verification, dict) and isinstance(verification.get("source"), str)
            and isinstance(verification.get("destination_ip"), str)):
        protocol = "ICMPv6" if verification.get("ip_version") == 6 else "ICMP"
        source, destination = verification["source"], verification["destination_ip"]
        reason = None if ok else reason_code(verification)
    else:
        protocol = pdu["protocol"]
        source, destination = pdu["source"], pdu["destination_ip"]
        reason = None if ok else "modeled_operation_failed"
    append(lab, "scheduled", protocol, source, destination, ok, reason,
           packet_seq=event["seq"], job_id=event["pdu"])

def load(raw):
    from .connectivity import FAILURE_CODES
    if raw is None:
        return defaults()
    if not isinstance(raw, dict) or set(raw) != set(defaults()):
        raise LabError("invalid defensive SOC journal")
    if type(raw["version"]) is not int or raw["version"] != 1:
        raise LabError("invalid defensive SOC version")
    if any(type(raw[k]) is not int or not 0 <= raw[k] <= 10**15 for k in ("next_id", "dropped")):
        raise LabError("invalid defensive SOC counters")
    logs = raw["logs"]
    if not isinstance(logs, list) or len(logs) > LIMIT or raw["next_id"] != raw["dropped"] + len(logs) + 1:
        raise LabError("invalid defensive SOC retention")
    for expected, entry in enumerate(logs, raw["dropped"] + 1):
        if not isinstance(entry, dict) or set(entry) != FIELDS:
            raise LabError("invalid defensive SOC entry")
        if type(entry["id"]) is not int or entry["id"] != expected:
            raise LabError("invalid defensive SOC entry ID")
        t = entry["sim_time"]
        if type(t) not in (int, float) or not 0 <= t <= 1e12 or not math.isfinite(t):
            raise LabError("invalid defensive SOC timestamp")
        if not isinstance(entry["kind"], str) or entry["kind"] not in KINDS or not isinstance(entry["outcome"], str) or entry["outcome"] not in OUTCOMES:
            raise LabError("invalid defensive SOC classification")
        for key, limit in (("protocol",32),("source",128),("destination",128),("job_id",128)):
            value = entry[key]
            if key == "job_id" and value is None:
                continue
            if not isinstance(value, str) or value != text(value, limit):
                raise LabError("invalid defensive SOC identifier")
        reason = entry["reason"]
        if entry["outcome"] == "success":
            if reason is not None: raise LabError("invalid defensive SOC success reason")
        elif not isinstance(reason,str) or reason not in set(FAILURE_CODES) | GENERIC_REASON:
            raise LabError("invalid defensive SOC failure reason")
        seq = entry["packet_seq"]
        if seq is not None and (type(seq) is not int or not 1 <= seq <= 10**15):
            raise LabError("invalid defensive SOC packet sequence")
    return deepcopy(raw)

def view(lab, kind=None, outcome=None):
    if kind is not None and kind not in KINDS:
        raise LabError("unknown SOC event kind")
    if outcome is not None and outcome not in OUTCOMES:
        raise LabError("unknown SOC outcome")
    journal = lab.defensive_soc
    logs = [dict(e) for e in journal["logs"]
            if (kind is None or e["kind"] == kind) and (outcome is None or e["outcome"] == outcome)]
    alerts = []
    cases_by_event = {e["id"]:c for c in lab.incident_cases["cases"] for e in c["evidence"]}
    for entry in logs:
        if entry["kind"] == "packet" or entry["outcome"] != "failure":
            continue
        policy = entry["reason"] in {"acl_in_denied", "acl_out_denied", "host_firewall_denied", "ipv6_firewall_denied"}
        case = cases_by_event.get(entry["id"])
        alerts.append({"id": "A" + str(entry["id"]), "event_id": entry["id"],
                       "case_id":case["id"] if case else None,
                       "acknowledged":bool(case and case["ack_event_id"] == entry["id"]),
                       "severity": "info" if policy else "warning",
                       "category": "policy_observation" if policy else "availability_observation",
                       "title": "Modeled policy denial" if policy else "Modeled operation unsuccessful",
                       "interpretation": "Review configuration and context; this is not proof of an attack."})
    return {"ok": True, "version": 1, "evidence_type": "modeled_synthetic",
            "retention": {"limit": LIMIT, "dropped": journal["dropped"], "retained": len(journal["logs"])},
            "logs": logs, "alerts": alerts,
            "limitations": ["Simulation time, not wall-clock time.", "Alerts are derived from retained completed-operation records; packet observations alone do not raise alerts.",
                            "History follows lab save, reset and undo semantics; it is not an immutable audit log."]}

def schema():
    return {"version": 1, "read": "GET /api/cyber-range/soc",
            "filters": {"kind": sorted(KINDS), "outcome": sorted(OUTCOMES)},
            "evidence_type": "modeled_synthetic", "retention": LIMIT,
            "rules": ["Completed unsuccessful modeled operations produce review alerts.",
                      "Policy denials are informational, not evidence of compromise.",
                      "Successful operations and packet observations are logged without alerts."]}

"""Persistent defensive investigations of benign modeled connectivity observations."""
from copy import deepcopy
from .model import LabError

MAX_CASES = 24
MAX_EVIDENCE = 32
MAX_NOTES = 12
POLICY = {"acl_in_denied", "acl_out_denied", "host_firewall_denied", "ipv6_firewall_denied"}
STATUSES = {"open", "investigating", "recovered", "resolved"}
CASE_FIELDS = {"id","status","evidence","notes","ack_event_id","recovery_event_id","omitted"}
ACTIONS = {"acknowledge", "add_note", "remove_note", "verify_recovery", "resolve"}

def defaults():
    return {"version": 1, "skipped": 0, "cases": []}

def eligible(entry):
    return (entry["kind"] in {"connectivity","scheduled"} and entry["protocol"] in {"ICMP","ICMPv6"}) or (entry["kind"]=="service" and entry["protocol"]=="HTTP")

def key(entry):
    return (entry["source"], entry["destination"], entry["protocol"])

def last_failure(case):
    return next(e for e in reversed(case["evidence"]) if e["outcome"] == "failure")

def observe(lab, entry):
    if not eligible(entry):
        return
    store = lab.incident_cases
    case = next((c for c in reversed(store["cases"]) if c["status"] != "resolved"
                 and key(c["evidence"][0]) == key(entry)), None)
    if case is None:
        if entry["outcome"] != "failure" or entry["reason"] in POLICY:
            return
        if len(store["cases"]) >= MAX_CASES:
            store["skipped"] += 1
            return
        store["cases"].append({"id": "C" + str(entry["id"]), "status": "open",
                               "evidence": [deepcopy(entry)], "notes": [], "ack_event_id": None,
                               "recovery_event_id": None, "omitted": 0})
        return
    if entry["outcome"] == "success" and case["evidence"][-1]["outcome"] == "success":
        return  # One recovery candidate per failure episode is sufficient.
    if entry["outcome"] == "failure":
        case["recovery_event_id"] = None
        case["ack_event_id"] = None
        if case["status"] == "recovered":
            case["status"] = "investigating"
    case["evidence"].append(deepcopy(entry))
    if len(case["evidence"]) > MAX_EVIDENCE:
        # Preserve origin, latest failure and all evidence explicitly cited by analysts.
        pinned = {case["evidence"][0]["id"], last_failure(case)["id"], entry["id"],
                  case["ack_event_id"], case["recovery_event_id"]}
        pinned.update(n["event_id"] for n in case["notes"])
        index = next(i for i,e in enumerate(case["evidence"]) if e["id"] not in pinned)
        case["evidence"].pop(index)
        case["omitted"] += 1

def score(case):
    failure = last_failure(case)["id"]
    criteria = [
        ("acknowledged_latest_failure", 20, case["ack_event_id"] == failure),
        ("note_cites_latest_failure", 25, any(n["event_id"] == failure for n in case["notes"])),
        ("verified_later_success", 35, case["recovery_event_id"] is not None),
        ("resolved", 20, case["status"] == "resolved"),
    ]
    return {"points": sum(points for _,points,done in criteria if done), "maximum": 100,
            "criteria": [{"id": name,"points": points,"met": done} for name,points,done in criteria],
            "scope": "Workflow completion only; note accuracy and actual incident attribution are not graded."}

def view(lab):
    store = lab.incident_cases
    return {"ok": True, "version": 1, "evidence_type": "modeled_synthetic", "skipped": store["skipped"],
            "cases": [{**deepcopy(c), "score": score(c)} for c in store["cases"]],
            "limitations": ["Same modeled source, destination and protocol is a correlation heuristic, not root-cause attribution.",
                            "Cases and evidence follow lab save/reset/undo semantics; not an immutable audit trail.",
                            "Case capacity is bounded; additional new cases are counted as skipped."]}

def schema():
    return {"version": 1, "read": "GET /api/cyber-range/incidents",
            "write": "POST /api/cyber-range/incidents/action", "actions": sorted(ACTIONS),
            "fields": {"case_id":"C-prefixed case identifier", "event_id":"required for acknowledge, add_note, remove_note, verify_recovery",
                       "note":"required for add_note; 1-500 printable characters"},
            "statuses": sorted(STATUSES), "limits": {"cases":MAX_CASES,"evidence":MAX_EVIDENCE,"notes":MAX_NOTES},
            "correlation": "Completed ICMP/ICMPv6 checks or explicit modeled HTTP service observations sharing source, destination and protocol; policy-only denials do not open cases.",
            "recovery": "Explicit verification of the recorded successful observation after the latest failed check."}

def valid_note(value):
    return isinstance(value,str) and 1 <= len(value) <= 500 and value.strip() == value and bool(value) and all(c.isprintable() for c in value)

def action(lab, body):
    op = body.get("action")
    if not isinstance(op,str) or op not in ACTIONS:
        raise LabError("unknown incident action")
    fields = {"action","case_id"} | ({"event_id"} if op != "resolve" else set()) | ({"note"} if op == "add_note" else set())
    if set(body) != fields or not isinstance(body["case_id"],str):
        raise LabError("invalid incident action fields")
    case = next((c for c in lab.incident_cases["cases"] if c["id"] == body["case_id"]),None)
    if case is None: raise LabError("unknown incident case")
    if case["status"] == "resolved": raise LabError("resolved case is read-only")
    failure = last_failure(case)["id"]
    if op != "resolve":
        event_id = body["event_id"]
        if type(event_id) is not int or not any(e["id"] == event_id for e in case["evidence"]):
            raise LabError("event is not retained in this case")
    if op == "acknowledge":
        if event_id != failure: raise LabError("acknowledge the latest failure")
        case["ack_event_id"] = event_id
        if case["status"] == "open": case["status"] = "investigating"
    elif op == "add_note":
        note = body["note"]
        if not valid_note(note): raise LabError("note must be 1-500 printable characters without surrounding whitespace")
        existing = next((n for n in case["notes"] if n["event_id"] == event_id),None)
        if existing is not None:
            existing["text"] = note
        else:
            if len(case["notes"]) >= MAX_NOTES: raise LabError("case note limit reached; remove an older note first")
            case["notes"].append({"event_id":event_id,"text":note})
        if case["status"] == "open": case["status"] = "investigating"
    elif op == "remove_note":
        existing = next((n for n in case["notes"] if n["event_id"] == event_id),None)
        if existing is None: raise LabError("no note for this event")
        case["notes"].remove(existing)
    elif op == "verify_recovery":
        latest = case["evidence"][-1]
        if latest["id"] != event_id or latest["outcome"] != "success" or event_id <= failure:
            raise LabError("recovery requires the latest successful observation after the last failure")
        case["recovery_event_id"] = event_id
        case["status"] = "recovered"
    else:
        if case["status"] != "recovered" or case["ack_event_id"] != failure or not any(n["event_id"] == failure for n in case["notes"]):
            raise LabError("resolve requires acknowledgement, a note citing the latest failure, and verified recovery")
        case["status"] = "resolved"
    return {"case_id":case["id"],"status":case["status"],"score":score(case)}

def load(raw, journal):
    from .defensive_soc import load as validate_journal
    if raw is None: return defaults()
    if not isinstance(raw,dict) or set(raw) != set(defaults()) or type(raw["version"]) is not int or raw["version"] != 1:
        raise LabError("invalid incident store")
    if type(raw["skipped"]) is not int or not 0 <= raw["skipped"] <= 10**15:
        raise LabError("invalid incident skipped count")
    cases = raw["cases"]
    if not isinstance(cases,list) or len(cases)>MAX_CASES: raise LabError("invalid incident case count")
    retained = {e["id"]:e for e in journal["logs"]}
    used = set()
    active = set()
    previous = 0
    for c in cases:
        if not isinstance(c,dict) or set(c) != CASE_FIELDS or not isinstance(c["status"],str) or c["status"] not in STATUSES:
            raise LabError("invalid incident case")
        evidence = c["evidence"]
        if not isinstance(evidence,list) or not 1 <= len(evidence) <= MAX_EVIDENCE:
            raise LabError("invalid incident evidence count")
        last = 0
        for e in evidence:
            if not isinstance(e,dict) or type(e.get("id")) is not int or not last < e["id"] < journal["next_id"] or e["id"] in used:
                raise LabError("invalid incident event reference")
            ident = e["id"]
            validate_journal({"version":1,"next_id":ident+1,"dropped":ident-1,"logs":[e]})
            if not eligible(e) or key(e) != key(evidence[0]) or (ident in retained and e != retained[ident]):
                raise LabError("incident evidence does not match journal or case")
            last = ident; used.add(ident)
        first = evidence[0]
        if first["id"] <= previous or c["id"] != "C"+str(first["id"]) or first["outcome"] != "failure" or first["reason"] in POLICY:
            raise LabError("invalid incident origin")
        previous = first["id"]
        if c["status"] != "resolved":
            if key(first) in active: raise LabError("duplicate active incident")
            active.add(key(first))
        if type(c["omitted"]) is not int or not 0 <= c["omitted"] <= 10**15: raise LabError("invalid incident retention")
        ids = {e["id"] for e in evidence}
        notes = c["notes"]
        if not isinstance(notes,list) or len(notes)>MAX_NOTES: raise LabError("invalid incident notes")
        for n in notes:
            if not isinstance(n,dict) or set(n)!={"event_id","text"} or type(n["event_id"]) is not int or n["event_id"] not in ids or not valid_note(n["text"]):
                raise LabError("invalid incident note")
        if len({n["event_id"] for n in notes}) != len(notes): raise LabError("duplicate incident notes")
        failure = last_failure(c)["id"]
        ack, recovery = c["ack_event_id"], c["recovery_event_id"]
        if ack is not None and (type(ack) is not int or ack != failure): raise LabError("invalid incident acknowledgement")
        if recovery is not None and (type(recovery) is not int or recovery != evidence[-1]["id"] or evidence[-1]["outcome"] != "success" or recovery <= failure):
            raise LabError("invalid incident recovery")
        if (c["status"] in {"recovered","resolved"}) != (recovery is not None):
            raise LabError("invalid incident recovery status")
        if c["status"] == "open" and (ack is not None or notes): raise LabError("invalid open incident")
        if c["status"] == "resolved" and (ack != failure or not any(n["event_id"] == failure for n in notes)):
            raise LabError("invalid resolved incident")
    return deepcopy(raw)

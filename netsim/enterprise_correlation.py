"""Dependency-specific correlation of private enterprise DNS availability observations."""
from copy import deepcopy
from .model import LabError

PHASES=("baseline","fault","recovery","recovery_5s","recovery_10s")
RECOVERY=PHASES[2:]
KINDS=("dns","named_http","direct_http","app_icmp")

def event(row,kind):
    return row[kind]["event"] if kind in ("named_http","direct_http") else row[kind]

def require(condition,message):
    if not condition:raise LabError(message)

def indexed(inventory,phase):
    expected={c["device"]:c["department"] for c in inventory["clients"]}
    rows=phase["clients"]
    require(bool(expected) and len(rows)==len(expected),"incomplete enterprise client observations")
    result={r["client"]:r for r in rows}
    require(set(result)==set(expected),"missing or duplicate enterprise client observations")
    require(all(r["department"]==expected[name] for name,r in result.items()),"client department mismatch")
    return result

def correlation(inventory,checks,cases,run_id,stage):
    if "fault" not in checks:return None
    rows={p:indexed(inventory,checks[p]) for p in PHASES if p in checks}
    baseline,fault=rows["baseline"],rows["fault"]
    component=checks["fault"]["component"]
    require(component["source"]==inventory["dns"]["device"] and component["destination"]=="eth0"
            and component["outcome"]=="failure" and component["reason"]=="modeled_interface_down",
            "shared DNS fault evidence is missing")
    require(checks["baseline"]["component"]["outcome"]=="success","healthy dependency baseline required")
    # Reject mislabeled, reused or out-of-order evidence rather than count it as coverage.
    seen=set();previous=0
    expected_targets={"dns":inventory["hostname"],"named_http":inventory["hostname"],
                      "direct_http":inventory["app"]["ip"],"app_icmp":inventory["app"]["ip"]}
    for phase,clients in rows.items():
        root=checks[phase]["component"]
        require(checks[phase]["phase"]==phase and root["source"]==inventory["dns"]["device"]
                and root["destination"]=="eth0" and root["protocol"]=="LINK", "invalid dependency sample identity")
        phase_events=[root]
        for name,row in clients.items():
            for kind in KINDS:
                e=event(row,kind)
                require(e["source"]==name and e["destination"]==expected_targets[kind],"incorrect client evidence identity")
                phase_events.append(e)
        ids=[e["id"] for e in phase_events]
        require(all(type(i) is int and i>previous for i in ids) and len(set(ids))==len(ids) and not seen.intersection(ids),"reused or stale enterprise event IDs")
        seen.update(ids);previous=max(ids)
    parent_id="P-"+run_id
    children=[];linked=set()
    for name,b in baseline.items():
        f=fault[name]
        if not (all(event(b,k)["outcome"]=="success" for k in KINDS)
                and event(f,"dns")["outcome"]==event(f,"named_http")["outcome"]=="failure"
                and event(f,"direct_http")["outcome"]==event(f,"app_icmp")["outcome"]=="success"):
            continue
        failure=event(f,"named_http")
        matches=[c for c in cases if c["evidence"] and c["evidence"][0]==failure]
        require(len(matches)==1,"affected client must have exactly one matching service case")
        case=matches[0]
        require(case["id"] not in linked,"duplicate child incident")
        linked.add(case["id"])
        snapshots={p:deepcopy(r[name]) for p,r in rows.items()}
        samples=[]
        for p in RECOVERY:
            if p not in snapshots:continue
            r=snapshots[p]
            events=[event(r,k) for k in KINDS]
            healthy=checks[p]["component"]["outcome"]=="success" and all(
                e["source"]==name and e["outcome"]=="success" and e["id"]>failure["id"] for e in events
            ) and r["resolved_ip"]==inventory["app"]["ip"] and r["named_http"]["http_status"]==r["direct_http"]["http_status"]==200
            samples.append({"phase":p,"healthy":healthy,"event_ids":[e["id"] for e in events]})
        verified=len(samples)==len(RECOVERY) and all(s["healthy"] for s in samples)
        if verified:
            first=event(snapshots["recovery"],"named_http")
            require(any(e==first for e in case["evidence"]),"child recovery evidence is missing")
        children.append({"case_id":case["id"],"parent_id":parent_id,"client":name,"department":f["department"],
                         "failure_event_id":failure["id"],"recovery_verified":verified,
                         "recovery_samples":samples,"evidence":snapshots})
    require(bool(children),"no correlated clients for the shared dependency fault")
    require(len(children)==len(baseline),"not all affected clients have complete fault evidence")
    require(linked=={c["id"] for c in cases},"unexpected uncorrelated service case")
    samples=[checks[p]["component"] for p in RECOVERY if p in checks]
    span=round(samples[-1]["sim_time"]-samples[0]["sim_time"],6) if samples else 0
    verified=len(samples)==3 and span>=10 and all(c["recovery_verified"] for c in children)
    status="open"
    if "recovery" in checks:status="recovering"
    if stage in ("recovery_verified","completed"):
        require(verified,"cannot verify or close parent: every affected client needs three healthy recovery samples")
        status="closed" if stage=="completed" else "recovery_verified"
    return {"id":parent_id,"status":status,"dependency":"DNS-SERVER:eth0","category":"modeled_availability",
            "fault_event_id":component["id"],"dependency_evidence":{p:deepcopy(checks[p]["component"]) for p in rows},
            "child_case_ids":[c["case_id"] for c in children],"children":children,
            "affected_clients":len(children),"verified_clients":sum(c["recovery_verified"] for c in children),
            "recovery_span_simulated_seconds":span,"closure_ready":verified,
            "interpretation":"Shared modeled DNS dependency outage supported by failed DNS/named HTTP checks and healthy direct application controls.",
            "limitations":"Correlation is scoped to this fixed synthetic dependency; child cases are recovery-verified, not analyst-acknowledged or individually resolved."}

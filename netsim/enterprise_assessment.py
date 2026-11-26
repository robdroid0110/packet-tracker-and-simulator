"""Structured analyst assessment for the modeled enterprise DNS availability lab."""
from copy import deepcopy
from .model import LabError
from .incident_cases import valid_note

FLOW=("inject_fault","acknowledge","assess","restore","verify_recovery","resolve")
STAGES=("baseline_verified","fault_observed","acknowledged","assessed","restored","recovery_verified","completed")
DIAGNOSES={"dns_interface_down":"Shared DNS server interface unavailable",
           "app_service_down":"Application service unavailable",
           "routing_failure":"Application routing unavailable",
           "insufficient_evidence":"Insufficient evidence"}
FIELDS={"inject_fault":{"action"},"acknowledge":{"action","event_id"},
        "assess":{"action","diagnosis","root_refs","impact_clients","impact_departments","impact_refs","note","note_event_id"},
        "restore":{"action"},"verify_recovery":{"action"},
        "resolve":{"action","dependency_event_id","recovery_refs"}}

def require(ok,message):
    if not ok:raise LabError(message)

def event_id(value):
    require(type(value) is int and value>0,"positive integer evidence ID required")
    return value

def names(values,allowed):
    require(isinstance(values,list) and len(values)<=len(allowed) and all(isinstance(v,str) and v in allowed for v in values),"invalid impact selection")
    require(len(set(values))==len(values),"duplicate impact selection")
    return set(values)

def rowmap(checks,phase):
    return {r["client"]:r for r in checks[phase]["clients"]}

def evidence(checks,phases):
    ids=set()
    for p in phases:
        c=checks[p];ids.add(c["component"]["id"])
        for r in c["clients"]:
            ids.update((r["dns"]["id"],r["named_http"]["event"]["id"],r["direct_http"]["event"]["id"],r["app_icmp"]["id"]))
    return ids

def refs(value,keys,allowed):
    require(isinstance(value,dict) and set(value)==set(keys),"incorrect evidence reference fields")
    require(all(event_id(v) in allowed for v in value.values()),"evidence ID is not from the required phases")

def evaluate(cfg,steps):
    from .enterprise_training import replay
    require(isinstance(steps,list) and len(steps)<=len(FLOW),"invalid analyst history")
    for op,step in zip(FLOW,steps):
        require(isinstance(step,dict) and step.get("action")==op and set(step)==FIELDS[op],"invalid analyst action or stage")
    sim=[s["action"] if s["action"]!="resolve" else "complete" for s in steps if s["action"] in {"inject_fault","restore","verify_recovery","resolve"}]
    lab,inventory,checks=replay(cfg,sim)
    by={s["action"]:s for s in steps}
    if "acknowledge" in by:
        require(event_id(by["acknowledge"]["event_id"])==checks["fault"]["component"]["id"],"acknowledge the shared fault event")
    if "assess" in by:
        a=by["assess"];allowed=evidence(checks,("baseline","fault"))
        require(isinstance(a["diagnosis"],str) and a["diagnosis"] in DIAGNOSES,"unknown diagnosis")
        clients={c["device"] for c in inventory["clients"]};departments={c["department"] for c in inventory["clients"]}
        selected=names(a["impact_clients"],clients);names(a["impact_departments"],departments)
        refs(a["root_refs"],("component","dns","direct_http"),allowed)
        ir=a["impact_refs"]
        require(isinstance(ir,dict) and set(ir)==selected,"cite baseline and failure for every selected client")
        for r in ir.values():refs(r,("baseline","fault"),allowed)
        require(valid_note(a["note"]),"note must contain 1-500 printable characters")
        require(event_id(a["note_event_id"]) in allowed,"note evidence must belong to baseline or fault")
    if "resolve" in by:
        a=by["resolve"];latest=checks["recovery_10s"];rows=rowmap(checks,"recovery_10s")
        require(event_id(a["dependency_event_id"])==latest["component"]["id"],"cite latest dependency recovery")
        rr=a["recovery_refs"]
        require(isinstance(rr,dict) and set(rr)==set(rows),"resolution requires every affected client")
        allowed=evidence(checks,("recovery_10s",))
        for name,r in rows.items():
            refs(rr[name],("dns","http"),allowed)
            require(rr[name]=={"dns":r["dns"]["id"],"http":r["named_http"]["event"]["id"]},"cite current DNS and HTTP recovery for each client")
    return lab,inventory,checks

def assessment(steps,inventory,checks):
    by={s["action"]:s for s in steps};a=by.get("assess")
    rows=[]
    def criterion(name,points,met):rows.append({"id":name,"points":points,"met":bool(met)})
    criterion("parent_acknowledged",10,"acknowledge" in by)
    component=contrast=diagnosis=impact_clients=impact_departments=impact_evidence=note=False
    if a:
        f=rowmap(checks,"fault");b=rowmap(checks,"baseline");r=a["root_refs"]
        component=r["component"]==checks["fault"]["component"]["id"]
        contrast=any(r["dns"]==x["dns"]["id"] and r["direct_http"]==x["direct_http"]["event"]["id"] for x in f.values())
        diagnosis=a["diagnosis"]=="dns_interface_down" and component and contrast
        impact_clients=set(a["impact_clients"])==set(f)
        impact_departments=set(a["impact_departments"])=={x["department"] for x in f.values()}
        impact_evidence=impact_clients and all(a["impact_refs"][name]=={"baseline":b[name]["named_http"]["event"]["id"],"fault":f[name]["named_http"]["event"]["id"]} for name in f)
        note=a["note_event_id"] in {checks["fault"]["component"]["id"],*(x["named_http"]["event"]["id"] for x in f.values()),*(x["dns"]["id"] for x in f.values())}
    criterion("shared_component_evidence",10,component)
    criterion("dns_failure_and_healthy_app_control",15,contrast)
    criterion("evidence_supported_root_cause",15,diagnosis)
    criterion("affected_client_set",10,impact_clients)
    criterion("affected_department_set",10,impact_departments)
    criterion("per_client_impact_evidence",10,impact_evidence)
    criterion("note_cites_fault_evidence",5,note)
    criterion("all_client_recovery_verified",10,"verify_recovery" in by)
    criterion("explicit_evidence_linked_resolution",5,"resolve" in by)
    return {"acknowledgement":deepcopy(by.get("acknowledge")),"assessment":deepcopy(a),"resolution":deepcopy(by.get("resolve")),
            "score":{"points":sum(r["points"] for r in rows if r["met"]),"maximum":100,"criteria":rows,
                     "scope":"Structured diagnosis, observed client/department availability impact and evidence citations; free-text correctness and financial impact are not graded."}}

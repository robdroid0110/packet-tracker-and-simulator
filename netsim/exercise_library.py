"""Version 2 benign availability templates, evaluated only on a private model."""
from copy import deepcopy
from .model import LabError
from . import defensive_soc as soc, incident_cases as incidents
from .device_services import service
from .simulation import advance

TEMPLATES = {
    "interface-availability": {"title":"Client connectivity outage","difficulty":"foundation","diagnosis":"client_interface_down","component":"CLIENT"},
    "server-interface-availability": {"title":"Server connectivity outage","difficulty":"foundation","diagnosis":"server_interface_down","component":"APP"},
    "http-availability": {"title":"HTTP service unavailable","difficulty":"intermediate","diagnosis":"application_only","component":"APP"},
}
DIAGNOSES = {"client_interface_down":"Client interface administratively down",
             "server_interface_down":"Server interface administratively down",
             "application_only":"Application-only outage",
             "insufficient_evidence":"Insufficient evidence"}
ROLES = {"baseline_icmp":"Baseline connectivity","baseline_http":"Baseline HTTP",
         "fault_icmp":"Connectivity during fault","fault_http":"HTTP during fault",
         "component_state":"Component state during fault"}
FLOW = ("inject_fault","acknowledge","assess","restore","monitor_recovery","verify_recovery","complete")
STAGES = ("baseline_verified","fault_observed","acknowledged","assessed","restored",
          "recovery_monitored","recovery_verified","completed")
RECOVERY_PHASES = ("recovery","recovery_5s","recovery_10s")

def check(lab, template, phase, healthy):
    from .exercise_runner import SOURCE,TARGET
    spec=TEMPLATES[template]
    app_only=template=="http-availability"
    component=spec["component"]
    enabled=service(lab.devices[component],"http")["enabled"] if app_only else lab.devices[component].interfaces["eth0"].admin_up
    soc.append(lab,"health","SERVICE" if app_only else "LINK",component,"http" if app_only else "eth0",enabled,
               None if enabled else "modeled_service_disabled" if app_only else "modeled_interface_down")
    component_event=deepcopy(lab.defensive_soc["logs"][-1])
    ping=lab.ping_detailed(SOURCE,TARGET)
    icmp=deepcopy(lab.defensive_soc["logs"][-1])
    status=None
    try:
        response=lab.http_request(SOURCE,"http://"+TARGET+"/")
        status=response["status"]
        available=response["ok"] is True and status==200
    except LabError:
        available=False
    soc.append(lab,"service" if app_only else "health","HTTP",SOURCE,TARGET,available,
               None if available else "modeled_operation_failed")
    http=deepcopy(lab.defensive_soc["logs"][-1])
    if (enabled,ping["reachable"],available)!=(healthy,healthy or app_only,healthy):
        raise LabError("exercise observations did not match the modeled availability state")
    return {"phase":phase,"component":component_event,"icmp":icmp,"http":http,"http_status":status}

def primary(template, checks, phase):
    return checks[phase]["http" if template=="http-availability" else "icmp"]

def set_available(lab,template,enabled):
    if template=="http-availability":
        lab.http_service("APP",enabled)
    else:
        lab.set_interface_state(TEMPLATES[template]["component"],"eth0",enabled)

def replay(template,steps):
    from .exercise_runner import topology,event_id,STEP_FIELDS
    if not isinstance(template,str) or template not in TEMPLATES or not isinstance(steps,list) or len(steps)>len(FLOW):
        raise LabError("invalid library exercise history")
    lab=topology()
    checks={"baseline":check(lab,template,"baseline",True)}
    assessment=None
    for op,step in zip(FLOW,steps):
        expected=({"action"} if op=="monitor_recovery" else STEP_FIELDS[op])
        if not isinstance(step,dict) or step.get("action")!=op or set(step)!=expected:
            raise LabError("invalid exercise action or stage")
        if op=="inject_fault":
            set_available(lab,template,False)
            checks["fault"]=check(lab,template,"fault",False)
        elif op=="acknowledge":
            failure=primary(template,checks,"fault")["id"]
            if event_id(step["event_id"])!=failure:raise LabError("acknowledge the primary failed observation")
            incidents.action(lab,{"action":"acknowledge","case_id":lab.incident_cases["cases"][0]["id"],"event_id":failure})
        elif op=="assess":
            refs=step["references"]
            if not isinstance(step["diagnosis"],str) or step["diagnosis"] not in DIAGNOSES:
                raise LabError("unknown exercise diagnosis")
            if not isinstance(refs,dict) or set(refs)!=set(ROLES):raise LabError("all five evidence roles are required")
            available={checks[p][k]["id"] for p in ("baseline","fault") for k in ("component","icmp","http")}
            if any(event_id(v) not in available for v in refs.values()):raise LabError("assessment references must belong to this attempt")
            if not incidents.valid_note(step["note"]):raise LabError("invalid assessment note")
            assessment={k:deepcopy(step[k]) for k in ("diagnosis","references","note")}
            incidents.action(lab,{"action":"add_note","case_id":lab.incident_cases["cases"][0]["id"],
                                   "event_id":primary(template,checks,"fault")["id"],"note":step["note"]})
        elif op=="restore":
            set_available(lab,template,True)
            checks["recovery"]=check(lab,template,"recovery",True)
        elif op=="monitor_recovery":
            origin=checks["recovery"]["component"]["sim_time"]
            for offset,phase in ((5,"recovery_5s"),(10,"recovery_10s")):
                advance(lab,max(0,origin+offset-lab.simulation["master_time"]))
                checks[phase]=check(lab,template,phase,True)
        elif op=="verify_recovery":
            latest=checks["recovery_10s"]
            if event_id(step["icmp_event_id"])!=latest["icmp"]["id"] or event_id(step["http_event_id"])!=latest["http"]["id"]:
                raise LabError("verification requires both latest monitoring observations")
            # Incident engine retains the first successful operation per failure episode.
            incidents.action(lab,{"action":"verify_recovery","case_id":lab.incident_cases["cases"][0]["id"],
                                   "event_id":primary(template,checks,"recovery")["id"]})
        elif op=="complete":
            incidents.action(lab,{"action":"resolve","case_id":lab.incident_cases["cases"][0]["id"]})
    return lab,checks,assessment

def rubric(template,steps,checks,assessment):
    refs=assessment["references"] if assessment else {}
    def cited(role,phase,kind):
        return phase in checks and refs.get(role)==checks[phase][kind]["id"]
    baseline=cited("baseline_icmp","baseline","icmp") and cited("baseline_http","baseline","http")
    fault=cited("fault_icmp","fault","icmp") and cited("fault_http","fault","http")
    component=cited("component_state","fault","component")
    diagnosis=bool(assessment and assessment["diagnosis"]==TEMPLATES[template]["diagnosis"] and component and fault)
    rows=[("baseline_evidence",10,baseline),("fault_connectivity_and_http_evidence",20,fault),
          ("component_state_evidence",15,component),("evidence_backed_diagnosis",20,diagnosis),
          ("acknowledged_incident",10,len(steps)>=2),("verified_sampled_recovery",20,len(steps)>=6),
          ("resolved_and_completed",5,len(steps)==len(FLOW))]
    return {"points":sum(p for _,p,met in rows if met),"maximum":100,
            "criteria":[{"id":name,"points":p,"met":met} for name,p,met in rows],
            "scope":"Structured evidence and diagnosis; free-text note accuracy is not graded."}

def monitoring(checks):
    samples=[{"phase":p,"time":checks[p]["component"]["sim_time"],
              "icmp_event_id":checks[p]["icmp"]["id"],"http_event_id":checks[p]["http"]["id"],
              "healthy":all(checks[p][k]["outcome"]=="success" for k in ("component","icmp","http"))}
             for p in RECOVERY_PHASES if p in checks]
    span=round(samples[-1]["time"]-samples[0]["time"],6) if samples else 0
    return {"samples":samples,"span_simulated_seconds":span,"required_samples":3,
            "passed":len(samples)==3 and span>=10 and all(s["healthy"] for s in samples),
            "scope":"Discrete simulated checks, not continuous monitoring or a real SLA."}

"""Configurable private enterprise availability exercise; all operations are modeled.

A fixed fault is applied only to a newly constructed NetworkLab. No external
network access, host interface changes, or real services are performed.
"""
from copy import deepcopy
import json
import re
import uuid
from .model import NetworkLab, LabError
from . import defensive_soc as soc, incident_cases as incidents
from .simulation import advance
from .enterprise_correlation import correlation
from . import enterprise_assessment as analyst
from . import enterprise_resilience as resilience

VERSION=1
DEPARTMENTS=("IT","FINANCE","OPERATIONS")
HOSTNAME="portal.example.test"
FLOW=("inject_fault","restore","verify_recovery","complete")
STAGES=("baseline_verified","fault_observed","restored","recovery_verified","completed")
RECOVERY_PHASES=("recovery","recovery_5s","recovery_10s")

def config(raw):
    if not isinstance(raw,dict) or set(raw)!={"departments","hosts_per_department"}:
        raise LabError("enterprise configuration requires departments and hosts_per_department")
    d,h=raw["departments"],raw["hosts_per_department"]
    if type(d) is not int or not 2<=d<=3 or type(h) is not int or not 1<=h<=2:
        raise LabError("departments must be 2-3; hosts per department must be 1-2")
    return {"departments":d,"hosts_per_department":h}

def build(raw):
    cfg=config(raw);lab=NetworkLab()
    names=DEPARTMENTS[:cfg["departments"]]
    lab.add_device("router","CORE",420,45)
    clients=[];segments=[]
    for i,zone in enumerate((*names,"SERVICES")):
        prefix="10.77."+str(i+1);switch=zone+"-SW";x=60+i*260
        lab.add_device("switch",switch,x+65,175)
        lab.connect("CORE","g0/"+str(i),switch,"g0/1")
        lab.set_ip("CORE","g0/"+str(i),prefix+".1/24")
        members=[]
        for j in range(2 if zone=="SERVICES" else cfg["hosts_per_department"]):
            device=("APP-SERVER","DNS-SERVER")[j] if zone=="SERVICES" else zone+"-PC"+str(j+1)
            ip=prefix+"."+str(j+10)
            lab.add_device("server" if zone=="SERVICES" else "pc",device,x+j*110,290)
            lab.connect(switch,"fa0/"+str(j+1),device,"eth0")
            lab.set_ip(device,"eth0",ip+"/24");lab.set_gateway(device,prefix+".1")
            members.append({"device":device,"ip":ip})
            if zone!="SERVICES":clients.append({"device":device,"department":zone,"ip":ip})
        segments.append({"name":zone,"network":prefix+".0/24","gateway":prefix+".1","members":members})
    app,dns=segments[-1]["members"]
    lab.dns_service(dns["device"],True);lab.dns_record(dns["device"],HOSTNAME,app["ip"])
    lab.http_service(app["device"],True)
    for client in clients:lab.set_dns_client(client["device"],dns["ip"])
    inventory={"segments":segments,"clients":clients,"app":app,"dns":dns,
               "dependencies":[{"consumer":c["device"],"requires":"portal_by_name"} for c in clients]+[
                   {"consumer":"portal_by_name","requires":"dns_resolution"},
                   {"consumer":"portal_by_name","requires":"app_http"},
                   {"consumer":"dns_resolution","requires":"DNS-SERVER:eth0"},
                   {"consumer":"app_http","requires":"APP-SERVER:eth0"}],
               "hostname":HOSTNAME}
    return lab,inventory

def record(lab,kind,protocol,source,destination,ok,reason):
    soc.append(lab,kind,protocol,source,destination,ok,None if ok else reason)
    return deepcopy(lab.defensive_soc["logs"][-1])

def http(lab,source,target,kind):
    status=None
    try:
        response=lab.http_request(source,"http://"+target+"/")
        status=response["status"];ok=response["ok"] is True and status==200
    except LabError:
        ok=False
    return {"event":record(lab,kind,"HTTP",source,target,ok,"modeled_operation_failed"),"http_status":status}

def check(lab,inventory,phase,expect_dns):
    dns=inventory["dns"];app=inventory["app"]
    up=lab.devices[dns["device"]].interfaces["eth0"].admin_up
    component=record(lab,"health","LINK",dns["device"],"eth0",up,"modeled_interface_down")
    observations=[]
    for client in inventory["clients"]:
        source=client["device"]
        try:resolved=lab.resolve_dns(source,HOSTNAME)
        except LabError:resolved=None
        dns_ok=resolved==app["ip"]
        dns_event=record(lab,"health","DNS",source,HOSTNAME,dns_ok,"modeled_operation_failed")
        named=http(lab,source,HOSTNAME,"service")
        direct=http(lab,source,app["ip"],"health")
        ping=lab.ping_detailed(source,app["ip"])
        connectivity=deepcopy(lab.defensive_soc["logs"][-1])
        actual=(up,dns_ok,named["event"]["outcome"]=="success",direct["event"]["outcome"]=="success",ping["reachable"])
        if actual!=(expect_dns,expect_dns,expect_dns,True,True):
            raise LabError("enterprise availability checks did not match the modeled fault")
        observations.append({"client":source,"department":client["department"],"dns":dns_event,
                             "resolved_ip":resolved,"named_http":named,"direct_http":direct,"app_icmp":connectivity})
    return {"phase":phase,"component":component,"clients":observations}

def impact(checks):
    if "fault" not in checks:return None
    base={x["client"]:x for x in checks["baseline"]["clients"]}
    affected=[x for x in checks["fault"]["clients"] if base[x["client"]]["named_http"]["event"]["outcome"]=="success"
              and x["named_http"]["event"]["outcome"]=="failure"]
    recovered={x["client"] for x in checks.get("recovery",{}).get("clients",[])
               if x["named_http"]["event"]["outcome"]=="success"}
    return {"affected_clients":[x["client"] for x in affected],
            "affected_departments":sorted({x["department"] for x in affected}),
            "total_clients":len(base),"affected_count":len(affected),
            "dependency_fault_event_id":checks["fault"]["component"]["id"],
            "dependency_recovery_event_id":checks["recovery"]["component"]["id"] if "recovery" in checks else None,
            "app_ip_controls_healthy":all(x["direct_http"]["event"]["outcome"]=="success" and x["app_icmp"]["outcome"]=="success" for x in checks["fault"]["clients"]),
            "recovered_clients":[x["client"] for x in affected if x["client"] in recovered],
            "evidence":[{"client":x["client"],"baseline_id":base[x["client"]]["named_http"]["event"]["id"],
                         "dns_failure_id":x["dns"]["id"],"portal_failure_id":x["named_http"]["event"]["id"],
                         "direct_http_control_id":x["direct_http"]["event"]["id"],"icmp_control_id":x["app_icmp"]["id"]}
                        for x in affected],
            "interpretation":"Observed dependency failure, not evidence of an attack or enforced security segmentation."}

def monitoring(checks):
    samples=[]
    for p in RECOVERY_PHASES:
        if p not in checks:continue
        c=checks[p]
        samples.append({"phase":p,"sim_time":c["component"]["sim_time"],
                        "healthy":c["component"]["outcome"]=="success" and all(
                            x["dns"]["outcome"]==x["named_http"]["event"]["outcome"]==x["direct_http"]["event"]["outcome"]==x["app_icmp"]["outcome"]=="success"
                            for x in c["clients"])})
    span=round(samples[-1]["sim_time"]-samples[0]["sim_time"],6) if samples else 0
    return {"samples":samples,"span_simulated_seconds":span,
            "passed":len(samples)==3 and span>=10 and all(s["healthy"] for s in samples)}

def replay(cfg,steps):
    if not isinstance(steps,list) or len(steps)>len(FLOW) or any(type(s) is not str for s in steps) or tuple(steps)!=FLOW[:len(steps)]:
        raise LabError("invalid enterprise exercise lifecycle")
    lab,inventory=build(cfg);checks={"baseline":check(lab,inventory,"baseline",True)}
    for step in steps:
        if step=="inject_fault":
            lab.set_interface_state("DNS-SERVER","eth0",False)
            checks["fault"]=check(lab,inventory,"fault",False)
        elif step=="restore":
            lab.set_interface_state("DNS-SERVER","eth0",True)
            checks["recovery"]=check(lab,inventory,"recovery",True)
        elif step=="verify_recovery":
            origin=checks["recovery"]["component"]["sim_time"]
            for offset,phase in ((5,"recovery_5s"),(10,"recovery_10s")):
                advance(lab,max(0,origin+offset-lab.simulation["master_time"]))
                checks[phase]=check(lab,inventory,phase,True)
            if not monitoring(checks)["passed"]:raise LabError("enterprise recovery checks incomplete")
            parent=correlation(inventory,checks,lab.incident_cases["cases"],"replay","recovery_verified")
            for child in parent["children"]:
                incidents.action(lab,{"action":"verify_recovery","case_id":child["case_id"],
                    "event_id":child["evidence"]["recovery"]["named_http"]["event"]["id"]})
        elif step=="complete":
            if not monitoring(checks)["passed"]:raise LabError("verify recovery before completion")
            correlation(inventory,checks,lab.incident_cases["cases"],"replay","completed")
            if any(c["status"]!="recovered" for c in lab.incident_cases["cases"]):
                raise LabError("every child case requires verified recovery")
    return lab,inventory,checks

def canonical(value):
    try:return json.dumps(value,sort_keys=True,separators=(",",":"),allow_nan=False)
    except (ValueError,TypeError,OverflowError) as exc:raise LabError("invalid enterprise evidence") from exc

def lifecycle(run):
    if run["version"]==3:return resilience.FLOW,resilience.STAGES
    return (analyst.FLOW,analyst.STAGES) if run["version"]==2 else (FLOW,STAGES)

def evaluate(run):
    if run["version"]==3:return resilience.evaluate(run["config"],run["steps"])
    return analyst.evaluate(run["config"],run["steps"]) if run["version"]==2 else replay(run["config"],run["steps"])

def load(raw):
    if raw is None:return None
    if not isinstance(raw,dict) or set(raw)!={"version","run_id","config","steps","observations"} or type(raw["version"]) is not int or raw["version"] not in (1,2,3):
        raise LabError("invalid enterprise state")
    if not isinstance(raw["run_id"],str) or not re.fullmatch("[a-f0-9]{32}",raw["run_id"]):
        raise LabError("invalid enterprise run ID")
    _,_,checks=evaluate(raw)
    if canonical(raw["observations"])!=canonical(checks):raise LabError("enterprise evidence does not match modeled replay")
    return deepcopy(raw)

def action(lab,body):
    if not isinstance(body,dict) or not isinstance(body.get("action"),str):raise LabError("invalid enterprise action")
    op=body["action"];run=lab.enterprise_training
    from . import enterprise_archive as archive
    if op=="set_retention":return archive.set_retention(lab,body)
    if op=="start":
        if run is not None or set(body) not in ({"action","config"},{"action","config","mode"}):raise LabError("start requires an idle enterprise exercise")
        mode=body.get("mode","legacy" if run is None or run["version"]==1 else "assessment")
        if mode not in ("legacy","assessment","resilience"):raise LabError("unknown enterprise mode")
        candidate={"version":{"legacy":1,"assessment":2,"resilience":3}[mode],"run_id":uuid.uuid4().hex,"config":config(body["config"]),"steps":[]}
    else:
        if run is None or body.get("run_id")!=run["run_id"] or type(body.get("step")) is not int or body["step"]!=len(run["steps"]):
            raise LabError("stale enterprise request; refresh current run")
        if op=="restart":
            if set(body) not in ({"action","run_id","step","config"},{"action","run_id","step","config","mode"}):raise LabError("invalid restart fields")
            mode=body.get("mode",{1:"legacy",2:"assessment",3:"resilience"}[run["version"]])
            if mode not in ("legacy","assessment","resilience"):raise LabError("unknown enterprise mode")
            candidate={"version":{"legacy":1,"assessment":2,"resilience":3}[mode],"run_id":uuid.uuid4().hex,"config":config(body["config"]),"steps":[]}
        else:
            n=len(run["steps"])
            sequence,_=lifecycle(run)
            if n>=len(sequence) or op!=sequence[n]:raise LabError("invalid enterprise action or stage")
            step={k:v for k,v in body.items() if k not in {"run_id","step"}}
            if run["version"]==1 and set(step)!={"action"}:raise LabError("invalid legacy action fields")
            candidate=deepcopy(run);candidate["steps"].append(step if run["version"]>=2 else op)
    _,_,candidate["observations"]=evaluate(candidate)
    archive.record(lab,candidate)
    lab.enterprise_training=candidate
    return {"run_id":candidate["run_id"],"status":lifecycle(candidate)[1][len(candidate["steps"])]}

def report_run(run):
    if run["version"]==3:return resilience.report(run)
    sandbox,inventory,checks=evaluate(run);n=len(run["steps"]);sequence,stages=lifecycle(run)
    parent=correlation(inventory,checks,sandbox.incident_cases["cases"],run["run_id"],stages[n])
    report={"version":run["version"],"run_id":run["run_id"],"config":deepcopy(run["config"]),"status":stages[n],"complete":n==len(sequence),
            "evidence_type":"modeled_synthetic","inventory":inventory,"topology":{"devices":len(sandbox.devices),"links":len(sandbox.links)},
            "observations":checks,"impact":impact(checks),"monitoring":monitoring(checks),"parent_incident":parent,
            "soc":soc.view(sandbox),"incidents":incidents.view(sandbox),
            "limitations":["Routed subnets, not enforced security zones; one shared DNS dependency, no redundancy.",
                           "The DNS interface fault is modeled; client-side DNS caching is not modeled here.",
                           "Recovery sampling is discrete simulated time, not a real SLA.",
                           "Phase snapshots retain observation IDs even if the bounded SOC journal evicts them.",
                           "Parent closure requires all affected clients to pass three recovery samples. Child cases are recovered, not analyst-resolved."]}
    if run["version"]==2:
        report["analyst"]=analyst.assessment(run["steps"],inventory,checks)
        if parent:
            parent["acknowledged"]=report["analyst"]["acknowledgement"] is not None
            parent["analyst_resolved"]=report["analyst"]["resolution"] is not None
            parent["closure_ready"]=parent["closure_ready"] and parent["acknowledged"] and report["analyst"]["assessment"] is not None
    if parent:
        child_ids=set(parent["child_case_ids"])
        event_ids={parent["fault_event_id"]}
        for child in parent["children"]:
            event_ids.update((child["failure_event_id"],child["evidence"]["fault"]["dns"]["id"]))
        for case in report["incidents"]["cases"]:
            if case["id"] in child_ids:case["parent_id"]=parent["id"]
        for alert in report["soc"]["alerts"]:
            if alert["event_id"] in event_ids:
                alert["parent_id"]=parent["id"]
                if run["version"]==2:alert["parent_acknowledged"]=parent["acknowledged"]
    return report

def view(lab):
    run=lab.enterprise_training
    if run is None:return {"ok":True,"version":VERSION,"status":"idle","next_action":"start","report":None}
    sequence,stages=lifecycle(run);n=len(run["steps"])
    return {"ok":True,"version":VERSION,"run_id":run["run_id"],"step":n,"status":stages[n],
            "next_action":sequence[n] if n<len(sequence) else None,"report":report_run(run)}

def schema():
    return {"version":VERSION,"read":"GET /api/cyber-range/enterprise","write":"POST /api/cyber-range/enterprise/action",
            "config":{"departments":{"minimum":2,"maximum":3},"hosts_per_department":{"minimum":1,"maximum":2}},
            "lifecycle":["start",*FLOW,"restart"],"assessment_lifecycle":["start",*analyst.FLOW,"restart"],
            "mode":"Set mode=assessment for version 2 or mode=resilience for version 3 on start/restart; legacy requests and saves retain original workflow.",
            "resilience_lifecycle":["start",*resilience.FLOW,"restart"],"resilience_fields":{k:sorted(v) for k,v in resilience.FIELDS.items()},
            "resilience_roles":list(resilience.ROLES),"resilience_diagnoses":resilience.DIAGNOSES,
            "assessment_fields":{k:sorted(v) for k,v in analyst.FIELDS.items()},"diagnoses":analyst.DIAGNOSES,"context":"run_id and integer step required except start",
            "fault":"Modeled DNS-SERVER interface availability only",
            "archive":"GET /api/cyber-range/enterprise/archive",
            "archived_report":"GET /api/cyber-range/enterprise/report?run_id=ID",
            "retention_action":{"action":"set_retention","limit":"integer 1-24","expected_limit":"current limit"},
            "correlation":"One parent per run; all affected clients require three healthy recovery samples before closure.",
            "isolation":"Private in-memory NetworkLab; no host or external network operations."}

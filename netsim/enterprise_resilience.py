"""Private, deterministic DNS resilience training (enterprise rubric v3)."""
from copy import deepcopy
from .model import LabError
from .simulation import advance
from .incident_cases import valid_note
from .enterprise_assessment import require,event_id,refs,names

TEMPLATE="enterprise-dns-resilience"
FLOW=("observe_failover","observe_interruption","observe_partial","monitor_unstable","restore","verify_recovery","assess","resolve")
STAGES=("baseline_verified","failover_observed","interruption_observed","partial_recovery","unstable_recovery","restored","recovery_verified","assessed","completed")
DIAGNOSES={"redundancy_degraded":"Intermittent DNS redundancy loss","app_outage":"Application outage","routing_failure":"Application routing failure","insufficient_evidence":"Insufficient evidence"}
ROLES=("primary_failure","secondary_success","failover_portal","partial_portal","partial_secondary_failure","relapse_portal_failure","healthy_app_control")
FIELDS={op:{"action"} for op in FLOW}
FIELDS["assess"]={"action","diagnosis","references","affected_clients","note","note_event_id"}
FIELDS["resolve"]={"action","resolver_refs","client_refs"}
RECOVERY=("restored","recovery_5s","recovery_10s")

def build(cfg):
    from .enterprise_training import build as enterprise_build
    lab,inventory=enterprise_build(cfg)
    primary=inventory["dns"];secondary={"device":"DNS-BACKUP","ip":primary["ip"].rsplit(".",1)[0]+".12"}
    lab.add_device("server",secondary["device"],840,390)
    lab.connect("SERVICES-SW","fa0/3",secondary["device"],"eth0")
    lab.set_ip(secondary["device"],"eth0",secondary["ip"]+"/24")
    lab.set_gateway(secondary["device"],inventory["segments"][-1]["gateway"])
    lab.dns_service(secondary["device"],True)
    lab.dns_record(secondary["device"],inventory["hostname"],inventory["app"]["ip"])
    inventory["segments"][-1]["members"].append(secondary)
    inventory["resolvers"]={"primary":primary,"secondary":secondary}
    inventory["dependencies"]=[
        *[{"consumer":c["device"],"requires":"portal_by_name"} for c in inventory["clients"]],
        {"consumer":"portal_by_name","requires":"dns_primary_or_secondary"},
        {"consumer":"portal_by_name","requires":"app_http"},
        {"consumer":"dns_primary_or_secondary","requires_any":[primary["device"],secondary["device"]]}]
    return lab,inventory

def check(lab,inventory,phase,primary_up,secondary_up):
    from .enterprise_training import record,http
    components={}
    for role,expected in (("primary",primary_up),("secondary",secondary_up)):
        device=inventory["resolvers"][role]["device"]
        up=lab.devices[device].interfaces["eth0"].admin_up
        require(up==expected,"unexpected modeled resolver state")
        components[role]=record(lab,"health","LINK",device,"eth0",up,"modeled_interface_down")
    clients=[]
    for c in inventory["clients"]:
        source=c["device"];attempts={};addresses={}
        # Probe both modeled resolvers independently, including the standby.
        for role,expected in (("primary",primary_up),("secondary",secondary_up)):
            ip=inventory["resolvers"][role]["ip"];lab.set_dns_client(source,ip)
            try:resolved=lab.resolve_dns(source,inventory["hostname"])
            except LabError:resolved=None
            ok=resolved==inventory["app"]["ip"];require(ok==expected,"unexpected modeled DNS response")
            attempts[role]=record(lab,"health","DNS",source,ip,ok,"modeled_operation_failed")
            addresses[role]=resolved
        selected=next((role for role in ("primary","secondary") if addresses[role]==inventory["app"]["ip"]),None)
        # Use selected resolver for actual hostname HTTP; if neither worked, test primary.
        lab.set_dns_client(source,inventory["resolvers"][selected or "primary"]["ip"])
        named=http(lab,source,inventory["hostname"],"health")
        direct=http(lab,source,inventory["app"]["ip"],"health")
        require((named["http_status"]==200)==bool(selected) and direct["http_status"]==200,"unexpected modeled HTTP response")
        lab.set_dns_client(source,inventory["resolvers"]["primary"]["ip"])
        clients.append({"client":source,"department":c["department"],"attempts":attempts,
                        "resolved":addresses,"selected":selected,"portal":named,"direct":direct})
    return {"phase":phase,"sim_time":lab.simulation["master_time"],"components":components,"clients":clients}

def set_state(lab,inventory,primary,secondary):
    for role,up in (("primary",primary),("secondary",secondary)):
        lab.set_interface_state(inventory["resolvers"][role]["device"],"eth0",up)

def sample(lab,inventory,checks,phase,primary,secondary,delay=5):
    if delay:advance(lab,delay)
    set_state(lab,inventory,primary,secondary)
    checks[phase]=check(lab,inventory,phase,primary,secondary)

def evidence(checks):
    ids=set()
    for phase in checks.values():
        ids.update(e["id"] for e in phase["components"].values())
        for r in phase["clients"]:
            ids.update(e["id"] for e in r["attempts"].values())
            ids.update(r[k]["event"]["id"] for k in ("portal","direct"))
    return ids

def healthy(phase,expected):
    rows=phase["clients"]
    return (len(rows)==len(expected) and {r["client"] for r in rows}==expected
            and set(phase["components"])=={"primary","secondary"} and all(e["outcome"]=="success" for e in phase["components"].values())
            and all(r["selected"]=="primary" and all(e["outcome"]=="success" for e in r["attempts"].values())
                    and r["portal"]["event"]["outcome"]==r["direct"]["event"]["outcome"]=="success"
                    and r["portal"]["http_status"]==r["direct"]["http_status"]==200 for r in rows))

def monitoring(checks):
    expected={r["client"] for r in checks["baseline"]["clients"]}
    samples=[{"phase":p,"sim_time":checks[p]["sim_time"],"healthy":healthy(checks[p],expected)} for p in RECOVERY if p in checks]
    span=round(samples[-1]["sim_time"]-samples[0]["sim_time"],6) if samples else 0
    distinct=True;seen=set();last=0
    for p in RECOVERY:
        if p not in checks:continue
        c=checks[p];ids=[e["id"] for e in c["components"].values()]
        for r in c["clients"]:
            ids.extend(e["id"] for e in r["attempts"].values())
            ids.extend(r[k]["event"]["id"] for k in ("portal","direct"))
        if c["phase"]!=p or len(ids)!=len(set(ids)) or seen.intersection(ids) or any(type(i) is not int or i<=last for i in ids):
            distinct=False
        if ids:last=max(ids)
        seen.update(ids)
    spacing=all(b["sim_time"]-a["sim_time"]>=5-1e-6 for a,b in zip(samples,samples[1:]))
    return {"samples":samples,"span_simulated_seconds":span,"passed":len(samples)==3 and span>=10 and distinct and spacing and all(s["healthy"] for s in samples),
            "partial_recovery_detected":"partial" in checks and all(r["portal"]["http_status"]==200 for r in checks["partial"]["clients"]) and not healthy(checks["partial"],expected),
            "relapse_detected":"relapse" in checks and any(r["portal"]["http_status"]!=200 for r in checks["relapse"]["clients"])}

def evaluate(cfg,steps):
    require(isinstance(steps,list) and len(steps)<=len(FLOW),"invalid resilience history")
    for op,s in zip(FLOW,steps):require(isinstance(s,dict) and s.get("action")==op and set(s)==FIELDS[op],"invalid resilience action or stage")
    lab,inventory=build(cfg);checks={"baseline":check(lab,inventory,"baseline",True,True)}
    for s in steps:
        op=s["action"]
        if op=="observe_failover":sample(lab,inventory,checks,"failover",False,True)
        elif op=="observe_interruption":sample(lab,inventory,checks,"interruption",False,False)
        elif op=="observe_partial":sample(lab,inventory,checks,"partial",True,False)
        elif op=="monitor_unstable":
            sample(lab,inventory,checks,"relapse",False,False)
            require(not monitoring(checks)["passed"] and monitoring(checks)["relapse_detected"],"unstable recovery was not detected")
        elif op=="restore":sample(lab,inventory,checks,"restored",True,True)
        elif op=="verify_recovery":
            sample(lab,inventory,checks,"recovery_5s",True,True)
            sample(lab,inventory,checks,"recovery_10s",True,True)
            require(monitoring(checks)["passed"],"all-client redundant recovery not verified")
        elif op=="assess":
            require(isinstance(s["diagnosis"],str) and s["diagnosis"] in DIAGNOSES,"unknown resilience diagnosis")
            allowed=evidence(checks)
            refs(s["references"],ROLES,allowed)
            names(s["affected_clients"],{r["device"] for r in inventory["clients"]})
            require(valid_note(s["note"]) and event_id(s["note_event_id"]) in allowed,"valid evidence-linked note required")
        elif op=="resolve":
            require(monitoring(checks)["passed"],"sustained recovery required")
            latest=checks["recovery_10s"]
            expected={k:v["id"] for k,v in latest["components"].items()}
            refs(s["resolver_refs"],expected,evidence(checks))
            require(s["resolver_refs"]==expected,"cite latest resolver recovery evidence")
            expected={r["client"]:{"primary":r["attempts"]["primary"]["id"],"secondary":r["attempts"]["secondary"]["id"],"portal":r["portal"]["event"]["id"]} for r in latest["clients"]}
            require(isinstance(s["client_refs"],dict) and set(s["client_refs"])==set(expected),"resolution requires every client")
            for name,r in expected.items():
                refs(s["client_refs"][name],r,evidence(checks));require(s["client_refs"][name]==r,"cite latest per-client redundant DNS and portal evidence")
    return lab,inventory,checks

def assessment(steps,checks):
    by={s["action"]:s for s in steps};a=by.get("assess");r=a["references"] if a else {}
    def match(phase,roles):
        if phase not in checks:return False
        for x in checks[phase]["clients"]:
            actual={"primary":x["attempts"]["primary"]["id"],"secondary":x["attempts"]["secondary"]["id"],"portal":x["portal"]["event"]["id"],"direct":x["direct"]["event"]["id"]}
            if all(r.get(k)==actual[v] for k,v in roles.items()):return True
        return False
    failover=match("failover",{"primary_failure":"primary","secondary_success":"secondary","failover_portal":"portal"})
    partial=match("partial",{"partial_portal":"portal","partial_secondary_failure":"secondary"})
    relapse=match("relapse",{"relapse_portal_failure":"portal","healthy_app_control":"direct"})
    impact=bool(a and set(a["affected_clients"])=={x["client"] for x in checks["relapse"]["clients"] if x["portal"]["http_status"]!=200})
    diagnosis=bool(a and a["diagnosis"]=="redundancy_degraded" and failover and partial and relapse)
    note=bool(a and a["note_event_id"] in {e["id"] for phase in ("failover","partial","relapse") for e in checks[phase]["components"].values()})
    rows=[("failover_evidence",20,failover),("partial_recovery_evidence",15,partial),("relapse_and_healthy_app_control",15,relapse),
          ("evidence_backed_diagnosis",20,diagnosis),("affected_client_set",10,impact),("dependency_linked_note",5,note),
          ("sustained_recovery_verified",10,"verify_recovery" in by),("explicit_resolution",5,"resolve" in by)]
    return {"assessment":deepcopy(a),"resolution":deepcopy(by.get("resolve")),
            "score":{"points":sum(p for _,p,m in rows if m),"maximum":100,"criteria":[{"id":k,"points":p,"met":bool(m)} for k,p,m in rows],
                     "scope":"Structured resilience diagnosis and evidence; free-text note correctness is not graded."}}

def report(run):
    from .defensive_soc import view as soc_view
    lab,inventory,checks=evaluate(run["config"],run["steps"]);n=len(run["steps"]);m=monitoring(checks)
    parent=None
    if "failover" in checks:
        status="closed" if n==len(FLOW) else "recovery_verified" if m["passed"] else "unstable" if "relapse" in checks and "restored" not in checks else "recovering" if "partial" in checks else "open"
        parent={"id":"P-"+run["run_id"],"status":status,"closure_ready":m["passed"] and "assess" in {s["action"] for s in run["steps"]},
                "affected_clients":sorted({r["client"] for phase in checks.values() for r in phase["clients"] if r["portal"]["http_status"]!=200})}
    return {"version":3,"template":TEMPLATE,"run_id":run["run_id"],"config":deepcopy(run["config"]),"status":STAGES[n],"complete":n==len(FLOW),
            "evidence_type":"modeled_synthetic","inventory":inventory,"topology":{"devices":len(lab.devices),"links":len(lab.links)},
            "observations":checks,"monitoring":m,"parent_incident":parent,"analyst":assessment(run["steps"],checks),"soc":soc_view(lab),
            "limitations":["Ordered resolver choice is an exercise-local model, not OS DNS retry timing or production resolver configuration.",
                           "Both DNS servers share the services subnet; no redundant network path or client cache is modeled.",
                           "Recovery is three discrete samples over ten simulated seconds; not continuous monitoring.",
                           "Phase evidence survives bounded SOC journal eviction. No real network activity."]}

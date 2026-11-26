"""Guided defensive availability exercises on a private, deterministic simulator.

Only a fixed in-memory topology is used. Persisted action history and observed
check snapshots are replayed/validated, never executed against the host network.
"""
from copy import deepcopy
import json
import re
import uuid
from .model import NetworkLab, LabError
from . import defensive_soc as soc, incident_cases as incidents

VERSION = 1
TEMPLATE = "interface-availability"
SOURCE = "CLIENT"
TARGET = "192.0.2.20"
DIAGNOSES = {
    "client_interface_down": "Client interface administratively down",
    "application_only": "Application-only outage",
    "insufficient_evidence": "Insufficient evidence",
}
ROLES = ("baseline_icmp", "baseline_http", "failure_icmp", "failure_http", "interface_state")
FLOW = ("inject_fault", "acknowledge", "assess", "restore", "verify_recovery", "complete")
STAGES = ("baseline_verified", "fault_observed", "acknowledged", "assessed", "restored",
          "recovery_verified", "completed")
STEP_FIELDS = {
    "inject_fault": {"action"}, "acknowledge": {"action","event_id"},
    "assess": {"action","diagnosis","references","note"}, "restore": {"action"},
    "verify_recovery": {"action","icmp_event_id","http_event_id"}, "complete": {"action"},
}

def topology():
    lab = NetworkLab()
    for kind,name,x in (("pc",SOURCE,80),("switch","ACCESS",260),("server","APP",440)):
        lab.add_device(kind,name,x,120)
    lab.connect(SOURCE,"eth0","ACCESS","fa0/1")
    lab.connect("APP","eth0","ACCESS","fa0/2")
    lab.set_ip(SOURCE,"eth0","192.0.2.10/24")
    lab.set_ip("APP","eth0",TARGET+"/24")
    return lab

def check(lab, phase, expected):
    # Administrative state, completed ICMP result, and actual simulated HTTP
    # request are separate evidence sources. No real sockets are used.
    up = lab.devices[SOURCE].interfaces["eth0"].admin_up
    soc.append(lab,"health","LINK",SOURCE,"eth0",up,None if up else "modeled_interface_down")
    interface = deepcopy(lab.defensive_soc["logs"][-1])
    ping = lab.ping_detailed(SOURCE,TARGET)
    icmp = deepcopy(lab.defensive_soc["logs"][-1])
    status = None
    try:
        result = lab.http_request(SOURCE,"http://"+TARGET+"/")
        status = result["status"]
        healthy = result["ok"] is True and status == 200
    except LabError:
        healthy = False
    soc.append(lab,"health","HTTP",SOURCE,TARGET,healthy,
               None if healthy else "modeled_operation_failed")
    http = deepcopy(lab.defensive_soc["logs"][-1])
    if (up, ping["reachable"], healthy) != (expected,expected,expected):
        raise LabError("exercise model did not produce the expected availability observations")
    return {"phase":phase,"interface":interface,"icmp":icmp,"http":http,
            "http_status":status}

def event_id(value):
    if type(value) is not int or not 1 <= value <= 10**15:
        raise LabError("event ID must be a positive integer")
    return value

def validate_step(step, expected):
    if not isinstance(step,dict) or step.get("action") != expected or set(step) != STEP_FIELDS[expected]:
        raise LabError("invalid exercise action or stage")

def replay(steps):
    if not isinstance(steps,list) or len(steps)>len(FLOW):
        raise LabError("invalid exercise history")
    lab=topology()
    checks={"baseline":check(lab,"baseline",True)}
    assessment=None
    for op,step in zip(FLOW,steps):
        validate_step(step,op)
        if op=="inject_fault":
            lab.set_interface_state(SOURCE,"eth0",False)
            checks["fault"]=check(lab,"fault",False)
        elif op=="acknowledge":
            failure=checks["fault"]["icmp"]["id"]
            if event_id(step["event_id"])!=failure:
                raise LabError("acknowledge the observed failed connectivity check")
            case=lab.incident_cases["cases"][0]
            incidents.action(lab,{"action":"acknowledge","case_id":case["id"],"event_id":failure})
        elif op=="assess":
            diagnosis=step["diagnosis"]
            refs=step["references"]
            if not isinstance(diagnosis,str) or diagnosis not in DIAGNOSES:
                raise LabError("unknown exercise diagnosis")
            if not isinstance(refs,dict) or set(refs)!=set(ROLES):
                raise LabError("all five assessment evidence roles are required")
            available={checks[p][k]["id"] for p in ("baseline","fault") for k in ("interface","icmp","http")}
            if any(event_id(v) not in available for v in refs.values()):
                raise LabError("assessment references must belong to this attempt's baseline or fault")
            if not incidents.valid_note(step["note"]):
                raise LabError("assessment note must be 1-500 printable characters")
            assessment={"diagnosis":diagnosis,"references":deepcopy(refs),"note":step["note"]}
            case=lab.incident_cases["cases"][0]
            incidents.action(lab,{"action":"add_note","case_id":case["id"],
                                  "event_id":checks["fault"]["icmp"]["id"],"note":step["note"]})
        elif op=="restore":
            lab.set_interface_state(SOURCE,"eth0",True)
            checks["recovery"]=check(lab,"recovery",True)
        elif op=="verify_recovery":
            recovery=checks["recovery"]
            if event_id(step["icmp_event_id"])!=recovery["icmp"]["id"] or event_id(step["http_event_id"])!=recovery["http"]["id"]:
                raise LabError("verification requires both current recovery observations")
            case=lab.incident_cases["cases"][0]
            incidents.action(lab,{"action":"verify_recovery","case_id":case["id"],
                                  "event_id":recovery["icmp"]["id"]})
        elif op=="complete":
            case=lab.incident_cases["cases"][0]
            incidents.action(lab,{"action":"resolve","case_id":case["id"]})
    return lab,checks,assessment

def rubric(steps, checks, assessment):
    refs=assessment["references"] if assessment else {}
    def cited(role,phase,kind):
        return phase in checks and refs.get(role)==checks[phase][kind]["id"]
    baseline=cited("baseline_icmp","baseline","icmp") and cited("baseline_http","baseline","http")
    failed=cited("failure_icmp","fault","icmp") and cited("failure_http","fault","http")
    interface=cited("interface_state","fault","interface")
    diagnosis=bool(assessment and assessment["diagnosis"]=="client_interface_down" and interface and failed)
    rows=[
        ("baseline_evidence",10,baseline),
        ("connectivity_and_http_failure_evidence",20,failed),
        ("interface_state_evidence",15,interface),
        ("evidence_backed_diagnosis",20,diagnosis),
        ("acknowledged_incident",10,len(steps)>=2),
        ("verified_connectivity_and_http_recovery",20,len(steps)>=5),
        ("resolved_and_completed",5,len(steps)==len(FLOW)),
    ]
    return {"points":sum(p for _,p,met in rows if met),"maximum":100,
            "criteria":[{"id":name,"points":p,"met":met} for name,p,met in rows],
            "scope":"Structured evidence and diagnosis are graded; free-text note accuracy is not graded."}

ARCHIVE_LIMIT = 12

def flow(run):
    from . import exercise_library as library
    return (FLOW,STAGES) if run["version"]==1 else (library.FLOW,library.STAGES)

def evaluate(run):
    if run["version"]==1:
        return replay(run["steps"])
    from .exercise_library import replay as replay_v2
    return replay_v2(run["template"],run["steps"])

def new_run(attempt,template=TEMPLATE,version=1):
    from .exercise_library import TEMPLATES
    if type(attempt) is not int or not 1<=attempt<=10**9:
        raise LabError("exercise attempt limit reached")
    if type(version) is not int or version not in (1,2) or not isinstance(template,str) or template not in TEMPLATES or (version==1 and template!=TEMPLATE):
        raise LabError("unknown exercise template or version")
    run={"version":version,"template":template,"run_id":uuid.uuid4().hex,
         "attempt":attempt,"steps":[],"observations":{}}
    _,run["observations"],_=evaluate(run)
    return run

def canonical(value):
    try:return json.dumps(value,sort_keys=True,separators=(",",":"),allow_nan=False)
    except (TypeError,ValueError,OverflowError) as exc:raise LabError("invalid exercise evidence") from exc

def load(raw):
    from .exercise_library import TEMPLATES
    if raw is None:return None
    if not isinstance(raw,dict) or set(raw)!={"version","template","run_id","attempt","steps","observations"}:
        raise LabError("invalid exercise state")
    if type(raw["version"]) is not int or raw["version"] not in (1,2) or not isinstance(raw["template"],str) or raw["template"] not in TEMPLATES or (raw["version"]==1 and raw["template"]!=TEMPLATE):
        raise LabError("unsupported exercise version or template")
    if not isinstance(raw["run_id"],str) or not re.fullmatch("[a-f0-9]{32}",raw["run_id"]):
        raise LabError("invalid exercise run ID")
    if type(raw["attempt"]) is not int or not 1<=raw["attempt"]<=10**9:
        raise LabError("invalid exercise attempt")
    _,checks,_=evaluate(raw)
    if canonical(raw["observations"])!=canonical(checks):
        raise LabError("stored exercise evidence does not match modeled replay")
    return deepcopy(raw)

def completed(run):
    return run is not None and len(run["steps"])==len(flow(run)[0])

def load_archive(raw,current):
    if raw is None:  # migration from labs saved before the archive
        return {"version":1,"evicted":0,"runs":[deepcopy(current)] if completed(current) else []}
    if not isinstance(raw,dict) or set(raw)!={"version","evicted","runs"} or type(raw["version"]) is not int or raw["version"]!=1:
        raise LabError("invalid exercise archive")
    if type(raw["evicted"]) is not int or not 0<=raw["evicted"]<=10**9 or not isinstance(raw["runs"],list) or len(raw["runs"])>ARCHIVE_LIMIT:
        raise LabError("invalid exercise archive capacity")
    previous=0
    seen=set()
    for run in raw["runs"]:
        run=load(run)
        if not completed(run) or run["run_id"] in seen or run["attempt"]<=previous:
            raise LabError("invalid archived attempt")
        seen.add(run["run_id"]);previous=run["attempt"]
        if current and run["attempt"]>=current["attempt"] and (run!=current or not completed(current)):
            raise LabError("archive conflicts with current attempt")
    if completed(current) and (not raw["runs"] or raw["runs"][-1]!=current):
        raise LabError("completed exercise is missing from archive")
    return deepcopy(raw)

def report_run(run):
    from . import exercise_library as library
    sandbox,checks,assessment=evaluate(run)
    sequence,stages=flow(run);n=len(run["steps"])
    legacy=run["version"]==1
    report={"version":run["version"],"evidence_type":"modeled_synthetic","template":run["template"],
            "run_id":run["run_id"],"attempt":run["attempt"],"status":stages[n],
            "complete":completed(run),"observations":deepcopy(checks),
            "history":["start",*[step["action"] for step in run["steps"]]],
            "sandbox":{"path":[SOURCE,"ACCESS","APP"],"service":"modeled HTTP",
                       "source_ip":"192.0.2.10","destination_ip":TARGET},
            "assessment":assessment,"score":rubric(run["steps"],checks,assessment) if legacy else library.rubric(run["template"],run["steps"],checks,assessment),
            "soc":soc.view(sandbox),"incidents":incidents.view(sandbox),
            "limitations":["Only a fixed private modeled topology; no real network or external traffic.",
                           "Evidence IDs are scoped to this run; restart creates a new run.",
                           "Saved action history and check snapshots are validated by deterministic replay.",
                           "HTTP status is simulated; recovery is a point-in-time check, not a sustained SLA." if legacy else "Recovery samples are discrete simulated checks, not continuous monitoring or a real SLA.",
                           "Free-text analyst notes are not graded for correctness."]}
    if not legacy:report["monitoring"]=library.monitoring(checks)
    return report

def progress(lab):
    from . import exercise_library as library
    archive=lab.exercise_archive
    rows=[]
    for run in archive["runs"]:
        assessment=next((s for s in run["steps"] if s["action"]=="assess"),None)
        checks=run["observations"]
        grade=rubric(run["steps"],checks,assessment) if run["version"]==1 else library.rubric(run["template"],run["steps"],checks,assessment)
        rows.append({"run_id":run["run_id"],"attempt":run["attempt"],"template":run["template"],
                     "version":run["version"],"points":grade["points"],"maximum":100})
    groups=[]
    for template,version in sorted({(r["template"],r["version"]) for r in rows}):
        items=[r for r in rows if (r["template"],r["version"])==(template,version)]
        scores=[r["points"] for r in items]
        groups.append({"template":template,"version":version,"completed":len(items),"best":max(scores),
                       "latest":scores[-1],"first":scores[0],"change":scores[-1]-scores[0]})
    return {"retained":len(rows),"evicted":archive["evicted"],"limit":ARCHIVE_LIMIT,"attempts":rows,"by_template":groups,
            "scope":"Retained completed attempts only; compare within the same template and rubric version."}

def archived_report(lab,run_id):
    if not isinstance(run_id,str) or not re.fullmatch("[a-f0-9]{32}",run_id):raise LabError("invalid report ID")
    run=next((r for r in lab.exercise_archive["runs"] if r["run_id"]==run_id),None)
    if run is None:raise LabError("archived report not found")
    return {"ok":True,"report":report_run(run)}

def catalog():
    from .exercise_library import TEMPLATES
    return [{"id":k,"title":v["title"],"difficulty":v["difficulty"]} for k,v in TEMPLATES.items()]

def view(lab):
    from . import exercise_library as library
    run=lab.exercise_runner
    common={"ok":True,"version":2,"library":catalog(),"progress":progress(lab)}
    if run is None:
        return {**common,"status":"idle","next_action":"start","report":None}
    sequence,stages=flow(run);n=len(run["steps"]);legacy=run["version"]==1
    report=report_run(run)
    return {**common,"status":stages[n],"run_id":run["run_id"],"attempt":run["attempt"],"step":n,
            "next_action":sequence[n] if n<len(sequence) else None,"report":report,
            "assessment_roles":dict(zip(ROLES,["Normal connectivity","Normal HTTP health","Failed connectivity","Failed HTTP health","Interface state during failure"])) if legacy else library.ROLES.copy(),
            "diagnoses":DIAGNOSES.copy() if legacy else library.DIAGNOSES.copy(),
            "primary_failure_event_id":(report["observations"]["fault"]["icmp" if legacy or run["template"]!="http-availability" else "http"]["id"] if "fault" in report["observations"] else None),
            "verification_phase":"recovery" if legacy else "recovery_10s"}

def action(lab,body):
    if not isinstance(body,dict) or not isinstance(body.get("action"),str):
        raise LabError("invalid exercise action")
    op=body["action"];run=lab.exercise_runner
    if op=="start":
        if set(body) not in ({"action"},{"action","template"}) or run is not None:
            raise LabError("start requires an idle exercise; restart an existing attempt explicitly")
        previous=max((r["attempt"] for r in lab.exercise_archive["runs"]),default=0)
        candidate=new_run(previous+1,body.get("template",TEMPLATE),2 if "template" in body else 1)
    else:
        if run is None:raise LabError("start an exercise first")
        if body.get("run_id")!=run["run_id"] or type(body.get("step")) is not int or body["step"]!=len(run["steps"]):
            raise LabError("stale exercise request; refresh the current attempt")
        step={k:v for k,v in body.items() if k not in {"run_id","step"}}
        if op=="restart":
            if set(step) not in ({"action"},{"action","template"}):raise LabError("invalid restart fields")
            candidate=new_run(run["attempt"]+1,step.get("template",run["template"]),2 if "template" in step else run["version"])
        else:
            sequence,_=flow(run);n=len(run["steps"])
            if n>=len(sequence) or op!=sequence[n]:raise LabError("action is not available at the current exercise stage")
            candidate=deepcopy(run)
            candidate["steps"].append(deepcopy(step))
            _,candidate["observations"],_=evaluate(candidate)
    if completed(candidate):
        archive=lab.exercise_archive
        if len(archive["runs"])>=ARCHIVE_LIMIT:
            archive["runs"].pop(0);archive["evicted"]+=1
        archive["runs"].append(deepcopy(candidate))
    lab.exercise_runner=candidate
    return {"status":flow(candidate)[1][len(candidate["steps"])],"run_id":candidate["run_id"],
            "attempt":candidate["attempt"],"step":len(candidate["steps"])}

def schema():
    from . import exercise_library as library
    return {"version":2,"library":catalog(),"read":"GET /api/cyber-range/exercises",
            "write":"POST /api/cyber-range/exercises/action","archive":"GET /api/cyber-range/exercises/report?run_id=ID",
            "lifecycle":["start",*library.FLOW,"restart"],"stages":["idle",*library.STAGES],
            "diagnoses":library.DIAGNOSES.copy(),"assessment_roles":library.ROLES.copy(),
            "actions":{"start":["action","template (optional)"],"restart":["action","template (optional)"],
                       "monitor_recovery":["action"],**{k:sorted(v) for k,v in STEP_FIELDS.items()}},
            "request_context":"Every action except start requires current run_id and integer step.",
            "isolation":"Private fixed in-memory simulator; active topology, SOC journal and cases are not modified.",
            "compatibility":"Start without template uses legacy v1; explicitly select template for v2. Legacy saved attempts retain their original rubric.",
            "enterprise_library":{"title":"Enterprise DNS availability assessment","entry":"POST /api/cyber-range/enterprise/action (mode=assessment)","archive":"GET /api/cyber-range/enterprise/archive"},
            "archive_limit":ARCHIVE_LIMIT,"restart":"Completed attempts are archived automatically; incomplete attempts are replaced.",
            "monitoring":"Three modeled samples spanning ten simulated seconds. Verify the latest pair."}

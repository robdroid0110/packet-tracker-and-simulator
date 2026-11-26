"""Bounded, versioned completed enterprise assessment history."""
from copy import deepcopy
from datetime import datetime, timezone
import re
from .model import LabError

DEFAULT_LIMIT=12
MAX_LIMIT=24

def defaults():
    return {"version":1,"limit":DEFAULT_LIMIT,"evicted":0,"next_sequence":1,"entries":[]}

def completed(run):
    from .enterprise_training import lifecycle
    return run is not None and run["version"] in (2,3) and len(run["steps"])==len(lifecycle(run)[0])

def trim(store):
    excess=max(0,len(store["entries"])-store["limit"])
    if excess:
        del store["entries"][:excess];store["evicted"]+=excess

def append(store,run,completed_at):
    if not completed(run):raise LabError("only completed enterprise assessments can be archived")
    if any(e["run"]["run_id"]==run["run_id"] for e in store["entries"]):
        raise LabError("enterprise report already archived")
    if store["next_sequence"]>=10**9:raise LabError("enterprise archive sequence limit reached")
    store["entries"].append({"sequence":store["next_sequence"],"completed_at":completed_at,"run":deepcopy(run)})
    store["next_sequence"]+=1;trim(store)

def record(lab,run):
    if completed(run):
        candidate=deepcopy(lab.enterprise_archive)
        append(candidate,run,datetime.now(timezone.utc).isoformat(timespec="seconds"))
        lab.enterprise_archive=candidate

def limit(value):
    if type(value) is not int or not 1<=value<=MAX_LIMIT:raise LabError("enterprise retention must be an integer from 1 to 24")
    return value

def set_retention(lab,body):
    if set(body)!={"action","limit","expected_limit"}:raise LabError("invalid retention action fields")
    new=limit(body["limit"]);old=limit(body["expected_limit"])
    if old!=lab.enterprise_archive["limit"]:raise LabError("stale retention settings; refresh")
    store=deepcopy(lab.enterprise_archive);store["limit"]=new;trim(store);lab.enterprise_archive=store
    return {"limit":new,"retained":len(store["entries"]),"evicted":store["evicted"]}

def load(raw,current):
    from .enterprise_training import load as load_run
    if raw is None:
        store=defaults()
        if completed(current):append(store,current,None)
        return store
    if not isinstance(raw,dict) or set(raw)!=set(defaults()) or type(raw["version"]) is not int or raw["version"]!=1:
        raise LabError("invalid enterprise archive")
    cap=limit(raw["limit"]);entries=raw["entries"]
    if not isinstance(entries,list) or len(entries)>cap:raise LabError("invalid enterprise archive capacity")
    if type(raw["evicted"]) is not int or type(raw["next_sequence"]) is not int or not 0<=raw["evicted"]<10**9 or not 1<=raw["next_sequence"]<=10**9 or raw["next_sequence"]!=raw["evicted"]+len(entries)+1:
        raise LabError("invalid enterprise archive counters")
    seen=set()
    for seq,e in enumerate(entries,raw["evicted"]+1):
        if not isinstance(e,dict) or set(e)!={"sequence","completed_at","run"} or type(e["sequence"]) is not int or e["sequence"]!=seq:
            raise LabError("invalid enterprise archive entry")
        ts=e["completed_at"]
        if ts is not None:
            if not isinstance(ts,str) or not re.fullmatch(r"\d{4}-\d{2}-\d{2}T\d{2}:\d{2}:\d{2}\+00:00",ts):raise LabError("invalid completion timestamp")
            try:datetime.fromisoformat(ts)
            except ValueError as exc:raise LabError("invalid completion timestamp") from exc
        run=load_run(e["run"])
        if not completed(run) or run["run_id"] in seen:raise LabError("invalid archived enterprise run")
        seen.add(run["run_id"])
        if current and run["run_id"]==current["run_id"] and (run!=current or not completed(current)):
            raise LabError("archived run conflicts with active attempt")
    if completed(current) and (not entries or entries[-1]["run"]!=current):
        raise LabError("completed enterprise assessment is missing from archive")
    return deepcopy(raw)

def progress(lab):
    from .enterprise_assessment import assessment
    from . import enterprise_resilience as resilience
    store=lab.enterprise_archive;rows=[]
    for entry in store["entries"]:
        run=entry["run"];cfg=run["config"]
        grade=(resilience.assessment(run["steps"],run["observations"]) if run["version"]==3 else assessment(run["steps"],None,run["observations"]))["score"]
        rows.append({"run_id":run["run_id"],"sequence":entry["sequence"],"completed_at":entry["completed_at"],
                     "template":resilience.TEMPLATE if run["version"]==3 else "enterprise-dns-availability","version":run["version"],"config":deepcopy(cfg),
                     "points":grade["points"],"maximum":grade["maximum"],"criteria":grade["criteria"]})
    def groupkey(r):
        return r["template"],r["version"],r["config"]["departments"],r["config"]["hosts_per_department"]
    groups=[]
    for key in sorted({groupkey(r) for r in rows}):
        items=[r for r in rows if groupkey(r)==key];first,last=items[0],items[-1]
        criteria=[]
        for a,b in zip(first["criteria"],last["criteria"]):
            criteria.append({"id":a["id"],"first_met":a["met"],"latest_met":b["met"],
                             "change":b["points"]*(int(b["met"])-int(a["met"])),
                             "met_count":sum(next(c["met"] for c in r["criteria"] if c["id"]==a["id"]) for r in items)})
        groups.append({"template":key[0],"version":key[1],"config":deepcopy(first["config"]),
                       "completed":len(items),"first":first["points"],"latest":last["points"],
                       "best":max(r["points"] for r in items),"change":last["points"]-first["points"],"criteria":criteria})
    return {"ok":True,"version":1,"limit":store["limit"],"minimum_limit":1,"maximum_limit":MAX_LIMIT,
            "retained":len(rows),"evicted":store["evicted"],"attempts":rows,"groups":groups,
            "scope":"Retained completed assessments only; compare matching template, configuration and rubric version. Sequence is completion order, not wall-clock ordering."}

def report(lab,run_id):
    from .enterprise_training import report_run
    if not isinstance(run_id,str) or not re.fullmatch("[a-f0-9]{32}",run_id):raise LabError("invalid enterprise report ID")
    entry=next((e for e in lab.enterprise_archive["entries"] if e["run"]["run_id"]==run_id),None)
    if entry is None:raise LabError("archived enterprise report not found")
    return {"ok":True,"sequence":entry["sequence"],"completed_at":entry["completed_at"],"report":report_run(entry["run"])}

# Cyber range roadmap

Phase 1 (implemented): deterministic routed enterprise topology generator, synthetic incident case
fixtures, SOC objectives, separate JSON exports, local agent endpoint and desktop/browser dialog.
Use the Cyber Range button, generate an exercise, download the topology and open it through the
normal import workflow. The generator does not overwrite the current topology or autosave.

Agent contract:
- GET /api/cyber-range/schema
- POST /api/cyber-range/generate with {"scenario":"account-anomaly","departments":3,"hosts_per_department":2}
- Response contains lab (native topology JSON) and case (inventory, synthetic events, objectives).
- Existing connectivity API can verify the generated topology after import. The case is not live telemetry.

## Defensive observability checkpoint (implemented)

The active lab records a bounded 256-entry SOC journal of completed IPv4/IPv6 connectivity
checks, modeled packet events, and completed scheduled operations. The journal is persisted in
native JSON labs; legacy labs start with an empty journal. Event IDs are independent of the
packet sequence, which can restart after power cycling. Simulation playback inspection does
not add duplicate observations. Full lab reset clears the journal; undo/redo restores snapshots.
No payload, URL path, or raw command/detail is copied into the SOC journal.

- GET /api/cyber-range/soc/schema
- GET /api/cyber-range/soc?kind=connectivity&outcome=failure (both filters optional)
- Toolbar: SOC → Refresh; filter by event kind and outcome, export JSON evidence.
- Alerts are derived from retained completed-operation failures; structured policy denials are
  informational, while other failures are availability review warnings. Neither establishes an attack.
- Packet events alone do not create alerts. Direct HTTP and other service operations currently
  contribute packet observations where supported, not universal operation-level alerts.
- Journal timestamps use simulator time, not wall clock. Multiple direct probes can share the
  same time. The journal is not immutable or tamper-evident; retention can evict prior alerts.
- The original exercise fixtures remain separate from this live modeled evidence view.

## Incident investigation checkpoint (implemented)

Completed failed modeled ICMP/ICMPv6 checks open availability cases. Repeated observations
for the same source, destination and protocol correlate into the active case; a policy-only
failure does not open a case. This is a correlation heuristic, not proof of root cause.
Cases preserve evidence snapshots independently of SOC journal eviction, including origin,
latest failure and notes' cited evidence. A success following the latest failure is a candidate
for explicit recovery verification; any new failure invalidates current acknowledgement and
recovery. Resolved cases remain read-only; a subsequent failure opens a new case.

Toolbar: Incidents → select case → acknowledge latest failure → add a note linked to an
observed event → restore benign network availability and run the same modeled check → refresh
→ verify observed recovery → resolve. The SOC view displays related case IDs and current
acknowledgement. Case JSON and scores are available through GET /api/cyber-range/incidents;
GET /api/cyber-range/incidents/schema describes POST /api/cyber-range/incidents/action.

Workflow score: 20 acknowledgement, 25 note citing latest failure, 35 verified later success,
20 resolution. It does not grade note correctness or prove sustained service availability.
Persistence follows native lab save/reset/undo. Limits: 24 cases, 32 retained observations per
case, 12 editable notes per case. Further case openings at capacity are counted, not silently
substituted; there is not yet an archive mechanism. Old unpinned observations may be evicted.
Only modeled observations are used; no external network activity or attack execution.

## Automated exercise runner (implemented)

Toolbar: Training. One guided template, interface availability, uses a fixed private three-device
NetworkLab: CLIENT → ACCESS → APP. The active topology, SOC journal, incident store and modeled
interfaces are not changed. No host networking, VM, external endpoint or attack activity is used.

Start automatically verifies baseline; introduce a modeled client interface outage, acknowledge
its incident, submit a structured diagnosis and evidence citations with an analyst note, restore
the interface, cite both new recovery observations, then complete/resolve. The runner checks
interface administrative state, actual modeled ICMP result and actual modeled HTTP response at
each of the three phases. HTTP failures do not invent a response code. Observations and the
private SOC journal are synthetic; recovery proves a point-in-time result only.

Assessment rubric (100 points): baseline pair 10, failed ICMP/HTTP pair 20, failed interface
state citation 15, diagnosis supported by the failed pair and interface evidence 20, acknowledgement
10, both recovery checks 20, completion 5. Incorrect but valid citations can reduce the score;
unknown event IDs and stale recovery evidence are rejected. Free-text notes are not graded.

GET /api/cyber-range/exercises returns the current state and provisional/final report;
GET /api/cyber-range/exercises/schema describes POST /api/cyber-range/exercises/action.
Actions other than start require current run_id and step. Restart explicitly replaces the current
attempt and assigns a fresh run ID. Export report JSON before restart to retain it separately.
Reports include run history, sandbox description, observations, assessment, SOC logs/alerts,
incident and criterion-level scoring. Action history and observed snapshots are saved in the native
lab and validated through deterministic version-1 replay; reads do not change the active lab.
Legacy labs have no active exercise. Reset and undo/redo follow native lab semantics.

## Exercise library and training progress (implemented)

The Training selector offers three version-2 templates: client interface outage, server interface
outage, and HTTP-only outage. The latter preserves ICMP connectivity and opens an HTTP-specific
incident from an explicit modeled service observation. All three operate exclusively in a private
fixed NetworkLab. The structured rubric requires correctly cited baseline, fault and component
observations; a successful ICMP check during an application outage is valid diagnostic evidence.

After restoration, the runner collects three healthy samples at offsets 0, 5 and 10 simulated
seconds. The analyst verifies the latest ICMP and HTTP evidence before completion. This is discrete
sampling, not continuous or wall-clock monitoring. Existing v1 saves and API starts without a
template retain point-in-time recovery and their original rubric. The UI explicitly selects v2.

Completed attempts are automatically archived in the lab as versioned replay histories and evidence
snapshots. GET /api/cyber-range/exercises/report?run_id=ID reconstructs a report from the retained
validated run. The Training dashboard lists attempts and groups best, first, latest and change by
template and rubric version. Retention is 12 completed attempts, oldest first eviction with a
visible count; export reports for long-term retention. Incomplete restarts are discarded. Legacy
completed saves are migrated into the archive. Archive follows native lab save/reset/undo semantics.

## Configurable enterprise training labs (implemented)

The Enterprise lab toolbar opens a private modeled availability exercise with 2-3 departments,
1-2 workstations per department, a core router, per-segment switches and a shared services subnet
containing DNS-SERVER and APP-SERVER. The largest configuration has 13 devices and 12 links.
All clients use the internal modeled DNS name portal.example.test; no external resolution or
traffic is performed. Routed subnet boundaries are not enforced security segmentation.

Baseline checks DNS resolution, named portal HTTP, direct application IP HTTP and application
ICMP from every workstation. A single modeled DNS-SERVER interface outage disrupts the named
portal while direct IP application checks remain healthy. Impact is derived from the before/after
observations and lists affected workstations and departments, with evidence IDs for the failed
shared dependency and per-client controls. Restoring the interface enables all checks again;
three recovery samples span ten simulated seconds. The report preserves phase evidence even
when older SOC journal entries are evicted. Cases are per-client HTTP observations, grouped under the dependency-scoped parent described below.

GET /api/cyber-range/enterprise returns the current report and stage; GET
/api/cyber-range/enterprise/schema describes POST /api/cyber-range/enterprise/action.
Start requires bounded config, subsequent actions use run_id and step. Restart replaces the
current enterprise run; export its JSON report first. This run is persisted independently of the
existing training archive, validated by deterministic replay, and follows lab reset/undo semantics.

## Enterprise incident correlation (implemented)

One parent incident is deterministically derived per enterprise run from the observed DNS
interface failure, each client's baseline and failed DNS/named HTTP checks, and the healthy
direct-IP application controls. It links the original client service cases by failure event ID,
retains their full phase snapshots independent of SOC retention, and labels matching retained
alerts. Parent state is open, recovering, recovery_verified, then closed on completion.
The recovery gate requires exactly the configured client set, distinct event identities, matching
source/destination and three healthy recovery samples per client over ten simulated seconds.
Missing, duplicated, stale or failed evidence and missing child cases block closure. The child
cases are marked recovered via the existing verification action; no analyst acknowledgement,
notes, or individual resolution is fabricated. Saved runs reconstruct the same parent ID from
the run ID and validated history, including legacy saved runs. Reports include parent and child
evidence. This is scenario-specific correlation, not general automatic root-cause attribution.

## Enterprise analyst assessment (implemented)

Enterprise lab starts/restarts assessment-mode runs by default in the UI; API clients select
mode=assessment explicitly on start/restart. Legacy version-1 saved runs and API starts without
a mode retain their original workflow. Version-2 history is validated by deterministic replay.

After the modeled DNS outage, acknowledge the parent with its shared failure event ID, submit
a diagnosis with component, DNS failure and healthy direct HTTP control references, select
affected clients/departments with baseline and failed portal evidence for each selected client,
and add a note linked to evidence. Restore and run the existing three-sample recovery checks.
Explicit resolution requires the latest dependency event plus matching latest DNS and named
HTTP success IDs for every affected client. Wrong but valid diagnostic/impact submissions are
graded, not silently corrected; a low score does not prevent evidence-verified operational
closure. Unknown IDs, incomplete recovery citations and out-of-order actions are rejected.

Score out of 100: acknowledgement 10, component evidence 10, DNS/control contrast 15,
supported diagnosis 15, client set 10, department set 10, per-client impact evidence 10,
fault-linked note 5, verified all-client recovery 10, explicit resolution 5. Free-text accuracy
and financial/business loss are not evaluated. Child cases retain separate analyst resolution
semantics. Assessment and citations persist in the versioned run and JSON report; completed
assessment runs enter the enterprise archive described below. Entirely modeled availability observations, no external network.

## Enterprise training archive (implemented)

Completed version-2 enterprise assessments automatically enter a persistent, per-lab archive.
Each entry retains the validated run history and all phase evidence, completion sequence and
UTC completion timestamp. Reports are reconstructed using the corresponding versioned
simulator/rubric, rather than storing an unvalidated score. Pre-archive completed assessments
migrate with an unknown completion date; unfinished or unscored legacy runs are not archived.
The archive is separate from the existing basic exercise archive, but both are available in
the Training dashboard, which also links to the Enterprise lab and back.

Default retention is 12 completed enterprise assessments, configurable from 1 to 24. Lowering
the cap or adding new reports at capacity evicts the oldest completed reports and increments
a visible counter; increasing retention does not recover evicted entries. Native lab save/load
and undo/redo preserve history and settings. Full reset clears the per-lab archive. Export
reports for long-term retention. Progress compares first/latest/best and change only within
matching scenario, topology configuration and rubric version, including per-criterion change
and success frequency. These statistics describe retained attempts, not lifetime performance.

GET /api/cyber-range/enterprise/archive returns progress and retention settings.
GET /api/cyber-range/enterprise/report?run_id=ID reconstructs one completed report with its
archive metadata. POST /api/cyber-range/enterprise/action accepts
{"action":"set_retention","limit":12,"expected_limit":12}; stale settings are rejected.
The existing basic training API schema links to enterprise training and archive endpoints.
No external network, host fault injection or real security activity is involved.

## Enterprise resilience simulation (implemented)

Select Redundant DNS resilience in Enterprise lab (API mode=resilience, version 3).
The private routed enterprise topology adds DNS-BACKUP with the same modeled portal
record. Every sample independently probes both resolvers through the simulator, chooses
primary if available and otherwise secondary, and performs a modeled hostname HTTP
request and direct application IP control. This is exercise-local ordered resolver selection,
not OS retry timing, client caching or general automatic failover configuration.

The deterministic availability sequence is baseline, primary outage with successful
fallback, both resolvers unavailable, partial recovery with only primary healthy, relapse
with both unavailable, restoration of both, and two more healthy samples separated by
at least five simulated seconds. Portal availability alone is not sufficient. The recovery
gate requires the complete client set, both resolvers, unique fresh evidence IDs, healthy
portal and direct controls, and three samples spanning at least ten simulated seconds.
Both resolvers share the services subnet; network-path redundancy is not modeled.

The rubric grades failover evidence (20), partial recovery evidence (15), relapse and
healthy app control (15), supported diagnosis (20), affected clients (10), dependency-linked
note (5), verified recovery (10), and explicit resolution (5). Resolution requires the latest
component IDs for both resolvers and matching DNS/portal evidence for every client.
Completed v3 reports enter the existing enterprise archive and are compared separately
from v2 availability assessments. Legacy runs remain unchanged. All faults are modeled;
no host network changes or real traffic occur.

Next milestones (not implemented):
1. Defensive segmentation and availability policy verification, including explicit intended
   connectivity boundaries, approved service access, and evidence-backed policy checks.
2. Additional resilience profiles and configurable recovery observation windows.
3. Provider-independent AI scenario planning: schema-constrained proposals, validation, preview,
   explicit approval for runtime actions and repeatable seeds.
4. Runtime abstraction for simulated, namespace, container and QEMU/KVM nodes. Begin with benign
   guest images on isolated virtual networks; no host bridging, default egress denial, resource
   quotas and lifecycle cleanup. Require explicit user opt-in and legally obtained guest images.
5. Collect actual guest telemetry (logs, network flow metadata) and correlate it with the topology.
6. Isolated security assessment exercises and public incident-inspired defensive training cases,
   using fictional organisations and sanitized data. Score detection, response and recovery.

Driver and kernel fidelity require full VMs rather than containers. No VM provisioning, real incident
replay, exploitation, SIEM ingestion or LLM provider integration is claimed in phase 1.

"""Deterministic, offline cyber-range exercises; no host/network execution."""
from .model import NetworkLab, LabError

TEMPLATES = {
    "account-anomaly": "Suspicious account activity",
    "service-outage": "Service availability incident",
}

def schema():
    return {"version": 1, "mode": "simulation-only",
            "templates": TEMPLATES.copy(),
            "input": {"scenario": "one of templates", "departments": "integer 1-3",
                      "hosts_per_department": "integer 1-4"},
            "endpoint": "POST /api/cyber-range/generate",
            "effects": "returns a new lab and synthetic case; never changes the active lab"}

def generate(options):
    if set(options) - {"scenario", "departments", "hosts_per_department"}:
        raise LabError("unknown cyber range option")
    scenario = options.get("scenario", "account-anomaly")
    if not isinstance(scenario, str) or scenario not in TEMPLATES:
        raise LabError("unknown scenario")
    departments = options.get("departments", 3)
    hosts = options.get("hosts_per_department", 2)
    if type(departments) is not int or not 1 <= departments <= 3:
        raise LabError("departments must be an integer from 1 to 3")
    if type(hosts) is not int or not 1 <= hosts <= 4:
        raise LabError("hosts_per_department must be an integer from 1 to 4")
    lab = NetworkLab()
    lab.add_device("router", "CORE", 420, 45)
    inventory = []
    for i in range(departments + 1):
        server_zone = i == departments
        zone = "SERVICES" if server_zone else ["IT", "FINANCE", "OPERATIONS"][i]
        switch = zone + "-SW"
        prefix = "10.77." + str(i + 1)
        x = 60 + i * 260
        lab.add_device("switch", switch, x + 65, 175)
        lab.connect("CORE", "g0/" + str(i), switch, "g0/1")
        lab.set_ip("CORE", "g0/" + str(i), prefix + ".1/24")
        for j in range(2 if server_zone else hosts):
            name = ["APP-SERVER", "LOG-SERVER"][j] if server_zone else zone + "-PC" + str(j + 1)
            address = prefix + "." + str(j + 10)
            lab.add_device("server" if server_zone else "pc", name,
                           x + (j % 2) * 110, 290 + (j // 2) * 95)
            lab.connect(switch, "fa0/" + str(j + 1), name, "eth0")
            lab.set_ip(name, "eth0", address + "/24")
            lab.set_gateway(name, prefix + ".1")
            inventory.append({"device": name, "zone": zone, "ip": address})
    source = inventory[0]["device"]
    target = "APP-SERVER"
    address = next(item["ip"] for item in inventory if item["device"] == target)
    if scenario == "account-anomaly":
        rows = [
            (0, source, "endpoint", "info", "Normal workstation session started"),
            (20, target, "authentication", "warning", "Several rejected sign-in attempts recorded"),
            (35, target, "authentication", "warning", "Sign-in accepted outside expected activity window"),
            (42, "LOG-SERVER", "monitor", "high", "Authentication anomaly flagged for review"),
            (65, target, "application", "info", "Service remains available"),
        ]
        objectives = ["Build an incident timeline using event IDs.",
                      "Identify the affected service and distinguish observations from hypotheses.",
                      "Propose proportionate containment and evidence-preservation steps."]
    else:
        rows = [
            (0, target, "monitor", "info", "Application health check passed"),
            (18, target, "application", "warning", "Service health degraded"),
            (30, source, "endpoint", "warning", "Application response timed out"),
            (45, "LOG-SERVER", "monitor", "high", "Service availability alert"),
            (70, "CORE", "network", "info", "Router interface health normal"),
        ]
        objectives = ["Identify the affected service and earliest observable symptom.",
                      "Separate application availability from network connectivity.",
                      "Propose recovery checks and document remaining uncertainty."]
    events = [{"id": "E%03d" % (i + 1), "offset_seconds": row[0], "device": row[1],
               "source": row[2], "severity": row[3], "message": row[4], "synthetic": True}
              for i, row in enumerate(rows)]
    return {"ok": True, "mode": "simulation-only", "lab": lab.to_dict(),
            "case": {"scenario": scenario, "title": TEMPLATES[scenario],
                     "evidence_type": "synthetic_fixture", "inventory": inventory,
                     "events": events, "objectives": objectives,
                     "baseline_check": {"source": source, "destination_ip": address,
                                        "description": "Verify routed connectivity in the generated lab."},
                     "limitations": ["Evidence is prewritten and is not captured from actual packets or processes.",
                                     "The lab has routed segments but no enforced security segmentation.",
                                     "No real OS, attack traffic, external targets or AI provider is invoked."]}}

"""Local learning-activity metadata and explicitly limited compatibility checks.

This is NOT the proprietary Packet Tracer Activity Wizard scorer. Never store
the plaintext teacher answer network or assessment XML in a converted lab.
"""
from __future__ import annotations

from copy import deepcopy
import hashlib
import json

from .model import LabError

FIELDS = {"ip", "ipv6", "admin_up", "mode", "access_vlan", "native_vlan",
          "default_gateway", "ospf_enabled", "vlans", "routes"}
MAX_PAGES = 48
MAX_CHECKS = 2000

def _fingerprint(value):
    return hashlib.sha256(json.dumps(value, sort_keys=True,
                                    separators=(",", ":"), default=str).encode("utf-8")).hexdigest()

def _current(device, field, interface=None):
    if field == "default_gateway":
        return device.default_gateway
    if field == "ospf_enabled":
        return device.ospf_enabled
    if field == "vlans":
        return sorted(device.vlans)
    if field == "routes":
        return sorted((r.network, r.next_hop, r.interface)
                      for r in device.routes if r.source == "static")
    port = device.interfaces.get(interface or "")
    if port is None or field not in FIELDS:
        raise ValueError("Unknown interface or field")
    return getattr(port, field)

def build_checks(initial, answer):
    """Only compare fields represented by our simulator, not the vendor rubric."""
    checks = []
    for name, expected in answer.devices.items():
        before = initial.devices.get(name)
        if before is None:
            continue
        for field in ("default_gateway", "ospf_enabled", "vlans", "routes"):
            actual = _current(before, field)
            wanted = _current(expected, field)
            if actual != wanted and wanted not in (None, [], False):
                checks.append({"device": name, "field": field,
                               "expected_sha256": _fingerprint(wanted)})
        for port_name, port in expected.interfaces.items():
            if port_name not in before.interfaces:
                continue
            for field in ("ip", "ipv6", "admin_up", "mode", "access_vlan", "native_vlan"):
                actual = _current(before, field, port_name)
                wanted = _current(expected, field, port_name)
                if actual != wanted and (wanted is not None):
                    checks.append({"device": name, "interface": port_name,
                                   "field": field, "expected_sha256": _fingerprint(wanted)})
    return checks[:MAX_CHECKS]

def validate_activity(obj):
    if obj is None:
        return None
    if not isinstance(obj, dict):
        raise LabError("Activity metadata must be an object")
    if obj.get("type") != "imported_pka":
        raise LabError("Unknown activity type")
    title = obj.get("title", "")
    version = obj.get("source_version", "")
    if not isinstance(title, str) or len(title) > 180:
        raise LabError("Invalid activity title")
    if not isinstance(version, str) or len(version) > 80:
        raise LabError("Invalid source activity version")
    pages = obj.get("pages", [])
    if not isinstance(pages, list) or len(pages) > MAX_PAGES:
        raise LabError("Too many activity instruction pages")
    clean_pages = []
    total = 0
    for page in pages:
        if not isinstance(page, dict):
            raise LabError("Invalid activity page")
        heading, text = page.get("title"), page.get("text")
        if not isinstance(heading, str) or len(heading) > 160:
            raise LabError("Invalid instruction page heading")
        if not isinstance(text, str) or len(text) > 100_000:
            raise LabError("Invalid instruction text")
        total += len(text)
        clean_pages.append({"title": heading, "text": text})
    if total > 500_000:
        raise LabError("Instruction set exceeds supported size")
    done = obj.get("completed_pages", [])
    if not isinstance(done, list) or any(type(n) is not int or n < 0 or n >= len(pages) for n in done):
        raise LabError("Invalid completed activity pages")
    checks = obj.get("checks", [])
    if not isinstance(checks, list) or len(checks) > MAX_CHECKS:
        raise LabError("Invalid supported activity checks")
    validated = []
    for item in checks:
        if not isinstance(item, dict):
            raise LabError("Invalid assessment check")
        name = item.get("device")
        field = item.get("field")
        interface = item.get("interface")
        signature = item.get("expected_sha256")
        if (not isinstance(name, str) or len(name) > 64 or field not in FIELDS or
                (interface is not None and (not isinstance(interface, str) or len(interface) > 64)) or
                not isinstance(signature, str) or len(signature) != 64 or
                any(c not in "0123456789abcdef" for c in signature)):
            raise LabError("Invalid activity assessment item")
        validated.append({"device": name, "field": field,
                          **({"interface": interface} if interface is not None else {}),
                          "expected_sha256": signature})
    total_criteria = obj.get("vendor_criterion_count", 0)
    if type(total_criteria) is not int or not 0 <= total_criteria <= 500_000:
        raise LabError("Invalid criterion count")
    return {"type": "imported_pka", "title": title, "source_version": version,
            "pages": clean_pages, "completed_pages": sorted(set(done)),
            "checks": validated, "vendor_criterion_count": total_criteria}

def progress(lab):
    activity = lab.activity
    if not activity:
        return None
    passed, unresolved = 0, 0
    for check in activity["checks"]:
        d = lab.devices.get(check["device"])
        if not d:
            unresolved += 1
            continue
        try:
            if _fingerprint(_current(d, check["field"], check.get("interface"))) == check["expected_sha256"]:
                passed += 1
        except ValueError:
            unresolved += 1
    return {"title": activity["title"], "source_version": activity["source_version"],
            "pages": deepcopy(activity["pages"]),
            "completed_pages": list(activity["completed_pages"]),
            "reviewed_pages": len(activity["completed_pages"]),
            "total_pages": len(activity["pages"]),
            "supported_checks": len(activity["checks"]),
            "supported_passed": passed, "supported_unavailable": unresolved,
            "vendor_criterion_count": activity["vendor_criterion_count"],
            "grading": "Partial independent comparison of supported IP/interface/routing fields; not official Packet Tracer activity grading."}

"""Defensive parent incident lifecycle and fail-closed evidence checks."""
import unittest
from copy import deepcopy
from netsim.model import NetworkLab, LabError
from netsim.enterprise_training import action, view, replay, FLOW
from netsim.enterprise_correlation import correlation

CFG={"departments":3,"hosts_per_department":2}

class ParentIncidentTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.sandbox,cls.inventory,cls.checks=replay(CFG,list(FLOW))
        cls.cases=cls.sandbox.incident_cases["cases"]

    def test_complete_evidence_and_children(self):
        p=correlation(self.inventory,self.checks,self.cases,"example","completed")
        self.assertEqual(p["status"],"closed")
        self.assertEqual(p["affected_clients"],6)
        self.assertEqual(p["verified_clients"],6)
        self.assertEqual(p["recovery_span_simulated_seconds"],10)
        self.assertEqual(len(set(p["child_case_ids"])),6)
        self.assertTrue(p["closure_ready"])
        self.assertEqual(p["fault_event_id"],self.checks["fault"]["component"]["id"])
        for child in p["children"]:
            self.assertEqual(child["parent_id"],p["id"])
            self.assertEqual(len(child["recovery_samples"]),3)
            self.assertTrue(all(s["healthy"] for s in child["recovery_samples"]))
            self.assertEqual(set(child["evidence"]),set(self.checks))
            for phase,rows in self.checks.items():
                expected=next(x for x in rows["clients"] if x["client"]==child["client"])
                self.assertEqual(child["evidence"][phase],expected)
            case=next(c for c in self.cases if c["id"]==child["case_id"])
            self.assertEqual(case["status"],"recovered")
        retained={e["id"] for e in self.sandbox.defensive_soc["logs"]}
        self.assertTrue(any(c["failure_event_id"] not in retained for c in p["children"]))

    def test_closure_rejects_incomplete_or_failed_client_evidence(self):
        variants=[]
        for phase in ("recovery","recovery_5s","recovery_10s"):
            c=deepcopy(self.checks);c.pop(phase);variants.append(c)
        c=deepcopy(self.checks);c["recovery_10s"]["clients"].pop();variants.append(c)
        c=deepcopy(self.checks);c["recovery_10s"]["clients"][-1]=c["recovery_10s"]["clients"][0];variants.append(c)
        for kind in ("dns","named_http","direct_http","app_icmp"):
            c=deepcopy(self.checks);row=c["recovery_10s"]["clients"][0]
            e=row[kind]["event"] if kind.endswith("http") else row[kind]
            e["outcome"]="failure";variants.append(c)
        c=deepcopy(self.checks);c["recovery_10s"]["clients"][0]["resolved_ip"]="10.0.0.1";variants.append(c)
        c=deepcopy(self.checks);c["recovery_10s"]["clients"][0]["named_http"]["http_status"]=503;variants.append(c)
        c=deepcopy(self.checks);c["recovery_10s"]["component"]["sim_time"]=c["recovery"]["component"]["sim_time"];variants.append(c)
        c=deepcopy(self.checks);c["fault"]["component"]["source"]="APP-SERVER";variants.append(c)
        c=deepcopy(self.checks);c["recovery_10s"]["clients"][0]["dns"]["id"]=c["recovery_5s"]["clients"][0]["dns"]["id"];variants.append(c)
        c=deepcopy(self.checks);c["recovery_10s"]["component"]["source"]="APP-SERVER";variants.append(c)
        c=deepcopy(self.checks);c["recovery_10s"]["clients"][0]["app_icmp"]["destination"]="10.0.0.1";variants.append(c)
        for i,c in enumerate(variants):
            with self.subTest(i=i),self.assertRaises(LabError):
                correlation(self.inventory,c,self.cases,"example","completed")

    def test_missing_case_and_mismatched_recovery_rejected(self):
        for cases in (self.cases[:-1],self.cases+[deepcopy(self.cases[0])]):
            with self.assertRaises(LabError):
                correlation(self.inventory,self.checks,cases,"example","completed")
        cases=deepcopy(self.cases);cases[0]["evidence"]=cases[0]["evidence"][:1]
        with self.assertRaises(LabError):
            correlation(self.inventory,self.checks,cases,"example","completed")

    def test_lifecycle_and_restart(self):
        lab=NetworkLab();action(lab,{"action":"start","config":CFG})
        v=view(lab);self.assertIsNone(v["report"]["parent_incident"])
        def advance(op):
            nonlocal v
            action(lab,{"action":op,"run_id":v["run_id"],"step":v["step"]});v=view(lab)
        advance("inject_fault");p=v["report"]["parent_incident"];pid=p["id"]
        self.assertEqual(p["status"],"open")
        self.assertTrue(all(a["parent_id"]==pid for a in v["report"]["soc"]["alerts"] if a["event_id"]==p["fault_event_id"]))
        advance("restore");p=v["report"]["parent_incident"]
        self.assertEqual(p["status"],"recovering");self.assertFalse(p["closure_ready"])
        before=lab.to_dict()
        with self.assertRaises(LabError):advance("complete")
        self.assertEqual(lab.to_dict(),before)
        advance("verify_recovery");self.assertEqual(v["report"]["parent_incident"]["status"],"recovery_verified")
        advance("complete");self.assertEqual(v["report"]["parent_incident"]["status"],"closed")
        self.assertEqual(v["report"]["parent_incident"]["id"],pid)
        self.assertTrue(all(c["parent_id"]==pid for c in v["report"]["incidents"]["cases"]))
        action(lab,{"action":"restart","run_id":v["run_id"],"step":v["step"],"config":CFG})
        v=view(lab);self.assertIsNone(v["report"]["parent_incident"])
        advance("inject_fault");self.assertNotEqual(v["report"]["parent_incident"]["id"],pid)

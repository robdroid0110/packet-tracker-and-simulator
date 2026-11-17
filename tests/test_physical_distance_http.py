"""Isolated HTTP contract tests for Physical Distance Measurements."""
import json,tempfile,threading,unittest
from http.server import ThreadingHTTPServer
from pathlib import Path
from urllib.request import Request,urlopen
from urllib.error import HTTPError

from netsim.model import NetworkLab
from netsim.cli import CommandProcessor


class PhysicalDistanceHttpTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.temp=tempfile.TemporaryDirectory(prefix="pt17-physics-http-")
        import server as app
        cls.app=app
        cls.backup=(app.LAB,app.PROC,app.STATE,app.BACKUPS)
        app.STATE=Path(cls.temp.name)/"state.json"
        app.BACKUPS=Path(cls.temp.name)/"backups"
        app.LAB=NetworkLab()
        app.PROC=CommandProcessor(app.LAB)
        class Quiet(app.Handler):
            def log_message(self,*args):pass
        cls.http=ThreadingHTTPServer(("127.0.0.1",0),Quiet)
        cls.port=cls.http.server_address[1]
        cls.thread=threading.Thread(target=cls.http.serve_forever,daemon=True)
        cls.thread.start()

    @classmethod
    def tearDownClass(cls):
        cls.http.shutdown();cls.http.server_close();cls.thread.join(timeout=5)
        cls.app.LAB,cls.app.PROC,cls.app.STATE,cls.app.BACKUPS=cls.backup
        cls.temp.cleanup()

    def setUp(self):
        with self.app.LOCK:
            self.app.LAB=NetworkLab()
            self.app.PROC=CommandProcessor(self.app.LAB)
            self.app.STATE.unlink(missing_ok=True)

    def request(self,path,payload=None):
        url=f"http://127.0.0.1:{self.port}"+path
        req=Request(url) if payload is None else Request(
            url,data=json.dumps(payload).encode(),headers={"content-type":"application/json"})
        try:
            with urlopen(req,timeout=5) as reply:return reply.status,json.load(reply)
        except HTTPError as err:
            try:return err.code,json.load(err)
            finally:err.close()

    def command(self,cmd):
        status,result=self.request("/api/command",{"command":cmd})
        self.assertTrue(result["ok"],(cmd,result))
        return result

    def setup_cable(self):
        for cmd in [
            "add pc PC1","add pc PC2",
            "physical place PC1 city0","physical place PC2 city0",
            "physical device-position PC1 100 100",
            "physical device-position PC2 120 100",
            "connect PC1 eth0 PC2 eth0"]:
            self.command(cmd)

    def test_read_and_schema(self):
        status,result=self.request("/api/physical-distance/schema")
        self.assertEqual(status,200)
        self.assertEqual(result["write"]["path"],"/api/physical-distance/action")
        status,result=self.request("/api/physical-distance?location=city0")
        self.assertEqual(status,200)
        self.assertTrue(result["ok"])
        self.assertEqual(result["ethernet_limit_m"],100)
        self.assertFalse(result["cable_length_effects"])
        self.assertEqual(result["geometry"]["width_m"],5000)

    def test_cable_turns_down_and_recovers_by_api(self):
        self.setup_cable()
        status,result=self.request("/api/physical-distance?source=PC1&target=PC2")
        self.assertEqual(status,200)
        self.assertEqual(result["distance_m"],100)
        status,result=self.request("/api/physical-distance?device=PC1&interface=eth0")
        self.assertEqual(status,200)
        self.assertEqual(result["total_length_m"],100)
        self.assertTrue(result["up"])
        status,result=self.request("/api/physical-distance/action",{"action":"cable_effects","enabled":True})
        self.assertEqual(status,200)
        self.assertTrue(result["state"]["cable_length_effects"])
        self.command("physical device-position PC2 121 100")
        status,result=self.request("/api/physical-distance?device=PC1&interface=eth0")
        self.assertEqual(status,200)
        self.assertEqual(result["distance_m"],105)
        self.assertFalse(result["up"])
        self.assertEqual(result["reason"],"cable length exceeds 100m")
        status,result=self.request("/api/physical-distance/action",{"action":"cable_effects","enabled":False})
        self.assertEqual(status,200)
        self.assertTrue(result["state"]["links"][0]["up"])
        self.assertTrue(self.app.STATE.is_file())
        self.assertFalse(json.loads(self.app.STATE.read_text())["cable_length_effects"])

    def test_radio_catalog_coverage_and_range_edit(self):
        self.command("add-model AccessPoint-PT AP1")
        self.command('add-model "Cell Tower" Tower1')
        self.command("add-model SMARTPHONE-PT Phone1")
        for name in ("AP1","Tower1","Phone1"):
            self.command("physical place "+name+" city0")
        status,result=self.request("/api/physical-distance?location=city0")
        self.assertEqual(status,200)
        radii={r["device"]:r["radius_m"] for r in result["radios"]}
        self.assertEqual(radii["AP1"],140)
        self.assertEqual(radii["Tower1"],1000)
        self.assertTrue(any(pair["medium"]=="wifi" for pair in result["radio_pairs"]))
        status,result=self.request("/api/physical-distance/action",
                                   {"action":"radio_range","device":"AP1","radius_m":240.0})
        self.assertEqual(status,200)
        self.assertEqual(result["state"]["radio_ranges"]["AP1"],240)
        status,result=self.request("/api/physical-distance/action",{"action":"undo"})
        self.assertEqual(status,200)
        self.assertNotIn("AP1",result["state"]["radio_ranges"])

    def test_invalid_api_keeps_saved_state(self):
        self.setup_cable()
        before=self.app.LAB.to_dict()
        for body in [
            {"action":"cable_effects","enabled":"yes"},
            {"action":"radio_range","device":"PC1","radius_m":140},
            {"action":"radio_range","device":"missing","radius_m":140},
            {"action":"radio_range","device":"PC1","radius_m":float("inf")},
            {"action":"radio_range","device":"PC1","radius_m":-1},
            {"action":"unknown"},
        ]:
            with self.subTest(body=body):
                status,response=self.request("/api/physical-distance/action",body)
                self.assertEqual(status,400)
                self.assertFalse(response["ok"])
                self.assertEqual(self.app.LAB.to_dict(),before)
        for suffix in ["?source=PC1","?source=PC1&target=missing",
                       "?device=PC1","?device=PC1&interface=g0/0",
                       "?location=missing"]:
            with self.subTest(suffix=suffix):
                status,response=self.request("/api/physical-distance"+suffix)
                self.assertEqual(status,400)
                self.assertFalse(response["ok"])

    def test_capability_registry(self):
        status,cap=self.request("/api/capabilities")
        self.assertEqual(status,200)
        names={a["id"] for a in cap["actions"]}
        for ident in ("physical_distance.measure","physical_distance.link",
                      "physical_distance.coverage","physical_distance.config",
                      "physical_distance.schema"):
            self.assertIn(ident,names)

if __name__=="__main__":unittest.main()

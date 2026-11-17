"""Isolated HTTP contract tests for legacy simulator Industrial Control Panels (§20)."""
from __future__ import annotations
import json,threading,tempfile,unittest
from http.server import ThreadingHTTPServer
from pathlib import Path
from urllib.request import Request,urlopen
from urllib.error import HTTPError
from netsim.model import NetworkLab
from netsim.cli import CommandProcessor

class IcpHTTPTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        import server
        cls.app=server
        cls.temp=tempfile.TemporaryDirectory(prefix="pt20-http-")
        cls.original=(server.LAB,server.PROC,server.STATE,server.BACKUPS)
        server.LAB=NetworkLab()
        server.PROC=CommandProcessor(server.LAB)
        server.STATE=Path(cls.temp.name)/"autosave.json"
        server.BACKUPS=Path(cls.temp.name)/"backups"
        class Quiet(server.Handler):
            def log_message(self,*args):pass
        cls.http=ThreadingHTTPServer(("127.0.0.1",0),Quiet)
        cls.port=cls.http.server_address[1]
        cls.thread=threading.Thread(target=cls.http.serve_forever,daemon=True)
        cls.thread.start()
    @classmethod
    def tearDownClass(cls):
        cls.http.shutdown();cls.http.server_close();cls.thread.join(timeout=5)
        cls.app.LAB,cls.app.PROC,cls.app.STATE,cls.app.BACKUPS=cls.original
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
            with urlopen(req,timeout=6) as response:return response.status,json.load(response)
        except HTTPError as exc:
            try:return exc.code,json.load(exc)
            finally:exc.close()
    def post(self,**payload):
        return self.request("/api/icp/action",payload)
    def cli(self,command):
        status,response=self.request("/api/command",{"command":command})
        self.assertEqual(status,200,response)
        self.assertTrue(response["ok"],response)
        return response
    def create(self,size="medium"):
        status,response=self.post(action="create",name="Factory Panel",parent="building0",size=size)
        self.assertEqual(status,200,response)
        location=response["output"].split()[-1]
        self.assertIn(location,response["state"]["icp_panels"])
        return location

    def test_schema_and_discovery(self):
        status,response=self.request("/api/icp/schema")
        self.assertEqual(status,200)
        self.assertEqual(response["presets"]["small"]["width_m"],1.2)
        self.assertIn("device_move",response["write"]["actions"])
        self.assertIn("fixture_join",response["write"]["actions"])
        status,cap=self.request("/api/capabilities")
        ids={a["id"] for a in cap["actions"]}
        self.assertEqual(status,200)
        for action in ("icp.view","icp.schema","icp.edit"):self.assertIn(action,ids)
        status,response=self.request("/api/icp")
        self.assertEqual(status,400)
        self.assertFalse(response["ok"])

    def test_create_enter_door_preview_and_restore(self):
        loc=self.create("large")
        status,response=self.request("/api/icp?location="+loc)
        self.assertEqual(status,200)
        self.assertEqual(response["location_meta"]["type"],"icp")
        self.assertFalse(response["panel"]["door_closed"])
        self.assertEqual(response["devices"],[])
        status,response=self.post(action="preview",location=loc,enabled=True)
        self.assertEqual(status,200)
        self.assertTrue(response["state"]["icp_panels"][loc]["workspace_mode"])
        self.assertTrue(response["state"]["icp_panels"][loc]["door_closed"])
        status,response=self.post(action="door",location=loc,closed=False)
        self.assertEqual(status,200)
        self.assertFalse(response["state"]["icp_panels"][loc]["workspace_mode"])
        status,response=self.post(action="undo")
        self.assertEqual(status,200)
        self.assertTrue(response["state"]["icp_panels"][loc]["workspace_mode"])
        self.assertTrue(self.app.STATE.exists())
        fresh=NetworkLab();fresh.load(str(self.app.STATE))
        self.assertTrue(fresh.icp_panels[loc]["workspace_mode"])

    def test_add_devices_fixtures_and_mount_via_api(self):
        loc=self.create()
        self.cli("add router R1")
        self.cli("add pc PC1")
        self.cli("physical place R1 "+loc)
        self.cli("physical place PC1 "+loc)
        status,res=self.post(action="fixture_add",location=loc,kind="din",
                             orientation="horizontal",x=260,y=160)
        self.assertEqual(status,200,res)
        rail=res["output"].split()[-1]
        status,res=self.post(action="fixture_add",location=loc,kind="din",
                             orientation="horizontal",x=360,y=160)
        self.assertEqual(status,200,res)
        rail2=res["output"].split()[-1]
        status,res=self.post(action="fixture_join",location=loc,fixture=rail,other=rail2)
        self.assertEqual(status,200,res)
        group=res["output"].split()[-1]
        status,res=self.post(action="mount",device="R1",fixture=rail)
        self.assertEqual(status,200,res)
        status,res=self.post(action="device_move",device="PC1",side="door",x=97,y=108,anchor=2,detach=False)
        self.assertEqual(status,200,res)
        self.assertEqual(res["state"]["physical_device_details"]["PC1"]["surface"],"door")
        status,res=self.post(action="fixture_move",location=loc,fixture=rail,x=440,y=200,detach=False)
        self.assertEqual(status,200,res)
        status,res=self.request("/api/icp?location="+loc)
        self.assertEqual(status,200)
        rails={x["id"]:x for x in res["fixtures"]}
        self.assertEqual(rails[rail2]["group"],group)
        self.assertEqual(rails[rail2]["x"],540)
        r1=next(d for d in res["devices"] if d["device"]=="R1")
        self.assertEqual(r1["mount"],rail)
        self.assertEqual(r1["x"],440)
        pc=next(d for d in res["devices"] if d["device"]=="PC1")
        self.assertEqual(pc["side"],"door")
        status,res=self.post(action="fixture_split",location=loc,fixture=rail)
        self.assertEqual(status,200)
        status,res=self.post(action="unmount",device="R1")
        self.assertEqual(status,200)
        self.assertEqual(res["state"]["icp_panels"][loc]["mounts"],{})
        self.cli("connect PC1 eth0 R1 g0/0")
        self.assertEqual(len(self.app.LAB.links),1)

    def test_invalid_actions_do_not_mutate_state(self):
        loc=self.create()
        self.cli("add router R1")
        self.cli("physical place R1 "+loc)
        before=self.app.LAB.to_dict()
        for payload in (
            {"action":"create","size":"huge","name":"Bad","parent":"building0"},
            {"action":"create","size":"medium","name":"Bad","parent":loc},
            {"action":"door","location":loc,"closed":"true"},
            {"action":"device_move","device":"R1","side":"door","x":"bad","y":100},
            {"action":"device_move","device":"R1","side":"door","x":float("nan"),"y":100},
            {"action":"fixture_add","location":loc,"kind":"din","orientation":"vertical","x":50,"y":50},
            {"action":"fixture_join","location":loc,"fixture":"fixture0","other":"fixture1"},
            {"action":"mount","device":"R1","fixture":"fixture404"},
            {"action":"unmount","device":"R1"},
        ):
            with self.subTest(payload=payload):
                status,response=self.post(**payload)
                self.assertEqual(status,400,response)
                self.assertFalse(response["ok"])
                self.assertEqual(before,self.app.LAB.to_dict())
        for locid in ("city0","missing"):
            status,response=self.request("/api/icp?location="+locid)
            self.assertEqual(status,400)
            self.assertFalse(response["ok"])

    def test_readonly_preview_rejects_edits(self):
        loc=self.create()
        self.cli("add pc PC1")
        self.cli("physical place PC1 "+loc)
        self.post(action="preview",location=loc,enabled=True)
        prior=self.app.LAB.to_dict()
        status,r=self.post(action="device_move",device="PC1",side="door",x=80,y=120,anchor=0,detach=False)
        self.assertEqual(status,400)
        self.assertIn("read-only",r["output"])
        self.assertEqual(self.app.LAB.to_dict(),prior)
        status,r=self.post(action="preview",location=loc,enabled=False)
        self.assertEqual(status,200)
        status,r=self.post(action="device_move",device="PC1",side="door",x=80,y=120,anchor=0,detach=False)
        self.assertEqual(status,200)

if __name__=="__main__":unittest.main()

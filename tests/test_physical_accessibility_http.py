"""Section 21 accessible Physical Workspace: live isolated HTTP API tests."""
import json
import tempfile
import threading
import unittest
from http.server import ThreadingHTTPServer
from pathlib import Path
from urllib.request import Request,urlopen
from urllib.error import HTTPError

from netsim.model import NetworkLab
from netsim.cli import CommandProcessor

class AccessibilityHTTPTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        import server
        cls.app=server
        cls.temp=tempfile.TemporaryDirectory(prefix="pt21-")
        cls.previous=(server.LAB,server.PROC,server.STATE,server.BACKUPS)
        server.LAB=NetworkLab()
        server.PROC=CommandProcessor(server.LAB)
        server.STATE=Path(cls.temp.name)/"autosave.json"
        server.BACKUPS=Path(cls.temp.name)/"backups"
        class Quiet(server.Handler):
            def log_message(self,*args):pass
        cls.server=ThreadingHTTPServer(("127.0.0.1",0),Quiet)
        cls.port=cls.server.server_address[1]
        cls.thread=threading.Thread(target=cls.server.serve_forever,daemon=True)
        cls.thread.start()
    @classmethod
    def tearDownClass(cls):
        cls.server.shutdown();cls.server.server_close();cls.thread.join(timeout=5)
        cls.app.LAB,cls.app.PROC,cls.app.STATE,cls.app.BACKUPS=cls.previous
        cls.temp.cleanup()
    def setUp(self):
        with self.app.LOCK:
            self.app.LAB=NetworkLab()
            self.app.PROC=CommandProcessor(self.app.LAB)
            self.app.STATE.unlink(missing_ok=True)

    def request(self,path,body=None):
        url=f"http://127.0.0.1:{self.port}"+path
        r=Request(url) if body is None else Request(url,data=json.dumps(body).encode(),
            headers={"content-type":"application/json"})
        try:
            with urlopen(r,timeout=8) as response:return response.status,json.load(response)
        except HTTPError as error:
            try:return error.code,json.load(error)
            finally:error.close()
    def action(self,**body):return self.request("/api/physical-accessibility/action",body)
    def cmd(self,command):
        status,data=self.request("/api/command",{"command":command})
        self.assertEqual(status,200,data)
        return data

    def test_api_schema_and_discovery(self):
        status,contract=self.request("/api/physical-accessibility/schema")
        self.assertEqual(status,200)
        self.assertTrue(contract["ok"])
        self.assertIn("mount_device",contract["write"]["actions"])
        status,registry=self.request("/api/capabilities")
        self.assertEqual(status,200)
        ids={x["id"] for x in registry["actions"]}
        for item in ("physical_accessibility.view","physical_accessibility.schema",
                     "physical_accessibility.edit"):
            self.assertIn(item,ids)
        status,data=self.request("/api/physical-accessibility")
        self.assertEqual(status,200)
        self.assertEqual(data["tree"]["id"],"intercity")
        self.assertEqual(data["children"][0]["id"],"city0")

    def test_add_take_place_connect_and_undo(self):
        for name,kind in (("PC1","pc"),("R1","router")):
            code,result=self.action(action="add_device",model=kind,name=name,location="building0")
            self.assertEqual(code,200,result)
        code,origin=self.request("/api/physical-accessibility?location=building0")
        self.assertEqual(code,200)
        self.assertEqual(len(origin["devices"]),2)
        self.assertEqual(origin["links"],[])
        self.assertFalse(self.app.LAB.links)
        code,moved=self.action(action="move_device",device="R1",location="closet0")
        self.assertEqual(code,200,moved)
        code,mounted=self.action(action="mount_device",device="R1",surface="rack")
        self.assertEqual(code,200,mounted)
        code,view=self.request("/api/physical-accessibility?location=closet0")
        self.assertEqual(code,200)
        self.assertEqual(view["devices"][0]["surface"],"rack")
        code,cabled=self.action(action="connect",a_device="PC1",a_if="eth0",
                                b_device="R1",b_if="g0/0",cable="auto")
        self.assertEqual(code,200,cabled)
        self.assertEqual(len(self.app.LAB.links),1)
        status,pc=self.request("/api/physical-accessibility?location=building0")
        self.assertEqual(status,200)
        self.assertTrue(pc["devices"][0]["ports"][0]["connected"])
        self.assertEqual(pc["devices"][0]["ports"][0]["peer"]["device"],"R1")
        code,undo=self.action(action="undo")
        self.assertEqual(code,200,undo)
        self.assertFalse(self.app.LAB.links)
        code,redo=self.action(action="redo")
        self.assertEqual(code,200,redo)
        self.assertEqual(len(self.app.LAB.links),1)
        self.assertTrue(self.app.STATE.exists())
        saved=NetworkLab()
        saved.load(str(self.app.STATE))
        self.assertEqual(len(saved.links),1)
        self.assertEqual(saved.device_locations["R1"],"closet0")

    def test_invalid_requests_have_no_side_effects(self):
        self.action(action="add_device",model="pc",name="PC1",location="closet0")
        before=self.app.LAB.to_dict()
        attempts=[
            {"action":"mount_device","device":"PC1","surface":"cloud"},
            {"action":"move_device","device":"Missing","location":"closet0"},
            {"action":"add_device","model":"pc","name":"PC2","location":"missing"},
            {"action":"connect","a_device":"PC1","a_if":"eth0","b_device":"Nope","b_if":"eth0","cable":"auto"},
            {"action":"power","device":"PC1","enabled":"off"},
        ]
        for attempt in attempts:
            with self.subTest(attempt=attempt):
                code,response=self.action(**attempt)
                self.assertEqual(code,400,response)
                self.assertFalse(response["ok"])
                self.assertEqual(self.app.LAB.to_dict(),before)
        code,response=self.request("/api/physical-accessibility?location=unknown")
        self.assertEqual(code,400)
        self.assertFalse(response["ok"])

if __name__=="__main__":unittest.main()

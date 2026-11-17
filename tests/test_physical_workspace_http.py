"""Isolated end-to-end HTTP tests for the Physical Workspace API."""
import json
import os
import tempfile
import threading
import unittest
from http.server import ThreadingHTTPServer
from pathlib import Path
from urllib.error import HTTPError
from urllib.request import Request,urlopen

from netsim.model import NetworkLab
from netsim.cli import CommandProcessor


class PhysicalWorkspaceHttpTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.temp=tempfile.TemporaryDirectory(prefix="pt-physical-http-")
        import server as app
        cls.app=app
        cls.original=(app.LAB,app.PROC,app.STATE,app.BACKUPS)
        app.STATE=Path(cls.temp.name)/"lab.json"
        app.BACKUPS=Path(cls.temp.name)/"backups"
        app.LAB=NetworkLab()
        app.PROC=CommandProcessor(app.LAB)
        class QuietHandler(app.Handler):
            def log_message(self,*args):pass
        cls.web=ThreadingHTTPServer(("127.0.0.1",0),QuietHandler)
        cls.port=cls.web.server_address[1]
        cls.thread=threading.Thread(target=cls.web.serve_forever,daemon=True)
        cls.thread.start()

    @classmethod
    def tearDownClass(cls):
        cls.web.shutdown()
        cls.web.server_close()
        cls.thread.join(timeout=5)
        cls.app.LAB,cls.app.PROC,cls.app.STATE,cls.app.BACKUPS=cls.original
        cls.temp.cleanup()

    def setUp(self):
        with self.app.LOCK:
            self.app.LAB=NetworkLab()
            self.app.PROC=CommandProcessor(self.app.LAB)
            self.app.STATE.unlink(missing_ok=True)

    def request(self,path,payload=None):
        url=f"http://127.0.0.1:{self.port}"+path
        req=Request(url)
        if payload is not None:
            req=Request(url,data=json.dumps(payload).encode(),headers={"content-type":"application/json"})
        try:
            with urlopen(req,timeout=4) as response:return response.status,json.load(response)
        except HTTPError as err:
            try:return err.code,json.load(err)
            finally:err.close()

    def action(self,**payload):
        return self.request("/api/physical-workspace/action",payload)

    def test_schema_and_initial_view(self):
        status,initial=self.request("/api/physical-workspace")
        self.assertEqual(status,200)
        self.assertTrue(initial["ok"])
        self.assertEqual(initial["location"],"intercity")
        self.assertEqual([x["name"] for x in initial["children"]],["Home City"])
        status,closet=self.request("/api/physical-workspace?location=closet0")
        self.assertEqual(closet["current"]["height"],4)
        self.assertEqual(closet["shelves"],0)
        status,schema=self.request("/api/physical-workspace/schema")
        self.assertEqual(status,200)
        self.assertIn("resize_location",schema["write"]["actions"])
        self.assertIn("mount_device_shelf",schema["write"]["actions"])

    def test_create_relocate_resize_and_undo(self):
        status,result=self.action(action="add_location",kind="generic",name="Storage",parent="closet0")
        self.assertEqual(status,200,result)
        self.assertIn("loc0",result["state"]["physical_locations"])
        status,result=self.action(action="resize_location",location="loc0",width=8,length=7,height=2)
        self.assertEqual(result["state"]["physical_locations"]["loc0"]["width"],8)
        status,result=self.action(action="relocate_location",location="loc0",parent="building0")
        self.assertEqual(result["state"]["physical_locations"]["loc0"]["parent"],"building0")
        status,result=self.action(action="move_location",location="loc0",x=125,y=280)
        self.assertEqual(result["state"]["physical_locations"]["loc0"]["x"],125)
        status,result=self.action(action="undo")
        self.assertEqual(result["state"]["physical_locations"]["loc0"]["x"],28)
        status,result=self.action(action="redo")
        self.assertEqual(result["state"]["physical_locations"]["loc0"]["x"],125)
        self.assertTrue(self.app.STATE.exists())

    def test_device_mount_rules_and_persistent_location(self):
        self.request("/api/command",{"command":"add router R1"})
        status,result=self.action(action="place_device",device="R1",location="closet0")
        self.assertEqual(status,200)
        status,result=self.action(action="add_shelf",closet="closet0")
        self.assertEqual(status,200)
        status,result=self.action(action="mount_device",device="R1",surface="shelf",shelf=0)
        self.assertEqual(status,400)
        self.assertIn("powered-off",result["output"])
        self.request("/api/command",{"command":"power R1 off"})
        status,result=self.action(action="mount_device",device="R1",surface="shelf",shelf=0)
        self.assertEqual(status,200)
        self.assertEqual(result["state"]["physical_device_details"]["R1"]["surface"],"shelf")
        status,view=self.request("/api/physical-workspace?location=closet0")
        self.assertEqual(view["devices"][0]["surface"],"shelf")
        self.assertEqual(view["shelves"],1)
        _,power_result=self.request("/api/command",{"command":"power R1 on"})
        self.assertFalse(power_result["ok"])
        status,result=self.action(action="mount_device",device="R1",surface="rack")
        self.assertEqual(status,200)
        self.assertEqual(result["state"]["physical_device_details"]["R1"]["surface"],"rack")
        self.assertEqual(self.request("/api/command",{"command":"power R1 on"})[0],200)

    def test_atomic_device_creation_api_and_undo(self):
        status,result=self.action(action="add_device",model="pc-pt",name="PC3",
                                  x=200,y=160,location="city0",
                                  physical_x=350,physical_y=230)
        self.assertEqual(status,200,result)
        self.assertEqual(result["state"]["device_locations"]["PC3"],"city0")
        self.assertEqual(result["state"]["physical_device_details"]["PC3"]["x"],350)
        self.assertEqual(result["state"]["devices"]["PC3"]["x"],200)
        status,result=self.action(action="undo")
        self.assertEqual(status,200)
        self.assertNotIn("PC3",result["state"]["devices"])
        status,result=self.action(action="add_device",model="pc-pt",name="BAD",
                                  x=200,y=160,location="nonexistent")
        self.assertEqual(status,400)
        self.assertNotIn("BAD",self.app.LAB.devices)

    def test_navigation_tree_and_atomic_group_move_http(self):
        self.request("/api/command",{"command":"add router R1"})
        self.request("/api/command",{"command":"add router R2"})
        self.request("/api/command",{"command":"connect R1 g0/0 R2 g0/0"})
        status,created=self.action(action="add_location",kind="city",
                                   name="Remote",parent="intercity")
        self.assertEqual(status,200)
        ident="loc0"
        status,before=self.request("/api/physical-workspace/tree")
        self.assertEqual(status,200)
        self.assertEqual(before["device_count"],2)
        self.assertEqual(before["tree"]["children"][1]["name"],"Remote")
        status,moved=self.action(action="move_devices",devices=["R1","R2"],location=ident)
        self.assertEqual(status,200,moved)
        self.assertEqual(moved["state"]["device_locations"]["R1"],ident)
        self.assertEqual(moved["state"]["device_locations"]["R2"],ident)
        self.assertEqual(len(moved["state"]["links"]),1)
        status,tree=self.request("/api/physical-workspace/tree")
        self.assertEqual({d["name"] for d in tree["tree"]["children"][1]["devices"]},
                         {"R1","R2"})
        status,done=self.action(action="undo")
        self.assertEqual(status,200)
        self.assertEqual(done["state"]["device_locations"]["R1"],"closet0")
        self.assertEqual(done["state"]["device_locations"]["R2"],"closet0")
        self.assertTrue(self.app.STATE.exists())

    def test_move_error_does_not_change_saved_http_state(self):
        self.request("/api/command",{"command":"add router R1"})
        before=self.app.LAB.to_dict()
        for req in [
            {"action":"move_devices","devices":["R1","Missing"],"location":"city0"},
            {"action":"move_devices","devices":["R1","R1"],"location":"city0"},
            {"action":"move_devices","devices":["R1"],"location":"bad"},
        ]:
            with self.subTest(req=req):
                status,result=self.action(**req)
                self.assertEqual(status,400)
                self.assertFalse(result["ok"])
                self.assertEqual(before,self.app.LAB.to_dict())

    def test_bad_http_input_keeps_state(self):
        self.action(action="add_location",kind="generic",name="Storage",parent="closet0")
        invalid=[
            {"action":"resize_location","location":"loc0","width":float("inf"),"length":2,"height":2},
            {"action":"relocate_location","location":"city0","parent":"closet0"},
            {"action":"mount_device","device":"missing","surface":"shelf","shelf":0},
            {"action":"add_location","kind":"city","name":"Impossible","parent":"closet0"},
            {"action":"position_device","device":"missing","x":1,"y":1},
            {"action":"add_shelf","closet":"city0"},
            {"action":"missing"},
        ]
        before=self.app.LAB.to_dict()
        for payload in invalid:
            with self.subTest(payload=payload):
                status,response=self.action(**payload)
                self.assertEqual(status,400)
                self.assertFalse(response["ok"])
                self.assertEqual(before,self.app.LAB.to_dict())
        status,response=self.request("/api/physical-workspace?location=unknown")
        self.assertEqual(status,400)
        self.assertFalse(response["ok"])

    def test_agent_discovery(self):
        status,cap=self.request("/api/capabilities")
        self.assertEqual(status,200)
        names={item["id"] for item in cap["actions"]}
        self.assertTrue({"physical_workspace.read","physical_workspace.schema","physical_workspace.edit"}.issubset(names))


if __name__=="__main__":unittest.main()

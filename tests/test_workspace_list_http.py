"""Real HTTP contract tests on an isolated in-process loopback server.

This suite never starts or modifies the user's live Packet Tracker and Simulator instance.
"""
from __future__ import annotations
import json
import os
import tempfile
import threading
import unittest
from http.server import ThreadingHTTPServer
from pathlib import Path
from urllib.error import HTTPError
from urllib.request import Request, urlopen

from netsim.model import NetworkLab
from netsim.cli import CommandProcessor


class WorkspaceListHttpTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.temp=tempfile.TemporaryDirectory(prefix="pt-workspace-list-http-")
        original={k:os.environ.get(k) for k in ("PACKETTRACKER_STATE","PACKETTRACKER_BACKUPS")}
        os.environ["PACKETTRACKER_STATE"]=str(Path(cls.temp.name)/"lab.json")
        os.environ["PACKETTRACKER_BACKUPS"]=str(Path(cls.temp.name)/"backups")
        import server as app
        for k,old in original.items():
            if old is None:os.environ.pop(k,None)
            else:os.environ[k]=old
        cls.app=app
        cls.app.STATE=Path(cls.temp.name)/"lab.json"
        cls.app.BACKUPS=Path(cls.temp.name)/"backups"
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
        cls.temp.cleanup()

    def setUp(self):
        self.app.LAB=NetworkLab()
        self.app.PROC=CommandProcessor(self.app.LAB)
        self.app.STATE.unlink(missing_ok=True)

    def request(self,path,body=None):
        url=f"http://127.0.0.1:{self.port}"+path
        req=Request(url)
        if body is not None:
            req=Request(url,data=json.dumps(body).encode(),headers={"content-type":"application/json"})
        try:
            with urlopen(req,timeout=5) as r:return r.status,json.load(r)
        except HTTPError as e:
            try:return e.code,json.load(e)
            finally:e.close()

    def test_read_projection_and_schema(self):
        status,data=self.request("/api/workspace-list")
        self.assertEqual(status,200)
        self.assertEqual(data["devices"],[])
        self.assertEqual(data["links"],[])
        status,data=self.request("/api/workspace-list/schema")
        self.assertEqual(status,200)
        self.assertEqual(data["write"]["method"],"POST")
        self.assertIn("set_module",data["write"]["actions"])
        self.assertTrue({"auto","copper-straight","copper-cross","fiber-sm","serial-dce","console"} <= set(data["supported_cables"]))

    def test_device_position_power_module_via_typed_api(self):
        status,data=self.request("/api/workspace-list/action",{"action":"add_device","model":"router-pt","name":"R1","x":175,"y":215})
        self.assertEqual(status,200)
        self.assertIn("R1",data["state"]["devices"])
        status,data=self.request("/api/workspace-list/action",{"action":"move_device","device":"R1","x":260,"y":310})
        self.assertEqual(data["state"]["devices"]["R1"]["x"],260)
        status,data=self.request("/api/workspace-list/action",{"action":"set_module","device":"R1","slot":"slot0","module":"PT-ETH-1"})
        self.assertEqual(status,400)
        self.assertEqual(self.app.LAB.devices["R1"].modules,{})
        status,data=self.request("/api/workspace-list/action",{"action":"power_device","device":"R1","powered":False})
        self.assertEqual(status,200)
        status,data=self.request("/api/workspace-list/action",{"action":"set_module","device":"R1","slot":"slot0","module":"PT-ETH-1"})
        self.assertEqual(status,200)
        self.assertIn("m0/1",data["state"]["devices"]["R1"]["interfaces"])
        status,data=self.request("/api/workspace-list?device=R1")
        self.assertEqual(data["selected"]["slots"][1]["module"],"PT-ETH-1")
        self.assertTrue(self.app.STATE.is_file())

    def test_connect_disconnect_and_undo(self):
        for item in [
            {"action":"add_device","kind":"router","name":"R1","x":100,"y":100},
            {"action":"add_device","kind":"pc","name":"PC1","x":300,"y":100},
        ]:
            self.assertEqual(self.request("/api/workspace-list/action",item)[0],200)
        status,data=self.request("/api/workspace-list/action",{"action":"add_link","a_device":"R1","a_if":"g0/0","b_device":"PC1","b_if":"eth0","cable":"auto"})
        self.assertEqual(status,200)
        self.assertEqual(len(data["workspace"]["links"]),1)
        status,data=self.request("/api/workspace-list/action",{"action":"remove_link","device":"R1","iface":"g0/0"})
        self.assertEqual(status,200)
        self.assertEqual(len(data["workspace"]["links"]),0)
        status,data=self.request("/api/workspace-list/action",{"action":"undo"})
        self.assertEqual(status,200)
        self.assertEqual(len(data["workspace"]["links"]),1)
        status,data=self.request("/api/workspace-list/action",{"action":"redo"})
        self.assertEqual(status,200)
        self.assertEqual(len(data["workspace"]["links"]),0)

    def test_invalid_requests_are_400_and_no_mutation(self):
        cases=[
            {"action":"add_device","kind":"pc","name":"bad name","x":100,"y":100},
            {"action":"move_device","device":"PC1","x":"NaN","y":100},
            {"action":"power_device","device":"PC1","powered":"off"},
            {"action":"set_module","device":"PC1","slot":"slot0","module":"unsupported"},
            {"action":"add_device","kind":"pc","name":"PC1","x":100,"y":100,"cluster":["root"]},
            {"action":"add_device","kind":"pc","name":"PC1","x":100,"y":100,"cluster":"missing"},
        ]
        for item in cases:
            with self.subTest(item=item):
                status,data=self.request("/api/workspace-list/action",item)
                self.assertEqual(status,400)
                self.assertFalse(data["ok"])
                self.assertEqual(self.app.LAB.devices,{})
        status,data=self.request("/api/workspace-list?cluster=missing")
        self.assertEqual(status,400)

    def test_cluster_visibility_and_direct_position_update_undo(self):
        self.request("/api/workspace-list/action",{"action":"add_device","kind":"pc","name":"PC1","x":100,"y":200})
        self.request("/api/workspace-list/action",{"action":"add_device","kind":"pc","name":"PC2","x":300,"y":200})
        self.request("/api/command",{"command":"cluster add Lab PC1"})
        status,data=self.request("/api/workspace-list")
        self.assertEqual([d["name"] for d in data["devices"]],["PC2"])
        self.assertEqual(data["clusters"][0]["name"],"Lab")
        status,data=self.request("/api/workspace-list?cluster=Cluster0&device=PC1")
        self.assertEqual(status,200)
        self.assertEqual([d["name"] for d in data["devices"]],["PC1"])
        status,data=self.request("/api/state",{"device":"PC2","x":444,"y":250})
        self.assertEqual(status,200)
        self.assertEqual(data["state"]["devices"]["PC2"]["x"],444)
        self.request("/api/command",{"command":"undo"})
        self.assertEqual(self.app.LAB.devices["PC2"].x,300)

    def test_nested_cluster_creation_via_json_api(self):
        for cmd in ("add pc PC1 100 100","cluster add Branch PC1","cluster add Floor none Cluster0"):
            self.assertEqual(self.request("/api/command",{"command":cmd})[0],200)
        payload={"action":"add_device","model":"pc-pt","name":"PC2","x":210,"y":230,"cluster":"Cluster1"}
        status,data=self.request("/api/workspace-list/action",payload)
        self.assertEqual(status,200,data)
        self.assertEqual(data["workspace"]["cluster"],"Cluster1")
        self.assertEqual([d["name"] for d in data["workspace"]["devices"]],["PC2"])
        self.assertIn("PC2",data["state"]["clusters"]["Cluster1"]["devices"])
        self.assertEqual(self.request("/api/workspace-list/action",{"action":"undo"})[0],200)
        self.assertNotIn("PC2",self.app.LAB.devices)

    def test_capabilities_discovery(self):
        status,data=self.request("/api/capabilities")
        self.assertEqual(status,200)
        actions={a["id"] for a in data["actions"]}
        for ident in ("workspace_list.read","workspace_list.schema","workspace_list.edit","device.module"):
            self.assertIn(ident,actions)


if __name__=="__main__":
    unittest.main()

"""Live localhost API tests for Section 19, isolated from production state."""
import json,tempfile,threading,unittest
from http.server import ThreadingHTTPServer
from pathlib import Path
from urllib.request import Request,urlopen
from urllib.error import HTTPError

from netsim.model import NetworkLab
from netsim.cli import CommandProcessor

class CableHttpTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        import server as app
        cls.app=app;cls.tmp=tempfile.TemporaryDirectory(prefix="pt19-")
        cls.original=(app.LAB,app.PROC,app.STATE,app.BACKUPS)
        app.LAB=NetworkLab();app.PROC=CommandProcessor(app.LAB)
        app.STATE=Path(cls.tmp.name)/"lab.json"
        app.BACKUPS=Path(cls.tmp.name)/"backups"
        class Handler(app.Handler):
            def log_message(self,*args):pass
        cls.http=ThreadingHTTPServer(("127.0.0.1",0),Handler)
        cls.port=cls.http.server_address[1]
        cls.thread=threading.Thread(target=cls.http.serve_forever,daemon=True)
        cls.thread.start()

    @classmethod
    def tearDownClass(cls):
        cls.http.shutdown();cls.http.server_close();cls.thread.join(timeout=5)
        cls.app.LAB,cls.app.PROC,cls.app.STATE,cls.app.BACKUPS=cls.original
        cls.tmp.cleanup()

    def setUp(self):
        with self.app.LOCK:
            self.app.LAB=NetworkLab()
            self.app.PROC=CommandProcessor(self.app.LAB)
            self.app.STATE.unlink(missing_ok=True)

    def request(self,path,body=None):
        url=f"http://127.0.0.1:{self.port}"+path
        req=Request(url) if body is None else Request(url,
            data=json.dumps(body).encode(),headers={"content-type":"application/json"})
        try:
            with urlopen(req,timeout=6) as resp:return resp.status,json.load(resp)
        except HTTPError as err:
            try:return err.code,json.load(err)
            finally:err.close()

    def cmd(self,command):
        status,response=self.request("/api/command",{"command":command})
        self.assertTrue(response["ok"],response)
        return response

    def action(self,**body):
        return self.request("/api/physical-cables/action",body)

    def setup_cables(self):
        for cmd in ["add pc A","add pc B","add pc C","add pc D",
                    "physical place A city0","physical place B city0",
                    "physical place C city0","physical place D city0",
                    "physical device-position A 100 100","physical device-position B 120 100",
                    "physical device-position C 100 130","physical device-position D 120 130",
                    "connect A eth0 B eth0","connect C eth0 D eth0"]:
            self.cmd(cmd)

    def test_read_and_discovery(self):
        s,doc=self.request("/api/physical-cables/schema")
        self.assertEqual(s,200)
        self.assertIn("group_bends",doc["write"]["actions"])
        s,view=self.request("/api/physical-cables?location=city0")
        self.assertEqual(s,200)
        self.assertEqual(view["cables"],[])
        self.assertEqual(view["world_origin_m"]["x_m"],2800)
        s,cap=self.request("/api/capabilities")
        self.assertEqual(s,200)
        ids={item["id"] for item in cap["actions"]}
        for item in ("physical_cables.view","physical_cables.schema","physical_cables.edit"):
            self.assertIn(item,ids)

    def test_route_group_length_undo_color_and_survive_save(self):
        self.setup_cables()
        self.cmd("physical cable-effects on")
        s,view=self.request("/api/physical-cables?location=city0")
        self.assertEqual(s,200)
        self.assertEqual(len(view["cables"]),2)
        self.assertEqual(view["cables"][0]["length"]["total_length_m"],100)
        ax,ay=view["cables"][0]["points"][0]["x_m"],view["cables"][0]["points"][0]["y_m"]
        s,a=self.action(action="add_bend",device="A",interface="eth0",x_m=ax+50,y_m=ay+40,after="start")
        self.assertEqual(s,200,a)
        bend_a=a["output"].split()[-1]
        s,b=self.action(action="add_bend",device="C",interface="eth0",x_m=ax+50,y_m=ay+50,after="start")
        self.assertEqual(s,200,b)
        bend_b=b["output"].split()[-1]
        s,g=self.action(action="group_bends",device="A",interface="eth0",bend=bend_a,
                        other_device="C",other_interface="eth0",other_bend=bend_b)
        self.assertEqual(s,200,g)
        group=g["output"].split()[-1]
        s,m=self.action(action="move_group",group=group,x_m=ax+50,y_m=ay+85)
        self.assertEqual(s,200,m)
        s,c=self.action(action="set_color",device="A",interface="eth0",color="#aa2288")
        self.assertEqual(s,200,c)
        s,info=self.request("/api/physical-distance?device=A&interface=eth0")
        self.assertEqual(s,200)
        self.assertFalse(info["up"])
        self.assertGreater(info["total_length_m"],100)
        s,routes=self.request("/api/physical-cables?location=city0")
        self.assertEqual(s,200)
        self.assertEqual(routes["group_count"],1)
        self.assertEqual(routes["cables"][0]["color"],"#aa2288")
        self.assertEqual(routes["cables"][0]["points"][1]["group"],group)
        self.assertTrue(self.app.STATE.is_file())
        restored=NetworkLab();restored.load(str(self.app.STATE))
        self.assertEqual(restored.cable_routes,self.app.LAB.cable_routes)
        s,u=self.action(action="ungroup",group=group,device="A",interface="eth0")
        self.assertEqual(s,200,u)
        self.assertEqual(self.app.LAB.cable_routes[next(iter(self.app.LAB.cable_routes))]["bends"][0]["group"],None)
        s,undo=self.action(action="undo")
        self.assertEqual(s,200,undo)
        self.assertEqual(self.request("/api/physical-cables?location=city0")[1]["group_count"],1)
        s,dele=self.action(action="delete_bend",device="A",interface="eth0",bend=bend_a)
        self.assertEqual(s,200,dele)
        self.assertEqual(len(self.app.LAB.links),2)
        self.assertFalse(self.app.LAB.cable_routes.get(next(iter(self.app.LAB.cable_routes)),{})["bends"])
        # Old snapshots have no routed bends.
        old=self.app.LAB.to_dict();old.pop("cable_routes")
        path=Path(self.tmp.name)/"legacy.json";path.write_text(json.dumps(old))
        legacy=NetworkLab();legacy.load(str(path))
        self.assertEqual(legacy.cable_routes,{})

    def test_bad_api_input_is_atomic(self):
        self.setup_cables()
        before=self.app.LAB.to_dict()
        for payload in [
            {"action":"add_bend","device":"A","interface":"eth0","x_m":"no","y_m":0},
            {"action":"add_bend","device":"A","interface":"eth0","x_m":float("nan"),"y_m":0},
            {"action":"add_bend","device":"wrong","interface":"eth0","x_m":1,"y_m":0},
            {"action":"move_bend","device":"A","interface":"eth0","bend":"fake","x_m":1,"y_m":0},
            {"action":"set_color","device":"A","interface":"eth0","color":"url(javascript:1)"},
            {"action":"group_bends","device":"A","interface":"eth0","bend":"b","other_device":"C","other_interface":"eth0","other_bend":"b"},
            {"action":"move_group","group":"group_missing","x_m":1,"y_m":1},
            {"action":"ungroup","group":"group_missing"},
        ]:
            with self.subTest(payload=payload):
                status,response=self.action(**payload)
                self.assertEqual(status,400,response)
                self.assertFalse(response["ok"])
                self.assertEqual(self.app.LAB.to_dict(),before)
        status,response=self.request("/api/physical-cables?location=unknown")
        self.assertEqual(status,400)
        self.assertFalse(response["ok"])

if __name__=="__main__":unittest.main()

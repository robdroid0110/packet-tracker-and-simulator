"""Real HTTP API acceptance for portable visual assets; never touches live lab."""
import base64,json,tempfile,threading,unittest
from http.server import ThreadingHTTPServer
from pathlib import Path
from urllib.error import HTTPError
from urllib.request import Request,urlopen

from netsim.model import NetworkLab
from netsim.cli import CommandProcessor
from test_visual_customization import png,b64

class VisualHttpTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        import server as app
        cls.app=app
        cls.tmp=tempfile.TemporaryDirectory(prefix="pt18-http-")
        cls.original=(app.LAB,app.PROC,app.STATE,app.BACKUPS)
        app.LAB=NetworkLab();app.PROC=CommandProcessor(app.LAB)
        app.STATE=Path(cls.tmp.name)/"state.json"
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

    def request(self,path,payload=None):
        url=f"http://127.0.0.1:{self.port}"+path
        req=Request(url) if payload is None else Request(
            url,data=json.dumps(payload).encode("utf-8"),headers={"content-type":"application/json"})
        try:
            with urlopen(req,timeout=6) as response:
                return response.status,response.headers,response.read()
        except HTTPError as exc:
            try:return exc.code,exc.headers,exc.read()
            finally:exc.close()

    def json(self,path,payload=None):
        status,headers,raw=self.request(path,payload)
        return status,json.loads(raw)

    def command(self,cmd):
        status,result=self.json("/api/command",{"command":cmd})
        self.assertTrue(result["ok"],result)
        return result

    def upload(self,data=None,mime="image/png",label="image.png"):
        status,response=self.json("/api/visuals/action",{
            "action":"upload_image","mime":mime,
            "data_base64":b64(data or png()),"label":label})
        self.assertEqual(status,200,response)
        self.assertTrue(response["ok"])
        self.assertEqual(len(response["asset_id"]),64)
        return response["asset_id"]

    def test_schema_and_empty_assets(self):
        status,result=self.json("/api/visuals/schema")
        self.assertEqual(status,200)
        self.assertIn("set_background",result["write"]["actions"])
        status,result=self.json("/api/visuals")
        self.assertEqual(status,200)
        self.assertEqual(result["assets"],[])
        self.assertEqual(result["storage"],"embedded in native lab JSON; images served by content hash")

    def test_upload_read_image_with_mime_and_nosniff(self):
        raw=png(45,31,(10,20,30))
        ident=self.upload(raw)
        status,headers,data=self.request("/api/visuals/assets/"+ident)
        self.assertEqual(status,200)
        self.assertEqual(data,raw)
        self.assertEqual(headers["Content-Type"],"image/png")
        self.assertEqual(headers["X-Content-Type-Options"],"nosniff")
        status,assets=self.json("/api/visuals")
        self.assertEqual(assets["assets"][0]["width"],45)
        self.assertEqual(assets["assets"][0]["height"],31)
        self.assertNotIn("data_base64",assets["assets"][0])
        self.assertEqual(self.upload(raw),ident)

    def test_assign_icon_bg_undo_reset_and_persistence(self):
        self.command("add router R1")
        ident=self.upload()
        status,result=self.json("/api/visuals/action",{
            "action":"set_device_icon","device":"R1","view":"physical","asset_id":ident})
        self.assertEqual(status,200)
        status,result=self.json("/api/visuals/action",{
            "action":"set_device_icon","device":"R1","view":"logical","asset_id":ident})
        self.assertEqual(result["state"]["device_icons"]["R1"],{"physical":ident,"logical":ident})
        status,result=self.json("/api/visuals/action",{
            "action":"set_background","location":"city0","asset_id":ident,
            "tiled":True,"color":"#aaccee"})
        self.assertEqual(status,200,result)
        self.assertEqual(result["state"]["location_backgrounds"]["city0"]["asset_id"],ident)
        self.assertTrue(result["state"]["location_backgrounds"]["city0"]["tiled"])
        self.assertTrue(self.app.STATE.exists())
        with self.app.LOCK:
            reloaded=NetworkLab();reloaded.load(str(self.app.STATE))
            self.assertEqual(reloaded.device_icons,self.app.LAB.device_icons)
            self.assertEqual(reloaded.location_backgrounds,self.app.LAB.location_backgrounds)
            self.assertEqual(reloaded.visual_assets,self.app.LAB.visual_assets)
        status,result=self.json("/api/visuals/action",{"action":"undo"})
        self.assertEqual(status,200)
        self.assertNotIn("city0",result["state"]["location_backgrounds"])
        status,result=self.json("/api/visuals/action",{"action":"redo"})
        self.assertEqual(result["state"]["location_backgrounds"]["city0"]["color"],"#aaccee")
        status,result=self.json("/api/visuals/action",{
            "action":"set_background","location":"city0","asset_id":None,
            "tiled":False,"color":"#e7e7e7"})
        self.assertEqual(status,200)
        self.assertNotIn("city0",result["state"]["location_backgrounds"])

    def test_invalid_upload_and_assignment_keep_state(self):
        self.command("add pc PC1")
        before=self.app.LAB.to_dict()
        for payload in [
            {"action":"upload_image","mime":"image/svg+xml","data_base64":b64(b"<svg/>")},
            {"action":"upload_image","mime":"image/png","data_base64":"$$invalid"},
            {"action":"upload_image","mime":"image/png","data_base64":b64(png()[:-3])},
            {"action":"set_device_icon","device":"PC1","view":"physical","asset_id":"f"*64},
            {"action":"set_device_icon","device":"Missing","view":"logical","asset_id":None},
            {"action":"set_device_icon","device":"PC1","view":"something","asset_id":None},
            {"action":"set_background","location":"unknown","asset_id":None},
            {"action":"set_background","location":"city0","asset_id":None,"color":"javascript:alert(1)"},
            {"action":"delete_image","asset_id":"f"*64},
        ]:
            with self.subTest(action=payload):
                status,response=self.json("/api/visuals/action",payload)
                self.assertEqual(status,400,response)
                self.assertFalse(response["ok"])
                self.assertEqual(self.app.LAB.to_dict(),before)
        for ref in ["blah","f"*64]:
            with self.subTest(image=ref):
                self.assertEqual(self.request("/api/visuals/assets/"+ref)[0],404)

    def test_upload_body_max_and_used_asset_rejection(self):
        big={"action":"upload_image","mime":"image/png","data_base64":"A"*1_501_000}
        status,result=self.json("/api/visuals/action",big)
        self.assertEqual(status,413)
        self.assertFalse(result["ok"])
        self.command("add pc PC1")
        ident=self.upload()
        status,result=self.json("/api/visuals/action",{
            "action":"set_device_icon","device":"PC1","view":"logical","asset_id":ident})
        self.assertEqual(status,200)
        status,result=self.json("/api/visuals/action",{"action":"delete_image","asset_id":ident})
        self.assertEqual(status,400)
        self.assertIn("in use",result["output"])
        self.assertIn(ident,self.app.LAB.visual_assets)

    def test_agent_capability_registry(self):
        status,cap=self.json("/api/capabilities")
        self.assertEqual(status,200)
        ids={x["id"] for x in cap["actions"]}
        for cap in ("visuals.assets","visuals.image","visuals.schema","visuals.edit"):
            self.assertIn(cap,ids)

if __name__=="__main__":unittest.main()

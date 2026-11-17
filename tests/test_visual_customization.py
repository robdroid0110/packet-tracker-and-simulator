"""vendor Help §18 portable physical backgrounds and independent device icons."""
from __future__ import annotations
import base64,io,json,struct,tempfile,unittest,zlib
from pathlib import Path
from netsim.model import LabError,NetworkLab
from netsim.cli import CommandProcessor
from netsim.visual_customization import (
    image_info,add_asset,set_icon,set_background,discard_asset,
    load_visuals,load_assignments,public_assets,command_from_action,schema,
    MAX_ASSET_BYTES
)

def png(width=45,height=31,color=(30,125,210)):
    def chunk(kind,payload):
        return (struct.pack(">I",len(payload))+kind+payload+
                struct.pack(">I",zlib.crc32(kind+payload)&0xffffffff))
    ihdr=struct.pack(">IIBBBBB",width,height,8,2,0,0,0)
    row=b"\x00"+bytes(color)*width
    data=zlib.compress(row*height)
    return b"\x89PNG\r\n\x1a\n"+chunk(b"IHDR",ihdr)+chunk(b"IDAT",data)+chunk(b"IEND",b"")

def b64(data:bytes)->str:
    return base64.b64encode(data).decode("ascii")

class VisualCustomizationTests(unittest.TestCase):
    def setUp(self):
        self.lab=NetworkLab();self.cp=CommandProcessor(self.lab)
        self.cp.execute("add router R1")
        self.cp.execute("add pc PC1")
        self.asset=add_asset(self.lab,"image/png",b64(png()),"router-icon.png")

    def test_dedup_metadata_and_safe_image_identity(self):
        self.assertEqual(add_asset(self.lab,"image/png",b64(png()),"same.png"),self.asset)
        self.assertEqual(len(self.lab.visual_assets),1)
        self.assertEqual(self.lab.visual_assets[self.asset]["width"],45)
        self.assertEqual(public_assets(self.lab)["assets"][0]["bytes"],len(png()))
        self.assertNotIn("data_base64",public_assets(self.lab)["assets"][0])
        self.assertEqual(image_info("image/png",b64(png()))[-1],self.asset)
        self.assertIn("upload_image",schema()["write"]["actions"])

    def test_independent_logical_and_physical_icons(self):
        second=add_asset(self.lab,"image/png",b64(png(45,31,(200,30,40))),"physical.png")
        set_icon(self.lab,"R1","logical",self.asset)
        set_icon(self.lab,"R1","physical",second)
        self.assertEqual(self.lab.device_icons["R1"],{"logical":self.asset,"physical":second})
        set_icon(self.lab,"R1","physical",None)
        self.assertEqual(self.lab.device_icons["R1"],{"logical":self.asset})
        set_icon(self.lab,"R1","logical",None)
        self.assertNotIn("R1",self.lab.device_icons)

    def test_each_location_background_and_reset(self):
        set_background(self.lab,"intercity",self.asset,True,"#AABBCC")
        set_background(self.lab,"city0",self.asset,False,"#bbccdd")
        self.assertEqual(self.lab.location_backgrounds["intercity"]["color"],"#aabbcc")
        self.assertTrue(self.lab.location_backgrounds["intercity"]["tiled"])
        self.assertFalse(self.lab.location_backgrounds["city0"]["tiled"])
        self.assertNotIn("building0",self.lab.location_backgrounds)
        set_background(self.lab,"city0",None,False,"#e7e7e7")
        self.assertNotIn("city0",self.lab.location_backgrounds)
        set_background(self.lab,"intercity",None,False,"#e7e7e7")
        self.assertEqual(self.lab.location_backgrounds,{})

    def test_cli_upload_assign_undo_and_delete(self):
        data=b64(png(12,13))
        output=self.cp.execute("visual upload image/png "+data+" test.png")
        self.assertIn("visual asset uploaded",output)
        asset=output.split()[-1]
        self.assertIn("updated",self.cp.execute("visual icon R1 physical "+asset))
        self.assertEqual(self.lab.device_icons["R1"]["physical"],asset)
        self.assertEqual(self.cp.execute("undo"),"Undo completed")
        self.assertNotIn("R1",self.lab.device_icons)
        self.assertEqual(self.cp.execute("redo"),"Redo completed")
        self.assertEqual(self.lab.device_icons["R1"]["physical"],asset)
        self.assertIn("updated",self.cp.execute("visual background city0 "+asset+" tile '#ccddee'"))
        self.assertEqual(self.lab.location_backgrounds["city0"]["asset_id"],asset)
        self.assertTrue(self.cp.execute("visual delete "+asset).startswith("ERROR:"))
        self.assertIn("reset",self.cp.execute("visual icon R1 physical default"))
        self.assertIn("reset",self.cp.execute("visual background city0 default fit '#e7e7e7'"))
        self.assertIn("deleted",self.cp.execute("visual delete "+asset))
        self.assertNotIn(asset,self.lab.visual_assets)

    def test_asset_import_from_local_file(self):
        with tempfile.TemporaryDirectory() as d:
            path=Path(d)/"device.png";path.write_bytes(png())
            text=self.cp.execute("visual import "+str(path))
            self.assertIn("visual asset uploaded",text)
            self.assertTrue(self.cp.execute("visual import "+str(path)+" renamed.png").startswith("visual asset"))
            path.with_suffix(".txt").write_bytes(png())
            self.assertTrue(self.cp.execute("visual import "+str(path.with_suffix(".txt"))).startswith("ERROR:"))

    def test_rename_delete_duplicate_and_reset(self):
        set_icon(self.lab,"R1","physical",self.asset)
        set_icon(self.lab,"R1","logical",self.asset)
        self.cp.execute("rename R1 Router2")
        self.assertNotIn("R1",self.lab.device_icons)
        self.assertEqual(self.lab.device_icons["Router2"]["logical"],self.asset)
        cloned=self.lab.duplicate_devices(["Router2"])
        self.assertEqual(self.lab.device_icons[cloned["Router2"]],self.lab.device_icons["Router2"])
        self.cp.execute("remove Router2")
        self.assertNotIn("Router2",self.lab.device_icons)
        self.lab.reset()
        self.assertEqual(self.lab.visual_assets,{})
        self.assertEqual(self.lab.device_icons,{})
        self.assertEqual(self.lab.location_backgrounds,{})

    def test_save_load_migration_and_asset_integrity(self):
        set_icon(self.lab,"PC1","logical",self.asset)
        set_background(self.lab,"city0",self.asset,True,"#112233")
        with tempfile.TemporaryDirectory() as d:
            path=Path(d)/"lab.json"
            self.lab.save(str(path))
            restored=NetworkLab();restored.load(str(path))
            self.assertEqual(restored.visual_assets,self.lab.visual_assets)
            self.assertEqual(restored.device_icons,self.lab.device_icons)
            self.assertEqual(restored.location_backgrounds,self.lab.location_backgrounds)
            raw=json.loads(path.read_text())
            raw.pop("visual_assets");raw.pop("device_icons");raw.pop("location_backgrounds")
            path.write_text(json.dumps(raw))
            old=NetworkLab();old.load(str(path))
            self.assertEqual(old.visual_assets,{})
            self.assertEqual(old.device_icons,{})
            self.assertEqual(old.location_backgrounds,{})

    def test_corrupt_saved_visuals_rejected(self):
        baseline=self.lab.to_dict()
        for change in [
            lambda d:d["visual_assets"][self.asset].update(data_base64=b64(png(1,1))),
            lambda d:d["visual_assets"][self.asset].update(bytes=10),
            lambda d:d["device_icons"].update(R1={"logical":"f"*64}),
            lambda d:d["device_icons"].update(missing={"logical":self.asset}),
            lambda d:d["location_backgrounds"].update(city0={"asset_id":"f"*64,"tiled":False,"color":"#ffffff"}),
            lambda d:d["location_backgrounds"].update(bogus={"asset_id":self.asset,"tiled":False,"color":"#ffffff"}),
            lambda d:d["location_backgrounds"].update(city0={"asset_id":self.asset,"tiled":"yes","color":"#ffffff"}),
        ]:
            raw=json.loads(json.dumps(baseline))
            change(raw)
            with tempfile.NamedTemporaryFile("w",suffix=".json") as f:
                json.dump(raw,f);f.flush()
                with self.subTest(change=change):
                    with self.assertRaises(LabError):NetworkLab().load(f.name)

    def test_image_validation_rejects_unsafe_uploads(self):
        valid=png()
        cases=[
            ("image/svg+xml",b64(b"<svg><script>alert(1)</script></svg>")),
            ("text/html",b64(b"<script></script>")),
            ("image/png","b@d!"),
            ("image/png",b64(b"not a PNG")),
            ("image/jpeg",b64(b"\xff\xd8\xff\xd9")),
            ("image/png",b64(valid[:-2])),
            ("image/png",b64(valid+b"extra")),
            ("image/png",b64(valid[:-18]+b"bad"+valid[-15:])),
            ("image/png",b64(png(8193,1))),
            ("image/png",b64(b"\x89PNG\r\n\x1a\n"+b"X"*(MAX_ASSET_BYTES+1))),
        ]
        for mime,encoded in cases:
            with self.subTest(mime=mime,encoded=encoded[:32]):
                with self.assertRaises(LabError):image_info(mime,encoded)
        for values in [
            ("R1","config",self.asset),
            ("R1","physical","f"*64),
            ("missing","physical",self.asset),
        ]:
            with self.subTest(values=values):
                with self.assertRaises(LabError):set_icon(self.lab,*values)
        with self.assertRaises(LabError):set_background(self.lab,"city0",self.asset,False,"red")
        with self.assertRaises(LabError):set_background(self.lab,"not-a-location",self.asset)
        with self.assertRaises(LabError):discard_asset(self.lab,"f"*64)

    def test_command_translation_validation(self):
        payload={"action":"upload_image","mime":"image/png","data_base64":b64(png()),"label":"test.png"}
        self.assertTrue(command_from_action(payload).startswith("visual upload image/png"))
        self.assertEqual(command_from_action({"action":"set_device_icon","device":"R1","view":"logical","asset_id":self.asset}),
                         "visual icon R1 logical "+self.asset)
        self.assertEqual(command_from_action({"action":"set_background","location":"city0",
                     "asset_id":None,"tiled":False,"color":"#ffffff"}),
                     "visual background city0 default fit #ffffff")
        bad=[
            {},{"action":"wat"},
            {"action":"upload_image","mime":"image/png","data_base64":"oops"},
            {"action":"set_device_icon","device":"R1","view":"custom","asset_id":self.asset},
            {"action":"set_background","location":"city0","asset_id":self.asset,"tiled":"yes"},
            {"action":"set_background","location":"city0","asset_id":"bad","tiled":False},
            {"action":"delete_image","asset_id":"not-hash"},
        ]
        for value in bad:
            with self.subTest(value=value):
                with self.assertRaises(LabError):command_from_action(value)

    def test_200_device_icon_assignments_stay_separate(self):
        test=NetworkLab()
        for i in range(200):test.add_device("pc",f"PC{i}")
        shared=add_asset(test,"image/png",b64(png()),"shared")
        for name in test.devices:
            set_icon(test,name,"physical",shared)
        self.assertEqual(len(test.visual_assets),1)
        self.assertEqual(len(test.device_icons),200)

    def test_gui_contract(self):
        root=Path(__file__).resolve().parents[1]
        html=(root/"web/index.html").read_text()
        js=(root/"web/visual-customization.js").read_text()
        physical=(root/"web/interface-overview.js").read_text()
        for name in ["visual-customization.js","visual-customization.css"]:
            self.assertIn(name,html)
        for fragment in ["ptVisualDialog","upload_image","set_device_icon","set_background","ptVisualScale",
                         "ptVisualTiled","ptVisualReset","ptVisualDelete","physical-distance?location=","renderLogical"]:
            self.assertIn(fragment,js)
        self.assertIn("PacketTrackerVisual?.openBackground",physical)
        self.assertIn("PacketTrackerVisual.renderPhysical()",physical)

if __name__=="__main__":unittest.main()

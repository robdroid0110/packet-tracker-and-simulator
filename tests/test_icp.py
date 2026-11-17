"""legacy simulator help §20: Industrial Control Panel data model and API parity."""
from __future__ import annotations
import json,tempfile,unittest
from pathlib import Path
from netsim.model import LabError,NetworkLab
from netsim.cli import CommandProcessor
from netsim import icp

class IcpTests(unittest.TestCase):
    def setUp(self):
        self.lab=NetworkLab()
        self.cli=CommandProcessor(self.lab)
        self.location=icp.create(self.lab,"Test ICP","building0","medium")
        for command in ("add pc PC1","add router R1","add pc PC2"):
            self.assertFalse(self.cli.execute(command).startswith("ERROR:"))
        for name in ("PC1","R1","PC2"):
            self.lab.place_physical_device(name,self.location)

    def test_presets_creation_and_hierarchy(self):
        loc=self.lab.physical_locations[self.location]
        self.assertEqual(loc["type"],"icp")
        self.assertEqual(tuple(loc[k] for k in ("width","length","height")),icp.PRESETS["medium"])
        self.assertFalse(self.lab.icp_panels[self.location]["door_closed"])
        self.assertEqual(self.lab.physical_device_details["R1"]["surface"],"cabinet")
        self.assertEqual(self.lab.device_locations["R1"],self.location)
        self.assertEqual(icp.panel_view(self.lab,self.location)["location_meta"]["name"],"Test ICP")
        self.assertEqual(icp.panel_view(self.lab,self.location)["snap_anchor_count"],6)
        with self.assertRaises(LabError):icp.create(self.lab,"Invalid","building0","giant")
        with self.assertRaises(LabError):icp.create(self.lab,"Nested ICP",self.location,"large")
        with self.assertRaises(LabError):self.lab.add_physical_location("city","city inside ICP",self.location)

    def test_api_translation_and_invalid_input(self):
        self.assertEqual(icp.action_command({"action":"create","name":"Machine Panel","size":"small","parent":"building0"}),
                         "icp create small 'Machine Panel' building0")
        self.assertEqual(icp.action_command({"action":"door","location":self.location,"closed":True}),
                         "icp door "+self.location+" on")
        self.assertEqual(icp.action_command({"action":"device_move","device":"PC1","side":"door",
                      "x":85,"y":65,"anchor":3,"detach":False}),
                         "icp device-move PC1 door 85.0 65.0 3 attached")
        self.assertIn("fixture_join",icp.schema()["write"]["actions"])
        for payload in (
            {},{"action":"not_found"},{"action":"create","name":"bad","size":"xx","parent":"building0"},
            {"action":"door","location":self.location,"closed":"yes"},
            {"action":"device_move","device":"PC1","side":"invalid","x":0,"y":0},
            {"action":"device_move","device":"PC1","side":"door","x":float("nan"),"y":0},
            {"action":"device_move","device":"PC1","side":"door","x":100,"y":0,"anchor":6},
            {"action":"fixture_add","location":self.location,"kind":"din","orientation":"diagonal","x":100,"y":100},
            {"action":"fixture_move","location":self.location,"fixture":"fixture0","x":100,"y":100,"detach":"yes"}
        ):
            with self.subTest(payload=payload):
                with self.assertRaises(LabError):icp.action_command(payload)

    def test_door_and_readonly_preview(self):
        icp.set_door(self.lab,self.location,True)
        self.assertTrue(self.lab.icp_panels[self.location]["door_closed"])
        icp.preview(self.lab,self.location,True)
        p=self.lab.icp_panels[self.location]
        self.assertTrue(p["workspace_mode"])
        self.assertTrue(p["door_closed"])
        with self.assertRaises(LabError):icp.move_device(self.lab,"PC1","door",80,60)
        with self.assertRaises(LabError):icp.add_fixture(self.lab,self.location,"din","horizontal",80,60)
        icp.set_door(self.lab,self.location,False)
        self.assertFalse(p["workspace_mode"])
        self.assertFalse(p["door_closed"])
        icp.preview(self.lab,self.location,True)
        icp.preview(self.lab,self.location,False)
        self.assertTrue(p["door_closed"])
        self.assertFalse(p["workspace_mode"])

    def test_snap_grid_and_six_anchors(self):
        icp.move_device(self.lab,"PC1","door",86,57,anchor=0)
        detail=self.lab.physical_device_details["PC1"]
        self.assertEqual((detail["x"],detail["y"]),(80,60))
        self.assertEqual(detail["surface"],"door")
        self.assertEqual(self.lab.icp_panels[self.location]["anchors"]["PC1"],0)
        distinct=set()
        for anchor in range(6):
            icp.move_device(self.lab,"PC1","door",101,101,anchor=anchor)
            detail=self.lab.physical_device_details["PC1"]
            distinct.add((detail["x"],detail["y"]))
        self.assertGreaterEqual(len(distinct),4)
        for fn,args in ((icp.move_device,("PC1","floor",40,60)),
                        (icp.move_device,("PC1","door",-5,60)),
                        (icp.move_device,("PC1","door",40,float("inf")))):
            with self.subTest(args=args):
                with self.assertRaises(LabError):fn(self.lab,*args)

    def test_fixtures_create_join_move_split_delete(self):
        a=icp.add_fixture(self.lab,self.location,"din","horizontal",200,200)
        b=icp.add_fixture(self.lab,self.location,"din","horizontal",260,200)
        c=icp.add_fixture(self.lab,self.location,"wic","vertical",320,300)
        self.assertEqual(set(self.lab.icp_panels[self.location]["fixtures"]),{a,b,c})
        with self.assertRaises(LabError):icp.add_fixture(self.lab,self.location,"din","vertical",10,10)
        with self.assertRaises(LabError):icp.join_fixtures(self.lab,self.location,a,c)
        group=icp.join_fixtures(self.lab,self.location,a,b)
        self.assertEqual(self.lab.icp_panels[self.location]["fixtures"][b]["group"],group)
        icp.move_fixture(self.lab,self.location,a,300,260)
        fixtures=self.lab.icp_panels[self.location]["fixtures"]
        self.assertEqual((fixtures[a]["x"],fixtures[a]["y"]),(300,260))
        self.assertEqual((fixtures[b]["x"],fixtures[b]["y"]),(360,260))
        icp.move_fixture(self.lab,self.location,b,440,240,detach=True)
        self.assertIsNone(fixtures[a]["group"])
        self.assertIsNone(fixtures[b]["group"])
        icp.delete_fixture(self.lab,self.location,c)
        self.assertNotIn(c,fixtures)

    def test_mount_unmount_rigid_assembly_and_cable_preserved(self):
        a=icp.add_fixture(self.lab,self.location,"din","horizontal",200,200)
        b=icp.add_fixture(self.lab,self.location,"din","horizontal",260,200)
        icp.join_fixtures(self.lab,self.location,a,b)
        icp.mount(self.lab,"PC1",a)
        icp.mount(self.lab,"R1",b)
        self.assertEqual(self.lab.icp_panels[self.location]["mounts"],{"PC1":a,"R1":b})
        self.cli.execute("connect PC1 eth0 R1 g0/0")
        original_links=len(self.lab.links)
        one_before=self.lab.physical_device_details["PC1"].copy()
        two_before=self.lab.physical_device_details["R1"].copy()
        icp.move_fixture(self.lab,self.location,a,300,220)
        one_after=self.lab.physical_device_details["PC1"]
        two_after=self.lab.physical_device_details["R1"]
        self.assertEqual(one_after["x"]-one_before["x"],100)
        self.assertEqual(one_after["y"]-one_before["y"],20)
        self.assertEqual(two_after["x"]-two_before["x"],100)
        self.assertEqual(len(self.lab.links),original_links)
        icp.move_device(self.lab,"PC1","cabinet",450,350,anchor=0,detach=True)
        self.assertNotIn("PC1",self.lab.icp_panels[self.location]["mounts"])
        self.assertIn("R1",self.lab.icp_panels[self.location]["mounts"])
        icp.unmount(self.lab,"R1")
        self.assertEqual(self.lab.icp_panels[self.location]["mounts"],{})

    def test_wic_non_electrical_and_mount_rules(self):
        w=icp.add_fixture(self.lab,self.location,"wic","horizontal",200,240)
        with self.assertRaises(LabError):icp.mount(self.lab,"PC1",w)
        with self.assertRaises(LabError):icp.unmount(self.lab,"PC1")
        icp.move_device(self.lab,"PC1","door",150,140)
        d=icp.add_fixture(self.lab,self.location,"din","horizontal",200,160)
        with self.assertRaises(LabError):icp.mount(self.lab,"PC1",d)
        self.assertEqual(len(self.lab.links),0)

    def test_state_is_saved_and_legacy_stays_valid(self):
        fid=icp.add_fixture(self.lab,self.location,"din","horizontal",200,160)
        icp.mount(self.lab,"R1",fid)
        icp.move_device(self.lab,"PC1","door",180,120,3)
        icp.set_door(self.lab,self.location,True)
        with tempfile.TemporaryDirectory() as d:
            file=Path(d)/"icp.json"
            self.lab.save(str(file))
            other=NetworkLab();other.load(str(file))
            self.assertEqual(other.icp_panels,self.lab.icp_panels)
            self.assertEqual(other.physical_device_details["PC1"]["surface"],"door")
            self.assertEqual(other.icp_panels[self.location]["mounts"]["R1"],fid)
            raw=json.loads(file.read_text())
            raw.pop("icp_panels")
            file.write_text(json.dumps(raw))
            legacy=NetworkLab()
            legacy.load(str(file))
            self.assertIn(self.location,legacy.icp_panels)
            self.assertEqual(legacy.icp_panels[self.location]["fixtures"],{})

    def test_corrupted_save_rejected(self):
        fixture=icp.add_fixture(self.lab,self.location,"din","horizontal",200,160)
        icp.mount(self.lab,"R1",fixture)
        baseline=self.lab.to_dict()
        damaged=[
            lambda d:d["icp_panels"][self.location].update(size="impossible"),
            lambda d:d["icp_panels"][self.location].update(door_closed="yes"),
            lambda d:d["icp_panels"][self.location].update(workspace_mode=True,door_closed=False),
            lambda d:d["icp_panels"][self.location]["fixtures"][fixture].update(kind="unknown"),
            lambda d:d["icp_panels"][self.location]["fixtures"][fixture].update(x=float("nan")),
            lambda d:d["icp_panels"][self.location]["mounts"].update(PC1="fixture999"),
            lambda d:d["icp_panels"][self.location]["mounts"].update(Unknown=fixture),
            lambda d:d["icp_panels"][self.location]["anchors"].update(PC1=9),
            lambda d:d["icp_panels"].update(no_such_icp=icp.default_panel()),
        ]
        with tempfile.TemporaryDirectory() as directory:
            path=Path(directory)/"bad.json"
            for modifier in damaged:
                data=json.loads(json.dumps(baseline));modifier(data)
                path.write_text(json.dumps(data))
                with self.subTest(modifier=modifier):
                    with self.assertRaises(LabError):NetworkLab().load(str(path))

    def test_cli_history_and_cleanup(self):
        fid=icp.add_fixture(self.lab,self.location,"din","horizontal",200,160)
        icp.mount(self.lab,"R1",fid)
        self.assertEqual(self.cli.execute("icp device-move PC1 door 65 65 0 attached"),"ICP device moved PC1")
        self.assertEqual(self.lab.physical_device_details["PC1"]["surface"],"door")
        self.assertEqual(self.cli.execute("undo"),"Undo completed")
        self.assertEqual(self.lab.physical_device_details["PC1"]["surface"],"cabinet")
        self.assertEqual(self.cli.execute("redo"),"Redo completed")
        self.assertEqual(self.lab.physical_device_details["PC1"]["surface"],"door")
        self.cli.execute("rename R1 RouterOne")
        self.assertIn("RouterOne",self.lab.icp_panels[self.location]["mounts"])
        self.cli.execute("physical place RouterOne building0")
        self.assertNotIn("RouterOne",self.lab.icp_panels[self.location]["mounts"])
        self.cli.execute("remove PC1")
        self.assertNotIn("PC1",self.lab.icp_panels[self.location]["anchors"])

    def test_200_devices_api_scaling(self):
        lab=NetworkLab()
        loc=icp.create(lab,"Large Unit","building0","large")
        for i in range(200):
            lab.add_device("pc",f"PC{i}")
            lab.place_physical_device(f"PC{i}",loc,recompute=False)
        summary=icp.panel_view(lab,loc)
        self.assertEqual(len(summary["devices"]),200)
        self.assertEqual(len(summary["fixtures"]),0)

    def test_gui_and_server_contract(self):
        root=Path(__file__).resolve().parents[1]
        frontend=(root/"web/icp.js").read_text()
        css=(root/"web/icp.css").read_text()
        markup=(root/"web/index.html").read_text()
        core=(root/"web/interface-overview.js").read_text()
        server=(root/"server.py").read_text()
        for fragment in ("Shift+drag","Ctrl+drag","Tab","pt-icp-handle","pt-icp-cabinet",
                         "pt-icp-door","pt-icp-fixture","fixture_add","device_move","mount"):
            self.assertIn(fragment,frontend+css)
        self.assertIn("Connect Auto Ethernet",frontend)
        self.assertIn("/api/command",frontend)
        self.assertIn("pt-icp-network",frontend)
        self.assertIn("New ICP",core)
        self.assertIn("icp.js",markup)
        self.assertIn("icp.css",markup)
        self.assertIn('"/api/icp/schema"',server)
        self.assertIn('"/api/icp/action"',server)

if __name__=="__main__":unittest.main()

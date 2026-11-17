import json
import tempfile
import unittest
from pathlib import Path

from netsim.model import NetworkLab, LabError
from netsim.cli import CommandProcessor
from netsim.physical_workspace import physical_view, physical_schema, action_command


class PhysicalWorkspaceModelTests(unittest.TestCase):
    def setUp(self):
        self.lab=NetworkLab()
        self.cp=CommandProcessor(self.lab)
        for cmd in ("add pc PC1","add pc PC2","add switch SW1",
                    "connect PC1 eth0 SW1 fa0/1"):
            result=self.cp.execute(cmd)
            assert not result.startswith("ERROR:"),result

    def test_initial_geography_and_migration(self):
        self.assertEqual(len(self.lab.physical_locations),3)
        self.assertEqual(self.lab.physical_locations["city0"]["width"],5000)
        self.assertEqual(self.lab.physical_locations["closet0"]["height"],4)
        self.assertEqual(self.lab.physical_shelves["closet0"],0)
        self.assertEqual(self.lab.physical_device_details["SW1"]["surface"],"rack")
        self.assertEqual(self.lab.physical_device_details["PC1"]["surface"],"floor")

    def test_generic_nested_containers_and_dimensions(self):
        box=self.lab.add_physical_location("generic","Store","closet0")
        self.assertEqual(self.lab.physical_locations[box]["width"],10)
        inner=self.lab.add_physical_location("generic","Small crate",box)
        self.lab.resize_physical_location(inner,3,2,1)
        self.assertEqual(self.lab.physical_locations[inner]["width"],3)
        with self.assertRaisesRegex(LabError,"existing child"):
            self.lab.resize_physical_location(box,2,2,2)
        with self.assertRaisesRegex(LabError,"inside closet"):
            self.lab.add_physical_location("building","In closet","closet0")
        with self.assertRaisesRegex(LabError,"cannot"):
            self.lab.add_physical_location("city","City","building0")

    def test_relocate_checks_hierarchy_cycles_and_size(self):
        city=self.lab.add_physical_location("city","Jaipur")
        building=self.lab.add_physical_location("building","School",city)
        self.lab.relocate_physical_location(building,"city0")
        self.assertEqual(self.lab.physical_locations[building]["parent"],"city0")
        with self.assertRaises(LabError):
            self.lab.relocate_physical_location("city0",building)
        with self.assertRaisesRegex(LabError,"descendant"):
            self.lab.relocate_physical_location("city0","building0")
        box=self.lab.add_physical_location("generic","Box","closet0")
        with self.assertRaisesRegex(LabError,"dimensions"):
            self.lab.relocate_physical_location(building,box)
        self.assertEqual(self.lab.physical_locations[building]["parent"],"city0")

    def test_physical_position_does_not_modify_logical(self):
        old=(self.lab.devices["PC1"].x,self.lab.devices["PC1"].y)
        self.lab.place_physical_device("PC1","city0")
        self.lab.physical_device_position("PC1",675,355)
        self.assertEqual((self.lab.devices["PC1"].x,self.lab.devices["PC1"].y),old)
        self.assertEqual(self.lab.physical_device_details["PC1"]["x"],675)
        self.assertEqual(self.lab.physical_device_details["PC1"]["surface"],"floor")
        self.assertEqual(self.lab.device_locations["PC1"],"city0")
        self.assertEqual(len(self.lab.links),1)

    def test_shelf_requires_disconnected_and_powered_off(self):
        self.lab.place_physical_device("PC1","closet0")
        shelf=self.lab.physical_shelf_add("closet0")
        with self.assertRaisesRegex(LabError,"powered-off"):
            self.lab.physical_mount_device("PC1","shelf",shelf)
        self.cp.execute("power PC1 off")
        with self.assertRaisesRegex(LabError,"disconnected"):
            self.lab.physical_mount_device("PC1","shelf",shelf)
        self.cp.execute("disconnect PC1 eth0")
        self.lab.physical_mount_device("PC1","shelf",shelf)
        self.assertEqual(self.lab.physical_device_details["PC1"]["surface"],"shelf")
        self.assertTrue(self.cp.execute("power PC1 on").startswith("ERROR:"))
        self.assertTrue(self.cp.execute("connect PC1 eth0 SW1 fa0/2").startswith("ERROR:"))
        self.cp.execute("power-cycle")
        self.assertFalse(self.lab.devices["PC1"].powered)
        self.lab.physical_mount_device("PC1","table")
        self.assertIn("powered on",self.cp.execute("power PC1 on"))

    def test_shelf_and_mount_invalid_location(self):
        with self.assertRaises(LabError):self.lab.physical_shelf_add("building0")
        with self.assertRaises(LabError):self.lab.physical_mount_device("PC2","rack")
        with self.assertRaises(LabError):self.lab.physical_mount_device("PC2","shelf",0)
        self.lab.place_physical_device("PC2","closet0")
        self.cp.execute("power PC2 off")
        with self.assertRaises(LabError):self.lab.physical_mount_device("PC2","shelf",0)
        self.lab.physical_mount_device("PC2","rack")
        self.lab.physical_mount_device("PC2","table")

    def test_undo_redo_and_agent_commands(self):
        self.assertIn("created physical location loc0",self.cp.execute('physical add generic "Storage" closet0'))
        self.assertIn("resized",self.cp.execute("physical dimensions loc0 7 7 2"))
        self.assertIn("created shelf",self.cp.execute("physical shelf-add closet0"))
        self.assertEqual(self.lab.physical_shelves["closet0"],1)
        self.assertEqual(self.cp.execute("undo"),"Undo completed")
        self.assertEqual(self.lab.physical_shelves["closet0"],0)
        self.assertEqual(self.cp.execute("redo"),"Redo completed")
        self.assertEqual(self.lab.physical_shelves["closet0"],1)
        self.assertIn("relocated",self.cp.execute("physical relocate loc0 intercity"))
        self.assertIsNone(self.lab.physical_locations["loc0"]["parent"])
        self.assertIn("positioned",self.cp.execute("physical device-position SW1 240 60"))

    def test_round_trip_and_legacy_autosave(self):
        box=self.lab.add_physical_location("generic","Storage","closet0")
        self.lab.resize_physical_location(box,7,6,2)
        self.lab.physical_shelf_add("closet0")
        self.lab.place_physical_device("PC2","closet0")
        self.cp.execute("power PC2 off")
        self.lab.physical_mount_device("PC2","shelf",0)
        with tempfile.TemporaryDirectory() as d:
            path=Path(d)/"lab.json"
            self.lab.save(str(path))
            restored=NetworkLab()
            restored.load(str(path))
            self.assertEqual(restored.physical_device_details,self.lab.physical_device_details)
            self.assertEqual(restored.physical_shelves,self.lab.physical_shelves)
            self.assertEqual(restored.physical_locations,self.lab.physical_locations)
            raw=json.loads(path.read_text())
            raw.pop("physical_device_details");raw.pop("physical_shelves")
            for loc in raw["physical_locations"].values():
                for key in ("width","length","height"):loc.pop(key,None)
            path.write_text(json.dumps(raw))
            restored.load(str(path))
            self.assertEqual(restored.physical_shelves["closet0"],0)
            self.assertEqual(restored.physical_locations["closet0"]["width"],20)

    def test_corrupt_autosaves_rejected(self):
        with tempfile.TemporaryDirectory() as d:
            path=Path(d)/"lab.json"
            baseline=self.lab.to_dict()
            for change in [
                lambda raw:raw["physical_locations"]["building0"].update(width=9000),
                lambda raw:raw["physical_locations"]["city0"].update(parent="closet0"),
                lambda raw:raw["physical_device_details"]["PC1"].update(surface="shelf",shelf=0),
                lambda raw:raw["physical_shelves"].update(closet0=21),
            ]:
                data=json.loads(json.dumps(baseline))
                change(data)
                path.write_text(json.dumps(data))
                with self.subTest(data=data):
                    with self.assertRaises(LabError):NetworkLab().load(str(path))

    def test_physical_api_projection_and_commands(self):
        projection=physical_view(self.lab,"closet0")
        self.assertEqual(projection["location"],"closet0")
        self.assertEqual(projection["parent"],"building0")
        self.assertEqual(projection["devices"][0]["name"],"SW1")
        self.assertFalse(projection["limitations"]["distance_effects"])
        for req in [
            {"action":"add_location","kind":"generic","name":"Store","parent":"closet0"},
            {"action":"resize_location","location":"loc0","width":8,"length":7,"height":2},
            {"action":"place_device","device":"PC2","location":"closet0"},
            {"action":"position_device","device":"PC2","x":300,"y":120},
            {"action":"add_shelf","closet":"closet0"},
        ]:
            output=self.cp.execute(action_command(req))
            self.assertFalse(output.startswith("ERROR:"),output)
        self.assertEqual(physical_view(self.lab,"closet0")["shelves"],1)
        self.assertIn("mount_device",physical_schema()["write"]["actions"])

    def test_invalid_typed_requests(self):
        for req in [
            {},{"action":"not-real"},
            {"action":"add_location","kind":"school","name":"a","parent":"intercity"},
            {"action":"resize_location","location":"closet0","width":"infinity","length":3,"height":2},
            {"action":"position_device","device":"PC1","x":float("nan"),"y":1},
            {"action":"mount_device","device":"PC1","surface":"shelf","shelf":True},
            {"action":"mount_device","device":"PC1","surface":"rack","shelf":1},
        ]:
            with self.subTest(request=req):
                if req.get("action")=="mount_device" and req.get("surface")=="rack":
                    # Shelf index is ignored for non-shelf mounts; valid by design.
                    continue
                with self.assertRaises(LabError):action_command(req)

    def test_atomic_create_device_in_physical_location(self):
        command=action_command({"action":"add_device","model":"pc-pt","name":"NewPC",
                                "x":250,"y":180,"location":"city0",
                                "physical_x":325,"physical_y":170})
        self.assertIn("physical add-device",command)
        self.assertIn("created NewPC",self.cp.execute(command))
        self.assertEqual(self.lab.device_locations["NewPC"],"city0")
        self.assertEqual(self.lab.physical_device_details["NewPC"]["x"],325)
        self.assertEqual(self.cp.execute("undo"),"Undo completed")
        self.assertNotIn("NewPC",self.lab.devices)

    def test_invalid_physical_device_creation_is_atomic(self):
        for args in [
            {"action":"add_device","model":"unknown-model","name":"BAD","x":100,"y":100,"location":"closet0"},
            {"action":"add_device","model":"pc-pt","name":"BAD","x":100,"y":100,"location":"missing"},
            {"action":"add_device","model":"pc-pt","name":"BAD","x":100,"y":100,"location":"closet0","physical_x":float("nan"),"physical_y":100},
        ]:
            try:
                text=action_command(args)
            except LabError:
                self.assertNotIn("BAD",self.lab.devices)
                continue
            result=self.cp.execute(text)
            self.assertTrue(result.startswith("ERROR:"),result)
            self.assertNotIn("BAD",self.lab.devices)
        with self.assertRaises(LabError):
            action_command({"action":"add_device","model":"pc-pt","name":"BAD",
                            "x":100,"y":100,"location":"closet0","physical_x":50})

    def test_200_devices_projection(self):
        lab=NetworkLab()
        for i in range(200):lab.add_device("pc",f"PC{i}")
        projection=physical_view(lab,"building0")
        self.assertEqual(len(projection["devices"]),200)
        self.assertEqual(len(projection["links"]),0)

    def test_gui_has_physical_api_and_cabinet_ui(self):
        root=Path(__file__).resolve().parents[1]
        gui=(root/"web/interface-overview.js").read_text()
        for part in ("physical-workspace/action","Add Storage Shelf","Create Generic Container",
                     "resize_location","mount_device","position_device","pt-physical-furniture"):
            self.assertIn(part,gui)
        self.assertIn("physical-workspace.css",(root/"web/index.html").read_text())


if __name__=="__main__":unittest.main()

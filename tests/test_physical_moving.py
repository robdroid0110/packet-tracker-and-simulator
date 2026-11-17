"""vendor Physical Workspace §16: move objects, navigation tree, cross-city cables."""
import json
import tempfile
import unittest
from pathlib import Path

from netsim.model import NetworkLab,LabError
from netsim.cli import CommandProcessor
from netsim.physical_workspace import physical_tree,physical_boundary_links,physical_view,action_command

class PhysicalMoveTests(unittest.TestCase):
    def setUp(self):
        self.lab=NetworkLab()
        self.cp=CommandProcessor(self.lab)
        for cmd in ["add router R1","add router R2","add pc PC1",
                    "connect R1 g0/0 R2 g0/0"]:
            self.assertFalse(self.cp.execute(cmd).startswith("ERROR:"),cmd)

    def test_group_move_stacks_and_preserves_links(self):
        city=self.lab.add_physical_location("city","Remote")
        original=[vars(x).copy() for x in self.lab.links]
        original_logical={n:(d.x,d.y) for n,d in self.lab.devices.items()}
        text=action_command({"action":"move_devices","devices":["R1","R2"],"location":city})
        self.assertEqual(text,"physical move-devices R1,R2 "+city)
        self.assertIn("moved 2",self.cp.execute(text))
        for name in ("R1","R2"):
            self.assertEqual(self.lab.device_locations[name],city)
            self.assertEqual((self.lab.physical_device_details[name]["x"],
                              self.lab.physical_device_details[name]["y"]),(28.0,24.0))
            self.assertEqual(self.lab.physical_device_details[name]["surface"],"floor")
            self.assertEqual((self.lab.devices[name].x,self.lab.devices[name].y),original_logical[name])
        self.assertEqual([vars(x) for x in self.lab.links],original)
        self.assertEqual(self.cp.execute("undo"),"Undo completed")
        self.assertEqual(self.lab.device_locations["R1"],"closet0")
        self.assertEqual(self.lab.device_locations["R2"],"closet0")
        self.assertEqual(self.cp.execute("redo"),"Redo completed")
        self.assertEqual(self.lab.device_locations["R1"],city)

    def test_move_into_closet_uses_rack_and_table(self):
        self.cp.execute("physical move-devices R1,PC1 intercity")
        self.assertIn("moved 2",self.cp.execute("physical move-devices R1,PC1 closet0"))
        self.assertEqual(self.lab.physical_device_details["R1"]["surface"],"rack")
        self.assertEqual(self.lab.physical_device_details["PC1"]["surface"],"table")

    def test_invalid_group_is_atomic(self):
        before=self.lab.to_dict()
        for cmd in [
            "physical move-devices R1,Missing city0",
            "physical move-devices R1,R1 city0",
            "physical move-devices R1 missing",
            "physical move-devices R1, city0",
        ]:
            with self.subTest(cmd=cmd):
                result=self.cp.execute(cmd)
                self.assertTrue(result.startswith("ERROR:"),result)
                self.assertEqual(self.lab.to_dict(),before)

    def test_invalid_json_action(self):
        bad=[
            {"action":"move_devices","devices":[],"location":"city0"},
            {"action":"move_devices","devices":"R1","location":"city0"},
            {"action":"move_devices","devices":["R1","R1"],"location":"city0"},
            {"action":"move_devices","devices":["R1",2],"location":"city0"},
            {"action":"move_devices","devices":["R1,M"],"location":"city0"},
            {"action":"move_devices","devices":["R1"],"location":None},
            {"action":"move_devices","devices":["R1"]*201,"location":"city0"},
        ]
        for item in bad:
            with self.subTest(item=item):
                with self.assertRaises(LabError):action_command(item)

    def test_tree_devices_nested_under_geography(self):
        tree=physical_tree(self.lab)
        self.assertTrue(tree["ok"])
        self.assertEqual(tree["device_count"],3)
        root=tree["tree"]
        self.assertEqual(root["id"],"intercity")
        city=root["children"][0];self.assertEqual(city["name"],"Home City")
        building=city["children"][0];self.assertEqual(building["name"],"Corporate Office")
        closet=building["children"][0]
        self.assertEqual({d["name"] for d in closet["devices"]},{"R1","R2"})
        self.assertEqual({d["name"] for d in building["devices"]},{"PC1"})
        self.assertEqual(closet["type"],"closet")
        self.assertEqual(tree["location_count"],3)

    def test_cross_city_boundary_links_and_status(self):
        distant=self.lab.add_physical_location("city","Remote")
        self.lab.move_physical_devices(["R1"],distant)
        at_top=physical_boundary_links(self.lab,"intercity")
        self.assertEqual(len(at_top),1)
        self.assertEqual(set((at_top[0]["source"],at_top[0]["destination"])),{"city0",distant})
        self.assertEqual(at_top[0]["links"],1)
        self.assertEqual(at_top[0]["up"],1)
        self.assertEqual(physical_boundary_links(self.lab,"closet0"),[])
        self.assertEqual(physical_view(self.lab)["boundary_links"],at_top)
        self.cp.execute("power R1 off")
        after=physical_boundary_links(self.lab,"intercity")
        self.assertEqual(after[0]["links"],1)
        self.assertEqual(after[0]["up"],0)
        self.cp.execute("physical move-devices R1 closet0")
        self.assertEqual(physical_boundary_links(self.lab,"intercity"),[])

    def test_multiple_cross_city_links_are_aggregated(self):
        distant=self.lab.add_physical_location("city","Remote")
        self.cp.execute("connect PC1 eth0 R1 g0/1")
        self.cp.execute("physical move-devices R1 "+distant)
        spans=physical_boundary_links(self.lab,"intercity")
        self.assertEqual(len(spans),1)
        self.assertEqual(spans[0]["links"],2)

    def test_relocate_container_reparents_descendants_without_resetting_devices(self):
        city=self.lab.add_physical_location("city","Remote")
        self.lab.relocate_physical_location("building0",city)
        self.assertIn("Remote",self.lab.physical_path("closet0"))
        self.assertEqual(self.lab.device_locations["R1"],"closet0")
        self.assertEqual(len(self.lab.links),1)

    def test_group_move_persists_saved_lab(self):
        city=self.lab.add_physical_location("city","Remote")
        self.lab.move_physical_devices(["R1","R2"],city)
        with tempfile.TemporaryDirectory() as d:
            path=Path(d)/"saved.json"
            self.lab.save(str(path))
            new=NetworkLab()
            new.load(str(path))
            self.assertEqual(new.device_locations,self.lab.device_locations)
            self.assertEqual(new.physical_device_details,self.lab.physical_device_details)
            self.assertEqual(physical_tree(new),physical_tree(self.lab))

    def test_200_device_move_and_tree(self):
        lab=NetworkLab()
        for i in range(200):lab.add_device("pc",f"PC{i}")
        city=lab.add_physical_location("city","Test")
        names=list(lab.devices)
        lab.move_physical_devices(names,city)
        self.assertEqual(physical_tree(lab)["device_count"],200)
        self.assertEqual(len(physical_tree(lab)["tree"]["children"][1]["devices"]),200)
        with self.assertRaises(LabError):lab.move_physical_devices(names+["PC0"],city)

    def test_ui_and_api_registration(self):
        root=Path(__file__).resolve().parents[1]
        src=(root/"web/physical-navigation.js").read_text()
        html=(root/"web/index.html").read_text()
        api=(root/"server.py").read_text()
        self.assertIn("physical-navigation.js",html)
        self.assertIn("physical-navigation.css",html)
        self.assertIn("ptPhysicalNavDialog",src)
        self.assertIn("application/x-pt-physical-move",src)
        self.assertIn("physical-workspace/tree",src)
        self.assertIn("move_devices",src)
        self.assertIn('"/api/physical-workspace/tree"',api)

if __name__=="__main__":unittest.main()

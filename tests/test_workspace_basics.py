import json
import tempfile
import unittest
from pathlib import Path

from netsim.model import LabError, NetworkLab
from netsim.cli import CommandProcessor

ROOT=Path(__file__).resolve().parents[1]


class WorkspaceBasicsTests(unittest.TestCase):
    def setUp(self):
        self.lab=NetworkLab()
        self.lab.add_device("pc","PC1",x=160,y=180)
        self.lab.add_device("switch","SW1",x=300,y=180)
        self.lab.add_device("pc","PC2",x=440,y=180)
        self.lab.connect("PC1","eth0","SW1","fa0/1")
        self.lab.connect("PC2","eth0","SW1","fa0/2")
        self.lab.set_ip("PC1","eth0","192.0.2.1/24")
        self.lab.set_ip("PC2","eth0","192.0.2.2/24")

    def test_default_hierarchy_and_placements(self):
        self.assertEqual(len(self.lab.physical_locations),3)
        self.assertEqual(self.lab.device_locations,{"PC1":"building0","PC2":"building0","SW1":"closet0"})
        self.assertEqual(self.lab.physical_path("closet0"),
                         "Intercity / Home City / Corporate Office / Main Wiring Closet")

    def test_add_move_rename_locations(self):
        city=self.lab.add_physical_location("city","Jaipur","intercity")
        building=self.lab.add_physical_location("building","School",city)
        closet=self.lab.add_physical_location("closet","Lab",building)
        self.lab.move_physical_location(building,345,580)
        self.lab.rename_physical_location(closet,"Networking Lab")
        self.assertEqual(self.lab.physical_locations[building]["x"],345)
        self.assertIn("Jaipur / School / Networking Lab",self.lab.physical_path(closet))

    def test_invalid_parent_rules_and_coordinates(self):
        for kind,parent in [("city","building0"),("building","closet0"),("closet","closet0")]:
            with self.assertRaises(LabError):
                self.lab.add_physical_location(kind,"X",parent)
        with self.assertRaises(LabError):
            self.lab.add_physical_location("rack","X","closet0")
        with self.assertRaises(LabError):
            self.lab.add_physical_location("city","Nope","missing")
        for val in (float("nan"),float("inf"),-1,10001):
            with self.assertRaises(LabError):
                self.lab.move_physical_location("city0",val,2)

    def test_move_physical_does_not_change_logical_network(self):
        before=self.lab.to_dict()
        ok,trace=self.lab.ping("PC1","192.0.2.2")
        self.assertTrue(ok,trace)
        new=self.lab.add_physical_location("city","Remote City")
        self.lab.place_physical_device("PC2",new)
        after=self.lab.to_dict()
        self.assertEqual(after["links"],self.lab.to_dict()["links"])
        self.assertEqual(after["links"],before["links"])
        for name in ("PC1","PC2","SW1"):
            for key in ("x","y","interfaces","routes"):
                self.assertEqual(after["devices"][name][key],self.lab.to_dict()["devices"][name][key])
        self.assertTrue(self.lab.ping("PC1","192.0.2.2")[0])

    def test_rename_remove_device_synchronizes_physical_placement(self):
        self.lab.place_physical_device("PC1","intercity")
        self.lab.rename_device("PC1","Client")
        self.assertNotIn("PC1",self.lab.device_locations)
        self.assertEqual(self.lab.device_locations["Client"],"intercity")
        self.lab.remove_device("Client")
        self.assertNotIn("Client",self.lab.device_locations)
        with self.assertRaises(LabError):
            self.lab.place_physical_device("Missing","closet0")
        with self.assertRaises(LabError):
            self.lab.place_physical_device("PC2","bad-location")

    def test_save_load_and_legacy_upgrade(self):
        city=self.lab.add_physical_location("city","Jaipur")
        self.lab.place_physical_device("PC1",city)
        with tempfile.TemporaryDirectory() as tmp:
            path=Path(tmp)/"network.json"
            self.lab.save(str(path))
            restored=NetworkLab();restored.load(str(path))
            self.assertEqual(restored.device_locations,self.lab.device_locations)
            self.assertEqual(restored.physical_locations,self.lab.physical_locations)
            self.assertTrue(restored.ping("PC1","192.0.2.2")[0])
            old=json.loads(path.read_text())
            old.pop("physical_locations")
            old.pop("device_locations")
            path.write_text(json.dumps(old))
            restored.load(str(path))
            self.assertEqual(restored.device_locations["PC1"],"building0")
            self.assertEqual(restored.device_locations["SW1"],"closet0")

    def test_reject_corrupt_placement_on_load(self):
        with tempfile.TemporaryDirectory() as tmp:
            path=Path(tmp)/"lab.json"
            data=self.lab.to_dict()
            data["device_locations"]["PC1"]="missing"
            path.write_text(json.dumps(data))
            with self.assertRaises(LabError):
                NetworkLab().load(str(path))
            data=self.lab.to_dict()
            data["physical_locations"]["city0"]["parent"]="building0"
            path.write_text(json.dumps(data))
            with self.assertRaises(LabError):
                NetworkLab().load(str(path))

    def test_agent_control_and_reset(self):
        cp=CommandProcessor(self.lab)
        self.assertIn("created physical location loc0",cp.execute('physical add building "Training Center" city0'))
        self.assertIn("placed PC1",cp.execute("physical place PC1 loc0"))
        self.assertIn("Training Center",cp.execute("show physical"))
        self.assertIn("renamed loc0",cp.execute('physical rename loc0 "Classroom"'))
        self.assertIn("moved location",cp.execute("physical position loc0 45 77"))
        self.assertTrue(cp.execute("physical add city Invalid closet0").startswith("ERROR:"))
        self.assertEqual(self.lab.physical_locations["loc0"]["name"],"Classroom")
        self.assertEqual(cp.execute("reset"),"lab reset")
        self.assertEqual(len(self.lab.physical_locations),3)
        self.assertEqual(self.lab.devices,{})
        self.assertEqual(self.lab.device_locations,{})

    def test_workspace_gui_has_state_synchronization(self):
        source=(ROOT/"web/interface-overview.js").read_text()
        for part in ["state.physical_locations","state.device_locations","action:'add_location'",
                     "window.PacketTrackerPhysicalNav?.open","action:'rename_location'","action:'move_location'","createInPhysical"]:
            self.assertIn(part,source)
        self.assertIn('workspace-basics.css',(ROOT/"web/index.html").read_text())


if __name__=="__main__":
    unittest.main()

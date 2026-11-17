"""legacy simulator help §17: physical distances, 100m copper gating and RF geometry."""
import json, math, tempfile, unittest
from pathlib import Path

from netsim.model import NetworkLab,LabError
from netsim.cli import CommandProcessor
from netsim.physical_distance import (
    distance_m,frame_scale,location_origin_m,projected_position,
    cable_length,physics_status,radio_default,radio_sources,radio_pairs,
    schema,action_command
)

class PhysicalDistanceTests(unittest.TestCase):
    def setUp(self):
        self.lab=NetworkLab();self.cp=CommandProcessor(self.lab)
        for cmd in [
            "add pc PC1","add pc PC2",
            "physical place PC1 city0","physical place PC2 city0",
            "physical device-position PC1 100 100",
            "physical device-position PC2 120 100",
            "connect PC1 eth0 PC2 eth0"
        ]:
            result=self.cp.execute(cmd)
            self.assertFalse(result.startswith("ERROR:"),result)

    def test_geometry_same_container_boundary_exact(self):
        self.assertAlmostEqual(distance_m(self.lab,"PC1","PC2"),100.0,places=6)
        cable=cable_length(self.lab,self.lab.links[0])
        self.assertTrue(cable["in_range"])
        self.assertEqual(cable["total_length_m"],100)
        self.assertEqual(len(cable["segments"]),1)
        self.assertEqual(cable["max_length_m"],100)
        self.assertFalse(cable["enforced"])
        self.assertEqual(frame_scale(self.lab,"city0")["meters_per_x"],5)

    def test_cable_effects_disabled_by_default(self):
        self.lab.physical_device_position("PC2",121,100)
        self.assertAlmostEqual(distance_m(self.lab,"PC1","PC2"),105)
        self.assertTrue(self.lab.link_operational(self.lab.links[0]))
        self.assertEqual(self.lab.link_status(self.lab.links[0])["reason"],"operational")

    def test_100m_limit_toggle_and_undo_redo(self):
        self.assertIn("on",self.cp.execute("physical cable-effects on"))
        self.assertTrue(self.lab.link_operational(self.lab.links[0]))
        self.assertTrue(self.lab.to_dict()["cable_length_effects"])
        self.cp.execute("physical device-position PC2 121 100")
        self.assertFalse(self.lab.link_operational(self.lab.links[0]))
        self.assertEqual(self.lab.link_status(self.lab.links[0])["reason"],
                         "cable length exceeds 100m")
        self.assertEqual(self.cp.execute("undo"),"Undo completed")
        self.assertTrue(self.lab.link_operational(self.lab.links[0]))
        self.assertEqual(self.cp.execute("redo"),"Redo completed")
        self.assertFalse(self.lab.link_operational(self.lab.links[0]))
        self.cp.execute("physical cable-effects off")
        self.assertTrue(self.lab.link_operational(self.lab.links[0]))

    def test_resizing_container_affects_distance(self):
        self.lab.physical_device_position("PC2",150,100)
        self.assertAlmostEqual(distance_m(self.lab,"PC1","PC2"),250)
        self.cp.execute("physical dimensions city0 1000 5000 500")
        self.assertAlmostEqual(distance_m(self.lab,"PC1","PC2"),50)
        self.lab.set_cable_length_effects(True)
        self.assertTrue(self.lab.link_operational(self.lab.links[0]))

    def test_nested_container_projection_across_city(self):
        self.lab.place_physical_device("PC1","closet0")
        self.lab.place_physical_device("PC2","building0")
        pos1=projected_position(self.lab,"PC1","city0")
        pos2=projected_position(self.lab,"PC2","city0")
        self.assertEqual(pos1["view_location"],"city0")
        self.assertNotEqual((pos1["x"],pos1["y"]),(pos2["x"],pos2["y"]))
        self.assertGreater(distance_m(self.lab,"PC1","PC2"),0)
        self.lab.move_physical_devices(["PC2"],"closet0")
        self.assertAlmostEqual(distance_m(self.lab,"PC1","PC2"),0)
        self.assertEqual(len(self.lab.links),1)

    def test_cross_city_distance_and_cable_down(self):
        city=self.lab.add_physical_location("city","Remote")
        self.lab.move_physical_location(city,350,150)
        self.lab.move_physical_devices(["PC2"],city)
        value=distance_m(self.lab,"PC1","PC2")
        self.assertGreater(value,1000)
        self.lab.set_cable_length_effects(True)
        self.assertFalse(self.lab.link_operational(self.lab.links[0]))
        self.assertTrue(self.lab.to_dict()["links"][0]["status"].startswith("cable length"))

    def test_source_and_client_radio_range_geometry(self):
        for cmd in [
            "add-model AccessPoint-PT AP1",
            'add-model "Cell Tower" Tower1',
            "add-model SMARTPHONE-PT Phone1",
            "add-model TabletPC-PT Tab1",
        ]:
            self.assertFalse(self.cp.execute(cmd).startswith("ERROR:"),cmd)
        for name in ("AP1","Tower1","Phone1","Tab1"):
            self.lab.place_physical_device(name,"city0")
        for cmd in [
            "physical device-position AP1 100 100",
            "physical device-position Tower1 100 100",
            "physical device-position Phone1 100 100",
            "physical device-position Tab1 102 100",
        ]:
            self.cp.execute(cmd)
        sources=radio_sources(self.lab,"city0")
        profiles={(entry["device"],entry["medium"]):entry["radius_m"] for entry in sources}
        self.assertEqual(profiles[("AP1","wifi")],140.0)
        self.assertEqual(profiles[("Tower1","cellular")],1000.0)
        self.assertEqual(profiles[("Phone1","bluetooth")],10.0)
        pairs=radio_pairs(self.lab)
        wifi=next(x for x in pairs if x["source"]=="AP1" and x["target"]=="Phone1")
        bt=next(x for x in pairs if x["source"]=="Phone1" and x["target"]=="Tab1")
        self.assertTrue(wifi["within_range"])
        self.assertTrue(bt["within_range"])
        self.assertEqual(bt["distance_m"],10.0)
        self.assertEqual(bt["protocol_association"],"not-modeled")
        self.lab.physical_device_position("Tab1",103,100)
        bt=next(x for x in radio_pairs(self.lab) if x["source"]=="Phone1" and x["target"]=="Tab1")
        self.assertFalse(bt["within_range"])
        self.lab.physical_device_position("Phone1",350,100)
        wifi=next(x for x in radio_pairs(self.lab) if x["source"]=="AP1" and x["target"]=="Phone1")
        self.assertFalse(wifi["within_range"])
        cell=next(x for x in radio_pairs(self.lab) if x["source"]=="Tower1" and x["target"]=="Phone1")
        self.assertFalse(cell["within_range"])

    def test_radio_range_configuration_validation_and_persistence(self):
        self.cp.execute("add-model AccessPoint-PT AP1")
        self.assertEqual(radio_default("AccessPoint-PT"),("wifi",140.0))
        self.assertEqual(radio_default("accesspoint-pt"),("wifi",140.0))
        self.assertIn("220m",self.cp.execute("physical radio-range AP1 220"))
        self.assertEqual(self.lab.radio_ranges["AP1"],220.0)
        self.assertEqual(self.cp.execute("undo"),"Undo completed")
        self.assertNotIn("AP1",self.lab.radio_ranges)
        self.assertEqual(self.cp.execute("redo"),"Redo completed")
        self.assertEqual(self.lab.radio_ranges["AP1"],220.0)
        self.assertTrue(self.cp.execute("physical radio-range PC1 140").startswith("ERROR:"))
        self.assertTrue(self.cp.execute("physical radio-range AP1 nan").startswith("ERROR:"))
        self.lab.rename_device("AP1","NewAP")
        self.assertEqual(self.lab.radio_ranges["NewAP"],220.0)
        self.lab.remove_device("NewAP")
        self.assertEqual(self.lab.radio_ranges,{})

    def test_radio_power_gate(self):
        self.cp.execute("add-model AccessPoint-PT AP1")
        self.cp.execute("add-model SMARTPHONE-PT Phone1")
        self.assertTrue(any(p["source"]=="AP1" for p in radio_pairs(self.lab)))
        self.cp.execute("power AP1 off")
        self.assertFalse(any(p["source"]=="AP1" for p in radio_pairs(self.lab)))
        self.assertFalse(next(x for x in radio_sources(self.lab) if x["device"]=="AP1")["powered"])

    def test_state_save_load_legacy(self):
        self.lab.set_cable_length_effects(True)
        self.cp.execute("add-model AccessPoint-PT AP1")
        self.lab.set_radio_range("AP1",140.5)
        with tempfile.TemporaryDirectory() as d:
            file=Path(d)/"saved.json"
            self.lab.save(str(file))
            loaded=NetworkLab();loaded.load(str(file))
            self.assertTrue(loaded.cable_length_effects)
            self.assertEqual(loaded.radio_ranges["AP1"],140.5)
            raw=json.loads(file.read_text())
            raw.pop("cable_length_effects")
            raw.pop("radio_ranges")
            file.write_text(json.dumps(raw))
            old=NetworkLab();old.load(str(file))
            self.assertFalse(old.cable_length_effects)
            self.assertEqual(old.radio_ranges,{})

    def test_reject_corrupt_saved_physics(self):
        self.cp.execute("add-model AccessPoint-PT AP1")
        cases=[
            {"cable_length_effects":"yes"},
            {"radio_ranges":{"AP1":float("nan")}},
            {"radio_ranges":{"PC1":140}},
            {"radio_ranges":{"missing":140}},
            {"radio_ranges":["bad"]},
        ]
        with tempfile.TemporaryDirectory() as d:
            file=Path(d)/"bad.json"
            for change in cases:
                raw=self.lab.to_dict()
                raw.update(change)
                file.write_text(json.dumps(raw))
                with self.subTest(change=change):
                    with self.assertRaises(LabError):NetworkLab().load(str(file))

    def test_api_action_validation_and_schema(self):
        self.assertEqual(action_command({"action":"cable_effects","enabled":True}),"physical cable-effects on")
        self.assertEqual(action_command({"action":"radio_range","device":"AP1","radius_m":140}),
                         "physical radio-range AP1 140")
        self.assertEqual(action_command({"action":"undo"}),"undo")
        self.assertEqual(schema()["write"]["method"],"POST")
        bad=[
            {},{"action":"fake"},
            {"action":"cable_effects","enabled":"on"},
            {"action":"radio_range","device":"AP1","radius_m":float("inf")},
            {"action":"radio_range","device":"AP1","radius_m":0},
            {"action":"radio_range","device":"AP1","radius_m":True},
        ]
        for item in bad:
            with self.subTest(item=item):
                with self.assertRaises(ValueError):action_command(item)

    def test_200_node_scalability(self):
        lab=NetworkLab()
        lab.add_device("generic","AP1",model="accesspoint-pt")
        for i in range(199):lab.add_device("pc",f"PC{i}")
        result=physics_status(lab,"city0")
        self.assertEqual(len(lab.devices),200)
        self.assertEqual(len(result["radios"]),1)
        self.assertEqual(len(result["links"]),0)

    def test_ui_and_routes_present(self):
        root=Path(__file__).resolve().parents[1]
        app=(root/"web/physical-distance.js").read_text()
        html=(root/"web/index.html").read_text()
        server=(root/"server.py").read_text()
        prefs=(root/"web/preferences.js").read_text()
        self.assertIn("/api/physical-distance",app)
        self.assertIn("pt-distance-cover",app)
        self.assertIn("physical-distance.js",html)
        self.assertIn("physical-distance.css",html)
        self.assertIn('"/api/physical-distance/schema"',server)
        self.assertIn('"/api/physical-distance/action"',server)
        self.assertIn("ptPrefCableEffects",prefs)
        self.assertIn("ptPrefWirelessGrid",prefs)

if __name__=="__main__":unittest.main()

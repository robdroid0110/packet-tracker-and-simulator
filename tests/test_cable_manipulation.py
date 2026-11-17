"""vendor §19 cable bend points, color, shared group points and routed length."""
import json,math,tempfile,unittest
from pathlib import Path

from netsim.model import LabError,NetworkLab
from netsim.cli import CommandProcessor
from netsim.cable_manipulation import (
 key,view,route_for,add_bend,move_bend,delete_bend,group_bends,
 move_group,ungroup,set_color,group_members,validate_load,action_command,schema,
)

class CableManipulationTests(unittest.TestCase):
    def setUp(self):
        self.lab=NetworkLab();self.cp=CommandProcessor(self.lab)
        for command in [
            "add pc A","add pc B","add pc C","add pc D",
            "physical place A city0","physical place B city0",
            "physical place C city0","physical place D city0",
            "physical device-position A 100 100",
            "physical device-position B 120 100",
            "physical device-position C 100 120",
            "physical device-position D 120 120",
            "connect A eth0 B eth0","connect C eth0 D eth0"
        ]:
            result=self.cp.execute(command)
            self.assertFalse(result.startswith("ERROR:"),result)

    def bends(self,device="A"):
        link=self.lab.link_for(device,"eth0")
        return route_for(self.lab,link)["bends"]

    def test_default_has_straight_length_and_no_route(self):
        self.assertEqual(len(self.lab.cable_routes),0)
        summary=self.lab.link_status(self.lab.links[0])
        self.assertEqual(summary["total_length_m"],100)
        self.assertEqual(summary["model"],"2d-straight-line")
        self.assertEqual(len(view(self.lab,"city0")["cables"]),2)

    def test_adding_and_moving_bend_updates_path_and_100m_carrier(self):
        self.lab.set_cable_length_effects(True)
        link=self.lab.links[0]
        self.assertTrue(self.lab.link_operational(link))
        direct=self.lab.link_status(link)["distance_m"]
        p1=self.lab.physical_device_details["A"]
        b=add_bend(self.lab,"A","eth0",3350,3114.285714285714+25)
        summary=self.lab.link_status(link)
        self.assertEqual(len(summary["segments"]),2)
        self.assertEqual(summary["model"],"2d-polyline")
        self.assertAlmostEqual(summary["distance_m"],direct)
        self.assertGreater(summary["total_length_m"],100)
        self.assertFalse(summary["up"])
        self.assertEqual(summary["reason"],"cable length exceeds 100m")
        move_bend(self.lab,"A","eth0",b,3350,3114.285714285714)
        self.assertAlmostEqual(self.lab.link_status(link)["total_length_m"],100,places=4)
        self.assertTrue(self.lab.link_operational(link))
        delete_bend(self.lab,"A","eth0",b)
        self.assertEqual(self.lab.link_status(link)["model"],"2d-straight-line")
        self.assertNotIn(key(link),self.lab.cable_routes)

    def test_insert_bends_in_order_and_recalculate_length(self):
        first=add_bend(self.lab,"A","eth0",3300,3120)
        second=add_bend(self.lab,"A","eth0",3400,3120,after=first)
        third=add_bend(self.lab,"A","eth0",3300,3130,after="start")
        self.assertEqual([b["id"] for b in self.bends()],[third,first,second])
        with self.assertRaises(LabError):
            add_bend(self.lab,"A","eth0",3300,3100,after="missing")
        self.assertEqual(len(self.bends()),3)

    def test_two_cables_group_synchronize_coordinate_movement(self):
        first=add_bend(self.lab,"A","eth0",3350,3150)
        second=add_bend(self.lab,"C","eth0",3350,3150)
        group=group_bends(self.lab,"A","eth0",first,"C","eth0",second)
        self.assertTrue(group.startswith("group_"))
        self.assertEqual(len(group_members(self.lab,group)),2)
        self.assertEqual(self.bends("A")[0]["group"],group)
        self.assertEqual(self.bends("C")[0]["group"],group)
        move_group(self.lab,group,3344,3100)
        self.assertEqual((self.bends("A")[0]["x_m"],self.bends("A")[0]["y_m"]),(3344,3100))
        self.assertEqual((self.bends("C")[0]["x_m"],self.bends("C")[0]["y_m"]),(3344,3100))
        move_bend(self.lab,"A","eth0",first,3300,3010)
        self.assertEqual((self.bends("C")[0]["x_m"],self.bends("C")[0]["y_m"]),(3300,3010))
        moved=ungroup(self.lab,group,"A","eth0")
        self.assertEqual(moved,1)
        self.assertIsNone(self.bends("A")[0]["group"])
        self.assertIsNone(self.bends("C")[0]["group"])
        self.assertEqual(len(self.lab.links),2)

    def test_two_group_points_make_shared_black_segment(self):
        a1=add_bend(self.lab,"A","eth0",3330,3150)
        c1=add_bend(self.lab,"C","eth0",3330,3150)
        a2=add_bend(self.lab,"A","eth0",3380,3150)
        c2=add_bend(self.lab,"C","eth0",3380,3150)
        group_bends(self.lab,"A","eth0",a1,"C","eth0",c1)
        group_bends(self.lab,"A","eth0",a2,"C","eth0",c2)
        set_color(self.lab,"A","eth0","#ff1122")
        lengths=self.lab.link_status(self.lab.links[0])["segments"]
        self.assertEqual([s["color"] for s in lengths],["#ff1122","#202020","#ff1122"])
        self.assertEqual([s["grouped"] for s in lengths],[False,True,False])

    def test_ungroup_all_and_deleting_bend_does_not_delete_cable(self):
        x=add_bend(self.lab,"A","eth0",3301,3100)
        y=add_bend(self.lab,"C","eth0",3301,3100)
        group=group_bends(self.lab,"A","eth0",x,"C","eth0",y)
        self.assertEqual(ungroup(self.lab,group),2)
        self.assertIsNone(self.bends("A")[0]["group"])
        self.assertIsNone(self.bends("C")[0]["group"])
        with self.assertRaises(LabError):ungroup(self.lab,group)
        delete_bend(self.lab,"A","eth0",x)
        self.assertEqual(len(self.lab.links),2)
        self.assertEqual(self.bends("A"),[])

    def test_color_and_reset_not_same_as_group_color(self):
        set_color(self.lab,"A","eth0","#AABBcc")
        self.assertEqual(route_for(self.lab,self.lab.links[0])["color"],"#aabbcc")
        self.assertEqual(self.lab.link_status(self.lab.links[0])["segments"][0]["color"],"#aabbcc")
        set_color(self.lab,"A","eth0","#24354b")
        self.assertNotIn(key(self.lab.links[0]),self.lab.cable_routes)

    def test_disconnection_cleanup_and_renaming_preserves_route(self):
        self.lab.set_cable_length_effects(True)
        bend=add_bend(self.lab,"A","eth0",3300,3200)
        set_color(self.lab,"A","eth0","#0000dd")
        self.cp.execute("rename A Alpha")
        self.assertEqual(len(self.lab.cable_routes),1)
        self.assertEqual(self.bends("Alpha")[0]["id"],bend)
        self.assertEqual(route_for(self.lab,self.lab.links[0])["color"],"#0000dd")
        self.cp.execute("disconnect Alpha eth0")
        self.assertEqual(len(self.lab.links),1)
        self.assertEqual(self.lab.cable_routes,{})
        self.cp.execute("remove C")
        self.assertEqual(self.lab.cable_routes,{})

    def test_shared_group_cleanup_on_disconnection(self):
        x=add_bend(self.lab,"A","eth0",3300,3100)
        y=add_bend(self.lab,"C","eth0",3300,3100)
        group=group_bends(self.lab,"A","eth0",x,"C","eth0",y)
        self.cp.execute("disconnect A eth0")
        self.assertIsNone(self.bends("C")[0]["group"])
        self.assertFalse(group_members(self.lab,group))

    def test_cli_undo_redo_and_portable_save_load(self):
        self.lab.set_cable_length_effects(True)
        res=self.cp.execute("cable bend-add A eth0 3300 3140")
        self.assertIn("bend created",res)
        ident=res.split()[-1]
        self.assertFalse(self.lab.link_operational(self.lab.links[0]))
        self.assertEqual(self.cp.execute("undo"),"Undo completed")
        self.assertTrue(self.lab.link_operational(self.lab.links[0]))
        self.assertEqual(self.cp.execute("redo"),"Redo completed")
        self.assertFalse(self.lab.link_operational(self.lab.links[0]))
        self.assertEqual(self.bends()[0]["id"],ident)
        self.cp.execute("cable color A eth0 #00bbdd")
        with tempfile.TemporaryDirectory() as d:
            path=Path(d)/"lab.json"
            self.lab.save(str(path))
            restored=NetworkLab();restored.load(str(path))
            self.assertEqual(restored.cable_routes,self.lab.cable_routes)
            self.assertEqual(restored.link_status(restored.links[0])["up"],False)
            data=json.loads(path.read_text())
            data.pop("cable_routes")
            path.write_text(json.dumps(data))
            legacy=NetworkLab();legacy.load(str(path))
            self.assertEqual(legacy.cable_routes,{})
            self.assertEqual(legacy.link_status(legacy.links[0])["total_length_m"],100)

    def test_invalid_actions_dont_mutate(self):
        before=self.lab.to_dict()
        for action in [
            "cable bend-add A eth0 nan 1",
            "cable bend-add A eth0 inf 1",
            "cable color A eth0 red",
            "cable bend-delete A eth0 unknown",
            "cable bend-move A eth0 unknown 1 2",
            "cable group-move group_notreal 1 2",
            "cable bend-add Missing eth0 1 2",
            "cable group A eth0 fake C eth0 fake",
            "cable ungroup group_missing",
        ]:
            with self.subTest(action=action):
                result=self.cp.execute(action)
                self.assertTrue(result.startswith("ERROR:"),result)
                self.assertEqual(self.lab.to_dict(),before)

    def test_saved_route_validation(self):
        x=add_bend(self.lab,"A","eth0",3300,3100)
        y=add_bend(self.lab,"C","eth0",3300,3100)
        group=group_bends(self.lab,"A","eth0",x,"C","eth0",y)
        baseline=self.lab.to_dict()
        def damage(data,f):
            return f(data)
        for mutate in [
            lambda d:d["cable_routes"].update({"bogus":{"color":"#000000","bends":[]}}),
            lambda d:next(iter(d["cable_routes"].values())).update(color="red"),
            lambda d:next(iter(d["cable_routes"].values()))["bends"][0].update(x_m=float("nan")),
            lambda d:next(iter(d["cable_routes"].values()))["bends"][0].update(id="bad"),
            lambda d:next(iter(d["cable_routes"].values()))["bends"][0].update(group="group_deadbeefdeadbeef"),
            lambda d:next(iter(d["cable_routes"].values()))["bends"].append(dict(next(iter(d["cable_routes"].values()))["bends"][0])),
        ]:
            with self.subTest(mutation=mutate):
                data=json.loads(json.dumps(baseline))
                mutate(data)
                with tempfile.NamedTemporaryFile("w",suffix=".json") as f:
                    json.dump(data,f);f.flush()
                    with self.assertRaises(LabError):NetworkLab().load(f.name)

    def test_api_contract_and_bad_input(self):
        result=action_command({"action":"add_bend","device":"A","interface":"eth0","x_m":3300,"y_m":3100,"after":"start"})
        self.assertEqual(result,"cable bend-add A eth0 3300.0 3100.0 start")
        self.assertEqual(action_command({"action":"undo"}),"undo")
        self.assertIn("group_bends",schema()["write"]["actions"])
        for action in [
            {"action":"add_bend","device":"A","interface":"eth0","x_m":"bad","y_m":5},
            {"action":"move_group","group":"g","x_m":float("inf"),"y_m":1},
            {"action":"set_color","device":"A","interface":"eth0","color":"javascript:1"},
            {"action":"invalid"},
        ]:
            with self.subTest(action=action):
                with self.assertRaises(LabError):action_command(action)

    def test_100_links_and_200_devices(self):
        lab=NetworkLab()
        for i in range(200):lab.add_device("pc",f"PC{i}")
        for i in range(0,200,2):
            lab.connect(f"PC{i}","eth0",f"PC{i+1}","eth0")
        self.assertEqual(len(lab.links),100)
        for i in range(0,200,2):
            add_bend(lab,f"PC{i}","eth0",3300,3100)
        self.assertEqual(len(view(lab,"building0")["cables"]),100)
        self.assertEqual(sum(len(r["bends"]) for r in lab.cable_routes.values()),100)

    def test_web_bundle_registered(self):
        root=Path(__file__).resolve().parents[1]
        html=(root/"web/index.html").read_text()
        js=(root/"web/physical-cables.js").read_text()
        server=(root/"server.py").read_text()
        for phrase in ("physical-cables.js","physical-cables.css"):self.assertIn(phrase,html)
        for phrase in ("pt-cable-group-point","group_bends","move_group","delete_bend","set_color","ptCablePanel"):
            self.assertIn(phrase,js)
        self.assertIn('"/api/physical-cables/schema"',server)
        self.assertIn('"/api/physical-cables/action"',server)

if __name__=="__main__":unittest.main()

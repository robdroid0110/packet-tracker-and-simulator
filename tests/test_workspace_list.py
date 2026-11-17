import json
import tempfile
import unittest
from pathlib import Path

from netsim.model import LabError, NetworkLab
from netsim.cli import CommandProcessor
from netsim.workspace_list import workspace_list, action_to_command


class WorkspaceListTests(unittest.TestCase):
    def setUp(self):
        self.lab=NetworkLab()
        self.cp=CommandProcessor(self.lab)
        for cmd in [
            "add-model router-pt R1 200 100",
            "add-model pc-pt PC1 450 100",
            "add-model switch-pt SW1 300 190",
            "connect R1 g0/0 SW1 fa0/1 copper-straight",
            "connect PC1 eth0 SW1 fa0/2 copper-straight",
        ]:
            out=self.cp.execute(cmd)
            self.assertFalse(out.startswith("ERROR:"),out)

    def test_root_projection_has_device_columns_and_links(self):
        data=workspace_list(self.lab)
        self.assertEqual(len(data["devices"]),3)
        self.assertEqual(len(data["links"]),2)
        self.assertEqual(data["path"],[{"id":"root","name":"Root"}])
        self.assertEqual(data["devices"][0]["model"],"router-pt")
        self.assertEqual((data["devices"][0]["x"],data["devices"][0]["y"]),(200,100))
        self.assertEqual(data["links"][0]["cable"],"copper-straight")
        self.assertEqual(data["links"][1]["source"],"PC1:eth0")

    def test_nested_cluster_scope_and_parent(self):
        self.assertIn("created cluster",self.cp.execute("cluster add Campus PC1,SW1"))
        self.assertIn("created cluster",self.cp.execute("cluster add Floor PC1 Cluster0"))
        root=workspace_list(self.lab)
        self.assertEqual([d["name"] for d in root["devices"]],["R1"])
        self.assertEqual([c["name"] for c in root["clusters"]],["Campus"])
        self.assertEqual(root["links"],[])
        campus=workspace_list(self.lab,"Cluster0")
        self.assertEqual([d["name"] for d in campus["devices"]],["SW1"])
        self.assertEqual(campus["parent"],"root")
        self.assertEqual([c["name"] for c in campus["clusters"]],["Floor"])
        floor=workspace_list(self.lab,"Cluster1","PC1")
        self.assertEqual([d["name"] for d in floor["devices"]],["PC1"])
        self.assertEqual(floor["parent"],"Cluster0")
        self.assertEqual(len(floor["path"]),3)
        with self.assertRaises(LabError):workspace_list(self.lab,"root","PC1")
        with self.assertRaises(LabError):workspace_list(self.lab,"missing")

    def test_add_inside_nested_cluster_is_atomic_and_undoable(self):
        self.cp.execute("cluster add Campus PC1")
        self.cp.execute("cluster add Floor none Cluster0")
        req={"action":"add_device","model":"pc-pt","name":"PC2NEW","x":188,"y":214,"cluster":"Cluster1"}
        output=self.cp.execute(action_to_command(req))
        self.assertIn("added PC2NEW in cluster Cluster1",output)
        self.assertEqual([d["name"] for d in workspace_list(self.lab,"Cluster1")["devices"]],["PC2NEW"])
        self.assertEqual([d["name"] for d in workspace_list(self.lab,"root")["devices"]],["R1","SW1"])
        self.assertEqual(self.cp.execute("undo"),"Undo completed")
        self.assertNotIn("PC2NEW",self.lab.devices)
        self.assertNotIn("PC2NEW",self.lab.clusters["Cluster1"]["devices"])
        self.assertTrue(self.cp.execute("add-in-cluster pc P3 120 140 missing").startswith("ERROR:"))
        self.assertNotIn("P3",self.lab.devices)

    def test_link_light_updates_power_and_wrong_cable(self):
        before=workspace_list(self.lab)["links"]
        self.assertTrue(before[0]["up"])
        self.assertEqual(before[0]["light"],"green")
        self.cp.execute("power SW1 off")
        after=workspace_list(self.lab)["links"]
        self.assertTrue(all(not link["up"] for link in after))
        self.assertTrue(all(link["light"]=="red" for link in after))

    def test_module_install_requires_power_off(self):
        data=workspace_list(self.lab,device="R1")
        self.assertEqual(len(data["selected"]["slots"]),3)
        self.assertEqual(data["selected"]["slots"][1]["slot"],"slot0")
        self.assertEqual(data["selected"]["slots"][1]["module"],None)
        self.assertIn("ERROR:",self.cp.execute("module R1 slot0 PT-ETH-4"))
        self.assertFalse(self.lab.devices["R1"].modules)
        self.cp.execute("power R1 off")
        self.assertIn("set to",self.cp.execute("module R1 slot0 PT-ETH-4"))
        slots=workspace_list(self.lab,device="R1")["selected"]["slots"]
        self.assertEqual(slots[1]["interfaces"],["m0/1","m0/2","m0/3","m0/4"])
        self.assertIn("m0/4",self.lab.devices["R1"].interfaces)

    def test_module_cabling_and_removal_guard(self):
        self.cp.execute("power R1 off")
        self.cp.execute("module R1 slot0 PT-ETH-1")
        self.cp.execute("power R1 on")
        self.assertEqual(self.cp.execute("connect R1 m0/1 PC1 eth0"),"ERROR: an interface can only have one cable")  # PC eth0 already occupied
        self.cp.execute("add pc PC2 100 100")
        self.assertEqual(self.cp.execute("connect R1 m0/1 PC2 eth0"),"link created")
        self.cp.execute("power R1 off")
        self.assertTrue(self.cp.execute("module R1 slot0 none").startswith("ERROR:"))
        self.assertIn("m0/1",self.lab.devices["R1"].interfaces)
        self.cp.execute("disconnect PC2 eth0")
        self.assertIn("set to none",self.cp.execute("module R1 slot0 none"))
        self.assertNotIn("m0/1",self.lab.devices["R1"].interfaces)

    def test_non_pt_vendor_hardware_no_fake_slots(self):
        self.cp.execute("add-model 2960-24tt SW2")
        self.assertEqual(len(workspace_list(self.lab,device="SW2")["selected"]["slots"]),1)
        self.cp.execute("power SW2 off")
        self.assertTrue(self.cp.execute("module SW2 slot0 PT-ETH-1").startswith("ERROR:"))
        self.assertEqual(self.lab.devices["SW2"].modules,{})

    def test_save_load_module_and_legacy(self):
        self.cp.execute("power R1 off")
        self.cp.execute("module R1 slot1 PT-ETH-1")
        with tempfile.TemporaryDirectory() as temp:
            path=Path(temp)/"saved.json"
            self.lab.save(str(path))
            loaded=NetworkLab();loaded.load(str(path))
            self.assertEqual(loaded.devices["R1"].modules["slot1"],"PT-ETH-1")
            self.assertIn("m1/1",loaded.devices["R1"].interfaces)
            data=json.loads(path.read_text())
            del data["devices"]["R1"]["modules"]
            del data["devices"]["R1"]["interfaces"]["m1/1"]
            path.write_text(json.dumps(data))
            old=NetworkLab();old.load(str(path))
            self.assertEqual(old.devices["R1"].modules,{})
            self.assertEqual(len(old.module_slots("R1")),2)

    def test_invalid_saved_modules_rejected(self):
        data=self.lab.to_dict()
        data["devices"]["R1"]["modules"]={"slot6":"PT-ETH-4"}
        with tempfile.TemporaryDirectory() as temp:
            p=Path(temp)/"bad.json"
            p.write_text(json.dumps(data))
            with self.assertRaises(LabError):NetworkLab().load(str(p))

    def test_json_action_adapter_is_typed_and_undoable(self):
        req={"action":"add_device","model":"pc-pt","name":"PC2","x":180,"y":300}
        self.assertIn("pc-pt PC2",action_to_command(req))
        self.assertIn("added",self.cp.execute(action_to_command(req)))
        self.assertIn("PC2",self.lab.devices)
        move=action_to_command({"action":"move_device","device":"PC2","x":300.5,"y":420})
        self.assertEqual(self.cp.execute(move),"moved")
        self.cp.execute(action_to_command({"action":"undo"}))
        self.assertEqual(self.lab.devices["PC2"].x,180)

    def test_typed_actions_mapping(self):
        cases=[
            ({"action":"power_device","device":"PC1","powered":False},"power PC1 off"),
            ({"action":"remove_device","device":"PC1"},"remove PC1"),
            ({"action":"add_link","a_device":"PC1","a_if":"eth0","b_device":"SW1","b_if":"fa0/2","cable":"auto"},"connect PC1 eth0 SW1 fa0/2 auto"),
            ({"action":"remove_link","device":"PC1","iface":"eth0"},"disconnect PC1 eth0"),
            ({"action":"set_module","device":"R1","slot":"slot0","module":None},"module R1 slot0 none"),
            ({"action":"redo"},"redo"),
        ]
        for req,expected in cases:
            with self.subTest(req=req):
                self.assertEqual(action_to_command(req),expected)

    def test_invalid_json_actions_rejected(self):
        invalid=[
            {},{"action":"invalid"},
            {"action":"move_device","device":"PC1","x":float("nan"),"y":40},
            {"action":"add_device","model":"unknown","name":"New","x":100,"y":100},
            {"action":"add_link","a_device":"PC1","a_if":"eth0","b_device":"SW1","b_if":"fa0/1","cable":"quantum-cable"},
            {"action":"set_module","device":"R1","slot":"slot0","module":"CISCO-FAKE"},
            {"action":"power_device","device":"R1","powered":"off"},
        ]
        for req in invalid:
            with self.subTest(req=req):
                with self.assertRaises(LabError):action_to_command(req)

    def test_rest_projection_200_devices_efficiency(self):
        lab=NetworkLab()
        for i in range(200):lab.add_device("pc",f"PC{i}",x=(i%10)*130,y=(i//10)*80)
        result=workspace_list(lab)
        self.assertEqual(len(result["devices"]),200)
        self.assertEqual(len(result["links"]),0)

    def test_browser_resources_and_api_routes(self):
        root=Path(__file__).resolve().parents[1]
        js=(root/"web/workspace-list.js").read_text()
        html=(root/"web/index.html").read_text()
        api=(root/"server.py").read_text()
        self.assertIn("workspace-list.css",html)
        self.assertIn("workspace-list.js",html)
        self.assertIn('"/api/workspace-list"',api)
        self.assertIn('"/api/workspace-list/action"',api)
        self.assertIn("aria-live",js)
        self.assertIn("data-coordinate",js)
        self.assertIn("data-slot",js)


if __name__=="__main__":unittest.main()

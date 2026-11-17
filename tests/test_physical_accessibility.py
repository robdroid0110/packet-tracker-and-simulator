"""legacy network simulator help section 21: physical accessibility contracts."""
import unittest
from pathlib import Path
from netsim.model import NetworkLab,LabError
from netsim.cli import CommandProcessor
from netsim.physical_accessibility import view,command,schema

class PhysicalAccessibilityTests(unittest.TestCase):
    def setUp(self):
        self.lab=NetworkLab()
        self.cp=CommandProcessor(self.lab)
        for cmd in ["add pc PC1","add pc PC2","add router R1",
                    "physical place PC1 closet0","physical place PC2 closet0",
                    "physical place R1 closet0"]:
            out=self.cp.execute(cmd)
            self.assertFalse(out.startswith("ERROR:"),out)

    def test_location_tree_and_breadcrumbs(self):
        root=view(self.lab)
        self.assertEqual(root["children"][0]["id"],"city0")
        self.assertEqual(root["count"]["devices"],0)
        closet=view(self.lab,"closet0")
        self.assertEqual([p["id"] for p in closet["path"]],
                         ["intercity","city0","building0","closet0"])
        self.assertEqual(closet["parent"],"building0")
        self.assertEqual(closet["count"]["devices"],3)
        self.assertEqual({s["id"] for s in closet["surfaces"]},{"rack","table","floor"})
        with self.assertRaises(LabError):view(self.lab,"missing")

    def test_port_status_and_disconnection(self):
        self.assertEqual(self.cp.execute("connect PC1 eth0 R1 g0/0"),"link created")
        devices={d["name"]:d for d in view(self.lab,"closet0")["devices"]}
        self.assertEqual(devices["PC1"]["ports"][0]["peer"],{"device":"R1","interface":"g0/0"})
        self.assertTrue(devices["PC1"]["ports"][0]["operational"])
        self.assertFalse(devices["PC2"]["ports"][0]["connected"])
        self.cp.execute("power R1 off")
        self.assertFalse(next(d for d in view(self.lab,"closet0")["devices"]
                              if d["name"]=="PC1")["ports"][0]["operational"])
        self.cp.execute("disconnect PC1 eth0")
        self.assertFalse(next(d for d in view(self.lab,"closet0")["devices"]
                              if d["name"]=="PC1")["ports"][0]["connected"])

    def test_rack_and_shelf(self):
        self.assertEqual(next(s for s in view(self.lab,"closet0")["surfaces"]
                              if s["id"]=="rack")["count"],1)
        self.cp.execute("physical shelf-add closet0")
        self.cp.execute("power PC2 off")
        self.cp.execute("physical mount PC2 shelf 0")
        out=view(self.lab,"closet0")
        self.assertEqual(next(s for s in out["surfaces"] if s["id"]=="shelf:0")["count"],1)

    def test_industrial_control_panel(self):
        icp=self.cp.execute('icp create medium "Factory" building0').split()[-1]
        self.cp.execute("physical place PC1 "+icp)
        result=view(self.lab,icp)
        self.assertEqual([x["id"] for x in result["surfaces"]],["cabinet","door"])
        self.assertEqual(result["devices"][0]["surface"],"cabinet")

    def test_typed_actions(self):
        pairs=[
          (dict(action="move_device",device="PC1",location="closet0"),"physical place PC1 closet0"),
          (dict(action="mount_device",device="R1",surface="rack"),"physical mount R1 rack"),
          (dict(action="mount_device",device="PC2",surface="shelf",shelf=0),"physical mount PC2 shelf 0"),
          (dict(action="add_device",model="pc",name="PC4",location="closet0"),"physical add-device pc PC4 140 130 closet0"),
          (dict(action="place_icp_device",device="PC1",side="door",x=80,y=120),"icp device-move PC1 door 80 120 0 detach"),
          (dict(action="connect",a_device="PC1",a_if="eth0",b_device="R1",b_if="g0/0",cable="auto"),"connect PC1 eth0 R1 g0/0 auto"),
          (dict(action="disconnect",device="PC1",interface="eth0"),"disconnect PC1 eth0"),
          (dict(action="power",device="R1",enabled=False),"power R1 off"),
          (dict(action="add_shelf",location="closet0"),"physical shelf-add closet0"),
          (dict(action="set_module",device="R1",slot="0",module="PT-ETH-1"),"module R1 0 PT-ETH-1"),
          (dict(action="undo"),"undo"),(dict(action="redo"),"redo"),
        ]
        for payload,result in pairs:
            with self.subTest(payload=payload):self.assertEqual(command(payload),result)

    def test_invalid_typed_actions(self):
        invalid=[
          {},{"action":"missing"},
          {"action":"connect","a_device":"PC1","a_if":"eth0","b_device":"R1","b_if":"g0/0","cable":"fiber"},
          {"action":"mount_device","device":"PC1","surface":"ceiling"},
          {"action":"mount_device","device":"PC1","surface":"shelf","shelf":True},
          {"action":"power","device":"PC1","enabled":"on"},
          {"action":"place_icp_device","device":"PC1","side":"rack","x":100,"y":100},
          {"action":"place_icp_device","device":"PC1","side":"door","x":-5,"y":100},
          {"action":"add_device","model":"pc","name":"PC4","location":"closet0","x":-1},
        ]
        for payload in invalid:
            with self.subTest(payload=payload):
                with self.assertRaises((LabError,ValueError,TypeError)):command(payload)

    def test_agent_creates_connects_and_moves(self):
        for payload in [
          dict(action="add_device",model="server",name="Srv3",location="closet0"),
          dict(action="connect",a_device="Srv3",a_if="eth0",b_device="R1",b_if="g0/1",cable="auto"),
          dict(action="mount_device",device="Srv3",surface="rack"),
        ]:
            out=self.cp.execute(command(payload))
            self.assertFalse(out.startswith("ERROR:"),out)
        out=view(self.lab,"closet0")
        self.assertEqual(out["count"]["devices"],4)
        device=next(d for d in out["devices"] if d["name"]=="Srv3")
        self.assertEqual(device["surface"],"rack")
        self.assertTrue(device["ports"][0]["connected"])

    def test_200_devices(self):
        lab=NetworkLab()
        for i in range(200):
            lab.add_device("pc",f"PC{i}")
            lab.place_physical_device(f"PC{i}","closet0",recompute=False)
        result=view(lab,"closet0")
        self.assertEqual(result["count"]["devices"],200)

    def test_api_and_ui_contracts(self):
        s=schema()
        self.assertIn("connect",s["write"]["actions"])
        self.assertTrue(any("rack units" in p for p in s["rules"]))
        root=Path(__file__).resolve().parents[1]
        frontend=(root/"web/physical-accessibility.js").read_text()
        css=(root/"web/physical-accessibility.css").read_text()
        html=(root/"web/index.html").read_text()
        server=(root/"server.py").read_text()
        main=(root/"web/interface-overview.js").read_text()
        for text in ("role','dialog","aria-live","ArrowUp","ArrowDown",
                     "ArrowLeft","ArrowRight","Escape","altKey",
                     "mount_device","connect","disconnect","sourcePort"):
            self.assertIn(text,frontend)
        self.assertIn("focus-visible",css)
        self.assertIn("physical-accessibility.js",html)
        self.assertIn("Accessible Physical Navigation",main)
        self.assertIn('"/api/physical-accessibility/action"',server)

if __name__=="__main__":unittest.main()

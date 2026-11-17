import unittest
from pathlib import Path
from copy import deepcopy
from netsim.model import NetworkLab, LabError
from netsim.cli import CommandProcessor
ROOT=Path(__file__).resolve().parents[1]


class LogicalWorkspaceTests(unittest.TestCase):
    def setUp(self):
        self.lab=NetworkLab()
        self.cp=CommandProcessor(self.lab)
        for line in [
            "add pc PC1 150 150","add switch SW1 350 150","add router R1 550 150",
            "ip PC1 eth0 10.2.0.10/24","connect PC1 eth0 SW1 fa0/1",
            "connect SW1 fa0/2 R1 g0/0"
        ]:
            self.assertFalse(self.cp.execute(line).startswith("ERROR:"),line)

    def test_duplicate_copies_only_internal_links_and_fresh_macs(self):
        original=deepcopy(self.lab.to_dict())
        cmd=self.cp.execute("duplicate PC1,SW1 140 70")
        self.assertIn("PC1_copy",cmd)
        self.assertIn("SW1_copy",cmd)
        self.assertEqual(len(self.lab.devices),5)
        self.assertEqual(len(self.lab.links),3)
        self.assertEqual(self.lab.devices["PC1_copy"].interfaces["eth0"].ip,"10.2.0.10/24")
        self.assertNotEqual(self.lab.devices["PC1_copy"].interfaces["eth0"].mac,self.lab.devices["PC1"].interfaces["eth0"].mac)
        self.assertTrue(any({l.a_device,l.b_device}=={"PC1_copy","SW1_copy"} for l in self.lab.links))
        self.assertFalse(any({l.a_device,l.b_device}=={"SW1_copy","R1"} for l in self.lab.links))
        self.assertEqual(self.lab.devices["PC1_copy"].x,290)
        self.assertEqual(self.lab.device_locations["PC1_copy"],self.lab.device_locations["PC1"])
        self.assertEqual(self.lab.links[0].cable,original["links"][0]["cable"])

    def test_duplicate_names_are_unique_on_repeated_paste(self):
        self.cp.execute("duplicate PC1,SW1 100 100")
        self.cp.execute("duplicate PC1,SW1 160 160")
        self.assertIn("PC1_copy2",self.lab.devices)
        self.assertIn("SW1_copy2",self.lab.devices)
        self.assertEqual(len(self.lab.links),4)

    def test_undo_redo_restore_in_place(self):
        identity=id(self.lab)
        original=deepcopy(self.lab.to_dict())
        self.cp.execute("duplicate PC1,SW1 100 100")
        self.assertEqual(self.cp.execute("undo"),"Undo completed")
        self.assertEqual(id(self.lab),identity)
        self.assertEqual(set(self.lab.devices),set(original["devices"]))
        self.assertEqual(len(self.lab.links),2)
        self.assertEqual(self.cp.execute("redo"),"Redo completed")
        self.assertEqual(len(self.lab.links),3)
        self.assertEqual(len(self.lab.devices),5)

    def test_new_edit_invalidates_redo(self):
        self.cp.execute("duplicate PC1 100 100")
        self.cp.execute("undo")
        self.cp.execute("move PC1 200 200")
        self.assertEqual(self.cp.execute("redo"),"Nothing to redo")

    def test_read_only_commands_do_not_enter_history(self):
        cp=CommandProcessor(self.lab)
        self.assertEqual(cp.execute("undo"),"Nothing to undo")
        cp.execute("show topology")
        cp.execute("show links")
        self.assertEqual(cp.execute("undo"),"Nothing to undo")

    def test_failed_edits_do_not_pollute_undo(self):
        cp=CommandProcessor(self.lab)
        self.assertTrue(cp.execute("duplicate missing 10 20").startswith("ERROR:"))
        self.assertTrue(cp.execute("move-group PC1,missing 10 20").startswith("ERROR:"))
        self.assertEqual(cp.execute("undo"),"Nothing to undo")

    def test_group_move_atomic_and_undoable(self):
        before={n:(d.x,d.y) for n,d in self.lab.devices.items()}
        self.assertEqual(self.cp.execute("move-group PC1,SW1 40 65"),"group moved")
        self.assertEqual(self.lab.devices["PC1"].x,before["PC1"][0]+40)
        self.assertEqual(self.lab.devices["SW1"].y,before["SW1"][1]+65)
        self.assertEqual(self.lab.devices["R1"].x,before["R1"][0])
        self.cp.execute("undo")
        self.assertEqual({n:(d.x,d.y) for n,d in self.lab.devices.items()},before)

    def test_group_delete_atomic_undo(self):
        self.assertEqual(self.cp.execute("remove-group PC1,SW1"),"group removed")
        self.assertEqual(list(self.lab.devices),["R1"])
        self.assertEqual(self.lab.links,[])
        self.cp.execute("undo")
        self.assertEqual(len(self.lab.devices),3)
        self.assertEqual(len(self.lab.links),2)

    def test_clone_invalid_args_never_half_apply(self):
        before=deepcopy(self.lab.to_dict())
        for args in (["PC1","missing"],["PC1","PC1"]):
            with self.assertRaises(LabError):
                self.lab.duplicate_devices(args,100,100)
        for offset in (float("nan"),float("inf"),-50000):
            with self.assertRaises(LabError):
                self.lab.duplicate_devices(["PC1"],offset,0)
        self.assertEqual(self.lab.to_dict(),before)

    def test_topology_snapshot_undo_configuration(self):
        old=self.lab.devices["PC1"].interfaces["eth0"].ip
        self.assertIn("10.2.0.2/24",self.cp.execute("ip PC1 eth0 10.2.0.2/24"))
        self.cp.execute("undo")
        self.assertEqual(self.lab.devices["PC1"].interfaces["eth0"].ip,old)

    def test_ui_resources_and_shortcuts(self):
        page=(ROOT/"web/index.html").read_text()
        js=(ROOT/"web/logical-workspace.js").read_text()
        for resource in ("logical-workspace.js","logical-workspace.css"):
            self.assertIn(resource,page)
        for term in ("ptSelectionRect","move-group","duplicate ","remove-group","ctrlKey",
                     "metaKey","selectAll","Undo","edit.redo"):
            # "Undo" is on toolbar, not necessarily in helper source.
            self.assertIn(term,js+page)

if __name__=="__main__":
    unittest.main()

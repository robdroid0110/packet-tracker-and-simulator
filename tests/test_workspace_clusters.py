import json
import tempfile
import unittest
from pathlib import Path
from netsim.model import NetworkLab,LabError
from netsim.cli import CommandProcessor


class ClusterWorkspaceTests(unittest.TestCase):
    def setUp(self):
        self.lab=NetworkLab()
        self.lab.add_device("pc","PC1")
        self.lab.add_device("pc","PC2")
        self.lab.add_device("switch","SW1")
        self.lab.connect("PC1","eth0","SW1","fa0/1")
        self.cp=CommandProcessor(self.lab)

    def test_group_selection_and_nested_hierarchy(self):
        root=self.lab.add_cluster("Campus",["PC1","PC2"])
        inner=self.lab.add_cluster("Floor 1",["PC1"],root)
        self.assertEqual(self.lab.clusters[root]["devices"],["PC2"])
        self.assertEqual(self.lab.clusters[inner]["devices"],["PC1"])
        self.assertEqual(self.lab.clusters[inner]["parent"],root)
        self.assertEqual(len(self.lab.links),1)

    def test_prevent_duplicate_memberships_and_parent_cycles(self):
        outer=self.lab.add_cluster("A",["PC1"])
        child=self.lab.add_cluster("B",[],outer)
        with self.assertRaises(LabError):self.lab.add_cluster("Other",["PC1"])
        with self.assertRaises(LabError):self.lab.move_cluster(outer,child)
        with self.assertRaises(LabError):self.lab.move_cluster(outer,outer)
        with self.assertRaises(LabError):self.lab.add_cluster("X",["PC2"],"missing")

    def test_move_and_delete_cluster_leave_network_intact(self):
        root=self.lab.add_cluster("Group",["PC1","PC2"])
        child=self.lab.add_cluster("Nested",["PC1"],root)
        self.lab.place_in_cluster("PC2",child)
        self.assertEqual(self.lab.clusters[root]["devices"],[])
        self.lab.delete_cluster(root)
        self.assertIsNone(self.lab.clusters[child]["parent"])
        self.assertEqual(set(self.lab.devices),{"PC1","PC2","SW1"})
        self.assertEqual(len(self.lab.links),1)
        self.lab.delete_cluster(child)
        self.assertEqual(self.lab.clusters,{})
        self.assertEqual(len(self.lab.links),1)

    def test_rename_remove_and_clone_update_membership(self):
        root=self.lab.add_cluster("Group",["PC1","PC2"])
        self.lab.rename_device("PC1","Client")
        self.assertIn("Client",self.lab.clusters[root]["devices"])
        self.lab.duplicate_devices(["Client","SW1"],100,70)
        self.assertIn("Client_copy",self.lab.clusters[root]["devices"])
        self.lab.remove_device("Client")
        self.assertNotIn("Client",self.lab.clusters[root]["devices"])

    def test_persistence_legacy_and_corrupted_group_validation(self):
        self.lab.add_cluster("Lab",["PC1","PC2"])
        with tempfile.TemporaryDirectory() as tmp:
            path=Path(tmp)/"lab.json"
            self.lab.save(str(path))
            restored=NetworkLab();restored.load(str(path))
            self.assertEqual(restored.clusters,self.lab.clusters)
            data=json.loads(path.read_text())
            data["clusters"]["Cluster0"]["devices"].append("MISSING")
            path.write_text(json.dumps(data))
            with self.assertRaises(LabError):NetworkLab().load(str(path))
            data.pop("clusters")
            path.write_text(json.dumps(data))
            restored.load(str(path))
            self.assertEqual(restored.clusters,{})

    def test_agent_control_and_undo_redo(self):
        self.assertIn("created cluster Cluster0",self.cp.execute("cluster add Campus PC1,PC2"))
        self.assertIn("Cluster0",self.cp.execute("show clusters"))
        self.assertIn("created cluster Cluster1",self.cp.execute("cluster add Classroom PC1 Cluster0"))
        self.assertEqual(self.cp.execute("cluster move Cluster0 Cluster1")[:6],"ERROR:")
        self.assertIn("moved",self.cp.execute("cluster place SW1 Cluster1"))
        self.assertEqual(self.lab.clusters["Cluster1"]["devices"],["PC1","SW1"])
        self.assertEqual(self.cp.execute("undo"),"Undo completed")
        self.assertEqual(self.lab.clusters["Cluster1"]["devices"],["PC1"])
        self.assertEqual(self.cp.execute("redo"),"Redo completed")
        self.assertEqual(self.lab.clusters["Cluster1"]["devices"],["PC1","SW1"])
        self.assertIn("renamed",self.cp.execute('cluster rename Cluster1 "Training Floor"'))
        self.assertIn("deleted",self.cp.execute("cluster delete Cluster1"))
        self.assertEqual(self.lab.clusters["Cluster0"]["devices"],["PC2"])

    def test_gui_cluster_uses_shared_model(self):
        source=(Path(__file__).resolve().parents[1]/"web/interface-overview.js").read_text()
        for label in ("cluster add","cluster place","cluster rename","cluster delete","state.clusters","clusterSelections"):
            self.assertIn(label,source)


if __name__=="__main__":unittest.main()

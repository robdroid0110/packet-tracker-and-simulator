"""Diagram changes preserve network behavior and are atomic, portable and undoable."""
import json
import shlex
import tempfile
import unittest
from pathlib import Path
from netsim.model import NetworkLab, LabError
from netsim.cli import CommandProcessor
from netsim.topology_presentation import layout
from netsim.workspace_tools import command


class TopologyPresentationTests(unittest.TestCase):
    def setUp(self):
        self.lab = NetworkLab()
        for kind, name, x, y in [('router', 'R1', 900, 500), ('switch', 'S1', 700, 400), ('pc', 'P1', 500, 200)]:
            self.lab.add_device(kind, name, x, y)
        self.lab.connect('R1', 'g0/0', 'S1', 'fa0/1')
        self.lab.connect('S1', 'fa0/2', 'P1', 'eth0')
        self.lab.set_ip('R1', 'g0/0', '192.0.2.1/24')
        self.cp = CommandProcessor(self.lab)

    def action(self, **body):
        result = self.cp.execute('workspace-tool ' + shlex.quote(json.dumps(body)))
        self.assertFalse(result.startswith('ERROR:'), result)

    def test_preview_read_only_deterministic_apply_and_undo(self):
        before = self.lab.to_dict()
        plan = layout(self.lab)
        self.assertEqual(plan, layout(self.lab, ['S1', 'P1', 'R1']))
        self.assertEqual(before, self.lab.to_dict())
        self.assertLess(plan['positions']['R1']['y'], plan['positions']['S1']['y'])
        self.action(action='layout_apply', names=plan['names'], signature=plan['signature'])
        self.assertEqual(self.lab.devices['R1'].x, plan['positions']['R1']['x'])
        self.assertEqual(self.lab.devices['R1'].interfaces['g0/0'].ip, '192.0.2.1/24')
        self.assertEqual(before['links'], self.lab.to_dict()['links'])
        self.cp.execute('undo')
        self.assertEqual(self.lab.devices['R1'].x, 900)
        self.cp.execute('redo')
        self.assertEqual(self.lab.devices['R1'].x, plan['positions']['R1']['x'])

    def test_stale_preview_atomic_and_partial_layout_avoids_stationary_nodes(self):
        self.lab.devices['R1'].x = 80
        self.lab.devices['R1'].y = 60
        plan = layout(self.lab, ['P1'])
        self.assertNotEqual(plan['positions']['P1'], {'x':80, 'y':60})
        self.lab.devices['R1'].x += 10
        before = self.lab.to_dict()
        with self.assertRaisesRegex(LabError, 'Topology changed'):
            command(self.lab, {'action':'layout_apply', 'names':plan['names'], 'signature':plan['signature']})
        self.assertEqual(before, self.lab.to_dict())
        plan = layout(self.lab, ['P1'])
        self.action(action='layout_apply', names=plan['names'], signature=plan['signature'])
        self.assertEqual(self.lab.devices['R1'].x, 90)

    def test_groups_save_load_undo_rename_delete(self):
        self.action(action='diagram_group', name='Access', members=['S1', 'P1'])
        self.action(action='diagram_collapse', name='Access', collapsed=True)
        self.action(action='diagram_preferences', labels='none', routing=False)
        with tempfile.TemporaryDirectory() as folder:
            filename = str(Path(folder)/'lab.json')
            self.lab.save(filename)
            other = NetworkLab(); other.load(filename)
            self.assertEqual(other.workspace_tools, self.lab.workspace_tools)
            self.assertEqual(other.to_dict()['links'], self.lab.to_dict()['links'])
        self.lab.rename_device('P1', 'Host')
        self.assertEqual(self.lab.workspace_tools['diagram']['groups']['Access']['members'], ['S1', 'Host'])
        self.lab.remove_device('S1'); self.lab.remove_device('Host')
        self.assertEqual(self.lab.workspace_tools['diagram']['groups'], {})

    def test_group_invalid_requests_are_atomic(self):
        self.action(action='diagram_group', name='Access', members=['P1'])
        for body in [
            {'action':'diagram_group','name':'Other','members':['P1','R1']},
            {'action':'diagram_group','name':'Other','members':['Missing']},
            {'action':'diagram_group','name':'Other','members':[]},
            {'action':'diagram_group','name':'Other','members':['R1','R1']},
            {'action':'diagram_group','name':'','members':['R1']},
            {'action':'diagram_collapse','name':'Access','collapsed':'true'},
            {'action':'diagram_preferences','routing':1},
            {'action':'diagram_preferences','labels':'bad'},
        ]:
            before = self.lab.to_dict()
            with self.assertRaises(LabError): command(self.lab, body)
            self.assertEqual(before, self.lab.to_dict())
        self.action(action='diagram_ungroup', name='Access')
        self.cp.execute('undo')
        self.assertIn('Access', self.lab.workspace_tools['diagram']['groups'])

    def test_legacy_save_and_empty_or_invalid_preview(self):
        from netsim.workspace_tools import validate
        self.assertTrue(validate({})['diagram']['routing'])
        self.assertEqual(layout(self.lab, [])['positions'], {})
        for names in [['Missing'], ['P1','P1'], 'P1', [False]]:
            with self.assertRaises(LabError): layout(self.lab, names)

    def test_500_disconnected_devices_fit_without_overlap(self):
        lab = NetworkLab()
        for i in range(500): lab.add_device('pc', 'PC'+str(i))
        plan = layout(lab)
        positions = [(p['x'],p['y']) for p in plan['positions'].values()]
        self.assertEqual(len(set(positions)), 500)
        self.assertLess(max(y for x,y in positions), 10000)


if __name__ == '__main__': unittest.main()

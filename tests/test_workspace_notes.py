import json
import tempfile
import unittest
from pathlib import Path

from netsim.capabilities import registry
from netsim.cli import CommandProcessor
from netsim.model import LabError, NetworkLab


class WorkspaceNoteTests(unittest.TestCase):
    def setUp(self):
        self.lab = NetworkLab()
        self.agent = CommandProcessor(self.lab)

    def test_crud_via_agent_commands(self):
        self.assertEqual(self.agent.execute('note add 45 60 "Inspect this VLAN"'), 'added note Note0')
        self.assertEqual(self.agent.execute('note edit Note0 "New label"'), 'updated note Note0')
        self.assertEqual(self.agent.execute('note move Note0 120 160'), 'moved note Note0')
        self.assertEqual(self.lab.notes['Note0'], {'text': 'New label', 'x': 120.0, 'y': 160.0})
        self.assertIn('New label', self.agent.execute('show notes'))
        self.assertEqual(self.agent.execute('note delete Note0'), 'deleted note Note0')
        self.assertNotIn('Note0', self.lab.notes)

    def test_persistence_and_backward_compatibility(self):
        self.agent.execute('note add 1 2 "A persistent note"')
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / 'lab.json'
            self.lab.save(str(path))
            other = NetworkLab()
            other.load(str(path))
            self.assertEqual(other.notes, self.lab.notes)
            data = json.loads(path.read_text())
            del data['notes']
            path.write_text(json.dumps(data))
            other.load(str(path))
            self.assertEqual(other.notes, {})

    def test_validates_bad_content_and_position(self):
        self.assertTrue(self.agent.execute('note add inf 0 "Bad"').startswith('ERROR:'))
        self.assertTrue(self.agent.execute('note add 2 2 ""').startswith('ERROR:'))
        self.assertTrue(self.agent.execute('note add 2 2 "' + ('a' * 801) + '"').startswith('ERROR:'))
        self.assertEqual(self.lab.notes, {})
        with self.assertRaises(LabError):
            self.lab.remove_note('Note999')

    def test_reset_and_registry(self):
        self.agent.execute('note add 10 10 "Demo"')
        self.assertEqual(self.agent.execute('reset'), 'lab reset')
        self.assertFalse(self.lab.notes)
        names = {a['id'] for a in registry(self.lab)['actions']}
        for action in ('workspace.note_add','workspace.note_edit','workspace.note_move','workspace.note_delete'):
            self.assertIn(action, names)


if __name__ == '__main__':
    unittest.main()

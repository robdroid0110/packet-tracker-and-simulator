"""Preferences / host backup contracts."""
import json
from pathlib import Path
import shutil
import subprocess
import tempfile
import unittest

from netsim.backups import create_snapshot, list_snapshots, resolve_snapshot
from netsim.model import NetworkLab

ROOT=Path(__file__).resolve().parents[1]
JS=(ROOT/"web/preferences-extended.js").read_text()
HTML=(ROOT/"web/index.html").read_text()

class PreferencesTests(unittest.TestCase):
    def test_extended_ui_loaded_after_original(self):
        self.assertIn('src="/preferences-extended.js"', HTML)
        self.assertIn('href="/preferences-extended.css"', HTML)
        self.assertLess(HTML.index('src="/preferences.js"'),HTML.index('src="/preferences-extended.js"'))
        for key in ("Administrative","Answer Tree","Image Cleanup","Disable Auto Cable",
                    "IOS Command Logging","Color Scheme","Auto File Backup","Terminal Colors"):
            self.assertIn(key,JS)

    def test_js_parse(self):
        node=shutil.which("node")
        if node:
            subprocess.run([node,"--check",str(ROOT/"web/preferences-extended.js")],
                           check=True,capture_output=True,text=True)

    def test_snapshots_roundtrip_and_bounded_retention(self):
        with tempfile.TemporaryDirectory() as tmp:
            lab=NetworkLab()
            lab.add_device("pc","PC1")
            folder=Path(tmp)/"backups"
            names=[]
            for index in range(5):
                names.append(create_snapshot(lab,folder,max_count=3))
            items=list_snapshots(folder)
            self.assertEqual(len(items),3)
            self.assertNotIn(names[0],{x["name"] for x in items})
            target=resolve_snapshot(folder,names[-1])
            restored=NetworkLab()
            restored.load(str(target))
            self.assertIn("PC1",restored.devices)
            self.assertEqual(len([x for x in folder.iterdir() if x.is_file()]),3)

    def test_backup_path_guard(self):
        with tempfile.TemporaryDirectory() as tmp:
            folder=Path(tmp)
            for name in ("../../etc/passwd","backup-20260101T010203123456Z.json/../etc/passwd","data.json"):
                with self.assertRaises(ValueError):
                    resolve_snapshot(folder,name)
            with self.assertRaises(FileNotFoundError):
                resolve_snapshot(folder,"backup-20260101T010203123456Z.json")

if __name__=="__main__":
    unittest.main()

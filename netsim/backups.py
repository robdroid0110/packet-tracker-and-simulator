"""Bounded host-side snapshots for the Preferences backup workflow."""
from __future__ import annotations

from datetime import datetime, timezone
from pathlib import Path
import re

BACKUP_RE = re.compile(r"^backup-\d{8}T\d{12}Z\.json$")

def list_snapshots(folder: Path) -> list[dict]:
    if not folder.is_dir():
        return []
    entries = []
    for file in sorted(folder.iterdir(), reverse=True):
        if file.is_file() and BACKUP_RE.fullmatch(file.name):
            stat = file.stat()
            entries.append({"name": file.name, "bytes": stat.st_size})
    return entries

def create_snapshot(lab, folder: Path, *, max_count: int = 24) -> str:
    folder.mkdir(parents=True, exist_ok=True)
    stamp = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%S%f") + "Z"
    name = "backup-" + stamp + ".json"
    destination = folder / name
    lab.save(str(destination))
    for obsolete in list_snapshots(folder)[max_count:]:
        (folder / obsolete["name"]).unlink()
    return name

def resolve_snapshot(folder: Path, name: str) -> Path:
    if not isinstance(name, str) or not BACKUP_RE.fullmatch(name):
        raise ValueError("Invalid backup name")
    path = folder / name
    if not path.is_file() or not path.resolve().is_relative_to(folder.resolve()):
        raise FileNotFoundError("Backup not found")
    return path

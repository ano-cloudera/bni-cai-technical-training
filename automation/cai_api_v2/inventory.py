import json
from pathlib import Path


def write_inventory(path: Path, data: dict):
    path.write_text(json.dumps(data, indent=2, sort_keys=True) + "\n")


def read_inventory(path: Path) -> dict:
    return json.loads(path.read_text())

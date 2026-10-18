import argparse
import json
import os
from pathlib import Path


def execute(path: Path) -> None:
    doc = json.loads(path.read_text())
    namespace = {"__name__": "__notebook__"}
    old = os.environ.get("RUN_LIVE_LABS")
    os.environ["RUN_LIVE_LABS"] = "false"
    try:
        for cell in doc["cells"]:
            if cell["cell_type"] == "code":
                exec("".join(cell["source"]), namespace, namespace)
    finally:
        if old is None:
            os.environ.pop("RUN_LIVE_LABS", None)
        else:
            os.environ["RUN_LIVE_LABS"] = old


def main():
    p = argparse.ArgumentParser()
    p.add_argument("paths", nargs="*", type=Path)
    args = p.parse_args()
    paths = args.paths or sorted(Path("notebooks").glob("*.ipynb"))
    for path in paths:
        execute(path)
        print(f"PASS {path}")


if __name__ == "__main__":
    main()

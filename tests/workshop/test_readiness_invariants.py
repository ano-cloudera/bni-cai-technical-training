"""Cross-cutting readiness invariants that must hold on every commit."""

from __future__ import annotations

import subprocess
from pathlib import Path

import yaml

ROOT = Path(__file__).resolve().parents[2]


def tracked() -> list[str]:
    out = subprocess.run(["git", "ls-files"], cwd=ROOT, capture_output=True, text=True, check=True).stdout
    return out.splitlines()


def test_the_generated_runtime_hierarchy_and_group_env_files_are_never_tracked() -> None:
    names = tracked()
    assert not [n for n in names if n.startswith("workshop/runtime/")]
    assert not [n for n in names if Path(n).name == "group.env"]
    ignore = (ROOT / ".gitignore").read_text().split()
    assert "workshop/runtime/" in ignore and "group.env" in ignore


def test_the_registry_the_notebooks_and_the_scripts_agree() -> None:
    labs = yaml.safe_load((ROOT / "config/workshop/labs.yaml").read_text())["labs"]
    assert [lab["id"] for lab in labs] == [f"{n:02d}" for n in range(13)]
    for lab in labs:
        assert (ROOT / lab["script"]).is_file() and (ROOT / lab["notebook"]).is_file()
    templates = sorted(p.name for p in (ROOT / "notebooks/templates").glob("*.ipynb"))
    assert templates == sorted(Path(lab["notebook"]).name for lab in labs)


def test_no_model_weights_or_group_outputs_are_tracked() -> None:
    suffixes = (".safetensors", ".gguf", ".bin", ".pt", ".pth")
    assert not [n for n in tracked() if n.endswith(suffixes)]


def test_no_per_group_copy_of_the_dataset_is_tracked() -> None:
    csvs = [n for n in tracked() if n.endswith(".csv")]
    assert not [n for n in csvs if "group_" in n or n.startswith("workshop/runtime/")]
    assert sorted(n for n in csvs if n.startswith("data/raw/")) == [
        f"data/raw/{t}.csv" for t in ("accounts", "branches", "customers", "loans", "transactions")
    ]

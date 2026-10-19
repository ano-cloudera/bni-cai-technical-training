"""The canonical lab registry (config/workshop/labs.yaml). Never rely on filename order."""

from __future__ import annotations

import importlib.util
from collections.abc import Sequence
from dataclasses import dataclass
from pathlib import Path

import yaml

REPO_ROOT = Path(__file__).resolve().parents[2]
REGISTRY_PATH = REPO_ROOT / "config" / "workshop" / "labs.yaml"
EXPECTED_IDS = tuple(f"{i:02d}" for i in range(13))


@dataclass(frozen=True)
class Lab:
    id: str
    key: str
    title: str
    audience: tuple[str, ...]
    trainer_only: bool
    script: str
    notebook: str
    legacy_scripts: tuple[str, ...]
    duration_min: int
    exercise: str
    purpose: str
    theory: str
    expected: str

    @property
    def script_path(self) -> Path:
        return REPO_ROOT / self.script

    @property
    def notebook_path(self) -> Path:
        return REPO_ROOT / self.notebook

    @property
    def participant_lab(self) -> bool:
        return "participant" in self.audience and not self.trainer_only


class RegistryError(ValueError):
    pass


def load_registry(path: Path = REGISTRY_PATH) -> tuple[tuple[Lab, ...], tuple[str, ...]]:
    raw = yaml.safe_load(Path(path).read_text(encoding="utf-8"))
    labs = tuple(
        Lab(
            id=item["id"],
            key=item["key"],
            title=item["title"],
            audience=tuple(item["audience"]),
            trainer_only=bool(item["trainer_only"]),
            script=item["script"],
            notebook=item["notebook"],
            legacy_scripts=tuple(item.get("legacy_scripts", ())),
            duration_min=int(item["duration_min"]),
            exercise=item["exercise"],
            purpose=item["purpose"],
            theory=" ".join(item["theory"].split()),
            expected=item["expected"],
        )
        for item in raw["labs"]
    )
    if tuple(lab.id for lab in labs) != EXPECTED_IDS:
        raise RegistryError("The registry must list labs 00 through 12 in order")
    for lab in labs:
        if not lab.script.startswith("scripts/") or not lab.notebook.startswith("notebooks/templates/"):
            raise RegistryError(f"Lab {lab.id} has an unexpected script or notebook location")
    legacy_only = tuple(item["script"] for item in raw.get("legacy_only", ()))
    return labs, legacy_only


def canonical_labs() -> tuple[Lab, ...]:
    return load_registry()[0]


def legacy_only_scripts() -> tuple[str, ...]:
    return load_registry()[1]


def get_lab(identifier: str) -> Lab:
    for lab in canonical_labs():
        if identifier in (lab.id, lab.key):
            return lab
    raise RegistryError(f"Unknown lab: {identifier!r}")


def legacy_wrappers() -> dict[str, Lab]:
    """{rc1 script path: canonical lab} for scripts that are now thin compatibility wrappers."""
    return {legacy: lab for lab in canonical_labs() for legacy in lab.legacy_scripts}


def load_script_module(path: Path):
    spec = importlib.util.spec_from_file_location(f"lab_{Path(path).stem}", path)
    module = importlib.util.module_from_spec(spec)
    assert spec and spec.loader
    spec.loader.exec_module(module)
    return module


def delegate(legacy_script: str, argv: Sequence[str] | None = None) -> int:
    """Run the canonical lab behind an rc1 compatibility wrapper."""
    lab = legacy_wrappers().get(legacy_script)
    if lab is None:
        raise RegistryError(f"{legacy_script} is not a registered compatibility wrapper")
    return load_script_module(lab.script_path).main(list(argv) if argv is not None else None)

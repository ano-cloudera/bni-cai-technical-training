from __future__ import annotations

from collections.abc import Mapping
from dataclasses import dataclass
from pathlib import Path

import yaml

from bni_training.config import validate_group_id

REPO_ROOT = Path(__file__).resolve().parents[3]
DEFAULT_GROUPS_CONFIG = REPO_ROOT / "config" / "workshop" / "groups.yaml"


class UnknownGroupError(ValueError):
    """The group id is malformed or not in the registry."""


class GroupAccessError(PermissionError):
    """A group asked for a dataset or scenario that is not assigned to it."""


@dataclass(frozen=True)
class DatasetSpec:
    dataset_id: str
    title: str
    csv_dir: Path
    semantic_model: Path


@dataclass(frozen=True)
class ScenarioSpec:
    scenario_id: str
    title: str
    description: str
    sample_questions: tuple[str, ...]


@dataclass(frozen=True)
class GroupSpec:
    group_id: str
    scenario_ids: tuple[str, ...]
    dataset_ids: tuple[str, ...]


def _resolve(base: Path, value: str) -> Path:
    path = Path(value)
    return path if path.is_absolute() else base / path


class GroupRegistry:
    """Immutable view of config/workshop/groups.yaml. It holds no per-session state."""

    def __init__(self, raw: Mapping, base_dir: Path = REPO_ROOT):
        self._datasets = {
            key: DatasetSpec(
                key,
                value["title"],
                _resolve(base_dir, value["csv_dir"]),
                _resolve(base_dir, value["semantic_model"]),
            )
            for key, value in raw["datasets"].items()
        }
        self._scenarios = {
            key: ScenarioSpec(key, value["title"], value["description"], tuple(value["sample_questions"]))
            for key, value in raw["scenarios"].items()
        }
        groups = [
            GroupSpec(item["group_id"], tuple(item["scenarios"]), tuple(item["datasets"]))
            for item in raw["groups"]
        ]
        self._groups = {group.group_id: group for group in groups}
        self._validate()

    @classmethod
    def load(cls, path: Path = DEFAULT_GROUPS_CONFIG) -> GroupRegistry:
        return cls(yaml.safe_load(Path(path).read_text(encoding="utf-8")), base_dir=REPO_ROOT)

    def _validate(self) -> None:
        expected = [f"group_{i:02d}" for i in range(1, 11)]
        if sorted(self._groups) != expected:
            raise ValueError("groups.yaml must define exactly group_01 through group_10")
        for group in self._groups.values():
            validate_group_id(group.group_id)
            if not group.scenario_ids or not group.dataset_ids:
                raise ValueError(f"{group.group_id} needs at least one scenario and one dataset")
            for scenario_id in group.scenario_ids:
                if scenario_id not in self._scenarios:
                    raise ValueError(f"{group.group_id}: unknown scenario {scenario_id}")
            for dataset_id in group.dataset_ids:
                if dataset_id not in self._datasets:
                    raise ValueError(f"{group.group_id}: unknown dataset {dataset_id}")

    @property
    def group_ids(self) -> tuple[str, ...]:
        return tuple(sorted(self._groups))

    def validate(self, group_id: object) -> str:
        """Return the group id if it is well formed and registered; otherwise raise UnknownGroupError."""
        if not isinstance(group_id, str):
            raise UnknownGroupError("GROUP_ID must be a string")
        try:
            validate_group_id(group_id)
        except ValueError as exc:
            raise UnknownGroupError(str(exc)) from exc
        if group_id not in self._groups:
            raise UnknownGroupError(f"Unknown group: {group_id}")
        return group_id

    def group(self, group_id: str) -> GroupSpec:
        return self._groups[self.validate(group_id)]

    def scenario(self, scenario_id: str) -> ScenarioSpec:
        return self._scenarios[scenario_id]

    def dataset(self, dataset_id: str) -> DatasetSpec:
        return self._datasets[dataset_id]

    def require_dataset(self, group_id: str, dataset_id: str) -> DatasetSpec:
        if dataset_id not in self.group(group_id).dataset_ids:
            raise GroupAccessError(f"{group_id} is not assigned dataset {dataset_id!r}")
        return self._datasets[dataset_id]

    def require_scenario(self, group_id: str, scenario_id: str) -> ScenarioSpec:
        if scenario_id not in self.group(group_id).scenario_ids:
            raise GroupAccessError(f"{group_id} is not assigned scenario {scenario_id!r}")
        return self._scenarios[scenario_id]

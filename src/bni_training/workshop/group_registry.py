from __future__ import annotations

from collections.abc import Mapping, Sequence
from dataclasses import dataclass, field
from pathlib import Path

from bni_training.config import validate_group_id
from bni_training.data.bundles import BundleCatalog


class UnknownGroupError(ValueError):
    """The group id is malformed or not in the registry."""


class GroupAccessError(PermissionError):
    """A group asked for a dataset or scenario that is not assigned to it."""


@dataclass(frozen=True)
class DatasetSpec:
    """A group's logical dataset bundle (a view of the one physical dataset)."""

    dataset_id: str
    title: str
    csv_dir: Path
    tables: tuple[str, ...] = ()
    row_filters: Mapping[str, str] = field(default_factory=dict)
    allowed_metrics: tuple[str, ...] = ()
    mission_id: str = ""


@dataclass(frozen=True)
class ScenarioSpec:
    """A group's mission. ``scenario_id`` is the mission id."""

    scenario_id: str
    title: str
    description: str
    sample_questions: tuple[str, ...]

    @property
    def objective(self) -> str:
        return self.description


@dataclass(frozen=True)
class GroupSpec:
    group_id: str
    scenario_ids: tuple[str, ...]
    dataset_ids: tuple[str, ...]


class GroupRegistry:
    """Immutable view of the group assignments in data/scenarios. It holds no per-session state."""

    def __init__(
        self,
        datasets: Mapping[str, DatasetSpec],
        scenarios: Mapping[str, ScenarioSpec],
        groups: Sequence[GroupSpec],
    ):
        self._datasets = dict(datasets)
        self._scenarios = dict(scenarios)
        self._groups = {group.group_id: group for group in groups}
        self._validate()

    @classmethod
    def from_catalog(cls, catalog: BundleCatalog) -> GroupRegistry:
        datasets, scenarios, groups = {}, {}, []
        for group_id, bundle in catalog.bundles.items():
            datasets[bundle.dataset_id] = DatasetSpec(
                bundle.dataset_id,
                bundle.mission_title,
                bundle.csv_dir,
                bundle.tables,
                dict(bundle.row_filters),
                bundle.allowed_metrics,
                bundle.mission_id,
            )
            scenarios[bundle.mission_id] = ScenarioSpec(
                bundle.mission_id, bundle.mission_title, bundle.mission_objective, bundle.sample_questions
            )
            groups.append(GroupSpec(group_id, (bundle.mission_id,), (bundle.dataset_id,)))
        return cls(datasets, scenarios, groups)

    @classmethod
    def load(cls, directory: Path | None = None) -> GroupRegistry:
        return cls.from_catalog(BundleCatalog.load(directory) if directory else BundleCatalog.load())

    def _validate(self) -> None:
        expected = [f"group_{i:02d}" for i in range(1, 11)]
        if sorted(self._groups) != expected:
            raise ValueError("The registry must define exactly group_01 through group_10")
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

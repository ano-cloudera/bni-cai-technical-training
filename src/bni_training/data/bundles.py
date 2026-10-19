"""Logical dataset bundles and group missions. One physical dataset, ten logical views of it."""

from __future__ import annotations

from collections.abc import Mapping
from dataclasses import dataclass
from pathlib import Path

import sqlglot
import yaml
from sqlglot import exp

from .dictionary import REPO_ROOT, DataDictionary
from .engine import AccessPolicy
from .semantic_layer import SemanticModel

SCENARIOS_DIR = REPO_ROOT / "data" / "scenarios"
GROUP_IDS = tuple(f"group_{i:02d}" for i in range(1, 11))


class BundleConfigError(ValueError):
    pass


@dataclass(frozen=True)
class GroupBundle:
    group_id: str
    dataset_id: str
    mission_id: str
    mission_title: str
    mission_objective: str
    tables: tuple[str, ...]
    row_filters: Mapping[str, str]
    allowed_metrics: tuple[str, ...]
    sample_questions: tuple[str, ...]
    csv_dir: Path

    @property
    def policy(self) -> AccessPolicy:
        return AccessPolicy(frozenset(self.tables), dict(self.row_filters))


@dataclass(frozen=True)
class BundleCatalog:
    bundles: Mapping[str, GroupBundle]  # keyed by group_id

    @classmethod
    def load(
        cls,
        directory: Path = SCENARIOS_DIR,
        *,
        dictionary: DataDictionary | None = None,
        semantic: SemanticModel | None = None,
    ) -> BundleCatalog:
        directory = Path(directory)
        dictionary = dictionary or DataDictionary.load()
        semantic = semantic or SemanticModel.load()
        raw_bundles = yaml.safe_load((directory / "dataset_bundles.yaml").read_text(encoding="utf-8"))
        assignments = yaml.safe_load((directory / "group_assignments.yaml").read_text(encoding="utf-8"))
        questions = yaml.safe_load((directory / "sample_questions.yaml").read_text(encoding="utf-8"))
        csv_dir = Path(raw_bundles["csv_dir"])
        csv_dir = csv_dir if csv_dir.is_absolute() else REPO_ROOT / csv_dir
        found: dict[str, GroupBundle] = {}
        used_datasets: set[str] = set()
        for item in assignments["assignments"]:
            group_id, dataset_id, mission_id = item["group_id"], item["dataset_id"], item["mission_id"]
            if group_id in found:
                raise BundleConfigError(f"{group_id} is assigned twice")
            if dataset_id in used_datasets:
                raise BundleConfigError(f"Bundle {dataset_id} is assigned to more than one group")
            used_datasets.add(dataset_id)
            if dataset_id not in raw_bundles["bundles"]:
                raise BundleConfigError(f"{group_id}: unknown bundle {dataset_id}")
            spec = raw_bundles["bundles"][dataset_id]
            tables = tuple(spec["tables"])
            unknown = [t for t in tables if t not in dictionary.tables]
            if unknown:
                raise BundleConfigError(f"{dataset_id}: unknown tables {unknown}")
            metrics = tuple(spec["allowed_metrics"])
            for metric_name in metrics:
                if metric_name not in semantic.metrics:
                    raise BundleConfigError(f"{dataset_id}: unknown metric {metric_name}")
                missing = semantic.metrics[metric_name].tables - set(tables)
                if missing:
                    raise BundleConfigError(
                        f"{dataset_id}: metric {metric_name} needs tables {sorted(missing)}"
                    )
            filters = dict(spec.get("row_filters") or {})
            for table, predicate in filters.items():
                if table not in tables:
                    raise BundleConfigError(f"{dataset_id}: row filter on table {table} outside the bundle")
                columns = {
                    c.name
                    for c in sqlglot.parse_one(f"SELECT 1 WHERE {predicate}", read="sqlite").find_all(
                        exp.Column
                    )
                }
                if not columns <= set(dictionary.tables[table].exposed_columns):
                    raise BundleConfigError(
                        f"{dataset_id}: row filter uses unavailable columns {sorted(columns)}"
                    )
            sample = tuple(questions["missions"].get(mission_id, ()))
            if not 3 <= len(sample) <= 5:
                raise BundleConfigError(
                    f"{mission_id}: needs three to five sample questions, found {len(sample)}"
                )
            for question in sample:
                semantic.resolve_question(question, allowed_tables=tables, allowed_metrics=metrics)
            found[group_id] = GroupBundle(
                group_id, dataset_id, mission_id, item["mission_title"], item["mission_objective"],
                tables, filters, metrics, sample, csv_dir,
            )  # fmt: skip
        if tuple(sorted(found)) != GROUP_IDS:
            raise BundleConfigError("group_assignments.yaml must assign exactly group_01 through group_10")
        if len({b.mission_id for b in found.values()}) != 10:
            raise BundleConfigError("Every group needs its own mission")
        return cls(found)

    def for_group(self, group_id: str) -> GroupBundle:
        return self.bundles[group_id]

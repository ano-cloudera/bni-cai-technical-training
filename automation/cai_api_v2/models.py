from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

import yaml


@dataclass(frozen=True)
class ProjectSpec:
    name: str
    group_id: str | None = None
    application: str | None = None


@dataclass(frozen=True)
class WorkshopSpec:
    label: str
    projects: tuple[ProjectSpec, ...]
    resources: dict
    max_concurrent_apps: int

    @classmethod
    def load(cls, groups_path: Path, resources_path: Path) -> "WorkshopSpec":
        groups = yaml.safe_load(groups_path.read_text())
        resources = yaml.safe_load(resources_path.read_text())
        projects = [ProjectSpec(groups["shared_project"])]
        projects.extend(
            ProjectSpec(item["project"], item["group_id"], item["application"]) for item in groups["groups"]
        )
        return cls(
            groups["training_label"], tuple(projects), resources, groups["max_concurrent_group_applications"]
        )

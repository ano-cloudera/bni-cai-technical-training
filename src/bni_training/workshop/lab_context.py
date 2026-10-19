"""Every participant lab resolves the same four values: GROUP_ID, DATASET_ID, MISSION_ID and GROUP_WORKSPACE.

Sources, in this order: environment variables, then the group's ``config/group.env`` (named by
GROUP_ENV_FILE or found through GROUP_WORKSPACE). A value that disagrees with the assignment is an
error, never a silent override. In cai mode nothing is guessed; in local mode the first group and a
throwaway prepared workspace are used.
"""

from __future__ import annotations

import atexit
import os
import shutil
import tempfile
import uuid
from collections.abc import Mapping
from dataclasses import dataclass, field
from pathlib import Path

from bni_training.data.bundles import BundleCatalog, GroupBundle
from bni_training.data.dictionary import REPO_ROOT
from bni_training.data.engine import CsvEngine
from bni_training.data.semantic_layer import SemanticModel
from bni_training.data.tool import DataRequest, WorkshopDataTool

from . import group_paths
from .group_registry import UnknownGroupError
from .notebook_support import participant_settings
from .workspace_manager import TEMPLATES_DIR, WorkspaceError, WorkspaceManager, parse_env

LOCAL_DEFAULT_GROUP = "group_01"
KEYS = ("GROUP_ID", "DATASET_ID", "MISSION_ID", "GROUP_WORKSPACE")


class LabContextError(ValueError):
    """The group configuration is missing or inconsistent. The message is safe to show."""


@dataclass
class LabContext:
    group_id: str
    dataset_id: str
    mission_id: str
    workspace: Path
    runtime_root: Path
    bundle: GroupBundle
    source: str
    participant_mode: str = "group_driver"
    participant_ref: str = "participant_01"
    participant_workspace: Path | None = None
    run_id: str = field(default_factory=lambda: uuid.uuid4().hex)
    _engine: CsvEngine | None = field(default=None, repr=False)

    def describe(self) -> dict:
        return {
            "group_id": self.group_id,
            "dataset_id": self.dataset_id,
            "mission_id": self.mission_id,
            "workspace": f"groups/{self.group_id}",
            "participant_mode": self.participant_mode,
            "participant_ref": self.participant_ref,
            "source": self.source,
        }

    def request(self) -> DataRequest:
        return DataRequest(self.group_id, self.run_id, self.dataset_id, self.mission_id)

    def data_tool(self) -> WorkshopDataTool:
        """The read-only data tool bound to this group's bundle (one shared in-memory copy per lab run)."""
        if self._engine is None:
            self._engine = CsvEngine(self.bundle.csv_dir)
        return WorkshopDataTool(self._engine, SemanticModel.load(), self.bundle)

    def write_output(self, name: str, text: str) -> Path:
        """Save to the selected group or anonymous participant output folder."""
        if self.participant_mode == "individual_learning":
            return group_paths.write_participant_output(
                self.runtime_root, self.group_id, self.participant_ref, name, text
            )
        return group_paths.write_group_output(self.runtime_root, self.group_id, name, text)

    def close(self) -> None:
        if self._engine is not None:
            self._engine.close()
            self._engine = None


def _find_group_env(env: Mapping[str, str]) -> Path | None:
    explicit = env.get("GROUP_ENV_FILE")
    if explicit:
        path = Path(explicit)
        if not path.is_file():
            raise LabContextError("GROUP_ENV_FILE does not point to a file")
        return path
    workspace = env.get("GROUP_WORKSPACE")
    if workspace:
        for base in (Path(workspace), REPO_ROOT / workspace):
            candidate = base / "config" / "group.env"
            if candidate.is_file():
                return candidate
    return None


def _prepare_local_workspace(group_id: str, env: Mapping[str, str]) -> tuple[Path, Path]:
    runtime = env.get("WORKSHOP_RUNTIME_DIR")
    if runtime:
        root = Path(runtime)
        root.mkdir(parents=True, exist_ok=True)
    else:
        root = Path(tempfile.mkdtemp(prefix="bni-lab-runtime-"))
        atexit.register(shutil.rmtree, root, True)
    base = root / "groups" / group_id
    if not (base / "config" / "group.env").is_file():
        if TEMPLATES_DIR.is_dir() and any(TEMPLATES_DIR.glob("*.ipynb")):
            WorkspaceManager(root, TEMPLATES_DIR).sync(apply=True)
        else:  # no templates available: create just this group's folders and group.env
            for sub in ("config", "notebooks", "output", "logs", "tmp"):
                (base / sub).mkdir(parents=True, exist_ok=True)
            text = WorkspaceManager(root, root).group_env_text(group_id)
            (base / "config" / "group.env").write_text(text, encoding="utf-8")
    return root, base


def resolve_lab_context(
    mode: str, env: Mapping[str, str] | None = None, catalog: BundleCatalog | None = None
) -> LabContext:
    source_env = dict(os.environ if env is None else env)
    catalog = catalog or BundleCatalog.load()
    env_file = _find_group_env(source_env)
    from_file = parse_env(env_file.read_text(encoding="utf-8")) if env_file else {}
    participant = participant_settings({**from_file, **source_env})
    values: dict[str, str] = {}
    for key in KEYS:
        from_env, from_group_file = source_env.get(key, ""), from_file.get(key, "")
        if from_env and from_group_file and key != "GROUP_WORKSPACE" and from_env != from_group_file:
            raise LabContextError(
                f"{key} in the environment ({from_env}) conflicts with group.env ({from_group_file})"
            )
        values[key] = from_env or from_group_file
    group_id = values["GROUP_ID"]
    if not group_id:
        if mode == "cai":
            raise LabContextError(
                "GROUP_ID is not set. Load your group.env (see the README in your workspace)."
            )
        group_id = LOCAL_DEFAULT_GROUP
    try:
        bundle = catalog.for_group(group_id)
    except KeyError as exc:
        raise LabContextError("GROUP_ID must be group_01 through group_10") from exc
    if values["DATASET_ID"] and values["DATASET_ID"] != bundle.dataset_id:
        raise LabContextError(
            f"DATASET_ID {values['DATASET_ID']!r} is not the dataset assigned to {group_id}"
        )
    if values["MISSION_ID"] and values["MISSION_ID"] != bundle.mission_id:
        raise LabContextError(
            f"MISSION_ID {values['MISSION_ID']!r} is not the mission assigned to {group_id}"
        )
    backend = source_env.get("DATA_BACKEND", "csv").lower()
    if backend not in ("csv", "impala"):
        raise LabContextError("DATA_BACKEND must be csv or impala")

    workspace_value = values["GROUP_WORKSPACE"]
    if workspace_value:
        workspace = Path(workspace_value)
        if not workspace.is_absolute() and not workspace.exists():
            workspace = REPO_ROOT / workspace
        try:
            resolved = workspace.resolve()
            if resolved.name != group_id or resolved.parent.name != "groups":
                raise LabContextError(f"GROUP_WORKSPACE must be the folder of {group_id}")
            if any(p.is_symlink() for p in (workspace, *workspace.parents)[:3]):
                raise LabContextError("GROUP_WORKSPACE must not contain symlinks")
        except OSError as exc:
            raise LabContextError("GROUP_WORKSPACE cannot be resolved") from exc
        if not (resolved / "output").is_dir():
            if mode == "cai":
                raise LabContextError(
                    "The group workspace is not prepared. Ask the trainer to run prepare_group_workspaces.py."
                )
            resolved.mkdir(parents=True, exist_ok=True)
            (resolved / "output").mkdir(exist_ok=True)
        participant_workspace = None
        if participant.mode == "individual_learning":
            configured = source_env.get("PARTICIPANT_WORKSPACE") or from_file.get(
                "PARTICIPANT_WORKSPACE"
            )
            participant_workspace = (
                Path(configured)
                if configured
                else resolved / "participants" / participant.participant_ref
            )
            if not participant_workspace.is_absolute() and not participant_workspace.exists():
                participant_workspace = REPO_ROOT / participant_workspace
            participant_workspace = participant_workspace.resolve()
            expected = (resolved / "participants" / participant.participant_ref).resolve()
            if participant_workspace != expected:
                raise LabContextError(
                    "PARTICIPANT_WORKSPACE must match this group and PARTICIPANT_REF"
                )
            if not (participant_workspace / "output").is_dir():
                raise LabContextError(
                    "The participant workspace is not prepared. Ask the trainer to prepare individual mode."
                )
        return LabContext(
            group_id,
            bundle.dataset_id,
            bundle.mission_id,
            resolved,
            resolved.parent.parent,
            bundle,
            "environment",
            participant.mode,
            participant.participant_ref,
            participant_workspace,
        )
    if mode == "cai":
        raise LabContextError(
            "GROUP_WORKSPACE is not set. Load your group.env (see the README in your workspace)."
        )
    try:
        root, base = _prepare_local_workspace(group_id, source_env)
    except WorkspaceError as exc:
        raise LabContextError(str(exc)) from exc
    return LabContext(
        group_id,
        bundle.dataset_id,
        bundle.mission_id,
        base,
        root,
        bundle,
        "local-default",
        participant.mode,
        participant.participant_ref,
        None,
    )


__all__ = ("LabContext", "LabContextError", "resolve_lab_context", "UnknownGroupError")

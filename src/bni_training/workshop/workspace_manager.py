"""Lifecycle of the ten generated group workspaces under ``workshop/runtime``.

Operational isolation only: every path goes through ``group_paths.safe_join`` (no traversal, no
symlinks), and the physical CSV dataset is never copied into a group folder.

Planning and applying share one code path (``sync``), so a dry run shows exactly what ``--apply`` does.
"""

from __future__ import annotations

import hashlib
import json
import os
import re
import shutil
import tempfile
import time
import zipfile
from collections.abc import Callable
from dataclasses import dataclass, field
from pathlib import Path

from bni_training.data.bundles import GROUP_IDS, BundleCatalog, GroupBundle
from bni_training.data.dictionary import REPO_ROOT

from . import group_paths
from .group_paths import UnsafePathError, safe_join

SCHEMA_VERSION = 1
GROUP_SUBDIRS = ("config", "notebooks", "output", "logs", "tmp")
PARTICIPANT_SUBDIRS = ("config", "notebooks", "output", "logs", "tmp")
PARTICIPANT_MODES = ("group_driver", "individual_learning")
PARTICIPANT_REFS = tuple(f"participant_{number:02d}" for number in range(1, 5))
SHARED_SUBDIRS = ("config", "state", "logs")
MANIFEST_NAME = "workspace-manifest.json"
README_TEMPLATE = REPO_ROOT / "workshop" / "templates" / "group" / "README.md"
TEMPLATES_DIR = REPO_ROOT / "notebooks" / "templates"
SECRET_KEY = re.compile(r"(KEY|TOKEN|SECRET|PASSWORD|PASSWD|CREDENTIAL|BEARER)", re.I)
SECRET_VALUE = re.compile(r"(?:Bearer\s+\S{8,}|\bsk-[A-Za-z0-9_-]{8,}|-----BEGIN [A-Z ]*PRIVATE KEY-----)")
ENV_LINE = re.compile(r"^\s*([A-Za-z_][A-Za-z0-9_]*)\s*=\s*(.*?)\s*$")


class WorkspaceError(ValueError):
    """A workspace operation was refused. The message is safe to show to the trainer."""


def sha256_bytes(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def sha256_file(path: Path) -> str:
    return sha256_bytes(Path(path).read_bytes())


def parse_env(text: str) -> dict[str, str]:
    values = {}
    for line in text.splitlines():
        if line.strip().startswith("#") or not line.strip():
            continue
        match = ENV_LINE.match(line)
        if match:
            values[match.group(1)] = match.group(2)
    return values


@dataclass(frozen=True)
class Action:
    group_id: str
    kind: str  # create_dir, write_file, copy_notebook, refresh_notebook, preserve_modified, unchanged, ...
    path: str
    detail: str = ""

    def as_dict(self) -> dict:
        return {"group": self.group_id, "action": self.kind, "path": self.path, "detail": self.detail}


@dataclass
class Check:
    name: str
    passed: bool
    detail: str = ""


@dataclass
class WorkspaceReport:
    checks: list[Check] = field(default_factory=list)

    def add(self, name: str, passed: bool, detail: str = "") -> None:
        self.checks.append(Check(name, bool(passed), detail))

    @property
    def passed(self) -> bool:
        return bool(self.checks) and all(c.passed for c in self.checks)

    def render(self) -> str:
        lines = [
            f"[{'PASS' if c.passed else 'FAIL'}] {c.name}" + (f": {c.detail}" if c.detail else "")
            for c in self.checks
        ]
        failed = sum(not c.passed for c in self.checks)
        lines.append(
            f"RESULT: {'PASS' if self.passed else 'FAIL'} "
            f"({len(self.checks) - failed}/{len(self.checks)} checks)"
        )
        return "\n".join(lines)


class WorkspaceManager:
    def __init__(
        self,
        runtime_root: Path,
        templates_dir: Path = TEMPLATES_DIR,
        catalog: BundleCatalog | None = None,
        *,
        repo_root: Path = REPO_ROOT,
        clock: Callable[[], float] = time.time,
        participant_mode: str = "group_driver",
    ):
        self.root = Path(runtime_root)
        self.templates_dir = Path(templates_dir)
        self.catalog = catalog or BundleCatalog.load()
        self.repo_root = Path(repo_root)
        self._clock = clock
        if participant_mode not in PARTICIPANT_MODES:
            raise WorkspaceError(
                "PARTICIPANT_MODE must be group_driver or individual_learning"
            )
        self.participant_mode = participant_mode

    # paths
    def group_dir(self, group_id: str) -> Path:
        if group_id not in GROUP_IDS:
            raise WorkspaceError(f"Unknown group: {group_id!r}")
        return group_paths.group_workspace(self.root, group_id)

    def shared_dir(self, name: str) -> Path:
        if name not in SHARED_SUBDIRS:
            raise WorkspaceError(f"Unknown shared folder: {name!r}")
        return safe_join(self.root, "shared", name)

    def templates(self) -> dict[str, Path]:
        if not self.templates_dir.is_dir():
            raise WorkspaceError(f"Notebook templates folder not found: {self.templates_dir.name}")
        found = {p.name: p for p in sorted(self.templates_dir.glob("*.ipynb"))}
        if not found:
            raise WorkspaceError("No notebook templates found")
        return found

    def _workspace_ref(self, group_id: str) -> str:
        """GROUP_WORKSPACE value: relative to the repository when the runtime lives inside it."""
        target = self.root.resolve() / "groups" / group_id
        try:
            return target.relative_to(self.repo_root.resolve()).as_posix()
        except ValueError:
            return target.as_posix()

    def group_env_text(self, group_id: str) -> str:
        bundle: GroupBundle = self.catalog.for_group(group_id)
        csv_dir = bundle.csv_dir
        try:
            csv_ref = csv_dir.resolve().relative_to(self.repo_root.resolve()).as_posix()
        except ValueError:
            csv_ref = csv_dir.as_posix()
        lines = [
            "# Generated by scripts/prepare_group_workspaces.py. Non-secret settings only.",
            f"GROUP_ID={group_id}",
            f"DATASET_ID={bundle.dataset_id}",
            f"MISSION_ID={bundle.mission_id}",
            f"GROUP_WORKSPACE={self._workspace_ref(group_id)}",
            f"PARTICIPANT_MODE={self.participant_mode}",
            "WORKSHOP_TOPOLOGY=single_project",
            "DATA_BACKEND=csv",
            f"CSV_DATA_DIR={csv_ref}",
        ]
        if self.participant_mode == "group_driver":
            lines.extend(
                [
                    "PARTICIPANT_REF=participant_01",
                    f"PARTICIPANT_WORKSPACE={self._workspace_ref(group_id)}",
                ]
            )
        return "\n".join(lines) + "\n"

    def participant_env_text(self, group_id: str, participant_ref: str) -> str:
        if participant_ref not in PARTICIPANT_REFS:
            raise WorkspaceError("participant_ref must be participant_01 through participant_04")
        participant_workspace = f"{self._workspace_ref(group_id)}/participants/{participant_ref}"
        return self.group_env_text(group_id) + "\n".join(
            [
                f"PARTICIPANT_REF={participant_ref}",
                f"PARTICIPANT_WORKSPACE={participant_workspace}",
            ]
        ) + "\n"

    @staticmethod
    def driver_rotation_text(group_id: str) -> str:
        rows = "\n".join(
            f"- `{ref}`: rotate keyboard control at the trainer's checkpoint."
            for ref in PARTICIPANT_REFS
        )
        return (
            f"# Driver rotation for {group_id}\n\n"
            "This group uses one CPU Session. Only the active driver edits or runs a cell.\n\n"
            f"{rows}\n"
        )

    def _participants_by_group(self) -> dict[str, tuple[str, ...]]:
        result = {group_id: () for group_id in GROUP_IDS}
        assignment_path = self.root / "shared" / "state" / "participant-assignments.csv"
        if not assignment_path.is_file():
            return result
        import csv

        found: dict[str, list[str]] = {group_id: [] for group_id in GROUP_IDS}
        with assignment_path.open(newline="", encoding="utf-8") as handle:
            for row in csv.DictReader(handle):
                group_id = (row.get("group_id") or "").strip()
                participant_ref = (row.get("participant_ref") or "").strip()
                if group_id not in GROUP_IDS or participant_ref not in PARTICIPANT_REFS:
                    raise WorkspaceError("participant assignment contains an invalid group or anonymous ref")
                if participant_ref in found[group_id]:
                    raise WorkspaceError(f"duplicate {participant_ref} in {group_id}")
                found[group_id].append(participant_ref)
        return {group_id: tuple(sorted(refs)) for group_id, refs in found.items()}

    def readme_text(self, group_id: str) -> str:
        bundle = self.catalog.for_group(group_id)
        text = README_TEMPLATE.read_text(encoding="utf-8")
        for key, value in (
            ("group_id", group_id),
            ("mission_title", bundle.mission_title),
            ("dataset_id", bundle.dataset_id),
            ("mission_id", bundle.mission_id),
        ):
            text = text.replace("{{" + key + "}}", value)
        return text

    # manifest
    def read_manifest(self, group_id: str) -> dict:
        path = safe_join(self.group_dir(group_id), "config", MANIFEST_NAME)
        if not path.is_file():
            return {"schema_version": SCHEMA_VERSION, "group_id": group_id, "files": {}}
        return json.loads(path.read_text(encoding="utf-8"))

    # atomic write
    def _write(self, directory: Path, name: str, data: bytes) -> Path:
        target = safe_join(directory, *Path(name).parts)
        target.parent.mkdir(parents=True, exist_ok=True)
        fd, tmp = tempfile.mkstemp(dir=target.parent, prefix=".tmp-")
        with os.fdopen(fd, "wb") as handle:
            handle.write(data)
        os.replace(tmp, target)
        return target

    def _timestamp(self) -> str:
        return time.strftime("%Y%m%dT%H%M%SZ", time.gmtime(self._clock()))

    def _backup(self, group_id: str, source: Path, relative: str, stamp: str) -> Path:
        directory = safe_join(self.root, "shared", "state")
        target_dir = directory / "backups" / group_id / stamp
        target = target_dir / relative
        target.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(source, target)
        return target

    # prepare
    def sync(self, *, apply: bool = False, overwrite: bool = False, yes: bool = False) -> list[Action]:
        """Plan (apply=False) or perform (apply=True) the creation and refresh of all ten workspaces."""
        if overwrite and not yes:
            raise WorkspaceError("--overwrite replaces participant files and requires --yes")
        templates = self.templates()
        participants = self._participants_by_group() if self.participant_mode == "individual_learning" else {}
        actions: list[Action] = []
        stamp = self._timestamp()
        for name in SHARED_SUBDIRS:
            path = self.shared_dir(name)
            if not path.is_dir():
                actions.append(Action("shared", "create_dir", f"shared/{name}"))
                if apply:
                    path.mkdir(parents=True, exist_ok=True)
        for group_id in GROUP_IDS:
            actions.extend(
                self._sync_group(
                    group_id,
                    templates,
                    apply,
                    overwrite,
                    stamp,
                    participants.get(group_id, ()),
                )
            )
        if self.participant_mode == "individual_learning" and not any(participants.values()):
            actions.append(
                Action(
                    "shared",
                    "no_participant_roster",
                    "shared/state/participant-assignments.csv",
                    "run assign_participants.py --apply before preparing individual folders",
                )
            )
        if apply:
            summary = {
                "schema_version": SCHEMA_VERSION,
                "participant_mode": self.participant_mode,
                "groups": {
                    g: {
                        "dataset_id": self.catalog.for_group(g).dataset_id,
                        "mission_id": self.catalog.for_group(g).mission_id,
                    }
                    for g in GROUP_IDS
                },
                "templates": {name: sha256_file(path) for name, path in templates.items()},
            }
            self._write(
                self.shared_dir("state"), "workspaces.json", (json.dumps(summary, indent=2) + "\n").encode()
            )
        return actions

    def _sync_group(
        self,
        group_id: str,
        templates: dict[str, Path],
        apply: bool,
        overwrite: bool,
        stamp: str,
        participant_refs: tuple[str, ...],
    ) -> list[Action]:
        actions: list[Action] = []
        base = self.group_dir(group_id)
        for sub in GROUP_SUBDIRS:
            directory = safe_join(base, sub)
            if not directory.is_dir():
                actions.append(Action(group_id, "create_dir", f"groups/{group_id}/{sub}"))
                if apply:
                    directory.mkdir(parents=True, exist_ok=True)
        manifest = self.read_manifest(group_id)
        files: dict = manifest.setdefault("files", {})
        manifest.update(
            {
                "schema_version": SCHEMA_VERSION,
                "group_id": group_id,
                "dataset_id": self.catalog.for_group(group_id).dataset_id,
                "mission_id": self.catalog.for_group(group_id).mission_id,
                "participant_mode": self.participant_mode,
            }
        )

        def sync_file(
            relative: str,
            desired: bytes,
            kind_new: str,
            kind_refresh: str,
            kind_replace: str,
            template_sha: str | None = None,
        ) -> None:
            target = safe_join(base, *relative.split("/"))
            desired_sha = sha256_bytes(desired)
            entry = files.get(relative, {})
            display = f"groups/{group_id}/{relative}"
            if not target.exists():
                actions.append(Action(group_id, kind_new, display))
                if apply:
                    self._write(base, relative, desired)
                    files[relative] = {
                        "template_sha256": template_sha or desired_sha,
                        "installed_sha256": desired_sha,
                    }
                return
            current = sha256_file(target)
            if current == desired_sha:
                actions.append(Action(group_id, "unchanged", display))
                if apply:
                    files[relative] = {
                        "template_sha256": template_sha or desired_sha,
                        "installed_sha256": desired_sha,
                    }
                return
            if entry and current == entry.get("installed_sha256"):  # still exactly what we installed earlier
                actions.append(
                    Action(group_id, kind_refresh, display, "template changed; participant did not edit it")
                )
                if apply:
                    self._write(base, relative, desired)
                    files[relative] = {
                        "template_sha256": template_sha or desired_sha,
                        "installed_sha256": desired_sha,
                    }
                return
            if overwrite:
                actions.append(
                    Action(
                        group_id, kind_replace, display, "participant edits backed up to shared/state/backups"
                    )
                )
                if apply:
                    self._backup(group_id, target, relative, stamp)
                    self._write(base, relative, desired)
                    files[relative] = {
                        "template_sha256": template_sha or desired_sha,
                        "installed_sha256": desired_sha,
                    }
                return
            actions.append(
                Action(
                    group_id,
                    "preserve_modified",
                    display,
                    "edited by the group; kept (use --overwrite --yes to replace)",
                )
            )

        if self.participant_mode == "group_driver":
            for name, path in templates.items():
                data = path.read_bytes()
                sync_file(
                    f"notebooks/{name}",
                    data,
                    "copy_notebook",
                    "refresh_notebook",
                    "replace_notebook",
                    sha256_bytes(data),
                )
            sync_file(
                "driver-rotation.md",
                self.driver_rotation_text(group_id).encode(),
                "write_file",
                "refresh_file",
                "replace_file",
            )
        else:
            for participant_ref in participant_refs:
                for sub in PARTICIPANT_SUBDIRS:
                    directory = safe_join(base, "participants", participant_ref, sub)
                    if not directory.is_dir():
                        relative = f"groups/{group_id}/participants/{participant_ref}/{sub}"
                        actions.append(Action(group_id, "create_dir", relative))
                        if apply:
                            directory.mkdir(parents=True, exist_ok=True)
                for name, path in templates.items():
                    data = path.read_bytes()
                    sync_file(
                        f"participants/{participant_ref}/notebooks/{name}",
                        data,
                        "copy_notebook",
                        "refresh_notebook",
                        "replace_notebook",
                        sha256_bytes(data),
                    )
                sync_file(
                    f"participants/{participant_ref}/config/group.env",
                    self.participant_env_text(group_id, participant_ref).encode(),
                    "write_file",
                    "refresh_file",
                    "replace_file",
                )
        sync_file(
            "config/group.env",
            self.group_env_text(group_id).encode(),
            "write_file",
            "refresh_file",
            "replace_file",
        )
        sync_file(
            "README.md", self.readme_text(group_id).encode(), "write_file", "refresh_file", "replace_file"
        )
        if apply:
            files_for_manifest = {k: v for k, v in files.items()}
            manifest["files"] = files_for_manifest
            self._write(
                base,
                f"config/{MANIFEST_NAME}",
                (json.dumps(manifest, indent=2, sort_keys=True) + "\n").encode(),
            )
        return actions

    # validate
    def validate(self) -> WorkspaceReport:
        report = WorkspaceReport()
        groups_dir = self.root / "groups"
        present = sorted(p.name for p in groups_dir.iterdir()) if groups_dir.is_dir() else []
        report.add(
            "exactly the ten valid group folders exist",
            present == list(GROUP_IDS),
            f"found {present}" if present != list(GROUP_IDS) else "",
        )
        if not groups_dir.is_dir():
            return report
        shared_missing = [n for n in SHARED_SUBDIRS if not (self.root / "shared" / n).is_dir()]
        report.add(
            "shared config, state and logs folders exist",
            not shared_missing,
            f"missing {shared_missing}" if shared_missing else "",
        )
        symlinks = [str(p.relative_to(self.root)) for p in _walk(self.root) if p.is_symlink()]
        report.add("no symlinks anywhere in the runtime", not symlinks, "; ".join(symlinks[:3]))
        unsafe = []
        for p in _walk(self.root):
            try:
                group_paths.check_segment(p.name)
            except UnsafePathError:
                if not p.name.startswith(".tmp-") and not p.name.startswith(".write-"):
                    unsafe.append(str(p.relative_to(self.root)))
        report.add(
            "every file and folder name is a safe path segment (no traversal)",
            not unsafe,
            "; ".join(unsafe[:3]),
        )
        templates = self.templates()
        participants = (
            self._participants_by_group()
            if self.participant_mode == "individual_learning"
            else {}
        )
        env_errors, mission_errors, notebook_errors, secret_errors, folder_errors, write_errors = (
            [],
            [],
            [],
            [],
            [],
            [],
        )
        for group_id in GROUP_IDS:
            if group_id not in present:
                continue
            base = self.group_dir(group_id)
            bundle = self.catalog.for_group(group_id)
            missing_dirs = [s for s in GROUP_SUBDIRS if not (base / s).is_dir()]
            if missing_dirs:
                folder_errors.append(f"{group_id}: {missing_dirs}")
            env_path = base / "config" / "group.env"
            if not env_path.is_file():
                env_errors.append(f"{group_id}: group.env missing")
            else:
                values = parse_env(env_path.read_text(encoding="utf-8"))
                expected = {
                    "GROUP_ID": group_id,
                    "DATASET_ID": bundle.dataset_id,
                    "MISSION_ID": bundle.mission_id,
                }
                wrong = {k: values.get(k) for k, v in expected.items() if values.get(k) != v}
                if wrong:
                    mission_errors.append(f"{group_id}: {wrong}")
                if values.get("DATA_BACKEND", "csv") != "csv":
                    env_errors.append(f"{group_id}: DATA_BACKEND must be csv")
                if values.get("PARTICIPANT_MODE") != self.participant_mode:
                    env_errors.append(f"{group_id}: PARTICIPANT_MODE mismatch")
                try:
                    group_paths.check_segment(Path(values.get("GROUP_WORKSPACE", "")).name)
                    if Path(values.get("GROUP_WORKSPACE", "")).name != group_id:
                        env_errors.append(f"{group_id}: GROUP_WORKSPACE points at another folder")
                except UnsafePathError:
                    env_errors.append(f"{group_id}: GROUP_WORKSPACE is invalid")
                for key, value in values.items():
                    if SECRET_KEY.search(key) or SECRET_VALUE.search(value):
                        secret_errors.append(f"{group_id}: {key}")
            config_files = list((base / "config").glob("*")) if (base / "config").is_dir() else []
            config_files.extend((base / "participants").glob("*/config/*"))
            for path in config_files:
                if (
                    path.is_file()
                    and path.suffix in (".json", ".md", ".env")
                    and SECRET_VALUE.search(path.read_text(encoding="utf-8", errors="ignore"))
                ):
                    secret_errors.append(f"{group_id}: {path.name}")
            if self.participant_mode == "group_driver":
                missing_notebooks = [
                    name for name in templates if not (base / "notebooks" / name).is_file()
                ]
                if missing_notebooks:
                    notebook_errors.append(
                        f"{group_id}: missing {len(missing_notebooks)} ({missing_notebooks[0]}...)"
                    )
                if not (base / "driver-rotation.md").is_file():
                    folder_errors.append(f"{group_id}: driver-rotation.md missing")
                output_dirs = [base / "output"]
            else:
                output_dirs = []
                expected_refs = participants.get(group_id, ())
                actual_dir = base / "participants"
                actual_refs = (
                    sorted(path.name for path in actual_dir.iterdir())
                    if actual_dir.is_dir()
                    else []
                )
                if actual_refs != list(expected_refs):
                    folder_errors.append(f"{group_id}: participant folders {actual_refs}")
                for participant_ref in expected_refs:
                    participant = base / "participants" / participant_ref
                    missing_dirs = [
                        sub for sub in PARTICIPANT_SUBDIRS if not (participant / sub).is_dir()
                    ]
                    if missing_dirs:
                        folder_errors.append(
                            f"{group_id}/{participant_ref}: missing {missing_dirs}"
                        )
                    missing_notebooks = [
                        name
                        for name in templates
                        if not (participant / "notebooks" / name).is_file()
                    ]
                    if missing_notebooks:
                        notebook_errors.append(
                            f"{group_id}/{participant_ref}: missing {missing_notebooks[0]}"
                        )
                    output_dirs.append(participant / "output")
            for output_dir in output_dirs:
                if not output_dir.is_dir():
                    continue
                probe = safe_join(output_dir, "write-probe.tmp")
                try:
                    probe.write_text("ok", encoding="utf-8")
                    probe.unlink()
                except OSError as exc:
                    write_errors.append(f"{group_id}/{output_dir.parent.name}: {type(exc).__name__}")
        report.add(
            "every group has its config, notebooks, output, logs and tmp folders",
            not folder_errors,
            "; ".join(folder_errors[:3]),
        )
        report.add(
            "group.env files are present and consistent (backend csv)",
            not env_errors,
            "; ".join(env_errors[:3]),
        )
        report.add(
            "each group has its assigned dataset and mission",
            not mission_errors,
            "; ".join(mission_errors[:3]),
        )
        report.add(
            "every active workspace has all notebook templates",
            not notebook_errors,
            "; ".join(notebook_errors[:3]),
        )
        report.add("each group output folder is writable", not write_errors, "; ".join(write_errors[:3]))
        report.add(
            "no secret-like keys or values in workspace files",
            not secret_errors,
            "; ".join(secret_errors[:3]),
        )
        bundle = self.catalog.for_group(GROUP_IDS[0])
        csv_missing = [
            t
            for t in ("branches", "customers", "accounts", "transactions", "loans")
            if not (bundle.csv_dir / f"{t}.csv").is_file()
        ]
        readable = not csv_missing and all(
            os.access(bundle.csv_dir / f"{t}.csv", os.R_OK)
            for t in ("branches", "customers", "accounts", "transactions", "loans")
        )
        report.add(
            "the shared dataset is readable", readable, f"missing {csv_missing}" if csv_missing else ""
        )
        copies = [
            str(p.relative_to(self.root))
            for p in _walk(self.root / "groups")
            if p.suffix == ".csv"
        ]
        report.add(
            "the physical dataset is not duplicated into group folders", not copies, "; ".join(copies[:3])
        )
        return report

    # reset
    def reset(
        self,
        group_id: str,
        *,
        participant_ref: str | None = None,
        include_notebooks: bool = False,
        apply: bool = False,
        yes: bool = False,
    ) -> list[Action]:
        if group_id not in GROUP_IDS:
            raise WorkspaceError(f"Unknown group: {group_id!r}. Give one of group_01 to group_10.")
        if apply and not yes:
            raise WorkspaceError("Resetting deletes group files and requires --yes")
        group_base = self.group_dir(group_id)
        if not group_base.is_dir():
            raise WorkspaceError(f"{group_id} has no workspace yet")
        if participant_ref is not None:
            if participant_ref not in PARTICIPANT_REFS:
                raise WorkspaceError("participant_ref must be participant_01 through participant_04")
            base = safe_join(group_base, "participants", participant_ref)
            if not base.is_dir():
                raise WorkspaceError(f"{group_id}/{participant_ref} has no workspace yet")
            display_root = f"groups/{group_id}/participants/{participant_ref}"
            manifest_prefix = f"participants/{participant_ref}/"
        else:
            base = group_base
            display_root = f"groups/{group_id}"
            manifest_prefix = ""
        actions: list[Action] = []
        stamp = self._timestamp()
        for sub in ("output", "logs", "tmp"):
            directory = safe_join(base, sub)
            if not directory.is_dir():
                continue
            for path in sorted(directory.rglob("*"), reverse=True):
                if path.is_symlink():
                    raise WorkspaceError(f"Refusing to reset: symlink found at {sub}/{path.name}")
            files = [p for p in directory.rglob("*") if p.is_file()]
            actions.append(
                Action(
                    group_id,
                    "clear_dir",
                    f"{display_root}/{sub}",
                    f"{len(files)} files, {sum(p.stat().st_size for p in files)} bytes",
                )
            )
            if apply:
                for path in sorted(directory.iterdir()):
                    if path.is_dir():
                        shutil.rmtree(path)
                    else:
                        path.unlink()
        if include_notebooks:
            manifest = self.read_manifest(group_id)
            templates = self.templates()
            for name, template in templates.items():
                relative = f"notebooks/{name}"
                manifest_relative = manifest_prefix + relative
                target = safe_join(base, "notebooks", name)
                data = template.read_bytes()
                if target.exists():
                    modified = sha256_file(target) != sha256_bytes(data)
                    if not modified:
                        actions.append(Action(group_id, "unchanged", f"{display_root}/{relative}"))
                        continue
                    actions.append(
                        Action(
                            group_id,
                            "reset_notebook",
                            f"{display_root}/{relative}",
                            "modified notebook backed up first",
                        )
                    )
                    if apply:
                        self._backup(group_id, target, manifest_relative, stamp)
                else:
                    actions.append(Action(group_id, "restore_notebook", f"{display_root}/{relative}"))
                if apply:
                    self._write(base, relative, data)
                    manifest.setdefault("files", {})[manifest_relative] = {
                        "template_sha256": sha256_bytes(data),
                        "installed_sha256": sha256_bytes(data),
                    }
            if apply:
                self._write(
                    group_base,
                    f"config/{MANIFEST_NAME}",
                    (json.dumps(manifest, indent=2, sort_keys=True) + "\n").encode(),
                )
        return actions

    # archive
    def archive(
        self,
        group_id: str,
        *,
        participant_ref: str | None = None,
        include_logs: bool = False,
        apply: bool = False,
    ) -> dict:
        group_base = self.group_dir(group_id)
        if not group_base.is_dir():
            raise WorkspaceError(f"{group_id} has no workspace yet")
        if participant_ref is not None:
            if participant_ref not in PARTICIPANT_REFS:
                raise WorkspaceError("participant_ref must be participant_01 through participant_04")
            base = safe_join(group_base, "participants", participant_ref)
            if not base.is_dir():
                raise WorkspaceError(f"{group_id}/{participant_ref} has no workspace yet")
        else:
            base = group_base
        folders = ["output"] + (["logs"] if include_logs else [])
        entries: list[tuple[Path, str]] = []
        for sub in folders:
            directory = safe_join(base, sub)
            for path in sorted(directory.rglob("*")) if directory.is_dir() else []:
                if path.is_symlink():
                    raise WorkspaceError(f"Refusing to archive: symlink found at {sub}/{path.name}")
                if path.is_file():
                    entries.append((path, path.relative_to(base).as_posix()))
        summary = {
            "group_id": group_id,
            "participant_ref": participant_ref,
            "files": len(entries),
            "bytes": sum(p.stat().st_size for p, _ in entries),
            "archive": None,
        }
        if apply:
            stamp = self._timestamp()
            target_dir = safe_join(self.root, "shared", "state") / "archives"
            target_dir.mkdir(parents=True, exist_ok=True)
            target_name = (
                f"{group_id}-{participant_ref}-{stamp}.zip"
                if participant_ref
                else f"{group_id}-{stamp}.zip"
            )
            target = target_dir / target_name
            checksums = {}
            with zipfile.ZipFile(target, "w", zipfile.ZIP_DEFLATED) as archive:
                for path, name in entries:
                    data = path.read_bytes()
                    checksums[name] = sha256_bytes(data)
                    info = zipfile.ZipInfo(name, (2026, 1, 1, 0, 0, 0))
                    info.compress_type = zipfile.ZIP_DEFLATED
                    archive.writestr(info, data)
                archive.writestr("CHECKSUMS.json", json.dumps(checksums, indent=2, sort_keys=True))
            summary["archive"] = f"shared/state/archives/{target.name}"
        return summary


def _walk(root: Path):
    """Every path below root without following symlinks."""
    root = Path(root)
    if not root.exists():
        return
    stack = [root]
    while stack:
        current = stack.pop()
        try:
            children = sorted(current.iterdir())
        except OSError:
            continue
        for child in children:
            yield child
            if child.is_dir() and not child.is_symlink():
                stack.append(child)

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
    ):
        self.root = Path(runtime_root)
        self.templates_dir = Path(templates_dir)
        self.catalog = catalog or BundleCatalog.load()
        self.repo_root = Path(repo_root)
        self._clock = clock

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
            "WORKSHOP_TOPOLOGY=single_project",
            "DATA_BACKEND=csv",
            f"CSV_DATA_DIR={csv_ref}",
        ]
        return "\n".join(lines) + "\n"

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
        actions: list[Action] = []
        stamp = self._timestamp()
        for name in SHARED_SUBDIRS:
            path = self.shared_dir(name)
            if not path.is_dir():
                actions.append(Action("shared", "create_dir", f"shared/{name}"))
                if apply:
                    path.mkdir(parents=True, exist_ok=True)
        for group_id in GROUP_IDS:
            actions.extend(self._sync_group(group_id, templates, apply, overwrite, stamp))
        if apply:
            summary = {
                "schema_version": SCHEMA_VERSION,
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
        self, group_id: str, templates: dict[str, Path], apply: bool, overwrite: bool, stamp: str
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
                try:
                    group_paths.check_segment(Path(values.get("GROUP_WORKSPACE", "")).name)
                    if Path(values.get("GROUP_WORKSPACE", "")).name != group_id:
                        env_errors.append(f"{group_id}: GROUP_WORKSPACE points at another folder")
                except UnsafePathError:
                    env_errors.append(f"{group_id}: GROUP_WORKSPACE is invalid")
                for key, value in values.items():
                    if SECRET_KEY.search(key) or SECRET_VALUE.search(value):
                        secret_errors.append(f"{group_id}: {key}")
            for path in (base / "config").glob("*") if (base / "config").is_dir() else []:
                if (
                    path.is_file()
                    and path.suffix in (".json", ".md", ".env")
                    and SECRET_VALUE.search(path.read_text(encoding="utf-8", errors="ignore"))
                ):
                    secret_errors.append(f"{group_id}: {path.name}")
            missing_notebooks = [n for n in templates if not (base / "notebooks" / n).is_file()]
            if missing_notebooks:
                notebook_errors.append(
                    f"{group_id}: missing {len(missing_notebooks)} ({missing_notebooks[0]}...)"
                )
            if (base / "output").is_dir():
                probe = safe_join(base, "output", "write-probe.tmp")
                try:
                    probe.write_text("ok", encoding="utf-8")
                    probe.unlink()
                except OSError as exc:
                    write_errors.append(f"{group_id}: {type(exc).__name__}")
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
            "every group has all notebook templates", not notebook_errors, "; ".join(notebook_errors[:3])
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
        copies = [str(p.relative_to(self.root)) for p in _walk(self.root) if p.suffix == ".csv"]
        report.add(
            "the physical dataset is not duplicated into group folders", not copies, "; ".join(copies[:3])
        )
        return report

    # reset
    def reset(
        self, group_id: str, *, include_notebooks: bool = False, apply: bool = False, yes: bool = False
    ) -> list[Action]:
        if group_id not in GROUP_IDS:
            raise WorkspaceError(f"Unknown group: {group_id!r}. Give one of group_01 to group_10.")
        if apply and not yes:
            raise WorkspaceError("Resetting deletes group files and requires --yes")
        base = self.group_dir(group_id)
        if not base.is_dir():
            raise WorkspaceError(f"{group_id} has no workspace yet")
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
                    f"groups/{group_id}/{sub}",
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
                target = safe_join(base, "notebooks", name)
                data = template.read_bytes()
                if target.exists():
                    modified = sha256_file(target) != sha256_bytes(data)
                    if not modified:
                        actions.append(Action(group_id, "unchanged", f"groups/{group_id}/{relative}"))
                        continue
                    actions.append(
                        Action(
                            group_id,
                            "reset_notebook",
                            f"groups/{group_id}/{relative}",
                            "modified notebook backed up first",
                        )
                    )
                    if apply:
                        self._backup(group_id, target, relative, stamp)
                else:
                    actions.append(Action(group_id, "restore_notebook", f"groups/{group_id}/{relative}"))
                if apply:
                    self._write(base, relative, data)
                    manifest.setdefault("files", {})[relative] = {
                        "template_sha256": sha256_bytes(data),
                        "installed_sha256": sha256_bytes(data),
                    }
            if apply:
                self._write(
                    base,
                    f"config/{MANIFEST_NAME}",
                    (json.dumps(manifest, indent=2, sort_keys=True) + "\n").encode(),
                )
        return actions

    # archive
    def archive(self, group_id: str, *, include_logs: bool = False, apply: bool = False) -> dict:
        base = self.group_dir(group_id)
        if not base.is_dir():
            raise WorkspaceError(f"{group_id} has no workspace yet")
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
            "files": len(entries),
            "bytes": sum(p.stat().st_size for p, _ in entries),
            "archive": None,
        }
        if apply:
            stamp = self._timestamp()
            target_dir = safe_join(self.root, "shared", "state") / "archives"
            target_dir.mkdir(parents=True, exist_ok=True)
            target = target_dir / f"{group_id}-{stamp}.zip"
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

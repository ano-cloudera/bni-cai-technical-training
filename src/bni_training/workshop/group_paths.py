"""The single write gate for group files. Application-layer validation, not OS-level isolation."""

from __future__ import annotations

import os
import re
import unicodedata
from collections.abc import Mapping
from pathlib import Path

from bni_training.data.dictionary import REPO_ROOT

RUNTIME_ENV = "WORKSHOP_RUNTIME_DIR"
_SEGMENT = re.compile(r"^[A-Za-z0-9][A-Za-z0-9._-]{0,127}$")
_FILENAME = re.compile(r"^[A-Za-z0-9][A-Za-z0-9._-]{0,79}$")
MAX_OUTPUT_BYTES = 1_000_000


class UnsafePathError(ValueError):
    """A path segment or resolved path would leave its permitted directory."""


def runtime_root(env: Mapping[str, str] | None = None) -> Path:
    value = (os.environ if env is None else env).get(RUNTIME_ENV)
    return Path(value) if value else REPO_ROOT / "workshop" / "runtime"


def check_segment(value: str, *, pattern: re.Pattern = _SEGMENT, label: str = "path segment") -> str:
    if not isinstance(value, str) or unicodedata.normalize("NFC", value) != value:
        raise UnsafePathError(f"Invalid {label}")
    if value in {"", ".", ".."} or not pattern.fullmatch(value) or ".." in value:
        raise UnsafePathError(f"Invalid {label}: {value!r}")
    return value


def check_filename(value: str) -> str:
    return check_segment(value, pattern=_FILENAME, label="file name")


def safe_join(base: Path, *segments: str) -> Path:
    """Join validated segments under ``base`` and prove the result stays inside it.

    Rejects traversal, absolute paths, separators, NUL bytes, odd Unicode, and any symlink component.
    """
    base = Path(base)
    resolved_base = base.resolve()
    current = base
    for segment in segments:
        check_segment(segment)
        current = current / segment
        if current.is_symlink():
            raise UnsafePathError(f"Symlinks are not allowed in group paths: {segment}")
    resolved = current.resolve()
    try:
        resolved.relative_to(resolved_base)
    except ValueError as exc:
        raise UnsafePathError("Path escapes its permitted directory") from exc
    return resolved


def group_workspace(root: Path, group_id: str) -> Path:
    """Directory a group may write to. ``group_id`` must already be validated by the registry."""
    return safe_join(Path(root), "groups", group_id)


def session_output_dir(root: Path, group_id: str, session_id: str) -> Path:
    return safe_join(group_workspace(root, group_id), "output", session_id)


def session_tmp_dir(root: Path, group_id: str, session_id: str) -> Path:
    return safe_join(group_workspace(root, group_id), "tmp", session_id)


def write_session_file(root: Path, group_id: str, session_id: str, name: str, text: str) -> Path:
    """Atomically write ``text`` into the session's output folder through the safe-path gate."""
    import tempfile

    check_filename(name)
    data = text.encode("utf-8")
    if len(data) > MAX_OUTPUT_BYTES:
        raise ValueError("Output is too large")
    out_dir = session_output_dir(root, group_id, session_id)
    tmp_dir = session_tmp_dir(root, group_id, session_id)
    out_dir.mkdir(parents=True, exist_ok=True)
    tmp_dir.mkdir(parents=True, exist_ok=True)
    fd, tmp_name = tempfile.mkstemp(dir=tmp_dir, prefix=".write-")
    with os.fdopen(fd, "wb") as handle:
        handle.write(data)
    target = safe_join(out_dir, name)
    os.replace(tmp_name, target)
    return target


def write_group_output(root: Path, group_id: str, name: str, text: str) -> Path:
    """Atomically write ``text`` into the group's own ``output`` folder (used by the labs)."""
    import tempfile

    check_filename(name)
    data = text.encode("utf-8")
    if len(data) > MAX_OUTPUT_BYTES:
        raise ValueError("Output is too large")
    out_dir = safe_join(group_workspace(root, group_id), "output")
    out_dir.mkdir(parents=True, exist_ok=True)
    fd, tmp_name = tempfile.mkstemp(dir=out_dir, prefix=".write-")
    with os.fdopen(fd, "wb") as handle:
        handle.write(data)
    target = safe_join(out_dir, name)
    os.replace(tmp_name, target)
    return target

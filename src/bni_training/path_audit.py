"""Audit tracked files for real machine-specific paths.

A hit is a path into somebody's home directory or a build machine's scratch area: a macOS or Linux user home,
a Windows profile, or a temporary-folder path. Placeholders such as ``<name>``, ``$USER`` or the CAI home
``cdsw`` are fine, and so are bare mentions of the directory names.

The patterns are built from fragments, so this file never matches itself and needs no exclusion.
"""

from __future__ import annotations

import re
import subprocess
from dataclasses import dataclass
from pathlib import Path

_SLASH = "/"
_NAME = r"(?!(?:cdsw|you|user|username|name|example|me|root|runner)\b)[A-Za-z0-9][A-Za-z0-9._-]*"
_START = r"(?<![\w.$<{-])"

PATTERNS = {
    "macos-home": re.compile(_START + _SLASH + "Us" + "ers" + _SLASH + _NAME + _SLASH),
    "linux-home": re.compile(_START + _SLASH + "ho" + "me" + _SLASH + _NAME + _SLASH),
    "private-scratch": re.compile(_START + _SLASH + "pri" + "vate" + _SLASH + r"(?:var|tmp|etc)" + _SLASH),
    "var-folders": re.compile(_START + _SLASH + "var" + _SLASH + "fol" + "ders" + _SLASH),
    "windows-profile": re.compile(r"\b[A-Za-z]:\\{1,2}Us" + r"ers\\{1,2}" + _NAME),
}
SKIPPED_WALK_PARTS = frozenset(
    {".git", ".venv", "__pycache__", ".pytest_cache", ".ruff_cache", "build", "dist"}
)


@dataclass(frozen=True)
class Finding:
    path: str
    line: int
    kind: str

    def __str__(self) -> str:
        return f"{self.path}:{self.line}: {self.kind}"


def scan_text(text: str, path: str = "<text>") -> list[Finding]:
    """Findings for one text. The matched text is never reported, only where and which kind."""
    found = []
    for number, line in enumerate(text.splitlines(), start=1):
        for kind, pattern in PATTERNS.items():
            if pattern.search(line):
                found.append(Finding(path, number, kind))
    return found


def tracked_files(root: Path) -> list[Path]:
    """Files tracked by git; outside a repository, all files except caches and build output."""
    try:
        out = subprocess.run(
            ["git", "ls-files", "-z"], cwd=root, capture_output=True, check=True, timeout=60
        ).stdout.decode("utf-8", errors="replace")
        names = [n for n in out.split("\0") if n]
    except (OSError, subprocess.SubprocessError):
        names = [
            p.relative_to(root).as_posix()
            for p in root.rglob("*")
            if p.is_file() and not SKIPPED_WALK_PARTS & set(p.relative_to(root).parts)
        ]
    return [root / n for n in names if (root / n).is_file()]


def scan_files(root: Path, files: list[Path] | None = None) -> list[Finding]:
    root = Path(root)
    found: list[Finding] = []
    for path in files if files is not None else tracked_files(root):
        data = path.read_bytes()
        if b"\0" in data:
            continue
        found += scan_text(data.decode("utf-8", errors="replace"), path.relative_to(root).as_posix())
    return found


def audit(root: Path) -> tuple[bool, list[Finding]]:
    findings = scan_files(root)
    return not findings, findings

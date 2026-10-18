from __future__ import annotations

import re
from pathlib import Path

TEXT_SUFFIXES = {
    ".py",
    ".md",
    ".yaml",
    ".yml",
    ".json",
    ".toml",
    ".txt",
    ".sh",
    ".sql",
    ".csv",
    ".ipynb",
    ".example",
}
SKIP_PARTS = {".git", ".venv", "dist", "build", ".pytest_cache", "__pycache__", "wheelhouse"}
PATTERNS = [
    ("private-domain", re.compile(r"[a-z0-9.-]+\.bni\.co\.id", re.I)),
    ("private-key", re.compile(r"-----BEGIN (?:RSA |EC |OPENSSH )?PRIVATE KEY-----")),
    ("bearer-token", re.compile(r"Bearer\s+[A-Za-z0-9_-]{24,}")),
    ("api-key-assignment", re.compile(r"(?:API_KEY|PASSWORD|TOKEN)[ \t]*=[ \t]*[A-Za-z0-9_-]{24,}", re.I)),
]


def scan_tree(root: Path) -> list[dict]:
    findings = []
    for path in root.rglob("*"):
        if not path.is_file() or any(part in SKIP_PARTS for part in path.parts):
            continue
        if path.suffix not in TEXT_SUFFIXES and path.name not in {"Makefile", "AGENTS.md"}:
            continue
        try:
            text = path.read_text(encoding="utf-8")
        except UnicodeDecodeError:
            continue
        for name, pattern in PATTERNS:
            if pattern.search(text):
                findings.append({"file": str(path), "pattern": name})
    return findings


if __name__ == "__main__":
    import json

    result = scan_tree(Path("."))
    print(json.dumps(result, indent=2))
    raise SystemExit(1 if result else 0)

from __future__ import annotations

import hashlib
import json
from pathlib import Path
from zipfile import ZIP_DEFLATED, ZipFile, ZipInfo

EXCLUDED_PARTS = {
    ".git",
    ".venv",
    "dist",
    "build",
    ".pytest_cache",
    ".ruff_cache",
    "__pycache__",
    ".superpowers",
    "superpowers",
}
EXCLUDED_PREFIXES = ("workshop/runtime/",)  # generated per-group workspaces: never packaged
EXCLUDED_NAMES = {".env", "local-inventory.json", "start.sh", "group.env"}
EXCLUDED_SUFFIXES = {".pyc", ".keytab", ".pem", ".crt", ".safetensors", ".bin"}


def approved(path: Path, root: Path | None = None) -> bool:
    relative = path.relative_to(root).as_posix() if root and path.is_absolute() else path.as_posix()
    return (
        not any(part in EXCLUDED_PARTS for part in path.parts)
        and not relative.startswith(EXCLUDED_PREFIXES)
        and path.suffix not in EXCLUDED_SUFFIXES
        and path.name not in EXCLUDED_NAMES
    )


def build_release(root: Path, dist: Path, version: str) -> Path:
    state = (root / "PROJECT_STATE.md").read_text()
    if "local_validation_passed" not in state and "cai_validated" not in state:
        raise RuntimeError("Local validation has not passed; update PROJECT_STATE.md after a validated run")
    entries = []
    for line in (root / "packaging/manifest.txt").read_text().splitlines():
        if not line.strip():
            continue
        path = root / line
        entries.extend([path] if path.is_file() else [p for p in path.rglob("*") if p.is_file()])
    entries = sorted({p for p in entries if approved(p, root)}, key=lambda p: str(p.relative_to(root)))
    dist.mkdir(parents=True, exist_ok=True)
    archive = dist / f"bni-cai-technical-training-{version}.zip"
    with ZipFile(archive, "w", ZIP_DEFLATED, compresslevel=9) as zf:
        for path in entries:
            arc = "bni-cai-technical-training/" + str(path.relative_to(root))
            info = ZipInfo(arc, (2026, 1, 1, 0, 0, 0))
            info.compress_type = ZIP_DEFLATED
            info.external_attr = 0o644 << 16
            zf.writestr(info, path.read_bytes())
    digest = hashlib.sha256(archive.read_bytes()).hexdigest()
    archive.with_suffix(archive.suffix + ".sha256").write_text(f"{digest}  {archive.name}\n")
    (dist / "release-manifest.json").write_text(
        json.dumps(
            {"version": version, "archive": archive.name, "sha256": digest, "files": len(entries)}, indent=2
        )
        + "\n"
    )
    return archive


if __name__ == "__main__":
    import argparse

    p = argparse.ArgumentParser()
    p.add_argument("--version", required=True)
    args = p.parse_args()
    print(build_release(Path("."), Path("dist"), args.version))

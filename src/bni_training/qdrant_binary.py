"""Prepare the Qdrant server binary for the CAI Application (run once, from a Session).

The launcher never downloads anything. This module downloads the pinned release asset over HTTPS, verifies its
SHA-256, extracts the single ``qdrant`` executable and places it at the destination. It is safe to run again.

Override the pinned asset with QDRANT_BINARY_URL and QDRANT_BINARY_SHA256 (both are required together), for
example to use a customer mirror. QDRANT_FORCE=1 replaces an existing binary.
"""

from __future__ import annotations

import hashlib
import json
import os
import shutil
import sys
import tarfile
import tempfile
import urllib.request
from collections.abc import Callable, Mapping
from pathlib import Path

MANIFEST = Path(__file__).resolve().parents[2] / "requirements" / "qdrant-binary-manifest.json"


class QdrantBinaryError(RuntimeError):
    """The binary could not be prepared. The message says what to fix."""


def load_manifest(path: Path = MANIFEST) -> dict:
    return json.loads(Path(path).read_text(encoding="utf-8"))


def resolve_asset(manifest: Mapping, env: Mapping[str, str]) -> tuple[str, str, str]:
    """(url, sha256, archive_kind). A URL override needs its own checksum."""
    url_override, sha_override = (
        env.get("QDRANT_BINARY_URL", "").strip(),
        env.get("QDRANT_BINARY_SHA256", "").strip(),
    )
    if bool(url_override) != bool(sha_override):
        raise QdrantBinaryError("Set both QDRANT_BINARY_URL and QDRANT_BINARY_SHA256, or neither")
    url, sha = (url_override, sha_override) if url_override else (manifest["url"], manifest["sha256"])
    if not url.lower().startswith("https://"):
        raise QdrantBinaryError("The Qdrant binary must be downloaded over https")
    if len(sha) != 64 or any(c not in "0123456789abcdefABCDEF" for c in sha):
        raise QdrantBinaryError("The SHA-256 checksum must be 64 hexadecimal characters")
    archive = "tar.gz" if url.lower().endswith((".tar.gz", ".tgz")) else "binary"
    return url, sha.lower(), archive


def sha256_of(path: Path) -> str:
    digest = hashlib.sha256()
    with Path(path).open("rb") as handle:
        while chunk := handle.read(1024 * 1024):
            digest.update(chunk)
    return digest.hexdigest()


def extract_binary(archive: Path, destination: Path, name: str = "qdrant") -> None:
    """Write only the single executable member (``qdrant`` or ``./qdrant``) to ``destination``."""
    with tarfile.open(archive, "r:gz") as tar:
        member = next((m for m in tar.getmembers() if m.isfile() and Path(m.name).name == name), None)
        if member is None:
            raise QdrantBinaryError(f"The archive does not contain a file named {name}")
        source = tar.extractfile(member)
        assert source is not None
        with destination.open("wb") as target:
            shutil.copyfileobj(source, target)


def download(url: str, target: Path) -> None:
    request = urllib.request.Request(url, headers={"User-Agent": "bni-training-qdrant-prepare"})
    with urllib.request.urlopen(request, timeout=120) as response, target.open("wb") as out:  # noqa: S310
        shutil.copyfileobj(response, out)


def prepare(
    destination: Path,
    env: Mapping[str, str],
    *,
    manifest: Mapping | None = None,
    fetch: Callable[[str, Path], None] = download,
) -> str:
    """Prepare the binary; returns a one-line status. Never leaves a half-written file at ``destination``."""
    destination = Path(destination)
    if destination.is_file() and os.access(destination, os.X_OK) and env.get("QDRANT_FORCE") != "1":
        return f"Qdrant binary already present at {destination} (set QDRANT_FORCE=1 to replace it)"
    url, expected, archive_kind = resolve_asset(manifest or load_manifest(), env)
    destination.parent.mkdir(parents=True, exist_ok=True)
    with tempfile.TemporaryDirectory(dir=destination.parent, prefix=".qdrant-prepare-") as work:
        downloaded = Path(work) / "asset"
        fetch(url, downloaded)
        actual = sha256_of(downloaded)
        if actual != expected:
            raise QdrantBinaryError(
                f"Checksum mismatch: expected {expected[:12]}..., got {actual[:12]}.... File discarded."
            )
        staged = Path(work) / "qdrant"
        if archive_kind == "tar.gz":
            extract_binary(downloaded, staged)
        else:
            shutil.copyfile(downloaded, staged)
        staged.chmod(0o755)
        os.replace(staged, destination)
    return f"Prepared verified Qdrant binary at {destination} ({expected[:12]}...)"


def main(argv: list[str] | None = None) -> int:
    args = sys.argv[1:] if argv is None else argv
    manifest = load_manifest()
    destination = Path(args[0] if args else manifest["default_destination"])
    try:
        print(prepare(destination, os.environ, manifest=manifest))
    except (QdrantBinaryError, OSError, tarfile.TarError) as exc:
        print(f"ERROR: {exc}", file=sys.stderr)
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

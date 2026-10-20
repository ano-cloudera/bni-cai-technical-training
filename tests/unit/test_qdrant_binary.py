"""Qdrant binary preparation: pinned, checksum-verified, never downloaded by the Application."""

from __future__ import annotations

import hashlib
import io
import json
import os
import re
import tarfile
from pathlib import Path

import pytest

from bni_training import qdrant_binary as qb
from deployments.cai.qdrant import app

ROOT = Path(__file__).resolve().parents[2]
FAKE_BINARY = b"#!/bin/sh\necho fake-qdrant\n"


def make_archive(path: Path, members: dict[str, bytes]) -> str:
    with tarfile.open(path, "w:gz") as tar:
        for name, data in members.items():
            info = tarfile.TarInfo(name)
            info.size = len(data)
            tar.addfile(info, io.BytesIO(data))
    return hashlib.sha256(path.read_bytes()).hexdigest()


def fetcher(source: Path):
    calls: list[str] = []

    def fetch(url: str, target: Path) -> None:
        calls.append(url)
        target.write_bytes(source.read_bytes())

    fetch.calls = calls  # type: ignore[attr-defined]
    return fetch


MANIFEST = {"url": "https://example.invalid/qdrant.tar.gz", "sha256": "0" * 64, "default_destination": "/x"}


def test_the_pinned_manifest_names_one_https_linux_release_with_a_checksum() -> None:
    manifest = qb.load_manifest()
    assert manifest["url"].startswith("https://github.com/qdrant/qdrant/releases/download/")
    assert manifest["version"] in manifest["url"] and manifest["asset"].endswith("linux-musl.tar.gz")
    assert re.fullmatch(r"[0-9a-f]{64}", manifest["sha256"])
    assert manifest["default_destination"] == "/home/cdsw/tools/qdrant/qdrant"
    assert qb.resolve_asset(manifest, {})[2] == "tar.gz"


def test_a_verified_archive_is_extracted_to_an_executable(tmp_path) -> None:
    archive = tmp_path / "a.tar.gz"
    sha = make_archive(archive, {"qdrant": FAKE_BINARY, "README": b"ignore me"})
    destination = tmp_path / "tools" / "qdrant" / "qdrant"
    status = qb.prepare(
        destination,
        {"QDRANT_BINARY_URL": "https://m.invalid/q.tar.gz", "QDRANT_BINARY_SHA256": sha},
        manifest=MANIFEST,
        fetch=fetcher(archive),
    )
    assert "Prepared verified Qdrant binary" in status
    assert destination.read_bytes() == FAKE_BINARY and os.access(destination, os.X_OK)
    assert sorted(p.name for p in destination.parent.iterdir()) == [
        "qdrant"
    ]  # no temporary files left behind


def test_a_member_named_with_a_dot_slash_prefix_is_found(tmp_path) -> None:
    archive = tmp_path / "a.tar.gz"
    sha = make_archive(archive, {"./qdrant": FAKE_BINARY})
    destination = tmp_path / "qdrant"
    qb.prepare(
        destination,
        {"QDRANT_BINARY_URL": "https://m.invalid/q.tgz", "QDRANT_BINARY_SHA256": sha},
        manifest=MANIFEST,
        fetch=fetcher(archive),
    )
    assert destination.read_bytes() == FAKE_BINARY


def test_a_checksum_mismatch_discards_the_download_and_leaves_nothing(tmp_path) -> None:
    archive = tmp_path / "a.tar.gz"
    make_archive(archive, {"qdrant": FAKE_BINARY})
    destination = tmp_path / "bin" / "qdrant"
    with pytest.raises(qb.QdrantBinaryError, match="Checksum mismatch"):
        qb.prepare(
            destination,
            {"QDRANT_BINARY_URL": "https://m.invalid/q.tar.gz", "QDRANT_BINARY_SHA256": "a" * 64},
            manifest=MANIFEST,
            fetch=fetcher(archive),
        )
    assert not destination.exists() and list(destination.parent.iterdir()) == []


def test_an_archive_without_the_binary_is_rejected(tmp_path) -> None:
    archive = tmp_path / "a.tar.gz"
    sha = make_archive(archive, {"other": b"x"})
    with pytest.raises(qb.QdrantBinaryError, match="does not contain"):
        qb.prepare(
            tmp_path / "qdrant",
            {"QDRANT_BINARY_URL": "https://m.invalid/q.tar.gz", "QDRANT_BINARY_SHA256": sha},
            manifest=MANIFEST,
            fetch=fetcher(archive),
        )


def test_a_raw_binary_url_is_supported(tmp_path) -> None:
    raw = tmp_path / "raw"
    raw.write_bytes(FAKE_BINARY)
    destination = tmp_path / "qdrant"
    env = {
        "QDRANT_BINARY_URL": "https://m.invalid/qdrant",
        "QDRANT_BINARY_SHA256": hashlib.sha256(FAKE_BINARY).hexdigest(),
    }
    qb.prepare(destination, env, manifest=MANIFEST, fetch=fetcher(raw))
    assert destination.read_bytes() == FAKE_BINARY


def test_running_again_does_nothing_unless_forced(tmp_path) -> None:
    destination = tmp_path / "qdrant"
    destination.write_bytes(b"existing")
    destination.chmod(0o755)
    fetch = fetcher(tmp_path / "unused")
    assert "already present" in qb.prepare(destination, {}, manifest=MANIFEST, fetch=fetch)
    assert fetch.calls == [] and destination.read_bytes() == b"existing"


def test_a_url_override_needs_its_own_checksum_and_must_use_https() -> None:
    with pytest.raises(qb.QdrantBinaryError, match="both"):
        qb.resolve_asset(MANIFEST, {"QDRANT_BINARY_URL": "https://m.invalid/q.tar.gz"})
    with pytest.raises(qb.QdrantBinaryError, match="both"):
        qb.resolve_asset(MANIFEST, {"QDRANT_BINARY_SHA256": "a" * 64})
    with pytest.raises(qb.QdrantBinaryError, match="https"):
        qb.resolve_asset(
            MANIFEST, {"QDRANT_BINARY_URL": "http://m.invalid/q", "QDRANT_BINARY_SHA256": "a" * 64}
        )
    with pytest.raises(qb.QdrantBinaryError, match="64 hexadecimal"):
        qb.resolve_asset(
            MANIFEST, {"QDRANT_BINARY_URL": "https://m.invalid/q", "QDRANT_BINARY_SHA256": "xyz"}
        )


def test_the_launcher_reports_a_missing_binary_clearly_and_never_downloads(tmp_path) -> None:
    missing = tmp_path / "no" / "qdrant"
    with pytest.raises(ValueError, match="prepare_qdrant_binary.sh") as error:
        app.check_binary({"QDRANT_BINARY": str(missing)})
    assert str(missing) in str(error.value)
    source = Path(app.__file__).read_text()
    assert not re.search(r"urlopen|urlretrieve|requests\.|curl|wget|tarfile", source)


def test_the_launcher_accepts_an_existing_executable(tmp_path) -> None:
    binary = tmp_path / "qdrant"
    binary.write_bytes(FAKE_BINARY)
    binary.chmod(0o755)
    assert app.check_binary({"QDRANT_BINARY": str(binary)}) == binary
    binary.chmod(0o644)
    with pytest.raises(ValueError, match="not executable"):
        app.check_binary({"QDRANT_BINARY": str(binary)})


def test_the_shell_wrapper_is_a_thin_call_into_the_tested_module() -> None:
    script = (ROOT / "scripts/prepare_qdrant_binary.sh").read_text()
    assert "set -euo pipefail" in script and "bni_training.qdrant_binary" in script
    assert "curl" not in script.replace("# ", "")  # no download logic in shell
    assert json.loads((ROOT / "requirements/qdrant-binary-manifest.json").read_text())["archive"] == "tar.gz"

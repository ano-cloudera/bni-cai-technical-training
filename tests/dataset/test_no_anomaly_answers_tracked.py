"""No anomaly flag, answer key or incident list may be committed anywhere in the project."""

from __future__ import annotations

import re
import subprocess
from pathlib import Path

from bni_training.data.synthetic import generate

ROOT = Path(__file__).resolve().parents[2]
# Needles are assembled at runtime so this file does not contain them itself.
FLAG = "is_" + "seeded_" + "anomaly"
MANIFEST = "anomaly_" + "test_" + "manifest"
INCIDENT_ID = re.compile(r"\b(?:velocity_burst|large_amount|structuring)-\d{2}\b")


def tracked_files() -> list[Path]:
    out = subprocess.run(
        ["git", "ls-files", "-z"], cwd=ROOT, capture_output=True, text=True, check=True
    ).stdout.split("\0")
    return [ROOT / name for name in out if name and (ROOT / name).is_file()]


def test_no_tracked_file_mentions_the_flag_the_manifest_or_an_incident_id() -> None:
    offenders = []
    for path in tracked_files():
        text = path.read_text(encoding="utf-8", errors="ignore")
        if FLAG in text or MANIFEST in text or INCIDENT_ID.search(text):
            offenders.append(str(path.relative_to(ROOT)))
    assert offenders == []


def test_no_tracked_file_lists_the_transaction_ids_of_an_incident() -> None:
    ids = {i for inc in generate().anomaly_incidents for i in inc["transaction_ids"][:3]}
    sample = sorted(ids)[:30]
    for path in tracked_files():
        if path.suffix in {".csv"}:
            continue
        text = path.read_text(encoding="utf-8", errors="ignore")
        assert not any(i in text for i in sample), path


def test_the_generator_keeps_the_incidents_in_memory_only(tmp_path) -> None:
    from bni_training.data.synthetic import write_dataset

    dataset = generate()
    assert dataset.anomaly_incidents
    write_dataset(dataset, tmp_path / "raw", tmp_path / "manifests")
    written = [p for p in tmp_path.rglob("*") if p.is_file()]
    assert sorted(p.name for p in written) == [
        "accounts.csv",
        "branches.csv",
        "checksums.json",
        "customers.csv",
        "dataset_manifest.json",
        "loans.csv",
        "transactions.csv",
    ]
    assert not any(INCIDENT_ID.search(p.read_text()) for p in written if p.suffix == ".json")

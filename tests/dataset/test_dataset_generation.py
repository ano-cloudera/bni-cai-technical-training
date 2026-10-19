from __future__ import annotations

import json
import re
from pathlib import Path

import pytest

from bni_training.data.dictionary import DEFAULT_MANIFEST_DIR, DEFAULT_RAW_DIR
from bni_training.data.synthetic import REFERENCE_DATE, SEED, generate, render_all, sha256, write_dataset

ROOT = Path(__file__).resolve().parents[2]


def test_the_same_seed_gives_identical_bytes_and_another_seed_does_not() -> None:
    a, b = render_all(generate(SEED, 0.05)), render_all(generate(SEED, 0.05))
    assert a == b
    assert render_all(generate(SEED + 1, 0.05)) != a


def test_the_committed_files_are_exactly_what_the_generator_produces() -> None:
    files = render_all(generate())
    recorded = json.loads((DEFAULT_MANIFEST_DIR / "checksums.json").read_text())["files"]
    for name, data in files.items():
        assert (DEFAULT_RAW_DIR / name).read_bytes() == data, name
        assert recorded[name]["sha256"] == sha256(data), name


def test_generation_never_uses_the_clock_or_the_network() -> None:
    source = (ROOT / "src/bni_training/data/synthetic.py").read_text()
    for forbidden in (
        "today(",
        "datetime.now",
        "date.today",
        "time.time",
        "urllib",
        "requests",
        "socket",
        "faker",
    ):
        assert forbidden not in source, forbidden
    assert REFERENCE_DATE.isoformat() == "2026-06-30"
    # only +,-,*,/ on floats: no libm functions whose last digit can differ between platforms
    libm_like = r"\bmath\.|\bexp\(|\blog\(|[\w)\]]\s*\*\*\s*[\w(]|\bpow\(|\bgauss|\blognormvariate"
    assert not re.search(libm_like, source)


def test_checksums_cover_every_csv_and_the_manifest_matches_the_files() -> None:
    checksums = json.loads((DEFAULT_MANIFEST_DIR / "checksums.json").read_text())
    manifest = json.loads((DEFAULT_MANIFEST_DIR / "dataset_manifest.json").read_text())
    assert sorted(checksums["files"]) == [f"{n}.csv" for n in sorted(manifest["row_counts"])]
    assert manifest["seed"] == SEED and manifest["fully_synthetic"] is True
    assert manifest["contains_personal_data"] is False and manifest["reference_date"] == "2026-06-30"
    assert manifest["history_window"] == {"start": "2024-07-01", "end": "2026-06-30", "months": 24}


def test_write_is_atomic_leaves_no_staging_files_and_overwrites_cleanly(tmp_path) -> None:
    dataset = generate(SEED, 0.05)
    raw, manifests = tmp_path / "raw", tmp_path / "manifests"
    write_dataset(dataset, raw, manifests)
    first = {p.name: p.read_bytes() for p in raw.iterdir()}
    write_dataset(dataset, raw, manifests)
    assert {p.name: p.read_bytes() for p in raw.iterdir()} == first
    assert sorted(p.name for p in raw.iterdir()) == [
        "accounts.csv",
        "branches.csv",
        "customers.csv",
        "loans.csv",
        "transactions.csv",
    ]
    assert sorted(p.name for p in manifests.iterdir()) == [
        "anomaly_test_manifest.json",
        "checksums.json",
        "dataset_manifest.json",
    ]


def test_cli_preview_writes_nothing_and_requires_an_explicit_output_dir(
    tmp_path, capsys, monkeypatch
) -> None:
    import runpy
    import sys

    monkeypatch.chdir(tmp_path)
    monkeypatch.setattr(sys, "argv", ["generate_synthetic_data.py", "--preview", "--scale", "0.05"])
    with pytest.raises(SystemExit) as exit_info:
        runpy.run_path(str(ROOT / "scripts/generate_synthetic_data.py"), run_name="__main__")
    assert exit_info.value.code == 0 and list(tmp_path.iterdir()) == []
    assert '"row_counts"' in capsys.readouterr().out
    monkeypatch.setattr(sys, "argv", ["generate_synthetic_data.py"])
    with pytest.raises(SystemExit) as missing:
        runpy.run_path(str(ROOT / "scripts/generate_synthetic_data.py"), run_name="__main__")
    assert missing.value.code == 2

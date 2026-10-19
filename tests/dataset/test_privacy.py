from __future__ import annotations

import csv
import re
from pathlib import Path

import yaml

from bni_training.data.dictionary import DEFAULT_RAW_DIR

ROOT = Path(__file__).resolve().parents[2]
TABLES = ("branches", "customers", "accounts", "transactions", "loans")
PII = {
    "email": re.compile(r"[\w.%+-]+@[\w.-]+\.[A-Za-z]{2,}"),
    "phone": re.compile(r"(?:\+|00)?\d[\d\s().-]{8,}\d"),
    "url": re.compile(r"https?://|www\.", re.I),
    "national_id_like": re.compile(r"\b\d{9,}\b"),
    "card_like": re.compile(r"\b(?:\d[ -]?){13,19}\b"),
    "ssn_like": re.compile(r"\b\d{3}-\d{2}-\d{4}\b"),
}
FORBIDDEN_COLUMN_WORDS = (
    "address",
    "phone",
    "email",
    "passport",
    "ssn",
    "nik",
    "birth",
    "dob",
    "firstname",
    "lastname",
    "surname",
)


def test_no_column_looks_like_personal_data(dictionary) -> None:
    for table in dictionary.tables.values():
        for column in table.column_names:
            assert not any(word in column.lower() for word in FORBIDDEN_COLUMN_WORDS), column
            assert column == "branch_name" or "name" not in column.lower(), (
                column
            )  # the only name is a fictional branch


def test_no_cell_matches_a_personal_data_pattern(dictionary) -> None:
    for name in TABLES:
        text_columns = [c.name for c in dictionary.tables[name].columns if c.type == "text"]
        with (DEFAULT_RAW_DIR / f"{name}.csv").open(newline="") as handle:
            for row in csv.DictReader(handle):
                for column in text_columns:
                    for label, pattern in PII.items():
                        assert not pattern.search(row[column]), (name, column, label)


def test_every_text_value_is_controlled_vocabulary_or_a_synthetic_id(dictionary) -> None:
    for name in TABLES:
        constrained = {
            c.name
            for c in dictionary.tables[name].columns
            if c.type == "text" and (c.allowed_values or c.pattern)
        }
        assert constrained == {c.name for c in dictionary.tables[name].columns if c.type == "text"}, name


def test_synthetic_ids_never_look_real() -> None:
    with (DEFAULT_RAW_DIR / "customers.csv").open() as handle:
        for row in csv.DictReader(handle):
            assert row["customer_id"].startswith("SYN-CUST-")


def test_no_participant_facing_code_references_an_anomaly_answer_key() -> None:
    portal = [p for p in (ROOT / "src/bni_training/workshop").rglob("*.py")] + list(
        (ROOT / "apps/workshop-portal").rglob("*.py")
    )
    assert portal and not any("anomaly" in p.read_text().lower() for p in portal)
    for name in ("engine.py", "tool.py", "bundles.py", "semantic_layer.py"):
        assert "anomaly" not in (ROOT / "src/bni_training/data" / name).read_text().lower(), name


def test_no_anomaly_flag_or_manifest_is_part_of_the_dictionary_or_the_data_files() -> None:
    raw = yaml.safe_load((ROOT / "semantic/data_dictionary.yaml").read_text())
    names = {c for tab in raw["tables"].values() for c in tab["columns"]}
    assert not any("anomal" in n or "seeded" in n for n in names)
    header = (DEFAULT_RAW_DIR / "transactions.csv").read_text().splitlines()[0]
    assert "anomal" not in header and "seeded" not in header
    assert sorted(p.name for p in (ROOT / "data/manifests").iterdir()) == [
        "checksums.json",
        "dataset_manifest.json",
    ]


def test_sample_questions_and_missions_never_mention_the_test_only_data() -> None:
    for name in ("sample_questions.yaml", "group_assignments.yaml", "dataset_bundles.yaml"):
        text = (ROOT / "data/scenarios" / name).read_text().lower()
        assert "seeded" not in text and "anomaly" not in text, name

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


def test_the_anomaly_manifest_is_not_reachable_from_any_participant_facing_code() -> None:
    allowed = {"synthetic.py", "validation.py"}  # trainer and test tooling only
    offenders = []
    for path in (ROOT / "src").rglob("*.py"):
        if "anomaly_test_manifest" in path.read_text() and path.name not in allowed:
            offenders.append(str(path))
    assert offenders == []
    portal = [p for p in (ROOT / "src/bni_training/workshop").rglob("*.py")] + list(
        (ROOT / "apps/workshop-portal").rglob("*.py")
    )
    assert portal and not any("anomaly" in p.read_text().lower() for p in portal)
    assert "anomaly_test_manifest" not in (ROOT / "src/bni_training/data/engine.py").read_text()
    assert "anomaly_test_manifest" not in (ROOT / "src/bni_training/data/tool.py").read_text()


def test_the_anomaly_flag_is_marked_internal_and_hidden_in_the_dictionary() -> None:
    raw = yaml.safe_load((ROOT / "semantic/data_dictionary.yaml").read_text())
    column = raw["tables"]["transactions"]["columns"]["is_seeded_anomaly"]
    assert column["participant_exposed"] is False and column["sensitivity"] == "internal_test_only"
    exposed_flags = [
        (t, c) for t, tab in raw["tables"].items() for c, col in tab["columns"].items()
        if col.get("sensitivity") == "internal_test_only" and col.get("participant_exposed", True)
    ]  # fmt: skip
    assert exposed_flags == []


def test_sample_questions_and_missions_never_mention_the_test_only_data() -> None:
    for name in ("sample_questions.yaml", "group_assignments.yaml", "dataset_bundles.yaml"):
        text = (ROOT / "data/scenarios" / name).read_text().lower()
        assert "seeded" not in text and "is_seeded" not in text and "anomaly_test" not in text, name

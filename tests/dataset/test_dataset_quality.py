"""Independent checks of the committed dataset, plus proof that the validator catches corrupted copies."""

from __future__ import annotations

import csv
from collections import Counter
from datetime import date, timedelta
from pathlib import Path
from statistics import mean, pstdev

import pytest

from bni_training.data.dictionary import DEFAULT_MANIFEST_DIR, DEFAULT_RAW_DIR
from bni_training.data.synthetic import SEED, generate, write_dataset
from bni_training.data.validation import validate_dataset

REF = date(2026, 6, 30)
TABLES = ("branches", "customers", "accounts", "transactions", "loans")


@pytest.fixture(scope="module")
def tables():
    result = {}
    for name in TABLES:
        with (DEFAULT_RAW_DIR / f"{name}.csv").open(newline="") as handle:
            result[name] = list(csv.DictReader(handle))
    return result


def test_row_counts_match_the_targets(tables) -> None:
    counts = {n: len(r) for n, r in tables.items()}
    assert counts["branches"] == 100 and counts["customers"] == 10_000 and counts["loans"] == 5_000
    assert 18_000 <= counts["accounts"] <= 22_000 and 90_000 <= counts["transactions"] <= 110_000


def test_required_tables_and_columns_exist_exactly(tables, dictionary) -> None:
    def cols(text: str) -> list[str]:
        return text.split()

    required = {
        "branches": cols(
            "branch_id branch_name region province city city_tier size_class open_date operational_status"
        ),
        "customers": cols(
            "customer_id home_branch_id segment region age_band income_band occupation_category join_date "
            "customer_status digital_adoption_level"
        ),
        "accounts": cols(
            "account_id customer_id branch_id product_code account_type open_date account_status balance "
            "average_monthly_balance last_activity_date channel_preference"
        ),
        "transactions": cols(
            "transaction_id account_id transaction_date transaction_type channel amount merchant_category "
            "transaction_status"
        ),
        "loans": cols(
            "loan_id customer_id account_id branch_id product_code origination_date maturity_date "
            "principal_amount "
            "outstanding_amount days_past_due loan_status risk_band"
        ),
    }
    for name, columns in required.items():
        assert list(dictionary.tables[name].column_names) == columns, name
        assert list(tables[name][0]) == columns, name


def test_identifiers_use_the_required_prefixes_and_widths(tables) -> None:
    patterns = {
        "branches": ("branch_id", "SYN-BR-", 5), "customers": ("customer_id", "SYN-CUST-", 5),
        "accounts": ("account_id", "SYN-ACC-", 5), "transactions": ("transaction_id", "SYN-TXN-", 6),
        "loans": ("loan_id", "SYN-LOAN-", 5),
    }  # fmt: skip
    for table, (column, prefix, width) in patterns.items():
        for row in tables[table]:
            value = row[column]
            assert (
                value.startswith(prefix)
                and value[len(prefix) :].isdigit()
                and len(value) == len(prefix) + width
            )


def test_primary_keys_are_unique_and_foreign_keys_resolve(tables, dictionary) -> None:
    for name in TABLES:
        key = dictionary.tables[name].primary_key
        values = [r[key] for r in tables[name]]
        assert len(values) == len(set(values)), name
    for child, child_col, parent, parent_col in dictionary.foreign_keys():
        parents = {r[parent_col] for r in tables[parent]}
        assert all(r[child_col] in parents for r in tables[child]), (child, child_col)


def test_amount_and_date_rules_hold(tables) -> None:
    accounts = {a["account_id"]: a for a in tables["accounts"]}
    customers = {c["customer_id"]: c for c in tables["customers"]}
    for loan in tables["loans"]:
        assert float(loan["outstanding_amount"]) <= float(loan["principal_amount"])
        assert (
            loan["maturity_date"] > loan["origination_date"] and loan["origination_date"] <= REF.isoformat()
        )
        assert int(loan["days_past_due"]) >= 0
        assert loan["origination_date"] >= max(
            customers[loan["customer_id"]]["join_date"], accounts[loan["account_id"]]["open_date"]
        )
    for txn in tables["transactions"]:
        assert accounts[txn["account_id"]]["open_date"] <= txn["transaction_date"] <= REF.isoformat()
        assert float(txn["amount"]) > 0
    for account in tables["accounts"]:
        assert account["open_date"] >= customers[account["customer_id"]]["join_date"]
        assert (
            float(account["balance"]) >= 0
            and account["open_date"] <= account["last_activity_date"] <= REF.isoformat()
        )


def test_closed_accounts_are_quiet_and_dormant_accounts_are_discoverable(tables) -> None:
    status = Counter(a["account_status"] for a in tables["accounts"])
    assert status["DORMANT"] >= 1000 and status["CLOSED"] >= 500 and status["ACTIVE"] > status["DORMANT"]
    for account in tables["accounts"]:
        last = date.fromisoformat(account["last_activity_date"])
        if account["account_status"] == "CLOSED":
            assert last <= REF - timedelta(days=90) and float(account["balance"]) == 0
        elif account["account_status"] == "DORMANT":
            assert last <= REF - timedelta(days=180)
        else:
            assert last > REF - timedelta(days=180)


def test_transactions_have_visible_monthly_patterns_and_a_24_month_history(tables) -> None:
    months = Counter(t["transaction_date"][:7] for t in tables["transactions"])
    assert len(months) == 24 and min(months) == "2024-07" and max(months) == "2026-06"
    values = [months[m] for m in sorted(months)]
    assert pstdev(values) / mean(values) >= 0.1
    assert months["2025-12"] > months["2025-11"] > months["2025-02"], "December peak and February dip"
    digital = {}
    for t in tables["transactions"]:
        half = t["transaction_date"][:4] + ("H1" if t["transaction_date"][5:7] <= "06" else "H2")
        total, dig = digital.get(half, (0, 0))
        digital[half] = (total + 1, dig + (t["channel"] in ("MOBILE", "ONLINE")))
    ratios = [d / n for _, (n, d) in sorted(digital.items())]
    assert ratios[-1] > ratios[0] + 0.05, "digital use grows over time"


def test_distributions_are_realistic_and_not_uniform(tables) -> None:
    for table, column in (
        ("customers", "region"),
        ("customers", "segment"),
        ("accounts", "product_code"),
        ("loans", "product_code"),
    ):
        counts = Counter(r[column] for r in tables[table]).values()
        assert max(counts) / min(counts) >= 1.5, (table, column)
    branch_customers = Counter(c["home_branch_id"] for c in tables["customers"])
    assert max(branch_customers.values()) > 2 * (sum(branch_customers.values()) / 100)


def test_total_dataset_size_is_below_fifty_megabytes() -> None:
    raw = sum((DEFAULT_RAW_DIR / f"{n}.csv").stat().st_size for n in TABLES)
    manifests = sum(p.stat().st_size for p in DEFAULT_MANIFEST_DIR.glob("*.json"))
    assert raw + manifests < 50 * 1_000_000
    placeholder = sum(p.stat().st_size for p in Path("data/csv").glob("*") if p.is_file())
    assert raw + manifests + placeholder < 50 * 1_000_000, "even with the rc1 placeholder kept"


def test_the_validator_passes_on_the_committed_dataset() -> None:
    report = validate_dataset()
    assert report.passed, report.render()
    names = " ".join(c.name for c in report.checks)
    expected_checks = (
        "required files", "columns match", "row counts", "unique", "foreign keys", "logically valid",
        "checksums.json", "50 MB", "byte for byte", "non-empty results", "Group 06",
    )  # fmt: skip
    for expected in expected_checks:
        assert expected in names, expected
    assert report.render().splitlines()[-1].startswith("RESULT: PASS")


# --- the validator must notice damage ---


@pytest.fixture()
def small_copy(tmp_path):
    raw, manifests = tmp_path / "raw", tmp_path / "manifests"
    write_dataset(generate(SEED, 0.05), raw, manifests)
    return raw, manifests


def check(raw: Path, manifests: Path):
    return validate_dataset(raw, manifests, expect_full_scale=False, check_missions=False)


def rewrite(path: Path, change) -> None:
    with path.open(newline="") as handle:
        rows = list(csv.reader(handle))
    change(rows)
    with path.open("w", newline="") as handle:
        csv.writer(handle, lineterminator="\n").writerows(rows)


def failed_names(report) -> str:
    return " | ".join(c.name for c in report.failures)


def test_an_untouched_small_dataset_passes(small_copy) -> None:
    assert check(*small_copy).passed


def test_a_missing_file_is_reported(small_copy) -> None:
    raw, manifests = small_copy
    (raw / "loans.csv").unlink()
    assert "required files" in failed_names(check(raw, manifests))


def test_a_duplicate_primary_key_is_reported(small_copy) -> None:
    raw, manifests = small_copy
    rewrite(raw / "customers.csv", lambda rows: rows.append(list(rows[1])))
    assert "customers.customer_id is unique" in failed_names(check(raw, manifests))


def test_an_orphan_foreign_key_is_reported(small_copy) -> None:
    raw, manifests = small_copy
    rewrite(raw / "accounts.csv", lambda rows: rows[1].__setitem__(1, "SYN-CUST-99999"))
    assert "foreign keys" in failed_names(check(raw, manifests))


def test_an_outstanding_amount_above_principal_is_reported(small_copy) -> None:
    raw, manifests = small_copy
    rewrite(raw / "loans.csv", lambda rows: rows[1].__setitem__(8, "99999999.00"))
    assert "logically valid" in failed_names(check(raw, manifests))


def test_a_bad_value_domain_is_reported(small_copy) -> None:
    raw, manifests = small_copy
    rewrite(raw / "customers.csv", lambda rows: rows[1].__setitem__(2, "VIP_PLATINUM"))
    assert "type, pattern, allowed values" in failed_names(check(raw, manifests))


def test_pii_like_content_is_reported(small_copy) -> None:
    raw, manifests = small_copy
    rewrite(raw / "branches.csv", lambda rows: rows[1].__setitem__(1, "Alder Bay Branch"))
    rewrite(
        raw / "branches.csv",
        lambda rows: rows[1].__setitem__(4, "call 0812345678901 or a.person@example.com"),
    )
    assert "email, phone" in failed_names(check(raw, manifests)) or "pattern" in failed_names(
        check(raw, manifests)
    )


def test_any_edit_breaks_the_checksums_and_the_determinism_check(small_copy) -> None:
    raw, manifests = small_copy
    text = (raw / "branches.csv").read_text()
    (raw / "branches.csv").write_text(text.replace("ACTIVE", "ACTIVE ", 1))
    names = failed_names(check(raw, manifests))
    assert "checksums.json" in names and "byte for byte" in names


def test_a_dataset_over_the_size_limit_is_reported(small_copy, monkeypatch) -> None:
    import bni_training.data.validation as validation

    monkeypatch.setattr(validation, "SIZE_LIMIT_BYTES", 1000)
    assert "50 MB" in failed_names(check(*small_copy))


def test_an_answer_key_column_in_a_csv_is_reported(small_copy) -> None:
    raw, manifests = small_copy
    path = raw / "transactions.csv"
    lines = path.read_text().splitlines()
    path.write_text("\n".join([lines[0] + ",answer_flag", *[line + ",0" for line in lines[1:]]]) + "\n")
    assert "columns match the data dictionary" in failed_names(check(raw, manifests))

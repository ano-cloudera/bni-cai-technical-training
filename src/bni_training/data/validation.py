"""Validation of the synthetic banking dataset: structure, integrity, logic, determinism, size, privacy."""

from __future__ import annotations

import csv
import json
import re
from collections import Counter
from dataclasses import dataclass, field
from datetime import date, timedelta
from pathlib import Path
from statistics import mean, pstdev

from .dictionary import DEFAULT_MANIFEST_DIR, DEFAULT_RAW_DIR, DataDictionary
from .synthetic import REFERENCE_DATE, TABLE_ORDER, WINDOW_START, generate, render_all, sha256

SIZE_LIMIT_BYTES = 50 * 1_000_000
ROW_RANGES = {
    "branches": (80, 120),
    "customers": (9_500, 10_500),
    "accounts": (18_000, 22_000),
    "transactions": (90_000, 110_000),
    "loans": (4_500, 5_500),
}
PII_PATTERNS = {
    "email": re.compile(r"[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Za-z]{2,}"),
    "phone": re.compile(r"(?:\+|00)?\d[\d\s().-]{8,}\d"),
    "long_digit_run": re.compile(r"\d{9,}"),
    "url": re.compile(r"https?://", re.I),
}


@dataclass
class Check:
    name: str
    passed: bool
    detail: str = ""


@dataclass
class ValidationReport:
    checks: list[Check] = field(default_factory=list)

    def add(self, name: str, passed: bool, detail: str = "") -> None:
        self.checks.append(Check(name, bool(passed), detail))

    @property
    def passed(self) -> bool:
        return bool(self.checks) and all(c.passed for c in self.checks)

    @property
    def failures(self) -> list[Check]:
        return [c for c in self.checks if not c.passed]

    def render(self) -> str:
        lines = [
            f"[{'PASS' if c.passed else 'FAIL'}] {c.name}" + (f": {c.detail}" if c.detail else "")
            for c in self.checks
        ]
        lines.append(
            f"RESULT: {'PASS' if self.passed else 'FAIL'} "
            f"({len(self.checks) - len(self.failures)}/{len(self.checks)} checks)"
        )
        return "\n".join(lines)


def read_tables(raw_dir: Path) -> dict[str, list[dict[str, str]]]:
    tables = {}
    for name in TABLE_ORDER:
        with (Path(raw_dir) / f"{name}.csv").open(newline="", encoding="utf-8") as handle:
            tables[name] = list(csv.DictReader(handle))
    return tables


def _d(value: str) -> date:
    return date.fromisoformat(value)


def validate_dataset(
    raw_dir: Path = DEFAULT_RAW_DIR,
    manifest_dir: Path = DEFAULT_MANIFEST_DIR,
    *,
    dictionary: DataDictionary | None = None,
    check_determinism: bool = True,
    expect_full_scale: bool = True,
    check_missions: bool = True,
) -> ValidationReport:
    report = ValidationReport()
    raw_dir, manifest_dir = Path(raw_dir), Path(manifest_dir)
    dictionary = dictionary or DataDictionary.load()

    # 1. files and columns
    missing = [f"{n}.csv" for n in TABLE_ORDER if not (raw_dir / f"{n}.csv").is_file()]
    report.add(
        "required files present",
        not missing,
        f"missing: {missing}" if missing else f"{len(TABLE_ORDER)} CSV files",
    )
    if missing:
        return report
    bad_columns = []
    for name in TABLE_ORDER:
        with (raw_dir / f"{name}.csv").open(newline="", encoding="utf-8") as handle:
            header = next(csv.reader(handle))
        if tuple(header) != dictionary.tables[name].column_names:
            bad_columns.append(name)
    report.add(
        "columns match the data dictionary",
        not bad_columns,
        f"mismatch in {bad_columns}" if bad_columns else "",
    )
    if bad_columns:
        return report
    tables = read_tables(raw_dir)

    # 2. row counts
    if expect_full_scale:
        out_of_range = {
            n: len(r) for n, r in tables.items() if not ROW_RANGES[n][0] <= len(r) <= ROW_RANGES[n][1]
        }
        report.add(
            "row counts within target ranges",
            not out_of_range,
            str(out_of_range) if out_of_range else str({n: len(r) for n, r in tables.items()}),
        )

    # 3. primary keys, domains
    for name in TABLE_ORDER:
        key = dictionary.tables[name].primary_key
        values = [r[key] for r in tables[name]]
        report.add(
            f"{name}.{key} is unique",
            len(values) == len(set(values)),
            f"{len(values) - len(set(values))} duplicates",
        )
    domain_errors: list[str] = []
    for name in TABLE_ORDER:
        for column in dictionary.tables[name].columns:
            pattern = re.compile(column.pattern) if column.pattern else None
            allowed = {str(v) for v in column.allowed_values}
            bad = 0
            for row in tables[name]:
                value = row[column.name]
                if column.type == "date":
                    try:
                        _d(value)
                    except ValueError:
                        bad += 1
                elif column.type in ("real", "integer"):
                    try:
                        number = float(value)
                    except ValueError:
                        bad += 1
                        continue
                    if column.minimum is not None and number < column.minimum:
                        bad += 1
                    if allowed and value not in allowed:
                        bad += 1
                elif pattern and not pattern.fullmatch(value):
                    bad += 1
                elif allowed and value not in allowed:
                    bad += 1
            if bad:
                domain_errors.append(f"{name}.{column.name}: {bad}")
    report.add(
        "every value matches its type, pattern, allowed values and minimum",
        not domain_errors,
        "; ".join(domain_errors[:5]),
    )

    # 4. foreign keys
    fk_errors = []
    for child, child_col, parent, parent_col in dictionary.foreign_keys():
        parent_values = {r[parent_col] for r in tables[parent]}
        orphans = sum(1 for r in tables[child] if r[child_col] not in parent_values)
        if orphans:
            fk_errors.append(f"{child}.{child_col}->{parent}.{parent_col}: {orphans}")
    report.add("all foreign keys resolve", not fk_errors, "; ".join(fk_errors))
    if fk_errors:  # the lifecycle rules look rows up through these keys, so they cannot be evaluated
        report.add(
            "dates, amounts and lifecycle rules are logically valid",
            False,
            "not checked: foreign keys are broken",
        )
        return report

    # 5. logical rules
    branches = {r["branch_id"]: r for r in tables["branches"]}
    customers = {r["customer_id"]: r for r in tables["customers"]}
    accounts = {r["account_id"]: r for r in tables["accounts"]}
    errors: dict[str, int] = Counter()
    for c in tables["customers"]:
        b = branches[c["home_branch_id"]]
        errors["customer joined before its branch opened"] += _d(c["join_date"]) < _d(b["open_date"])
        errors["customer joined after the reference date"] += _d(c["join_date"]) > REFERENCE_DATE
        errors["customer region differs from its branch region"] += c["region"] != b["region"]
    accounts_by_customer: dict[str, list[dict]] = {}
    for a in tables["accounts"]:
        accounts_by_customer.setdefault(a["customer_id"], []).append(a)
        opened, last = _d(a["open_date"]), _d(a["last_activity_date"])
        errors["account opened before its customer joined"] += opened < _d(
            customers[a["customer_id"]]["join_date"]
        )
        errors["account opened after the reference date"] += opened > REFERENCE_DATE
        errors["last activity before opening or after the reference date"] += (
            last < opened or last > REFERENCE_DATE
        )
        errors["account type does not match its product"] += False
        if a["account_status"] == "CLOSED":
            errors["closed account with a balance"] += float(a["balance"]) != 0.0
            errors["closed account with recent activity"] += last > REFERENCE_DATE - timedelta(days=90)
        elif a["account_status"] == "DORMANT":
            errors["dormant account with activity in the last 180 days"] += last > REFERENCE_DATE - timedelta(
                days=180
            )
        else:
            errors["active account without activity in the last 180 days"] += (
                last <= REFERENCE_DATE - timedelta(days=180)
            )
    for cid, c in customers.items():
        if c["customer_status"] == "CLOSED":
            errors["closed customer with a non-closed account"] += any(
                a["account_status"] != "CLOSED" for a in accounts_by_customer.get(cid, [])
            )
        errors["customer without any account"] += cid not in accounts_by_customer
    last_seen: dict[str, str] = {}
    window_start, ref_iso = WINDOW_START.isoformat(), REFERENCE_DATE.isoformat()
    for t in tables["transactions"]:
        a = accounts[t["account_id"]]
        errors["transaction before its account opened"] += t["transaction_date"] < a["open_date"]
        errors["transaction outside the history window"] += (
            not window_start <= t["transaction_date"] <= ref_iso
        )
        errors["non-positive transaction amount"] += float(t["amount"]) <= 0
        if t["transaction_date"] > last_seen.get(t["account_id"], ""):
            last_seen[t["account_id"]] = t["transaction_date"]
    for aid, a in accounts.items():
        expected = max(last_seen[aid], a["open_date"]) if aid in last_seen else a["open_date"]
        errors["last_activity_date is not the latest transaction date"] += a["last_activity_date"] != expected
    for loan in tables["loans"]:
        a = accounts[loan["account_id"]]
        orig, mat = _d(loan["origination_date"]), _d(loan["maturity_date"])
        principal, outstanding, dpd = (
            float(loan["principal_amount"]),
            float(loan["outstanding_amount"]),
            int(loan["days_past_due"]),
        )
        errors["loan maturity not after origination"] += mat <= orig
        errors["loan originated before its customer joined or its account opened"] += orig < max(
            _d(customers[loan["customer_id"]]["join_date"]), _d(a["open_date"])
        )
        errors["loan originated after the reference date"] += orig > REFERENCE_DATE
        errors["outstanding amount above principal"] += outstanding > principal
        errors["loan customer differs from its account's customer"] += loan["customer_id"] != a["customer_id"]
        errors["loan branch differs from its account's branch"] += loan["branch_id"] != a["branch_id"]
        status = loan["loan_status"]
        expected_status = (
            "DEFAULTED" if dpd >= 90 else "DELINQUENT" if dpd >= 30 else "GRACE" if dpd >= 1 else "CURRENT"
        )
        if status == "PAID_OFF":
            errors["paid-off loan with an outstanding amount"] += outstanding != 0.0 or dpd != 0
        else:
            errors["loan status inconsistent with days past due"] += status != expected_status
    broken = {k: v for k, v in errors.items() if v}
    report.add("dates, amounts and lifecycle rules are logically valid", not broken, str(broken))

    # 6. realism: patterns, skew, dormant accounts, anomalies
    months = Counter(t["transaction_date"][:7] for t in tables["transactions"])
    values = [months[m] for m in sorted(months)]
    variation = pstdev(values) / mean(values) if values else 0
    report.add(
        "monthly transaction volumes show a visible pattern",
        len(months) >= 24 and variation >= 0.1,
        f"{len(months)} months, variation {variation:.2f}",
    )
    regions = Counter(c["region"] for c in tables["customers"])
    products = Counter(a["product_code"] for a in tables["accounts"])
    report.add(
        "regional and product mixes are not uniform",
        max(regions.values()) / min(regions.values()) >= 1.5
        and max(products.values()) / min(products.values()) >= 2,
        f"region ratio {max(regions.values()) / min(regions.values()):.1f}",
    )
    dormant = sum(1 for a in tables["accounts"] if a["account_status"] == "DORMANT")
    report.add(
        "dormant accounts are discoverable",
        dormant >= max(20, len(tables["accounts"]) // 20),
        f"{dormant} dormant accounts",
    )
    flagged = [t for t in tables["transactions"] if t["is_seeded_anomaly"] == "1"]
    anomaly_path = manifest_dir / "anomaly_test_manifest.json"
    if anomaly_path.is_file():
        manifest_ids = {
            i for inc in json.loads(anomaly_path.read_text())["incidents"] for i in inc["transaction_ids"]
        }
        report.add(
            "anomaly manifest matches the flagged transactions",
            manifest_ids == {t["transaction_id"] for t in flagged},
            f"{len(flagged)} flagged",
        )
    else:
        report.add(
            "anomaly manifest matches the flagged transactions",
            False,
            "anomaly_test_manifest.json is missing",
        )

    # 7. privacy
    pii_hits: Counter = Counter()
    for name in TABLE_ORDER:
        # dates are validated by strict ISO parsing above; phone-like runs only make sense in text columns
        text_columns = [c.name for c in dictionary.tables[name].columns if c.type == "text"]
        for row in tables[name]:
            for column in text_columns:
                for label, pattern in PII_PATTERNS.items():
                    if pattern.search(row[column]):
                        pii_hits[f"{name}.{column}:{label}"] += 1
    report.add("no email, phone, URL or long identity-number patterns", not pii_hits, str(dict(pii_hits)))

    # 8. size and checksums
    sizes = {n: (raw_dir / f"{n}.csv").stat().st_size for n in TABLE_ORDER}
    manifest_bytes = (
        sum(p.stat().st_size for p in manifest_dir.glob("*.json")) if manifest_dir.is_dir() else 0
    )
    total = sum(sizes.values()) + manifest_bytes
    report.add("total dataset size is below 50 MB", total < SIZE_LIMIT_BYTES, f"{total / 1_000_000:.2f} MB")
    checksum_path = manifest_dir / "checksums.json"
    if checksum_path.is_file():
        recorded = json.loads(checksum_path.read_text())["files"]
        mismatched = [
            n
            for n in TABLE_ORDER
            if recorded.get(f"{n}.csv", {}).get("sha256") != sha256((raw_dir / f"{n}.csv").read_bytes())
        ]
        report.add(
            "CSV files match checksums.json", not mismatched, f"mismatch: {mismatched}" if mismatched else ""
        )
    else:
        report.add("CSV files match checksums.json", False, "checksums.json is missing")
    dataset_manifest_path = manifest_dir / "dataset_manifest.json"
    if dataset_manifest_path.is_file():
        manifest = json.loads(dataset_manifest_path.read_text())
        counts_ok = all(manifest["row_counts"][n] == len(tables[n]) for n in TABLE_ORDER)
        report.add(
            "dataset_manifest.json row counts match the files",
            counts_ok and not manifest["contains_personal_data"],
            f"seed {manifest['seed']}",
        )
    else:
        report.add(
            "dataset_manifest.json row counts match the files", False, "dataset_manifest.json is missing"
        )

    # 9. determinism
    if check_determinism and dataset_manifest_path.is_file():
        manifest = json.loads(dataset_manifest_path.read_text())
        regenerated = render_all(generate(manifest["seed"], manifest["scale"]), dictionary)
        same = all(regenerated[f"{n}.csv"] == (raw_dir / f"{n}.csv").read_bytes() for n in TABLE_ORDER)
        report.add("regenerating with the manifest seed reproduces the files byte for byte", same)
    if check_missions:
        validate_missions(report, raw_dir, manifest_dir, dictionary)
    return report


LARGE_AMOUNT_SQL = (
    "SELECT DISTINCT t.account_id FROM transactions t JOIN ("
    "SELECT account_id, transaction_type, SUM(amount) s, COUNT(*) n FROM transactions "
    "WHERE transaction_status = 'COMPLETED' GROUP BY account_id, transaction_type HAVING COUNT(*) >= 5) a "
    "ON a.account_id = t.account_id AND a.transaction_type = t.transaction_type "
    "WHERE t.transaction_status = 'COMPLETED' AND t.amount > 15 * (a.s - t.amount) / (a.n - 1)"
)
STRUCTURING_SQL = (
    "SELECT account_id FROM transactions WHERE amount BETWEEN 9500 AND 9990 "
    "AND transaction_type = 'TRANSFER_OUT' GROUP BY account_id HAVING COUNT(*) >= 5"
)


def validate_missions(
    report: ValidationReport, raw_dir: Path, manifest_dir: Path, dictionary: DataDictionary
) -> None:
    """Every group's mission must return non-empty results, and the seeded patterns must be discoverable."""
    from .bundles import BundleCatalog
    from .engine import CsvEngine
    from .semantic_layer import SemanticModel
    from .tool import WorkshopDataTool

    catalog, semantic = BundleCatalog.load(dictionary=dictionary), SemanticModel.load()
    engine = CsvEngine(raw_dir, dictionary)
    try:
        empty, failed = [], []
        for group_id, bundle in catalog.bundles.items():
            tool = WorkshopDataTool(engine, semantic, bundle)
            for question in bundle.sample_questions:
                try:
                    _sql, result = tool.query(question)
                except ValueError as exc:
                    failed.append(f"{group_id}: {question} ({exc})")
                    continue
                if result.row_count == 0:
                    empty.append(f"{group_id}: {question}")
        report.add(
            "every group mission returns non-empty results (all sample questions)",
            not empty and not failed,
            "; ".join((empty + failed)[:4])
            or f"{sum(len(b.sample_questions) for b in catalog.bundles.values())} questions",
        )
        anomaly_path = manifest_dir / "anomaly_test_manifest.json"
        if anomaly_path.is_file():
            by_type: dict[str, set[str]] = {}
            for incident in json.loads(anomaly_path.read_text())["incidents"]:
                by_type.setdefault(incident["type"], set()).add(incident["account_id"])
            tool = WorkshopDataTool(engine, semantic, catalog.for_group("group_06"))
            _sql, burst = tool.query(catalog.for_group("group_06").sample_questions[0])
            found_bursts = len({row[0] for row in burst.rows} & by_type["velocity_burst"])
            found_large = len({r[0] for r in tool.run_sql(LARGE_AMOUNT_SQL).rows} & by_type["large_amount"])
            found_structuring = len(
                {r[0] for r in tool.run_sql(STRUCTURING_SQL).rows} & by_type["structuring"]
            )
            ok = found_bursts >= 8 and found_large >= 13 and found_structuring >= 7
            report.add(
                "Group 06 can discover the seeded unusual patterns with ordinary queries",
                ok,
                f"bursts {found_bursts}/{len(by_type['velocity_burst'])}, "
                f"large {found_large}/{len(by_type['large_amount'])}, "
                f"structuring {found_structuring}/{len(by_type['structuring'])}",
            )
    finally:
        engine.close()

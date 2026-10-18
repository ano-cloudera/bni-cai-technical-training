from __future__ import annotations

import argparse
import csv
import hashlib
import json
import random
from dataclasses import dataclass
from datetime import date, timedelta
from pathlib import Path


@dataclass(frozen=True)
class DatasetManifest:
    seed: int
    scale: float
    row_counts: dict[str, int]
    hashes: dict[str, str]


def _write(path: Path, fieldnames: list[str], rows: list[dict]) -> str:
    with path.open("w", newline="", encoding="utf-8") as handle:
        writer = csv.DictWriter(handle, fieldnames=fieldnames)
        writer.writeheader()
        writer.writerows(rows)
    return hashlib.sha256(path.read_bytes()).hexdigest()


def generate_dataset(output_dir: Path, seed: int = 20261011, scale: float = 1.0) -> DatasetManifest:
    out = Path(output_dir)
    out.mkdir(parents=True, exist_ok=True)
    rng = random.Random(seed)
    regions = ["Central", "East", "North", "South", "West"]
    branches = [
        {
            "branch_id": f"BR{i:03d}",
            "branch_name": f"Synthetic Branch {i:03d}",
            "region": regions[(i - 1) % 5],
        }
        for i in range(1, 51)
    ]
    products = [
        {
            "product_id": f"PRD{i:02d}",
            "product_name": f"Synthetic Loan Product {i:02d}",
            "product_type": ["Consumer", "Mortgage", "SME", "Commercial", "Vehicle"][i % 5],
        }
        for i in range(1, 11)
    ]
    n_customers = max(100, int(10000 * scale))
    n_apps = max(250, int(25000 * scale))
    n_accounts = max(150, int(15000 * scale))
    n_payments = max(1800, int(180000 * scale))
    customers = []
    for i in range(1, n_customers + 1):
        branch = rng.choice(branches)
        customers.append(
            {
                "customer_id": f"CUST{i:06d}",
                "customer_segment": rng.choice(["Mass", "Affluent", "SME", "Commercial"]),
                "region": branch["region"],
                "branch_id": branch["branch_id"],
            }
        )
    start = date(2024, 1, 1)
    applications = []
    for i in range(1, n_apps + 1):
        requested = round(rng.uniform(5_000_000, 500_000_000), 2)
        status = rng.choices(["APPROVED", "REJECTED"], [0.68, 0.32])[0]
        applications.append(
            {
                "application_id": f"APP{i:07d}",
                "customer_id": rng.choice(customers)["customer_id"],
                "product_id": rng.choice(products)["product_id"],
                "application_date": str(start + timedelta(days=rng.randrange(900))),
                "status": status,
                "requested_amount": requested,
                "approved_amount": round(requested * rng.uniform(0.65, 1), 2) if status == "APPROVED" else 0,
            }
        )
    approved = [a for a in applications if a["status"] == "APPROVED"]
    accounts = []
    for i in range(1, n_accounts + 1):
        app = approved[i % len(approved)]
        customer = customers[int(app["customer_id"][4:]) - 1]
        balance = round(float(app["approved_amount"]) * rng.uniform(0.25, 0.98), 2)
        dpd = rng.choices([0, 15, 30, 60, 90], [0.72, 0.1, 0.08, 0.06, 0.04])[0]
        accounts.append(
            {
                "account_id": f"ACC{i:07d}",
                "application_id": app["application_id"],
                "customer_id": app["customer_id"],
                "branch_id": customer["branch_id"],
                "region": customer["region"],
                "customer_segment": customer["customer_segment"],
                "product_id": app["product_id"],
                "open_date": app["application_date"],
                "outstanding_balance": balance,
                "dpd": dpd,
                "risk_band": rng.choice(["LOW", "MEDIUM", "HIGH"]),
                "account_status": "ACTIVE" if balance > 0 else "CLOSED",
            }
        )
    payments = []
    for i in range(1, n_payments + 1):
        acc = accounts[i % len(accounts)]
        scheduled = round(max(float(acc["outstanding_balance"]) / 24, 100000), 2)
        actual = round(scheduled * rng.uniform(0.7, 1.05), 2)
        payments.append(
            {
                "transaction_id": f"TXN{i:09d}",
                "account_id": acc["account_id"],
                "payment_date": str(start + timedelta(days=rng.randrange(900))),
                "scheduled_amount": scheduled,
                "actual_amount": actual,
            }
        )
    datasets = {
        "branch_master": branches,
        "product_master": products,
        "customers": customers,
        "loan_applications": applications,
        "loan_accounts": accounts,
        "repayment_transactions": payments,
    }
    hashes = {}
    counts = {}
    for name, rows in datasets.items():
        hashes[name] = _write(out / f"{name}.csv", list(rows[0]), rows)
        counts[name] = len(rows)
    manifest = DatasetManifest(seed, scale, counts, hashes)
    (out / "manifest.json").write_text(
        json.dumps(
            {"seed": seed, "scale": scale, "row_counts": counts, "hashes": hashes}, indent=2, sort_keys=True
        )
        + "\n"
    )
    return manifest


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--output", type=Path, default=Path("data/csv"))
    parser.add_argument("--seed", type=int, default=20261011)
    parser.add_argument("--scale", type=float, default=1.0)
    args = parser.parse_args()
    print(generate_dataset(args.output, args.seed, args.scale))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

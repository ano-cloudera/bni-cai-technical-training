"""Deterministic generator of the fully synthetic workshop banking dataset.

Design rules that make the output reproducible byte for byte:

* A fixed seed and a fixed reference date. The system clock is never read.
* Only ``random.Random.random()`` is consumed, through our own helpers, so the stream does not depend on the
  Python version's higher-level sampling methods.
* Only +, -, *, / and comparisons on floats. No ``exp``, ``log``, ``pow`` or trigonometry, whose last
  digit can differ between C libraries, so Linux and macOS produce identical files.
* Every iteration is over lists or sorted keys, never over sets or unordered hashing.

The data contains no names, addresses, telephone numbers or identity numbers.
"""

from __future__ import annotations

import csv
import hashlib
import io
import json
import os
import random
import shutil
import tempfile
from bisect import bisect_left
from collections.abc import Sequence
from dataclasses import dataclass
from datetime import date, timedelta
from pathlib import Path

from .dictionary import DataDictionary

SEED = 20260630
REFERENCE_DATE = date(2026, 6, 30)
WINDOW_START = date(2024, 7, 1)
GENERATOR_VERSION = "1.0.0"
SCHEMA_VERSION = 1
TABLE_ORDER = ("branches", "customers", "accounts", "transactions", "loans")
BASE_ROWS = {"branches": 100, "customers": 10_000, "transactions": 100_000, "loans": 5_000}
DORMANT_DAYS = 180
CLOSED_QUIET_DAYS = 90
DIGITAL_CHANNELS = ("MOBILE", "ONLINE")


class Rng:
    """Thin deterministic wrapper that only uses ``random.random()``."""

    def __init__(self, seed: int):
        self._r = random.Random(seed)

    def u(self) -> float:
        return self._r.random()

    def uniform(self, low: float, high: float) -> float:
        return low + (high - low) * self.u()

    def randint(self, low: int, high: int) -> int:
        return low + int(self.u() * (high - low + 1))

    def chance(self, probability: float) -> bool:
        return self.u() < probability

    def heavy(self) -> float:
        """A right-skewed value in [0, 1): the cube of a uniform draw (multiplications only)."""
        x = self.u()
        return x * x * x

    def shuffle(self, items: list) -> None:
        for i in range(len(items) - 1, 0, -1):
            j = int(self.u() * (i + 1))
            items[i], items[j] = items[j], items[i]


class Dist:
    """A weighted choice with a precomputed cumulative table."""

    def __init__(self, pairs: Sequence[tuple[object, float]]):
        self.items = [item for item, _ in pairs]
        total = 0.0
        self.cum: list[float] = []
        for _, weight in pairs:
            total += weight
            self.cum.append(total)
        self.total = total

    def pick(self, rng: Rng):
        x = rng.u() * self.total
        return self.items[min(bisect_left(self.cum, x), len(self.items) - 1)]


def dist(**weights: float) -> Dist:
    return Dist(list(weights.items()))


def money(value: float) -> str:
    return f"{value:.2f}"


def iso(d: date) -> str:
    return d.isoformat()


# --- reference tables
REGION_DIST = Dist(
    [("North", 0.22), ("South", 0.20), ("East", 0.18), ("West", 0.17), ("Central", 0.15), ("Islands", 0.08)]
)
WORDS_FIRST = [
    "Alder", "Birch", "Cedar", "Dune", "Ember", "Fjord", "Glen", "Harbor", "Iris", "Juniper",
    "Kestrel", "Larch", "Meadow", "Nettle", "Oriel", "Pine", "Quarry", "Rowan", "Sable", "Thorn",
]  # fmt: skip
WORDS_SECOND = [
    "Bay",
    "Ridge",
    "Point",
    "Park",
    "Hill",
    "Cross",
    "Gate",
    "Field",
    "Vale",
    "Crest",
    "Mere",
    "Haven",
]
TIER_DIST = dist(TIER_1=0.25, TIER_2=0.45, TIER_3=0.30)
SIZE_BY_TIER = {
    "TIER_1": dist(SMALL=0.1, MEDIUM=0.35, LARGE=0.55),
    "TIER_2": dist(SMALL=0.25, MEDIUM=0.5, LARGE=0.25),
    "TIER_3": dist(SMALL=0.6, MEDIUM=0.3, LARGE=0.1),
}
SIZE_WEIGHT = {"SMALL": 1.0, "MEDIUM": 2.5, "LARGE": 5.0}
TIER_WEIGHT = {"TIER_1": 1.3, "TIER_2": 1.0, "TIER_3": 0.8}

SEGMENT_DIST = dist(RETAIL=0.66, AFFLUENT=0.12, SME=0.12, CORPORATE=0.03, STUDENT=0.07)
AGE_BY_SEGMENT = {
    "RETAIL": dist(
        **{"18-24": 0.08, "25-34": 0.24, "35-44": 0.25, "45-54": 0.21, "55-64": 0.14, "65+": 0.08}
    ),
    "AFFLUENT": dist(**{"25-34": 0.1, "35-44": 0.28, "45-54": 0.32, "55-64": 0.2, "65+": 0.1}),
    "SME": dist(**{"25-34": 0.12, "35-44": 0.33, "45-54": 0.33, "55-64": 0.17, "65+": 0.05}),
    "CORPORATE": dist(**{"35-44": 0.3, "45-54": 0.4, "55-64": 0.25, "65+": 0.05}),
    "STUDENT": dist(**{"18-24": 0.92, "25-34": 0.08}),
}
INCOME_BY_SEGMENT = {
    "RETAIL": dist(LOW=0.25, LOWER_MIDDLE=0.35, MIDDLE=0.28, UPPER_MIDDLE=0.10, HIGH=0.02),
    "AFFLUENT": dist(MIDDLE=0.10, UPPER_MIDDLE=0.40, HIGH=0.50),
    "SME": dist(LOWER_MIDDLE=0.15, MIDDLE=0.35, UPPER_MIDDLE=0.35, HIGH=0.15),
    "CORPORATE": dist(UPPER_MIDDLE=0.30, HIGH=0.70),
    "STUDENT": dist(LOW=0.70, LOWER_MIDDLE=0.30),
}
INCOME_FACTOR = {"LOW": 0.4, "LOWER_MIDDLE": 0.7, "MIDDLE": 1.0, "UPPER_MIDDLE": 1.8, "HIGH": 4.0}
OCCUPATION_GENERAL = dist(
    EMPLOYEE_PRIVATE=0.34, EMPLOYEE_PUBLIC=0.14, SELF_EMPLOYED=0.14, PROFESSIONAL=0.10,
    HOMEMAKER=0.08, BUSINESS_OWNER=0.05, OTHER=0.15,
)  # fmt: skip
DIGITAL_BY_AGE = {
    "18-24": dist(NONE=0.02, LOW=0.08, MEDIUM=0.30, HIGH=0.60),
    "25-34": dist(NONE=0.03, LOW=0.12, MEDIUM=0.35, HIGH=0.50),
    "35-44": dist(NONE=0.06, LOW=0.20, MEDIUM=0.40, HIGH=0.34),
    "45-54": dist(NONE=0.12, LOW=0.30, MEDIUM=0.38, HIGH=0.20),
    "55-64": dist(NONE=0.25, LOW=0.35, MEDIUM=0.30, HIGH=0.10),
    "65+": dist(NONE=0.45, LOW=0.35, MEDIUM=0.17, HIGH=0.03),
}
CUSTOMER_STATUS = dist(ACTIVE=0.88, INACTIVE=0.09, CLOSED=0.03)
ACCOUNT_COUNT = {
    "RETAIL": Dist([(1, 0.40), (2, 0.40), (3, 0.15), (4, 0.05)]),
    "AFFLUENT": Dist([(1, 0.10), (2, 0.40), (3, 0.40), (4, 0.10)]),
    "SME": Dist([(1, 0.25), (2, 0.45), (3, 0.25), (4, 0.05)]),
    "CORPORATE": Dist([(2, 0.40), (3, 0.40), (4, 0.20)]),
    "STUDENT": Dist([(1, 0.70), (2, 0.30)]),
}
PRODUCT_BY_SEGMENT = {
    "RETAIL": dist(
        **{"SAV-BASIC": 0.35, "CHK-STD": 0.30, "PAYROLL": 0.20, "SAV-PLUS": 0.10, "TD-FIXED": 0.05}
    ),
    "AFFLUENT": dist(**{"SAV-PLUS": 0.30, "CHK-PRM": 0.30, "TD-FIXED": 0.25, "PAYROLL": 0.15}),
    "SME": dist(**{"SME-OPER": 0.60, "CHK-STD": 0.20, "SAV-PLUS": 0.10, "TD-FIXED": 0.10}),
    "CORPORATE": dist(**{"SME-OPER": 0.50, "CHK-PRM": 0.30, "TD-FIXED": 0.20}),
    "STUDENT": dist(**{"STUDENT-SAV": 0.80, "SAV-BASIC": 0.20}),
}
TYPE_BY_PRODUCT = {
    "SAV-BASIC": "SAVINGS", "SAV-PLUS": "SAVINGS", "STUDENT-SAV": "SAVINGS", "CHK-STD": "CHECKING",
    "CHK-PRM": "CHECKING", "TD-FIXED": "TIME_DEPOSIT", "PAYROLL": "PAYROLL", "SME-OPER": "BUSINESS",
}  # fmt: skip
BALANCE_BASE = {
    "SAVINGS": 4000.0,
    "CHECKING": 1500.0,
    "TIME_DEPOSIT": 20000.0,
    "PAYROLL": 1200.0,
    "BUSINESS": 15000.0,
}
CHANNEL_PREF = {
    "HIGH": dist(MOBILE=0.55, ONLINE=0.35, ATM=0.06, BRANCH=0.04),
    "MEDIUM": dist(MOBILE=0.35, ONLINE=0.25, ATM=0.20, BRANCH=0.20),
    "LOW": dist(MOBILE=0.10, ONLINE=0.10, ATM=0.35, BRANCH=0.45),
    "NONE": dist(ATM=0.40, BRANCH=0.60),
}
ACTIVITY_WEIGHT = {"CHECKING": 3.0, "PAYROLL": 3.5, "SAVINGS": 1.0, "TIME_DEPOSIT": 0.15, "BUSINESS": 5.0}
TXN_TYPES = {
    "CHECKING": dist(PAYMENT=0.20, CARD_PURCHASE=0.28, WITHDRAWAL=0.10, DEPOSIT=0.08, TRANSFER_OUT=0.12, TRANSFER_IN=0.10, FEE=0.04, SALARY=0.08),
    "SAVINGS": dist(DEPOSIT=0.30, WITHDRAWAL=0.15, TRANSFER_IN=0.15, TRANSFER_OUT=0.15, INTEREST=0.20, FEE=0.02, SALARY=0.03),
    "TIME_DEPOSIT": dist(INTEREST=0.60, DEPOSIT=0.20, WITHDRAWAL=0.10, FEE=0.02, TRANSFER_OUT=0.08),
    "PAYROLL": dist(SALARY=0.25, CARD_PURCHASE=0.25, PAYMENT=0.20, WITHDRAWAL=0.12, TRANSFER_OUT=0.10, FEE=0.03, TRANSFER_IN=0.05),
    "BUSINESS": dist(DEPOSIT=0.20, TRANSFER_IN=0.20, TRANSFER_OUT=0.20, PAYMENT=0.25, WITHDRAWAL=0.05, FEE=0.05, CARD_PURCHASE=0.05),
}  # fmt: skip
AMOUNT_BASE = {
    "DEPOSIT": 800.0, "WITHDRAWAL": 300.0, "TRANSFER_IN": 700.0, "TRANSFER_OUT": 600.0, "PAYMENT": 250.0,
    "CARD_PURCHASE": 60.0, "FEE": 5.0, "INTEREST": 15.0, "SALARY": 2500.0,
}  # fmt: skip
TYPE_SCALE = {"BUSINESS": 6.0, "TIME_DEPOSIT": 10.0, "CHECKING": 1.0, "SAVINGS": 1.0, "PAYROLL": 1.0}
MERCHANT_CARD = dist(GROCERY=0.30, FUEL=0.10, DINING=0.15, RETAIL=0.20, UTILITIES=0.03, TRAVEL=0.08, HEALTHCARE=0.05, EDUCATION=0.03, ENTERTAINMENT=0.06)  # fmt: skip
MERCHANT_PAYMENT = dist(UTILITIES=0.40, EDUCATION=0.10, HEALTHCARE=0.10, RETAIL=0.10, ENTERTAINMENT=0.05, TRAVEL=0.05, GROCERY=0.10, FUEL=0.10)  # fmt: skip
STATUS_DIST = dist(COMPLETED=0.965, PENDING=0.012, FAILED=0.018, REVERSED=0.005)
MONTH_SEASON = {
    1: 1.05,
    2: 0.90,
    3: 1.00,
    4: 0.98,
    5: 1.02,
    6: 1.00,
    7: 0.97,
    8: 1.00,
    9: 1.00,
    10: 1.03,
    11: 1.10,
    12: 1.30,
}
LOAN_PROPENSITY = {"RETAIL": 0.38, "AFFLUENT": 0.55, "SME": 0.75, "CORPORATE": 0.90, "STUDENT": 0.08}
LOAN_PRODUCT = {
    "RETAIL": dist(
        **{"LOAN-PERSONAL": 0.35, "LOAN-AUTO": 0.25, "LOAN-HOME": 0.25, "LOAN-EDU": 0.05, "LOAN-SME": 0.10}
    ),
    "AFFLUENT": dist(**{"LOAN-HOME": 0.45, "LOAN-AUTO": 0.25, "LOAN-PERSONAL": 0.25, "LOAN-EDU": 0.05}),
    "SME": dist(**{"LOAN-SME": 0.80, "LOAN-PERSONAL": 0.10, "LOAN-AUTO": 0.10}),
    "CORPORATE": dist(**{"LOAN-SME": 0.90, "LOAN-AUTO": 0.10}),
    "STUDENT": dist(**{"LOAN-EDU": 0.70, "LOAN-PERSONAL": 0.30}),
}
LOAN_TERMS = {
    "LOAN-PERSONAL": (12, 60),
    "LOAN-AUTO": (24, 72),
    "LOAN-HOME": (120, 300),
    "LOAN-SME": (12, 84),
    "LOAN-EDU": (24, 96),
}
LOAN_PRINCIPAL = {
    "LOAN-PERSONAL": (2000.0, 30000.0), "LOAN-AUTO": (8000.0, 60000.0), "LOAN-HOME": (40000.0, 400000.0),
    "LOAN-SME": (10000.0, 500000.0), "LOAN-EDU": (3000.0, 40000.0),
}  # fmt: skip
LOAN_PRODUCT_RISK = {
    "LOAN-PERSONAL": 1.3,
    "LOAN-AUTO": 1.0,
    "LOAN-HOME": 0.6,
    "LOAN-SME": 1.5,
    "LOAN-EDU": 1.1,
}
REGION_RISK = {"North": 0.9, "South": 1.0, "East": 1.0, "West": 0.9, "Central": 1.1, "Islands": 1.6}


@dataclass
class GeneratedDataset:
    tables: dict[str, list[dict]]
    anomaly_incidents: list[dict]
    seed: int
    scale: float


def _day_weights() -> tuple[list[date], list[float]]:
    days, cumulative, total = [], [], 0.0
    span = (REFERENCE_DATE - WINDOW_START).days
    for offset in range(span + 1):
        d = WINDOW_START + timedelta(days=offset)
        weight = MONTH_SEASON[d.month] * (1.0 + 0.012 * (offset / 30.0))  # about 1.2% monthly growth
        weight *= 0.6 if d.weekday() >= 5 else 1.0  # quieter weekends
        weight *= 1.6 if (d.day >= 25 or d.day <= 3) else 1.0  # salary and bill peaks around month end
        total += weight
        days.append(d)
        cumulative.append(total)
    return days, cumulative


def _build_branches(rng: Rng, count: int) -> list[dict]:
    names = [f"{a} {b}" for a in WORDS_FIRST for b in WORDS_SECOND]
    rng.shuffle(names)
    rows = []
    for i in range(count):
        region = REGION_DIST.pick(rng)
        tier = TIER_DIST.pick(rng)
        size = SIZE_BY_TIER[tier].pick(rng)
        city = names[i % len(names)]
        rows.append(
            {
                "branch_id": f"SYN-BR-{i + 1:05d}",
                "branch_name": f"{city} Branch",
                "region": region,
                "province": f"{region} Province {rng.randint(1, 3)}",
                "city": city,
                "city_tier": tier,
                "size_class": size,
                "open_date": iso(
                    date(1990, 1, 1)
                    + timedelta(days=rng.randint(0, (date(2022, 12, 31) - date(1990, 1, 1)).days))
                ),
                "operational_status": "ACTIVE",
            }
        )
    order = list(range(count))
    rng.shuffle(order)
    for index in order[: max(2, count // 50)]:
        rows[index]["operational_status"] = "CLOSED"
    for index in order[max(2, count // 50) : max(2, count // 50) + max(4, count // 25)]:
        rows[index]["operational_status"] = "RENOVATION"
    return rows


def _build_customers(rng: Rng, count: int, branches: list[dict]) -> list[dict]:
    weights, total = [], 0.0
    for b in branches:
        w = (
            SIZE_WEIGHT[b["size_class"]]
            * TIER_WEIGHT[b["city_tier"]]
            * (0.2 if b["operational_status"] == "CLOSED" else 1.0)
        )
        total += w
        weights.append(total)
    branch_dist = Dist([(b, 0.0) for b in branches])
    branch_dist.cum, branch_dist.total = weights, total
    rows = []
    for i in range(count):
        branch = branch_dist.pick(rng)
        segment = SEGMENT_DIST.pick(rng)
        age = AGE_BY_SEGMENT[segment].pick(rng)
        income = INCOME_BY_SEGMENT[segment].pick(rng)
        if segment == "STUDENT":
            occupation = "STUDENT"
        elif segment == "SME":
            occupation = "BUSINESS_OWNER" if rng.chance(0.6) else "SELF_EMPLOYED"
        elif segment == "CORPORATE":
            occupation = "BUSINESS_OWNER"
        elif age == "65+" and rng.chance(0.7):
            occupation = "RETIRED"
        else:
            occupation = OCCUPATION_GENERAL.pick(rng)
        if segment == "STUDENT":
            join = date(2018, 1, 1) + timedelta(
                days=rng.randint(0, (date(2026, 5, 31) - date(2018, 1, 1)).days)
            )
        elif rng.chance(0.6):
            join = date(2020, 1, 1) + timedelta(
                days=rng.randint(0, (date(2026, 5, 31) - date(2020, 1, 1)).days)
            )
        else:
            join = date(2008, 1, 1) + timedelta(
                days=rng.randint(0, (date(2019, 12, 31) - date(2008, 1, 1)).days)
            )
        join = max(join, date.fromisoformat(branch["open_date"]))
        status = CUSTOMER_STATUS.pick(rng)
        if status == "CLOSED" and join > REFERENCE_DATE - timedelta(days=200):
            status = "INACTIVE"  # a customer cannot already be closed a few weeks after joining
        rows.append(
            {
                "customer_id": f"SYN-CUST-{i + 1:05d}",
                "home_branch_id": branch["branch_id"],
                "segment": segment,
                "region": branch["region"],
                "age_band": age,
                "income_band": income,
                "occupation_category": occupation,
                "join_date": iso(join),
                "customer_status": status,
                "digital_adoption_level": DIGITAL_BY_AGE[age].pick(rng),
            }
        )
    return rows


def _build_accounts(
    rng: Rng, customers: list[dict], branches: list[dict]
) -> tuple[list[dict], dict[str, dict]]:
    """Accounts plus a latent description of each one's activity window (used to place transactions)."""
    other = Dist([(b["branch_id"], SIZE_WEIGHT[b["size_class"]]) for b in branches])
    rows: list[dict] = []
    latent: dict[str, dict] = {}
    seq = 0
    for customer in customers:
        segment = customer["segment"]
        join = date.fromisoformat(customer["join_date"])
        for slot in range(ACCOUNT_COUNT[segment].pick(rng)):
            seq += 1
            account_id = f"SYN-ACC-{seq:05d}"
            product = PRODUCT_BY_SEGMENT[segment].pick(rng)
            account_type = TYPE_BY_PRODUCT[product]
            room = (REFERENCE_DATE - timedelta(days=1) - join).days
            open_date = join + timedelta(
                days=rng.randint(0, 60) if slot == 0 else rng.randint(0, max(room, 0))
            )
            open_date = min(open_date, REFERENCE_DATE - timedelta(days=1))
            if customer["customer_status"] == "CLOSED":
                open_date = min(open_date, REFERENCE_DATE - timedelta(days=CLOSED_QUIET_DAYS + 40))
            if customer["customer_status"] == "CLOSED":
                state = "CLOSED"
            elif customer["customer_status"] == "INACTIVE":
                state = ("DORMANT", "CLOSED", "ACTIVE")[
                    0 if rng.chance(0.7) else (1 if rng.chance(0.33) else 2)
                ]
            else:
                state = dist(ACTIVE=0.84, DORMANT=0.10, CLOSED=0.06).pick(rng)
            if state == "DORMANT" and open_date > REFERENCE_DATE - timedelta(days=DORMANT_DAYS + 20):
                state = "ACTIVE"
            if state == "CLOSED" and open_date > REFERENCE_DATE - timedelta(days=CLOSED_QUIET_DAYS + 30):
                state = "ACTIVE"
            low = max(open_date, REFERENCE_DATE - timedelta(days=540))
            if state == "DORMANT":
                end = low + timedelta(
                    days=rng.randint(
                        0, max((REFERENCE_DATE - timedelta(days=DORMANT_DAYS + 1) - low).days, 0)
                    )
                )
            elif state == "CLOSED":
                end = low + timedelta(
                    days=rng.randint(
                        0, max((REFERENCE_DATE - timedelta(days=CLOSED_QUIET_DAYS + 1) - low).days, 0)
                    )
                )
            else:
                end = REFERENCE_DATE
            branch_id = customer["home_branch_id"] if rng.chance(0.85) else other.pick(rng)
            income = INCOME_FACTOR[customer["income_band"]]
            segment_factor = {"CORPORATE": 6.0, "SME": 2.0}.get(segment, 1.0)
            balance = BALANCE_BASE[account_type] * income * segment_factor * (0.1 + 3.9 * rng.heavy())
            if state == "DORMANT":
                balance *= 0.5
            if state == "CLOSED":
                balance = 0.0
            average = 0.0 if state == "CLOSED" else balance * rng.uniform(0.6, 1.4)
            pref = CHANNEL_PREF[customer["digital_adoption_level"]].pick(rng)
            rows.append(
                {
                    "account_id": account_id,
                    "customer_id": customer["customer_id"],
                    "branch_id": branch_id,
                    "product_code": product,
                    "account_type": account_type,
                    "open_date": iso(open_date),
                    "account_status": state,
                    "balance": money(balance),
                    "average_monthly_balance": money(average),
                    "last_activity_date": iso(open_date),  # replaced after transactions exist
                    "channel_preference": pref,
                }
            )
            weight = (
                ACTIVITY_WEIGHT[account_type] * (0.3 + 2.7 * rng.u() * rng.u()) * (1.0 + 0.4 * income / 4.0)
            )
            if customer["digital_adoption_level"] in ("HIGH", "MEDIUM"):
                weight *= 1.2
            latent[account_id] = {
                "state": state,
                "open": open_date,
                "end": end,
                "weight": weight,
                "segment": segment,
            }
    return rows, latent


def _digital_probability(preference: str, progress: float) -> float:
    base = {"MOBILE": 0.85, "ONLINE": 0.80, "ATM": 0.25, "BRANCH": 0.10}[preference]
    return min(0.97, base + 0.15 * progress)


def _channel(rng: Rng, txn_type: str, preference: str, progress: float) -> str:
    if txn_type == "CARD_PURCHASE":
        return "CARD_POS" if rng.chance(0.95) else "ONLINE"
    if txn_type in ("INTEREST", "FEE", "SALARY"):
        return "SYSTEM"
    if rng.chance(_digital_probability(preference, progress)):
        return "MOBILE" if rng.chance(0.6) else "ONLINE"
    if txn_type in ("WITHDRAWAL", "DEPOSIT") and rng.chance(0.6):
        return "ATM"
    return "BRANCH"


def _amount(rng: Rng, txn_type: str, account_type: str, income: float) -> float:
    base = AMOUNT_BASE[txn_type]
    if txn_type in ("FEE", "INTEREST"):
        return max(
            0.01, base * (0.5 + rng.u()) * (TYPE_SCALE[account_type] if txn_type == "INTEREST" else 1.0)
        )
    return max(0.01, base * TYPE_SCALE[account_type] * (0.5 + 0.5 * income) * (0.15 + 3.5 * rng.heavy()))


def _build_transactions(
    rng: Rng, accounts: list[dict], latent: dict[str, dict], customers_by_id: dict[str, dict], target: int
) -> list[dict]:
    days, cumulative = _day_weights()
    horizon = len(days) - 1
    total_weight = 0.0
    shares: list[tuple[dict, float]] = []
    for account in accounts:
        info = latent[account["account_id"]]
        start = max(info["open"], WINDOW_START)
        if start > info["end"]:
            continue
        span = (info["end"] - start).days + 1
        weight = info["weight"] * span / (horizon + 1)
        shares.append((account, weight))
        total_weight += weight
    raw = [(account, target * weight / total_weight) for account, weight in shares]
    counts = [int(value) for _, value in raw]
    order = sorted(range(len(raw)), key=lambda i: (-(raw[i][1] - counts[i]), i))
    for i in order[: max(target - sum(counts), 0)]:
        counts[i] += 1
    rows: list[dict] = []
    for (account, _), count in zip(raw, counts, strict=True):
        info = latent[account["account_id"]]
        start = max(info["open"], WINDOW_START)
        if info["state"] == "ACTIVE":
            count = max(count, 1)
        if count == 0:
            continue
        i0, i1 = (start - WINDOW_START).days, (info["end"] - WINDOW_START).days
        low = cumulative[i0 - 1] if i0 > 0 else 0.0
        high = cumulative[i1]
        picked = sorted(min(bisect_left(cumulative, low + rng.u() * (high - low)), i1) for _ in range(count))
        if info["state"] in ("DORMANT", "CLOSED"):
            picked[-1] = i1  # the final activity lands exactly on the planned last day
        elif info["state"] == "ACTIVE" and info["open"] <= REFERENCE_DATE - timedelta(days=150):
            if picked[-1] < horizon - 150:
                picked[-1] = horizon - rng.randint(0, 149)
        customer = customers_by_id[account["customer_id"]]
        income = INCOME_FACTOR[customer["income_band"]]
        for index in sorted(picked):
            txn_type = TXN_TYPES[account["account_type"]].pick(rng)
            when = days[index]
            progress = index / horizon
            category = "NONE"
            if txn_type == "CARD_PURCHASE":
                category = MERCHANT_CARD.pick(rng)
            elif txn_type == "PAYMENT":
                category = MERCHANT_PAYMENT.pick(rng)
            rows.append(
                {
                    "transaction_id": "",
                    "account_id": account["account_id"],
                    "transaction_date": iso(when),
                    "transaction_type": txn_type,
                    "channel": _channel(rng, txn_type, account["channel_preference"], progress),
                    "amount": money(_amount(rng, txn_type, account["account_type"], income)),
                    "merchant_category": category,
                    "transaction_status": STATUS_DIST.pick(rng),
                    "is_seeded_anomaly": 0,
                }
            )
    return rows


def _seed_anomalies(rng: Rng, accounts: list[dict], latent: dict[str, dict], rows: list[dict]) -> list[dict]:
    """Add deterministic unusual patterns for the Group 06 mission and return their incidents.

    * velocity_burst: 18-30 transactions on one day.
    * large_amount: one transfer or withdrawal 20-40 times the account's average for that transaction type.
      Normal amounts are bounded (a type's largest value is under 4 times the type's mean), so these stand out.
    * structuring: 5-8 transfers just below a round limit over a few days.
    """
    by_type: dict[tuple[str, str], list[float]] = {}
    count: dict[str, int] = {}
    for row in rows:
        by_type.setdefault((row["account_id"], row["transaction_type"]), []).append(float(row["amount"]))
        count[row["account_id"]] = count.get(row["account_id"], 0) + 1
    candidates = [
        a["account_id"]
        for a in accounts
        if latent[a["account_id"]]["state"] == "ACTIVE"
        and count.get(a["account_id"], 0) >= 10
        and latent[a["account_id"]]["open"] <= REFERENCE_DATE - timedelta(days=60)
    ]
    rng.shuffle(candidates)
    incidents: list[dict] = []

    def typical(account_id: str) -> float:
        values = sorted(v for (acc, _), vs in by_type.items() if acc == account_id for v in vs)
        return max(values[len(values) // 2], 5.0)

    def add(account_id: str, day: date, txn_type: str, amount: float, channel: str, incident: dict) -> None:
        rows.append(
            {
                "transaction_id": "",
                "account_id": account_id,
                "transaction_date": iso(day),
                "transaction_type": txn_type,
                "channel": channel,
                "amount": money(amount),
                "merchant_category": "NONE",
                "transaction_status": "COMPLETED",
                "is_seeded_anomaly": 1,
            }
        )
        incident["_keys"].append((account_id, iso(day), money(amount)))

    def usable_type(account_id: str, preferred: str) -> str | None:
        other = "WITHDRAWAL" if preferred == "TRANSFER_OUT" else "TRANSFER_OUT"
        return next((t for t in (preferred, other) if len(by_type.get((account_id, t), ())) >= 5), None)

    cursor = 0
    for kind, number in (("velocity_burst", 10), ("large_amount", 15), ("structuring", 8)):
        for n in range(number):
            preferred = ("TRANSFER_OUT", "WITHDRAWAL")[rng.randint(0, 1)] if kind == "large_amount" else ""
            while True:
                account_id = candidates[cursor]
                cursor += 1
                if kind != "large_amount" or usable_type(account_id, preferred):
                    break
            earliest = max(
                latent[account_id]["open"] + timedelta(days=1), REFERENCE_DATE - timedelta(days=365)
            )
            latest = REFERENCE_DATE - timedelta(days=10)
            day = earliest + timedelta(days=rng.randint(0, (latest - earliest).days))
            incident = {
                "incident_id": f"{kind}-{n + 1:02d}",
                "type": kind,
                "account_id": account_id,
                "_keys": [],
            }
            if kind == "velocity_burst":
                med = typical(account_id)
                for _ in range(rng.randint(18, 30)):
                    kinds = ("WITHDRAWAL", "TRANSFER_OUT", "PAYMENT")
                    add(
                        account_id,
                        day,
                        kinds[rng.randint(0, 2)],
                        med * rng.uniform(0.6, 1.4),
                        "ONLINE",
                        incident,
                    )
            elif kind == "large_amount":
                chosen = usable_type(account_id, preferred)
                values = by_type[(account_id, chosen)]
                mean = sum(values) / len(values)
                add(account_id, day, chosen, mean * rng.uniform(20.0, 40.0), "ONLINE", incident)
            else:
                for step in range(rng.randint(5, 8)):
                    amount = float(rng.randint(9500, 9990))
                    add(
                        account_id,
                        day + timedelta(days=step // 2),
                        "TRANSFER_OUT",
                        amount,
                        "MOBILE",
                        incident,
                    )
            incidents.append(incident)
    return incidents


def _finalize_transactions(rows: list[dict], incidents: list[dict]) -> None:
    rows.sort(key=lambda r: (r["transaction_date"], r["account_id"], r["is_seeded_anomaly"], r["amount"]))
    index: dict[tuple[str, str, str], list[str]] = {}
    for n, row in enumerate(rows, start=1):
        row["transaction_id"] = f"SYN-TXN-{n:06d}"
        if row["is_seeded_anomaly"]:
            index.setdefault((row["account_id"], row["transaction_date"], row["amount"]), []).append(
                row["transaction_id"]
            )
    for incident in incidents:
        keys = incident.pop("_keys")
        ids = sorted(index[key].pop(0) for key in keys)
        incident["transaction_ids"] = ids
        incident["first_date"] = min(key[1] for key in keys)


def _update_last_activity(accounts: list[dict], rows: list[dict]) -> None:
    last: dict[str, str] = {}
    for row in rows:
        previous = last.get(row["account_id"], "")
        if row["transaction_date"] > previous:
            last[row["account_id"]] = row["transaction_date"]
    for account in accounts:
        if account["account_id"] in last:
            account["last_activity_date"] = max(last[account["account_id"]], account["open_date"])


def _build_loans(
    rng: Rng, count: int, customers: list[dict], accounts: list[dict], branches: list[dict]
) -> list[dict]:
    accounts_of: dict[str, list[dict]] = {}
    for account in accounts:
        accounts_of.setdefault(account["customer_id"], []).append(account)
    branch_region = {b["branch_id"]: b["region"] for b in branches}
    eligible = [c for c in customers if c["customer_status"] != "CLOSED"]
    weights, total = [], 0.0
    for c in eligible:
        total += LOAN_PROPENSITY[c["segment"]] * (0.5 if c["customer_status"] == "INACTIVE" else 1.0)
        weights.append(total)
    chooser = Dist([(c, 0.0) for c in eligible])
    chooser.cum, chooser.total = weights, total
    taken: dict[str, int] = {}
    rows: list[dict] = []
    attempts = 0
    while len(rows) < count and attempts < count * 20:
        attempts += 1
        customer = chooser.pick(rng)
        if taken.get(customer["customer_id"], 0) >= 3:
            continue
        usable = [a for a in accounts_of[customer["customer_id"]] if a["account_status"] != "CLOSED"]
        if not usable:
            continue
        preferred = [a for a in usable if a["account_type"] in ("CHECKING", "SAVINGS", "PAYROLL", "BUSINESS")]
        account = (preferred or usable)[rng.randint(0, len(preferred or usable) - 1)]
        earliest = max(date.fromisoformat(customer["join_date"]), date.fromisoformat(account["open_date"]))
        latest = REFERENCE_DATE - timedelta(days=30)
        if earliest > latest:
            continue
        origination = earliest + timedelta(days=rng.randint(0, (latest - earliest).days))
        product = LOAN_PRODUCT[customer["segment"]].pick(rng)
        term_low, term_high = LOAN_TERMS[product]
        term_months = rng.randint(term_low, term_high)
        maturity = origination + timedelta(days=term_months * 30 + term_months // 2)
        low, high = LOAN_PRINCIPAL[product]
        principal = low + (high - low) * rng.u() * rng.u()
        risk = REGION_RISK[branch_region[account["branch_id"]]] * LOAN_PRODUCT_RISK[product]
        if maturity <= REFERENCE_DATE:
            if rng.chance(0.93):
                outstanding, dpd, status = 0.0, 0, "PAID_OFF"
            else:
                outstanding, dpd = principal * rng.uniform(0.15, 0.6), rng.randint(91, 365)
                status = "DEFAULTED"
        else:
            elapsed = (REFERENCE_DATE - origination).days / (maturity - origination).days
            outstanding = principal * (1.0 - 0.92 * elapsed)
            roll = rng.u()
            if roll < 0.03 * risk:
                dpd = rng.randint(90, 365)
            elif roll < 0.03 * risk + 0.05 * risk:
                dpd = rng.randint(30, 89)
            elif roll < 0.03 * risk + 0.05 * risk + 0.10:
                dpd = rng.randint(1, 29)
            else:
                dpd = 0
            status = (
                "DEFAULTED"
                if dpd >= 90
                else "DELINQUENT"
                if dpd >= 30
                else "GRACE"
                if dpd >= 1
                else "CURRENT"
            )
        if status == "PAID_OFF":
            band = "LOW"
        elif dpd >= 30:
            band = "HIGH"
        elif dpd >= 1 or product == "LOAN-SME":
            band = "MEDIUM"
        else:
            band = "LOW"
        taken[customer["customer_id"]] = taken.get(customer["customer_id"], 0) + 1
        rows.append(
            {
                "loan_id": f"SYN-LOAN-{len(rows) + 1:05d}",
                "customer_id": customer["customer_id"],
                "account_id": account["account_id"],
                "branch_id": account["branch_id"],
                "product_code": product,
                "origination_date": iso(origination),
                "maturity_date": iso(maturity),
                "principal_amount": money(principal),
                "outstanding_amount": money(min(outstanding, principal)),
                "days_past_due": dpd,
                "loan_status": status,
                "risk_band": band,
            }
        )
    return rows


def generate(seed: int = SEED, scale: float = 1.0) -> GeneratedDataset:
    """Build every table in memory. The same seed and scale always give identical rows."""
    rng = Rng(seed)
    branches = _build_branches(
        rng, max(10, round(BASE_ROWS["branches"] * (1.0 if scale >= 1.0 else max(scale, 0.1))))
    )
    customers = _build_customers(rng, max(50, round(BASE_ROWS["customers"] * scale)), branches)
    accounts, latent = _build_accounts(rng, customers, branches)
    customers_by_id = {c["customer_id"]: c for c in customers}
    target = max(200, round(BASE_ROWS["transactions"] * scale) - round(330 * scale))
    transactions = _build_transactions(rng, accounts, latent, customers_by_id, target)
    incidents = _seed_anomalies(rng, accounts, latent, transactions)
    _finalize_transactions(transactions, incidents)
    _update_last_activity(accounts, transactions)
    loans = _build_loans(rng, max(20, round(BASE_ROWS["loans"] * scale)), customers, accounts, branches)
    tables = {
        "branches": branches,
        "customers": customers,
        "accounts": accounts,
        "transactions": transactions,
        "loans": loans,
    }
    return GeneratedDataset(tables, incidents, seed, scale)


# --- serialisation
def render_csv(rows: list[dict], columns: Sequence[str]) -> bytes:
    buffer = io.StringIO(newline="")
    writer = csv.writer(buffer, lineterminator="\n")
    writer.writerow(columns)
    for row in rows:
        writer.writerow([row[c] for c in columns])
    return buffer.getvalue().encode("utf-8")


def sha256(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def render_all(dataset: GeneratedDataset, dictionary: DataDictionary | None = None) -> dict[str, bytes]:
    dictionary = dictionary or DataDictionary.load()
    return {
        f"{name}.csv": render_csv(dataset.tables[name], dictionary.tables[name].column_names)
        for name in TABLE_ORDER
    }


def build_manifests(
    dataset: GeneratedDataset, files: dict[str, bytes], dictionary: DataDictionary
) -> dict[str, dict]:
    total = sum(len(data) for data in files.values())
    dataset_manifest = {
        "dataset": "synthetic_banking_workshop",
        "schema_version": SCHEMA_VERSION,
        "generator_version": GENERATOR_VERSION,
        "seed": dataset.seed,
        "scale": dataset.scale,
        "reference_date": iso(REFERENCE_DATE),
        "history_window": {"start": iso(WINDOW_START), "end": iso(REFERENCE_DATE), "months": 24},
        "fully_synthetic": True,
        "contains_personal_data": False,
        "row_counts": {name: len(dataset.tables[name]) for name in TABLE_ORDER},
        "columns": {name: list(dictionary.tables[name].column_names) for name in TABLE_ORDER},
        "total_size_bytes": total,
        "total_size_mb": round(total / 1_000_000, 3),
        "size_limit_mb": 50,
        "determinism": "Only random() with +,-,*,/ on floats; no exp/log/pow; identical on Linux and macOS.",
    }
    checksums = {
        "algorithm": "sha256",
        "files": {name: {"sha256": sha256(data), "bytes": len(data)} for name, data in sorted(files.items())},
    }
    anomaly_manifest = {
        "purpose": (
            "Automated tests and trainer validation ONLY. "
            "Never shown in the Workshop Portal or to participants."
        ),
        "column": "transactions.is_seeded_anomaly",
        "incident_count": len(dataset.anomaly_incidents),
        "transaction_count": sum(len(i["transaction_ids"]) for i in dataset.anomaly_incidents),
        "types": sorted({i["type"] for i in dataset.anomaly_incidents}),
        "incidents": dataset.anomaly_incidents,
    }
    return {
        "dataset_manifest.json": dataset_manifest,
        "checksums.json": checksums,
        "anomaly_test_manifest.json": anomaly_manifest,
    }


def write_dataset(
    dataset: GeneratedDataset,
    output_dir: Path,
    manifest_dir: Path,
    dictionary: DataDictionary | None = None,
) -> dict[str, dict]:
    """Write CSVs and manifests. Every file is replaced atomically; nothing touches the network."""
    dictionary = dictionary or DataDictionary.load()
    files = render_all(dataset, dictionary)
    manifests = build_manifests(dataset, files, dictionary)
    rendered_manifests = {
        name: (json.dumps(body, indent=2) + "\n").encode("utf-8") for name, body in manifests.items()
    }
    for target_dir, payload in ((Path(output_dir), files), (Path(manifest_dir), rendered_manifests)):
        target_dir.mkdir(parents=True, exist_ok=True)
        staging = Path(tempfile.mkdtemp(prefix=".staging-", dir=target_dir))
        try:
            for name, data in payload.items():
                (staging / name).write_bytes(data)
            for name in payload:
                os.replace(staging / name, target_dir / name)
        finally:
            shutil.rmtree(staging, ignore_errors=True)
    return manifests


def preview(dataset: GeneratedDataset, rows_per_table: int = 3) -> dict:
    return {
        "seed": dataset.seed,
        "scale": dataset.scale,
        "row_counts": {name: len(dataset.tables[name]) for name in TABLE_ORDER},
        "anomaly_incidents": len(dataset.anomaly_incidents),
        "sample": {name: dataset.tables[name][:rows_per_table] for name in TABLE_ORDER},
    }

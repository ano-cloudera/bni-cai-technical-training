"""Deterministic assignment of about 40 participants to the ten groups.

The trainer supplies the roster at run time. Nothing here stores names or e-mail addresses in the
repository, no CAI user is created, and the output goes to the git-ignored, trainer-only
``workshop/runtime/shared/state``.
"""

from __future__ import annotations

import csv
from collections import Counter
from dataclasses import dataclass
from pathlib import Path

from bni_training.data.bundles import GROUP_IDS

REF_COLUMNS = ("participant_ref", "participant_id", "name", "email")
DEFAULT_GROUP_SIZE = 4
DEFAULT_MAX_PER_GROUP = 5


class RosterError(ValueError):
    pass


@dataclass(frozen=True)
class RosterRow:
    ref: str
    group_id: str | None = None


def read_roster(path: Path) -> list[RosterRow]:
    with Path(path).open(newline="", encoding="utf-8-sig") as handle:
        reader = csv.DictReader(handle)
        fields = [f.strip().lower() for f in (reader.fieldnames or [])]
        ref_column = next((c for c in REF_COLUMNS if c in fields), None)
        if ref_column is None:
            raise RosterError(f"The roster needs one of these columns: {', '.join(REF_COLUMNS)}")
        rows = []
        for raw in reader:
            row = {k.strip().lower(): (v or "").strip() for k, v in raw.items() if k}
            if not row.get(ref_column):
                continue
            group = row.get("group_id") or None
            rows.append(RosterRow(row[ref_column], group))
    if not rows:
        raise RosterError("The roster is empty")
    return rows


def synthetic_roster(count: int) -> list[RosterRow]:
    if not 1 <= count <= len(GROUP_IDS) * DEFAULT_MAX_PER_GROUP:
        raise RosterError(f"count must be between 1 and {len(GROUP_IDS) * DEFAULT_MAX_PER_GROUP}")
    return [RosterRow(f"participant-{i:03d}") for i in range(1, count + 1)]


def assign(
    rows: list[RosterRow],
    *,
    groups: tuple[str, ...] = GROUP_IDS,
    max_per_group: int = DEFAULT_MAX_PER_GROUP,
) -> dict[str, str]:
    """Return {participant_ref: group_id}.

    Rows with an explicit group keep it (validated). The rest are spread round-robin in sorted-reference
    order, always into the currently smallest group (lowest group id first), so 40 people give ten
    groups of four.
    """
    refs = [r.ref for r in rows]
    duplicates = sorted({r for r, n in Counter(refs).items() if n > 1})
    if duplicates:
        raise RosterError(f"Duplicate participants in the roster: {len(duplicates)}")
    if len(rows) > len(groups) * max_per_group:
        raise RosterError(f"{len(rows)} participants exceed the capacity of {len(groups) * max_per_group}")
    counts: Counter[str] = Counter()
    result: dict[str, str] = {}
    for row in rows:
        if row.group_id is not None:
            if row.group_id not in groups:
                raise RosterError(f"Unknown group in the roster: {row.group_id!r}")
            result[row.ref] = row.group_id
            counts[row.group_id] += 1
    over = {g: n for g, n in counts.items() if n > max_per_group}
    if over:
        raise RosterError(f"Group capacity of {max_per_group} exceeded: {dict(sorted(over.items()))}")
    for row in sorted((r for r in rows if r.group_id is None), key=lambda r: r.ref.casefold()):
        target = min(groups, key=lambda g: (counts[g], g))
        result[row.ref] = target
        counts[target] += 1
    return result


def summarize(assignment: dict[str, str], groups: tuple[str, ...] = GROUP_IDS) -> dict:
    counts = Counter(assignment.values())
    return {
        "participants": len(assignment),
        "groups": {g: counts.get(g, 0) for g in groups},
        "smallest_group": min(counts.get(g, 0) for g in groups),
        "largest_group": max(counts.get(g, 0) for g in groups),
    }

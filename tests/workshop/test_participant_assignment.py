from __future__ import annotations

import csv
import json
import subprocess
from collections import Counter
from pathlib import Path

import pytest

from bni_training.data.bundles import GROUP_IDS
from bni_training.workshop.roster import (
    RosterError,
    RosterRow,
    assign,
    read_roster,
    summarize,
    synthetic_roster,
)
from scripts.assign_participants import main

ROOT = Path(__file__).resolve().parents[2]


def fake_roster(path: Path, count: int, explicit: dict[str, str] | None = None) -> Path:
    """A roster of invented labels generated at test time (no names or e-mails are ever committed)."""
    explicit = explicit or {}
    with path.open("w", newline="") as handle:
        writer = csv.writer(handle)
        writer.writerow(["participant_ref", "group_id"])
        for i in range(1, count + 1):
            ref = f"Trainee {i:02d}"
            writer.writerow([ref, explicit.get(ref, "")])
    return path


def test_forty_participants_give_ten_groups_of_four() -> None:
    assignment = assign(synthetic_roster(40))
    summary = summarize(assignment)
    assert summary["participants"] == 40 and set(summary["groups"].values()) == {4}
    assert set(assignment.values()) == set(GROUP_IDS)


def test_fewer_participants_are_spread_evenly() -> None:
    summary = summarize(assign(synthetic_roster(38)))
    assert sorted(summary["groups"].values()) == [3, 3] + [4] * 8
    assert summary["smallest_group"] == 3 and summary["largest_group"] == 4


def test_assignment_is_deterministic_and_independent_of_roster_order() -> None:
    rows = synthetic_roster(40)
    assert assign(rows) == assign(rows) == assign(list(reversed(rows)))


def test_explicit_groups_are_honoured_and_the_rest_fill_the_smallest_groups() -> None:
    rows = [
        RosterRow("a", "group_03"),
        RosterRow("b", "group_03"),
        RosterRow("c"),
        RosterRow("d"),
        RosterRow("e"),
    ]
    result = assign(rows)
    assert result["a"] == result["b"] == "group_03"
    assert Counter(result.values())["group_03"] == 2 and len(set(result.values())) == 4


def test_group_capacity_is_enforced() -> None:
    rows = [RosterRow(f"p{i}", "group_01") for i in range(6)]
    with pytest.raises(RosterError, match="capacity of 5"):
        assign(rows)
    assert len(assign(rows[:5])) == 5
    with pytest.raises(RosterError, match="exceed the capacity of 50"):
        assign([RosterRow(f"p{i}") for i in range(51)])
    with pytest.raises(RosterError, match="capacity of 4"):
        assign([RosterRow(f"p{i}", "group_02") for i in range(5)], max_per_group=4)


def test_unknown_groups_and_duplicate_participants_are_rejected() -> None:
    with pytest.raises(RosterError, match="Unknown group"):
        assign([RosterRow("a", "group_11")])
    with pytest.raises(RosterError, match="Duplicate"):
        assign([RosterRow("a"), RosterRow("a")])


def test_reading_a_roster_supports_several_column_names_and_rejects_bad_files(tmp_path) -> None:
    for column in ("participant_ref", "participant_id", "name", "email"):
        path = tmp_path / f"{column}.csv"
        path.write_text(f"{column}\nx1\nx2\n")
        assert [r.ref for r in read_roster(path)] == ["x1", "x2"]
    (tmp_path / "bad.csv").write_text("colour\nred\n")
    with pytest.raises(RosterError, match="needs one of"):
        read_roster(tmp_path / "bad.csv")
    (tmp_path / "empty.csv").write_text("participant_ref\n")
    with pytest.raises(RosterError, match="empty"):
        read_roster(tmp_path / "empty.csv")


def test_the_script_defaults_to_forty_in_ten_groups_and_writes_nothing_without_apply(
    tmp_path, capsys
) -> None:
    assert main(["--runtime-dir", str(tmp_path / "rt")]) == 0
    out = json.loads(capsys.readouterr().out)
    assert out["participants"] == 40 and out["smallest_group"] == out["largest_group"] == 4
    assert "dry-run" in out["mode"] and not (tmp_path / "rt").exists()


def test_apply_writes_a_trainer_only_assignment_with_dataset_and_mission(tmp_path, capsys) -> None:
    roster = fake_roster(tmp_path / "roster.csv", 40)
    assert main(["--roster", str(roster), "--runtime-dir", str(tmp_path / "rt"), "--apply"]) == 0
    capsys.readouterr()
    target = tmp_path / "rt" / "shared" / "state" / "participant-assignments.csv"
    rows = list(csv.DictReader(target.open()))
    assert len(rows) == 40 and list(rows[0]) == ["participant_ref", "group_id", "dataset_id", "mission_id"]
    assert Counter(r["group_id"] for r in rows) == {g: 4 for g in GROUP_IDS}
    assert all(r["mission_id"] and r["dataset_id"].endswith("_bundle") for r in rows)
    assert (
        json.loads(target.with_name("participant-assignments.summary.json").read_text())["participants"] == 40
    )


def test_script_refuses_over_capacity_and_missing_rosters(tmp_path, capsys) -> None:
    roster = fake_roster(tmp_path / "r.csv", 6, {f"Trainee {i:02d}": "group_01" for i in range(1, 7)})
    assert main(["--roster", str(roster)]) == 2
    assert main(["--roster", str(tmp_path / "missing.csv")]) == 2
    assert main(["--count", "60"]) == 2
    assert "REFUSED" in capsys.readouterr().err


def test_assignment_output_is_git_ignored_and_the_example_roster_has_no_personal_data() -> None:
    ignored = subprocess.run(
        ["git", "check-ignore", "workshop/runtime/shared/state/participant-assignments.csv"],
        cwd=ROOT,
        capture_output=True,
    )
    assert ignored.returncode == 0
    example = (ROOT / "workshop/templates/roster.example.csv").read_text()
    assert "@" not in example and all(
        line.startswith("participant-") or line.startswith("participant_ref") for line in example.splitlines()
    )

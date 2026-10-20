from __future__ import annotations

import json
import os
import re

import pytest
from helpers import write_templates

from bni_training.data.bundles import GROUP_IDS, BundleCatalog
from bni_training.workshop.workspace_manager import (
    SECRET_KEY,
    SECRET_VALUE,
    WorkspaceError,
    WorkspaceManager,
    parse_env,
    sha256_file,
)

NOTEBOOKS = ("00_a.ipynb", "01_b.ipynb", "02_c.ipynb")


def kinds(actions) -> set[str]:
    return {a.kind for a in actions}


def test_a_dry_run_writes_nothing(manager, tmp_path) -> None:
    actions = manager.sync()
    assert not (tmp_path / "runtime").exists()
    assert "create_dir" in kinds(actions) and "copy_notebook" in kinds(actions)
    assert len([a for a in actions if a.kind == "copy_notebook"]) == 10 * len(NOTEBOOKS)


def test_apply_creates_the_full_hierarchy_for_all_ten_groups(manager, tmp_path) -> None:
    manager.sync(apply=True)
    root = tmp_path / "runtime"
    for sub in ("config", "state", "logs"):
        assert (root / "shared" / sub).is_dir()
    assert sorted(p.name for p in (root / "groups").iterdir()) == list(GROUP_IDS)
    for group in GROUP_IDS:
        base = root / "groups" / group
        assert sorted(p.name for p in base.iterdir()) == [
            "README.md",
            "config",
            "driver-rotation.md",
            "logs",
            "notebooks",
            "output",
            "tmp",
        ]
        assert sorted(p.name for p in (base / "notebooks").iterdir()) == sorted(NOTEBOOKS)
        assert (base / "config" / "group.env").is_file() and (
            base / "config" / "workspace-manifest.json"
        ).is_file()
    assert (root / "shared" / "state" / "workspaces.json").is_file()


def test_group_env_has_the_assigned_dataset_and_mission_and_no_secrets(manager, tmp_path) -> None:
    manager.sync(apply=True)
    catalog = BundleCatalog.load()
    for group in GROUP_IDS:
        text = (tmp_path / "runtime" / "groups" / group / "config" / "group.env").read_text()
        values = parse_env(text)
        bundle = catalog.for_group(group)
        assert values["GROUP_ID"] == group and values["DATASET_ID"] == bundle.dataset_id
        assert values["MISSION_ID"] == bundle.mission_id and values["DATA_BACKEND"] == "csv"
        assert values["GROUP_WORKSPACE"].endswith(f"groups/{group}") and values["CSV_DATA_DIR"] == "data/raw"
        assert set(values) == {
            "BNI_REPO_ROOT",
            "LAB_MODE",
            "GROUP_ID",
            "DATASET_ID",
            "MISSION_ID",
            "GROUP_WORKSPACE",
            "PARTICIPANT_MODE",
            "PARTICIPANT_REF",
            "PARTICIPANT_WORKSPACE",
            "WORKSHOP_TOPOLOGY",
            "DATA_BACKEND",
            "CSV_DATA_DIR",
        }
        assert not any(SECRET_KEY.search(k) for k in values) and not SECRET_VALUE.search(text)
        assert values["PARTICIPANT_MODE"] == "group_driver"
        assert values["PARTICIPANT_REF"] == "participant_01"


def test_the_participant_readme_names_the_group_and_the_run_order(manager, tmp_path) -> None:
    manager.sync(apply=True)
    text = (tmp_path / "runtime" / "groups" / "group_06" / "README.md").read_text()
    assert "group_06" in text and "Unusual Transaction Patterns" in text and "00 to 12" in text
    assert "trainer-only" in text.lower() and "{{" not in text


def test_group_driver_is_default_and_has_no_participant_folders(manager, tmp_path) -> None:
    manager.sync(apply=True)

    for group in GROUP_IDS:
        base = tmp_path / "runtime" / "groups" / group
        assert (base / "driver-rotation.md").is_file()
        assert not (base / "participants").exists()


def test_individual_mode_creates_four_isolated_anonymous_workspaces_per_group(
    tmp_path, templates
) -> None:
    runtime = tmp_path / "runtime"
    assignment_dir = runtime / "shared" / "state"
    assignment_dir.mkdir(parents=True)
    rows = ["trainer_ref,participant_ref,group_id,dataset_id,mission_id"]
    for group in GROUP_IDS:
        for number in range(1, 5):
            rows.append(f"runtime-only-{group}-{number},participant_{number:02d},{group},d,m")
    (assignment_dir / "participant-assignments.csv").write_text("\n".join(rows) + "\n")
    individual = WorkspaceManager(runtime, templates, participant_mode="individual_learning")

    individual.sync(apply=True)

    outputs = []
    for group in GROUP_IDS:
        base = runtime / "groups" / group
        assert not (base / "driver-rotation.md").exists()
        for number in range(1, 5):
            participant = base / "participants" / f"participant_{number:02d}"
            assert sorted(path.name for path in (participant / "notebooks").iterdir()) == sorted(
                NOTEBOOKS
            )
            assert (participant / "config" / "group.env").is_file()
            outputs.append((participant / "output").resolve())
    assert len(outputs) == len(set(outputs)) == 40
    assert individual.validate().passed, individual.validate().render()


def test_individual_mode_without_assignment_creates_no_participant_folders(
    tmp_path, templates
) -> None:
    manager = WorkspaceManager(
        tmp_path / "runtime", templates, participant_mode="individual_learning"
    )

    actions = manager.sync(apply=True)

    assert any(action.kind == "no_participant_roster" for action in actions)
    assert not list((tmp_path / "runtime" / "groups").glob("*/participants/*"))


def test_reset_and_archive_can_target_one_anonymous_participant(tmp_path, templates) -> None:
    runtime = tmp_path / "runtime"
    assignment_dir = runtime / "shared" / "state"
    assignment_dir.mkdir(parents=True)
    assignment_dir.joinpath("participant-assignments.csv").write_text(
        "trainer_ref,participant_ref,group_id,dataset_id,mission_id\n"
        "runtime-only,participant_01,group_01,d,m\n"
    )
    manager = WorkspaceManager(runtime, templates, participant_mode="individual_learning")
    manager.sync(apply=True)
    target = runtime / "groups/group_01/participants/participant_01/output/result.json"
    target.write_text("{}")

    archive = manager.archive("group_01", participant_ref="participant_01", apply=True)
    manager.reset("group_01", participant_ref="participant_01", apply=True, yes=True)

    assert archive["files"] == 1 and "participant_01" in archive["archive"]
    assert not list(target.parent.iterdir())
    assert not (runtime / "groups/group_02/participants").exists()


def test_the_manifest_records_template_checksums(manager, tmp_path, templates) -> None:
    manager.sync(apply=True)
    manifest = json.loads((tmp_path / "runtime/groups/group_03/config/workspace-manifest.json").read_text())
    assert manifest["group_id"] == "group_03" and manifest["dataset_id"] == "loan_monitoring_bundle"
    for name in NOTEBOOKS:
        entry = manifest["files"][f"notebooks/{name}"]
        assert entry["template_sha256"] == sha256_file(templates / name) == entry["installed_sha256"]


def test_the_physical_dataset_is_never_copied_and_nothing_is_a_symlink(manager, tmp_path) -> None:
    manager.sync(apply=True)
    walked = [p for p in (tmp_path / "runtime").rglob("*")]
    assert not [p for p in walked if p.suffix == ".csv"] and not [p for p in walked if p.is_symlink()]


def test_applying_twice_is_idempotent(manager, tmp_path) -> None:
    manager.sync(apply=True)
    before = {str(p): p.read_bytes() for p in (tmp_path / "runtime").rglob("*") if p.is_file()}
    second = manager.sync(apply=True)
    assert kinds(second) == {"unchanged"}
    assert {str(p): p.read_bytes() for p in (tmp_path / "runtime").rglob("*") if p.is_file()} == before


def test_edited_notebooks_are_preserved(manager, tmp_path) -> None:
    manager.sync(apply=True)
    mine = tmp_path / "runtime/groups/group_02/notebooks/01_b.ipynb"
    mine.write_text('{"edited": "by the group"}')
    actions = manager.sync(apply=True)
    assert mine.read_text() == '{"edited": "by the group"}'
    preserved = [a for a in actions if a.kind == "preserve_modified"]
    assert [(a.group_id, a.path.split("/")[-1]) for a in preserved] == [("group_02", "01_b.ipynb")]


def test_a_changed_template_refreshes_only_untouched_notebooks(manager, tmp_path, templates) -> None:
    manager.sync(apply=True)
    mine = tmp_path / "runtime/groups/group_05/notebooks/00_a.ipynb"
    mine.write_text('{"edited": true}')
    write_templates(templates, marker="v2")
    actions = manager.sync(apply=True)
    refreshed = [a for a in actions if a.kind == "refresh_notebook"]
    assert len(refreshed) == 10 * len(NOTEBOOKS) - 1
    assert mine.read_text() == '{"edited": true}'
    assert "v2" in (tmp_path / "runtime/groups/group_01/notebooks/00_a.ipynb").read_text()


def test_overwrite_needs_yes_makes_a_backup_and_replaces(manager, tmp_path) -> None:
    manager.sync(apply=True)
    mine = tmp_path / "runtime/groups/group_04/notebooks/02_c.ipynb"
    mine.write_text('{"edited": "precious"}')
    with pytest.raises(WorkspaceError, match="requires --yes"):
        manager.sync(apply=True, overwrite=True)
    assert mine.read_text() == '{"edited": "precious"}'
    actions = manager.sync(apply=True, overwrite=True, yes=True)
    assert "replace_notebook" in kinds(actions) and "precious" not in mine.read_text()
    backups = list((tmp_path / "runtime/shared/state/backups/group_04").rglob("02_c.ipynb"))
    assert len(backups) == 1 and "precious" in backups[0].read_text()


def test_a_missing_template_folder_or_no_templates_is_refused(tmp_path) -> None:
    with pytest.raises(WorkspaceError):
        WorkspaceManager(tmp_path / "rt", tmp_path / "nope").sync()
    (tmp_path / "empty").mkdir()
    with pytest.raises(WorkspaceError):
        WorkspaceManager(tmp_path / "rt", tmp_path / "empty").sync()


def test_workspace_paths_reject_unknown_groups_and_traversal(manager) -> None:
    for bad in ("group_00", "group_11", "../group_01", "group_01/../group_02", ""):
        with pytest.raises(WorkspaceError):
            manager.group_dir(bad)


# --- validation ---


def test_a_fresh_workspace_validates(manager) -> None:
    manager.sync(apply=True)
    report = manager.validate()
    assert report.passed, report.render()
    assert report.render().splitlines()[-1].startswith("RESULT: PASS")


def mutate_missing_group(root):
    import shutil

    shutil.rmtree(root / "groups" / "group_07")


def mutate_missing_notebook(root):
    (root / "groups/group_03/notebooks/01_b.ipynb").unlink()


def mutate_wrong_mission(root):
    path = root / "groups/group_02/config/group.env"
    path.write_text(path.read_text().replace("transaction_trend_analysis", "regional_comparison"))


def mutate_symlink(root):
    os.symlink(root / "groups/group_02/output", root / "groups/group_01/output/link")


def mutate_secret(root):
    path = root / "groups/group_08/config/group.env"
    path.write_text(path.read_text() + "VLLM_API_KEY=abcdefghijklmnop\n")


def mutate_csv_copy(root):
    (root / "groups/group_09/output/customers.csv").write_text("a,b\n")


def mutate_extra_group(root):
    (root / "groups/group_12").mkdir()


def mutate_missing_env(root):
    (root / "groups/group_10/config/group.env").unlink()


@pytest.mark.parametrize(
    "mutate, expected",
    [
        (mutate_missing_group, "ten valid group folders"),
        (mutate_extra_group, "ten valid group folders"),
        (mutate_missing_notebook, "all notebook templates"),
        (mutate_wrong_mission, "assigned dataset and mission"),
        (mutate_symlink, "no symlinks"),
        (mutate_secret, "secret-like"),
        (mutate_csv_copy, "not duplicated"),
        (mutate_missing_env, "group.env"),
    ],
)
def test_validation_notices_damage(manager, tmp_path, mutate, expected) -> None:
    manager.sync(apply=True)
    mutate(tmp_path / "runtime")
    report = manager.validate()
    assert not report.passed
    assert any(expected in c.name and not c.passed for c in report.checks), report.render()


def test_an_unwritable_output_folder_is_reported(manager, tmp_path) -> None:
    manager.sync(apply=True)
    output = tmp_path / "runtime/groups/group_04/output"
    output.chmod(0o500)
    try:
        if os.access(output, os.W_OK):
            pytest.skip("running with privileges that ignore directory permissions")
        assert any("writable" in c.name and not c.passed for c in manager.validate().checks)
    finally:
        output.chmod(0o700)


# --- reset ---


def seed_outputs(root) -> None:
    for group in ("group_01", "group_02"):
        (root / "groups" / group / "output" / "a.json").write_text("{}")
        (root / "groups" / group / "output" / "sub").mkdir(exist_ok=True)
        (root / "groups" / group / "output" / "sub" / "b.json").write_text("{}")
        (root / "groups" / group / "logs" / "x.log").write_text("log")
        (root / "groups" / group / "tmp" / "t").write_text("t")


def snapshot(root, *parts) -> dict:
    return {str(p): p.read_bytes() for p in (root.joinpath(*parts)).rglob("*") if p.is_file()}


def test_reset_is_a_dry_run_by_default_and_requires_yes(manager, tmp_path) -> None:
    manager.sync(apply=True)
    root = tmp_path / "runtime"
    seed_outputs(root)
    before = snapshot(root)
    actions = manager.reset("group_01")
    assert {a.kind for a in actions} == {"clear_dir"} and snapshot(root) == before
    with pytest.raises(WorkspaceError, match="requires --yes"):
        manager.reset("group_01", apply=True)
    assert snapshot(root) == before


def test_reset_clears_only_output_logs_and_tmp_of_that_group(manager, tmp_path) -> None:
    manager.sync(apply=True)
    root = tmp_path / "runtime"
    seed_outputs(root)
    other = snapshot(root, "groups", "group_02")
    shared = snapshot(root, "shared")
    config_and_notebooks = {
        k: v for k, v in snapshot(root, "groups", "group_01").items() if "/config/" in k or "/notebooks/" in k
    }
    manager.reset("group_01", apply=True, yes=True)
    base = root / "groups" / "group_01"
    for sub in ("output", "logs", "tmp"):
        assert base.joinpath(sub).is_dir() and list(base.joinpath(sub).iterdir()) == []
    assert snapshot(root, "groups", "group_02") == other and snapshot(root, "shared") == shared
    assert {
        k: v for k, v in snapshot(root, "groups", "group_01").items() if "/config/" in k or "/notebooks/" in k
    } == config_and_notebooks


def test_reset_restores_notebooks_only_when_asked_and_backs_up_edits(manager, tmp_path) -> None:
    manager.sync(apply=True)
    root = tmp_path / "runtime"
    mine = root / "groups/group_01/notebooks/00_a.ipynb"
    mine.write_text('{"edited": "keep a copy"}')
    manager.reset("group_01", apply=True, yes=True)
    assert "keep a copy" in mine.read_text(), "notebooks are untouched by default"
    manager.reset("group_01", include_notebooks=True, apply=True, yes=True)
    assert "keep a copy" not in mine.read_text()
    backups = list((root / "shared/state/backups/group_01").rglob("00_a.ipynb"))
    assert len(backups) == 1 and "keep a copy" in backups[0].read_text()


@pytest.mark.parametrize(
    "bad", ["", "group_00", "group_11", "../group_02", "group_01/../group_02", "GROUP_01", "all"]
)
def test_reset_rejects_unknown_or_unsafe_group_ids(manager, tmp_path, bad) -> None:
    manager.sync(apply=True)
    with pytest.raises(WorkspaceError):
        manager.reset(bad, apply=True, yes=True)


def test_reset_refuses_when_a_symlink_could_escape(manager, tmp_path) -> None:
    manager.sync(apply=True)
    root = tmp_path / "runtime"
    (root / "groups/group_02/output/keep.json").write_text("{}")
    os.symlink(root / "groups/group_02/output", root / "groups/group_01/output/escape")
    with pytest.raises(WorkspaceError, match="symlink"):
        manager.reset("group_01", apply=True, yes=True)
    assert (root / "groups/group_02/output/keep.json").exists()


def test_reset_of_a_group_without_a_workspace_is_refused(manager) -> None:
    with pytest.raises(WorkspaceError, match="no workspace"):
        manager.reset("group_01")


# --- archive ---


def test_archive_is_a_dry_run_by_default_and_stays_inside_the_trainer_area(manager, tmp_path) -> None:
    import zipfile

    manager.sync(apply=True)
    root = tmp_path / "runtime"
    seed_outputs(root)
    plan = manager.archive("group_01")
    assert plan["files"] == 2 and plan["archive"] is None
    done = manager.archive("group_01", apply=True)
    archive = root / "shared/state/archives" / done["archive"].split("/")[-1]
    with zipfile.ZipFile(archive) as z:
        names = z.namelist()
    assert "output/a.json" in names and "CHECKSUMS.json" in names and not any("group_02" in n for n in names)
    assert re.fullmatch(r"group_01-\d{8}T\d{6}Z\.zip", archive.name)
    assert (root / "groups/group_01/output/a.json").exists(), "archiving never deletes"

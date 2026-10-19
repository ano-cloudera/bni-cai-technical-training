from __future__ import annotations

import json
from pathlib import Path

import pytest
from helpers import write_templates

from bni_training.data.bundles import BundleCatalog
from bni_training.workshop.lab_context import LabContextError, resolve_lab_context
from bni_training.workshop.workspace_manager import WorkspaceManager

CATALOG = BundleCatalog.load()


@pytest.fixture
def runtime(tmp_path):
    """A prepared runtime (all ten workspaces) built from throwaway notebook templates."""
    root = tmp_path / "runtime"
    WorkspaceManager(root, write_templates(tmp_path / "templates")).sync(apply=True)
    return root


def env_for(runtime: Path, group: str, **extra) -> dict:
    return {"GROUP_WORKSPACE": str(runtime / "groups" / group), **extra}


def test_local_mode_defaults_to_the_first_group_with_a_throwaway_workspace() -> None:
    ctx = resolve_lab_context("local", {})
    try:
        assert (ctx.group_id, ctx.dataset_id, ctx.mission_id) == (
            "group_01",
            "customer_portfolio_bundle",
            "customer_portfolio_summary",
        )
        assert (
            ctx.workspace.name == "group_01"
            and (ctx.workspace / "output").is_dir()
            and ctx.source == "local-default"
        )
    finally:
        ctx.close()


def test_cai_mode_never_guesses_the_group_or_the_workspace() -> None:
    with pytest.raises(LabContextError, match="GROUP_ID is not set"):
        resolve_lab_context("cai", {})
    with pytest.raises(LabContextError, match="GROUP_WORKSPACE is not set"):
        resolve_lab_context("cai", {"GROUP_ID": "group_03"})


def test_group_env_supplies_the_four_values(runtime) -> None:
    ctx = resolve_lab_context(
        "cai",
        {
            "GROUP_ENV_FILE": str(runtime / "groups/group_06/config/group.env"),
            "GROUP_WORKSPACE": str(runtime / "groups/group_06"),
        },
    )
    assert (
        ctx.group_id == "group_06"
        and ctx.dataset_id == "unusual_patterns_bundle"
        and ctx.mission_id == "unusual_transaction_patterns"
    )
    assert ctx.workspace == (runtime / "groups/group_06").resolve()


def test_the_workspace_alone_is_enough_to_find_group_env(runtime) -> None:
    ctx = resolve_lab_context("cai", env_for(runtime, "group_09"))
    assert ctx.group_id == "group_09" and ctx.mission_id == "regional_comparison"


@pytest.mark.parametrize("group", [f"group_{i:02d}" for i in range(1, 11)])
def test_every_group_resolves_to_its_own_bundle(runtime, group) -> None:
    ctx = resolve_lab_context("cai", env_for(runtime, group))
    bundle = CATALOG.for_group(group)
    assert (ctx.dataset_id, ctx.mission_id, ctx.bundle.tables) == (
        bundle.dataset_id,
        bundle.mission_id,
        bundle.tables,
    )


def test_a_conflict_between_the_environment_and_group_env_is_an_error_not_an_override(runtime) -> None:
    with pytest.raises(LabContextError, match="conflicts with group.env"):
        resolve_lab_context("cai", env_for(runtime, "group_01", GROUP_ID="group_02"))


def test_a_dataset_or_mission_that_is_not_assigned_is_refused(runtime) -> None:
    other = CATALOG.for_group("group_02")
    # group.env knows the right values, so a wrong environment value is reported as a conflict
    with pytest.raises(LabContextError, match="DATASET_ID in the environment .* conflicts with group.env"):
        resolve_lab_context("cai", {**env_for(runtime, "group_01"), "DATASET_ID": other.dataset_id})
    with pytest.raises(LabContextError, match="MISSION_ID in the environment .* conflicts with group.env"):
        resolve_lab_context("cai", {**env_for(runtime, "group_01"), "MISSION_ID": other.mission_id})
    # without a group.env the assignment itself is the reference
    bare = runtime.parent / "bare" / "groups" / "group_01"
    (bare / "output").mkdir(parents=True)
    env = {"GROUP_ID": "group_01", "GROUP_WORKSPACE": str(bare)}
    with pytest.raises(LabContextError, match="not the dataset assigned"):
        resolve_lab_context("cai", {**env, "DATASET_ID": other.dataset_id})
    with pytest.raises(LabContextError, match="not the mission assigned"):
        resolve_lab_context("cai", {**env, "MISSION_ID": other.mission_id})


def test_the_workspace_must_belong_to_the_group_and_be_prepared(runtime, tmp_path) -> None:
    with pytest.raises(LabContextError, match="conflicts with group.env"):
        resolve_lab_context(
            "cai", {"GROUP_ID": "group_01", "GROUP_WORKSPACE": str(runtime / "groups/group_02")}
        )
    wrong = tmp_path / "wrong" / "groups" / "group_02"
    (wrong / "output").mkdir(parents=True)
    with pytest.raises(LabContextError, match="folder of group_01"):
        resolve_lab_context("cai", {"GROUP_ID": "group_01", "GROUP_WORKSPACE": str(wrong)})
    unprepared = tmp_path / "other" / "groups" / "group_01"
    unprepared.mkdir(parents=True)
    with pytest.raises(LabContextError, match="not prepared"):
        resolve_lab_context("cai", {"GROUP_ID": "group_01", "GROUP_WORKSPACE": str(unprepared)})
    for bad in ("group_00", "group_11", "../group_01", "GROUP_01"):
        with pytest.raises(LabContextError):
            resolve_lab_context("cai", {"GROUP_ID": bad, "GROUP_WORKSPACE": str(runtime / "groups/group_01")})


def test_an_unknown_backend_value_is_refused() -> None:
    with pytest.raises(LabContextError, match="DATA_BACKEND"):
        resolve_lab_context("local", {"DATA_BACKEND": "postgres"})


def test_outputs_land_only_in_the_resolved_groups_output_folder(runtime) -> None:
    ctx = resolve_lab_context("cai", env_for(runtime, "group_04"))
    path = ctx.write_output("x.json", "{}")
    assert path.parent == (runtime / "groups/group_04/output").resolve()
    from bni_training.workshop.group_paths import UnsafePathError

    for bad in ("../x.json", "a/b.json", ".hidden"):
        with pytest.raises(UnsafePathError):
            ctx.write_output(bad, "{}")
    assert not list((runtime / "groups/group_03/output").iterdir())


def test_individual_outputs_land_only_in_the_anonymous_participant_folder(
    tmp_path,
) -> None:
    root = tmp_path / "runtime"
    assignments = root / "shared" / "state"
    assignments.mkdir(parents=True)
    assignments.joinpath("participant-assignments.csv").write_text(
        "trainer_ref,participant_ref,group_id,dataset_id,mission_id\n"
        "runtime-only,participant_02,group_03,d,m\n"
    )
    templates = write_templates(tmp_path / "templates-individual")
    WorkspaceManager(
        root, templates, participant_mode="individual_learning"
    ).sync(apply=True)
    env_file = root / "groups/group_03/participants/participant_02/config/group.env"

    ctx = resolve_lab_context(
        "cai",
        {
            "GROUP_ENV_FILE": str(env_file),
            "GROUP_WORKSPACE": str(root / "groups/group_03"),
        },
    )
    saved = ctx.write_output("individual.json", "{}")

    expected = root / "groups/group_03/participants/participant_02/output"
    assert ctx.participant_mode == "individual_learning"
    assert saved.parent == expected.resolve()
    assert not list((root / "groups/group_03/output").iterdir())
    other_output = root / "groups/group_03/participants/participant_01/output"
    assert not other_output.exists() or not list(other_output.iterdir())


def test_the_data_tool_is_bound_to_the_groups_bundle(runtime) -> None:
    ctx = resolve_lab_context("cai", env_for(runtime, "group_02"))
    try:
        tool = ctx.data_tool()
        assert tool.bundle.group_id == "group_02" and "loans" not in tool.bundle.tables
        assert tool.query("Show transaction count by month", ctx.request())[1].row_count == 24
    finally:
        ctx.close()


def test_a_lab_saves_its_report_in_the_group_workspace_only(runtime, monkeypatch, capsys) -> None:
    import importlib.util

    spec = importlib.util.spec_from_file_location("lab04", Path("scripts/04_csv_data_access.py"))
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    monkeypatch.setenv("GROUP_WORKSPACE", str(runtime / "groups/group_07"))
    for name in ("GROUP_ID", "DATASET_ID", "MISSION_ID", "GROUP_ENV_FILE"):
        monkeypatch.delenv(name, raising=False)
    assert module.main(["--mode", "cai"]) == 0
    output = capsys.readouterr().out
    saved = sorted(p.name for p in (runtime / "groups/group_07/output").iterdir())
    assert saved == ["04_dataset_preview.json", "lab-04-cai.json"]
    assert (
        json.loads((runtime / "groups/group_07/output/lab-04-cai.json").read_text().split("\nLAB_STATUS")[0])[
            "data"
        ]["group"]["group_id"]
        == "group_07"
    )
    assert all(
        not list((runtime / "groups" / g / "output").iterdir()) for g in ("group_01", "group_02", "group_08")
    )
    assert "groups/group_07/output/lab-04-cai.json" in output

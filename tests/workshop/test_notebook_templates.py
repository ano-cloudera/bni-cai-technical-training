"""All 13 canonical notebooks execute in local mode: from the templates and from a group workspace."""

from __future__ import annotations

import os
from pathlib import Path

import pytest

nbformat = pytest.importorskip("nbformat")

from bni_training.lab_registry import canonical_labs  # noqa: E402
from bni_training.workshop.workspace_manager import WorkspaceManager  # noqa: E402
from scripts.execute_notebooks import execute, output_text  # noqa: E402

ROOT = Path(__file__).resolve().parents[2]


@pytest.fixture(autouse=True)
def quiet(monkeypatch):
    monkeypatch.setenv("CREWAI_DISABLE_TELEMETRY", "true")
    for name in (
        "GROUP_ID",
        "GROUP_WORKSPACE",
        "GROUP_ENV_FILE",
        "DATASET_ID",
        "MISSION_ID",
        "WORKSHOP_ROLE",
    ):
        monkeypatch.delenv(name, raising=False)


@pytest.mark.parametrize("lab", canonical_labs(), ids=lambda lab: lab.id)
def test_template_executes_locally_through_the_notebook_executor(lab, tmp_path) -> None:
    result = execute(lab.notebook_path, tmp_path, "local", 600)
    assert result["result"] == "PASS", result
    assert result["lab_status"] in {"PASS", "SKIPPED"} and result["failed"] == 0 and result["problems"] == []


def test_a_notebook_runs_from_a_generated_group_workspace_and_writes_only_there(
    tmp_path, monkeypatch
) -> None:
    runtime = tmp_path / "runtime"  # outside the repository: the repo root comes from config/group.env
    WorkspaceManager(runtime).sync(apply=True)
    monkeypatch.delenv("BNI_REPO_ROOT", raising=False)
    assert f"BNI_REPO_ROOT={ROOT.as_posix()}" in (runtime / "groups/group_03/config/group.env").read_text()
    notebook = runtime / "groups" / "group_03" / "notebooks" / "04_csv_data_access.ipynb"
    assert notebook.is_file()
    result = execute(notebook, tmp_path / "executed", "local", 600)
    assert result["result"] == "PASS", result
    saved = sorted(p.name for p in (runtime / "groups/group_03/output").iterdir())
    assert saved == ["04_dataset_preview.json"]
    others = [
        p
        for g in range(1, 11)
        if g != 3
        for p in (runtime / "groups" / f"group_{g:02d}" / "output").iterdir()
    ]
    assert others == [], "no other group's folder was touched"
    preview = (runtime / "groups/group_03/output/04_dataset_preview.json").read_text()
    assert '"loans"' in preview and '"customers"' in preview and '"transactions"' not in preview


def test_a_notebook_runs_from_an_individual_workspace_and_writes_only_there(tmp_path, monkeypatch) -> None:
    runtime = tmp_path / "runtime"
    assignment_dir = runtime / "shared" / "state"
    assignment_dir.mkdir(parents=True)
    assignment_dir.joinpath("participant-assignments.csv").write_text(
        "trainer_ref,participant_ref,group_id,dataset_id,mission_id\n"
        "runtime-only,participant_03,group_04,d,m\n"
    )
    WorkspaceManager(runtime, participant_mode="individual_learning").sync(apply=True)
    participant = runtime / "groups/group_04/participants/participant_03"
    monkeypatch.delenv("BNI_REPO_ROOT", raising=False)
    monkeypatch.setenv("GROUP_ENV_FILE", str(participant / "config/group.env"))
    monkeypatch.setenv("GROUP_WORKSPACE", str(runtime / "groups/group_04"))
    notebook = participant / "notebooks/04_csv_data_access.ipynb"

    result = execute(notebook, tmp_path / "executed", "local", 600)

    assert result["result"] == "PASS", result
    assert sorted(path.name for path in (participant / "output").iterdir()) == ["04_dataset_preview.json"]
    assert not list((runtime / "groups/group_04/output").iterdir())


def test_every_generated_group_copy_matches_its_template(tmp_path) -> None:
    runtime = tmp_path / "runtime"
    WorkspaceManager(runtime).sync(apply=True)
    for lab in canonical_labs():
        template = lab.notebook_path.read_bytes()
        for group in range(1, 11):
            assert (
                runtime / "groups" / f"group_{group:02d}" / "notebooks" / lab.notebook_path.name
            ).read_bytes() == template
    assert not [p for p in runtime.rglob("*.csv")], "the dataset is never copied"
    assert os.listdir(runtime / "groups") and len(os.listdir(runtime / "groups")) == 10


def test_lab_08_execution_exposes_tool_evidence_and_both_agent_outputs(tmp_path) -> None:
    notebook = ROOT / "notebooks/templates/08_agent_workflow.ipynb"

    result = execute(notebook, tmp_path, "local", 600)

    assert result["result"] == "PASS", result
    executed = nbformat.read(tmp_path / notebook.name, as_version=4)
    rendered_output = "\n".join(output_text(cell) for cell in executed.cells if cell.cell_type == "code")
    for label in (
        "User question:",
        "Generated SQL:",
        "Returned rows:",
        "Analyst output:",
        "Reviewer output:",
        "'tool_executed': True",
        "'evidence_passed_to_both_agents': True",
    ):
        assert label in rendered_output


def test_every_notebook_finds_the_repository_from_the_workspace_group_env() -> None:
    """A workspace outside the repository used to fail with StopIteration in the setup cell."""
    for source in sorted((ROOT / "notebooks/authoring").glob("*.py")):
        text = source.read_text()
        assert "def _repo_root()" in text and 'saved.get("BNI_REPO_ROOT")' in text, source.name
        assert "StopIteration" not in text, source.name


def test_a_trainer_notebook_also_runs_from_a_workspace_outside_the_repository(tmp_path, monkeypatch) -> None:
    runtime = tmp_path / "runtime"
    WorkspaceManager(runtime).sync(apply=True)
    monkeypatch.delenv("BNI_REPO_ROOT", raising=False)
    notebook = runtime / "groups/group_02/notebooks/01_model_artifact_validation.ipynb"
    result = execute(notebook, tmp_path / "executed", "local", 600)
    assert result["result"] == "PASS", result


def test_every_notebook_loads_its_group_env_before_choosing_the_mode() -> None:
    """A generated workspace stores LAB_MODE in config/group.env; a notebook that only reads the environment runs the mock."""
    for source in sorted((ROOT / "notebooks/authoring").glob("*.py")):
        text = source.read_text(encoding="utf-8")
        assert "load_group_env(" in text, source.name
        assert text.index("load_group_env(") < text.index('os.getenv("LAB_MODE"'), source.name

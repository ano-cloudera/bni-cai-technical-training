from __future__ import annotations

import json
from pathlib import Path

import pytest

from bni_training.workshop.notebook_support import lab_status, participant_settings
from scripts.build_notebooks import AuthoringError, parse_percent_source

ROOT = Path(__file__).resolve().parents[2]


def test_percent_source_becomes_stripped_notebook_cells(tmp_path: Path) -> None:
    source = tmp_path / "sample.py"
    source.write_text(
        "# %% [markdown]\n"
        "# # Teaching title\n"
        "\n"
        "# What the next cell does and what output to expect.\n"
        "# %%\n"
        "# Show a visible value.\n"
        "value = 3\n"
        "print(value)\n",
        encoding="utf-8",
    )

    notebook = parse_percent_source(source)

    assert [cell["cell_type"] for cell in notebook["cells"]] == ["markdown", "code"]
    assert notebook["cells"][0]["source"] == [
        "# Teaching title\n",
        "\n",
        "What the next cell does and what output to expect.\n",
    ]
    assert notebook["cells"][1]["execution_count"] is None
    assert notebook["cells"][1]["outputs"] == []
    assert "value = 3" in "".join(notebook["cells"][1]["source"])


def test_percent_source_requires_explicit_cell_markers(tmp_path: Path) -> None:
    source = tmp_path / "broken.py"
    source.write_text("print('hidden preamble')\n# %%\nprint('cell')\n", encoding="utf-8")

    with pytest.raises(AuthoringError, match="before the first cell marker"):
        parse_percent_source(source)


def test_participant_settings_default_to_group_driver() -> None:
    settings = participant_settings({})

    assert settings.mode == "group_driver"
    assert settings.participant_ref == "participant_01"


def test_participant_settings_reject_unknown_modes_and_identifiers() -> None:
    with pytest.raises(ValueError, match="PARTICIPANT_MODE"):
        participant_settings({"PARTICIPANT_MODE": "shared"})
    with pytest.raises(ValueError, match="PARTICIPANT_REF"):
        participant_settings(
            {"PARTICIPANT_MODE": "individual_learning", "PARTICIPANT_REF": "../person"}
        )


def test_lab_status_has_the_executor_contract(capsys: pytest.CaptureFixture[str]) -> None:
    lab_status("03", "local", passed=4, skipped=1)

    assert capsys.readouterr().out.strip() == (
        "LAB_STATUS: lab=03 mode=local status=PASS passed=4 skipped=1 failed=0"
    )


@pytest.mark.parametrize(
    ("lab_id", "key", "visible_artifacts", "trainer_only"),
    [
        ("00", "environment_validation", ("PARTICIPANT_MODE", "GROUP_ID", "WORKSHOP_PORTAL_URL"), False),
        ("01", "model_artifact_validation", ("MODEL_PATH", "directory_manifest", "config.json"), True),
        ("02", "vllm_deployment", ("build_vllm_command", "/v1/models", "max_tokens"), True),
        ("03", "llm_api_testing", ("payload", "max_tokens", "429"), False),
        ("04", "csv_data_access", ("run_sql", "SELECT", "RestrictedTableError"), False),
        ("05", "semantic_layer", ("SemanticModel", ".plan(", "planned.sql"), False),
        ("06", "crewai_tools", ("@tool", "Agent(", "Task(", "Crew("), False),
        ("07", "qdrant_rag", ("HashingEmbedder", "group_filter_json", "search_group"), False),
        ("08", "agent_workflow", ("analyst_agent", "reviewer_agent", "Process.sequential"), False),
        (
            "09",
            "phoenix_monitoring",
            ("PHOENIX_COLLECTOR_ENDPOINT", "safe_trace_attributes", "participant_ref"),
            False,
        ),
        (
            "10",
            "litellm_routing",
            ("LITELLM_BASE_URL", "qwen-primary", "training-fallback"),
            False,
        ),
        (
            "11",
            "guardrails",
            ("validate_input", "validate_sql", "validate_grounded_answer"),
            False,
        ),
    ],
)
def test_migrated_notebooks_are_authored_as_direct_lessons(
    lab_id: str, key: str, visible_artifacts: tuple[str, ...], trainer_only: bool
) -> None:
    source = ROOT / "notebooks" / "authoring" / f"{lab_id}_{key}.py"
    notebook = ROOT / "notebooks" / "templates" / f"{lab_id}_{key}.ipynb"

    assert source.is_file()
    document = json.loads(notebook.read_text(encoding="utf-8"))
    rendered = "\n".join("".join(cell["source"]) for cell in document["cells"])
    for heading in (
        "Learning objectives",
        "Architecture context",
        "Prerequisites",
        "Configuration validation",
        "Step-by-step implementation",
        "Hands-on exercise",
        "Expected result",
        "Common errors",
        "Completion checkpoint",
        "Reference implementation",
        "Cleanup",
    ):
        assert heading in rendered
    assert ("TRAINER ONLY" in rendered) is trainer_only
    assert all(artifact in rendered for artifact in visible_artifacts)
    assert "get_lab(" not in rendered
    assert "load_script_module" not in rendered
    assert "module.main(" not in rendered
    if not trainer_only:
        assert "# EXERCISE" in rendered


def test_lab_08_explicitly_executes_and_hands_off_group_scoped_evidence() -> None:
    source = (
        ROOT / "notebooks" / "authoring" / "08_agent_workflow.py"
    ).read_text(encoding="utf-8")

    assert "bound_tool = context.data_tool().bind(context.request())" in source
    assert "evidence_sql, evidence_result = bound_tool.query(question)" in source
    assert 'print("Generated SQL:", evidence_sql)' in source
    assert 'print("Returned rows:", evidence_rows)' in source
    assert "evidence_sql in analyst_task.description" in source
    assert "evidence_sql in reviewer_task.description" in source
    assert "evidence_request_count = sum(evidence_sql in text for text in request_texts)" in source
    assert "assert evidence_request_count >= 2" in source
    assert "recording_tool.calls" not in source

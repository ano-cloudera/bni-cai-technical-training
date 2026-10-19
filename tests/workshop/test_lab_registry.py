from __future__ import annotations

import json
import re
import subprocess
import sys
from pathlib import Path

import pytest

from bni_training.lab_registry import (
    RegistryError,
    canonical_labs,
    delegate,
    get_lab,
    legacy_only_scripts,
    legacy_wrappers,
)

ROOT = Path(__file__).resolve().parents[2]
EXPECTED = {
    "00": ("Environment Validation", {"trainer", "participant"}, False, "00_environment_validation"),
    "01": ("Model Artifact Validation", {"trainer"}, True, "01_model_artifact_validation"),
    "02": ("vLLM Deployment", {"trainer"}, True, "02_vllm_deployment"),
    "03": ("LLM API Testing", {"participant"}, False, "03_llm_api_testing"),
    "04": ("CSV Data Access", {"participant"}, False, "04_csv_data_access"),
    "05": ("Semantic Layer", {"participant"}, False, "05_semantic_layer"),
    "06": ("CrewAI Tools", {"participant"}, False, "06_crewai_tools"),
    "07": ("Qdrant RAG", {"participant"}, False, "07_qdrant_rag"),
    "08": ("Multi-Agent Workflow", {"participant"}, False, "08_agent_workflow"),
    "09": ("Phoenix Monitoring", {"participant", "trainer"}, False, "09_phoenix_monitoring"),
    "10": ("LiteLLM Routing", {"participant", "trainer"}, False, "10_litellm_routing"),
    "11": ("Input and Output Guardrails", {"participant"}, False, "11_guardrails"),
    "12": ("End-to-End Workshop Portal", {"participant"}, False, "12_end_to_end_portal"),
}


def test_all_thirteen_canonical_labs_are_registered_in_order() -> None:
    labs = canonical_labs()
    assert [lab.id for lab in labs] == list(EXPECTED)
    for lab in labs:
        title, audience, trainer_only, stem = EXPECTED[lab.id]
        assert (lab.title, set(lab.audience), lab.trainer_only) == (title, audience, trainer_only), lab.id
        assert lab.script == f"scripts/{stem}.py" and lab.notebook == f"notebooks/templates/{stem}.ipynb"
        assert lab.script_path.is_file() and lab.notebook_path.is_file()
        assert lab.purpose and lab.theory and lab.expected


def test_only_the_model_labs_are_trainer_only() -> None:
    assert [lab.id for lab in canonical_labs() if lab.trainer_only] == ["01", "02"]
    assert [lab.id for lab in canonical_labs() if lab.participant_lab] == [
        f"{i:02d}" for i in (0, 3, 4, 5, 6, 7, 8, 9, 10, 11, 12)
    ]


def test_the_notebook_folder_holds_exactly_the_thirteen_templates() -> None:
    found = sorted(p.name for p in (ROOT / "notebooks" / "templates").glob("*.ipynb"))
    assert found == sorted(f"{stem}.ipynb" for *_rest, stem in EXPECTED.values())


def test_get_lab_accepts_id_or_key_and_rejects_unknown_labs() -> None:
    assert get_lab("07") is get_lab("qdrant_rag") or get_lab("07") == get_lab("qdrant_rag")
    with pytest.raises(RegistryError):
        get_lab("13")


def test_rc1_scripts_are_either_thin_wrappers_or_kept_legacy_scripts() -> None:
    wrappers, legacy = legacy_wrappers(), legacy_only_scripts()
    assert sorted(wrappers) == [
        "scripts/00_environment_check.py", "scripts/01_model_download.py", "scripts/02_vllm_server.py",
        "scripts/06_semantic_layer.py", "scripts/07_rag_with_qdrant.py", "scripts/08_multi_agent_workflow.py",
        "scripts/09_phoenix_observability.py", "scripts/11_llm_guardrails.py",
    ]  # fmt: skip
    assert sorted(legacy) == [
        "scripts/04_crewai_fundamentals.py",
        "scripts/05_impala_ask_data.py",
        "scripts/12_agent_studio_client.py",
    ]  # fmt: skip
    with pytest.raises(RegistryError):
        delegate("scripts/03_llm_api_testing.py")


def test_no_participant_lab_script_refers_to_the_rc1_placeholder_dataset() -> None:
    for lab in canonical_labs():
        source = lab.script_path.read_text()
        assert (
            "data/csv" not in source and "credit_portfolio" not in source and "build_settings" not in source
        ), lab.id


def test_the_builder_output_is_in_sync_with_the_registry() -> None:
    result = subprocess.run(
        [sys.executable, "scripts/build_notebooks.py", "--check"],
        cwd=ROOT, capture_output=True, text=True, env={"PYTHONPATH": "src:.", "PATH": "/usr/bin:/bin"},
    )  # fmt: skip
    assert result.returncode == 0, result.stdout + result.stderr


@pytest.mark.parametrize("lab", canonical_labs(), ids=lambda lab: lab.id)
def test_every_notebook_has_theory_checks_runnable_cells_and_expected_outcomes(lab) -> None:
    doc = json.loads(lab.notebook_path.read_text())
    kinds = [c["cell_type"] for c in doc["cells"]]
    text = "\n".join("".join(c["source"]) for c in doc["cells"])
    assert kinds.count("code") >= 4 and kinds.count("markdown") >= 5
    headings = (
        "## Learning objectives",
        "## Architecture context",
        "## Expected result",
        "## Completion checkpoint",
    )
    for heading in headings:
        assert heading in text, (lab.id, heading)
    assert (
        "TRAINER ONLY" in text
        if lab.trainer_only
        else "TRAINER ONLY" not in text.replace("TRAINER ONLY' if lab.trainer_only", "")
    )
    assert not re.search(r"module\.main\(|get_lab\(|load_script_module", text)
    assert "data/csv" not in text and "credit_portfolio" not in text

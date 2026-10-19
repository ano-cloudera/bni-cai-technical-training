"""Lab 03: authoring source and template stay in sync, the payload shows why thinking is off."""

from __future__ import annotations

import json
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
AUTHORING = ROOT / "notebooks/authoring/03_llm_api_testing.py"
TEMPLATE = ROOT / "notebooks/templates/03_llm_api_testing.ipynb"


def code_cells() -> list[str]:
    cells = json.loads(TEMPLATE.read_text())["cells"]
    return ["".join(c["source"]) for c in cells if c["cell_type"] == "code"]


def test_authoring_source_and_generated_template_are_synchronized() -> None:
    result = subprocess.run(
        [sys.executable, str(ROOT / "scripts/build_notebooks.py"), "--check"],
        capture_output=True,
        text=True,
        cwd=ROOT,
        env={"PYTHONPATH": f"{ROOT / 'src'}:{ROOT}", "PATH": "/usr/bin:/bin"},
    )
    assert result.returncode == 0, result.stdout + result.stderr


def test_the_request_payload_and_the_reason_for_disabling_thinking_are_visible() -> None:
    text = "\n".join(code_cells())
    assert 'model_request_extras(payload["model"])' in text and "payload.update(extras)" in text
    assert "thinks" in text and "internal reasoning" in text
    assert "extra_body=extras" in text  # streaming and the exercise reuse the same extras
    assert "visible_answer(" in text


def test_the_mock_server_is_started_only_in_local_mode() -> None:
    text = "\n".join(code_cells())
    assert 'MockOpenAIServer(fail_first=1).start() if LAB_MODE == "local" else None' in text
    assert text.count("MockOpenAIServer(") == 1


def test_the_exercise_call_uses_the_same_extras() -> None:
    text = "\n".join(code_cells())
    assert "client.chat(exercise_messages" in text  # the client already carries extra_body=extras

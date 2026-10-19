from __future__ import annotations

import json
from pathlib import Path

import pytest

from scripts.strip_notebooks import clean, findings

NOTEBOOKS = sorted([*Path("notebooks").glob("*.ipynb"), *Path("notebooks/templates").glob("*.ipynb")])


def test_there_are_thirteen_rc1_notebooks_and_thirteen_canonical_templates() -> None:
    assert len(list(Path("notebooks").glob("*.ipynb"))) == 13
    assert len(list(Path("notebooks/templates").glob("*.ipynb"))) == 13


@pytest.mark.parametrize("path", NOTEBOOKS, ids=lambda p: f"{p.parent.name}/{p.name}")
def test_notebook_is_stripped_and_free_of_local_values(path: Path) -> None:
    original = path.read_text()
    doc = json.loads(original)
    assert json.dumps(clean(json.loads(original)), indent=1) + "\n" == original, (
        "run scripts/strip_notebooks.py"
    )
    assert findings(doc) == []
    for cell in doc["cells"]:
        assert cell["metadata"] == {}
        if cell["cell_type"] == "code":
            assert cell["outputs"] == [] and cell["execution_count"] is None
    assert set(doc["metadata"]) <= {"kernelspec", "language_info"}


DIRTY_PATH = "/" + "Users" + "/someone/x"  # assembled at runtime so this file stays clean


def test_stripper_detects_paths_timestamps_endpoints_and_tokens() -> None:
    dirty = {
        "metadata": {"widgets": {}, "kernelspec": {}},
        "cells": [
            {
                "cell_type": "code",
                "metadata": {"execution": {"iopub.execute_input": "2026-10-18T12:00:00"}},
                "source": [f"p='{DIRTY_PATH}'; u='http://10.1.2.3:8000'; k='Bearer abcdefgh12345678'"],
                "outputs": [{"output_type": "stream", "text": "x"}],
                "execution_count": 3,
            }
        ],
    }
    assert {"local-path", "endpoint", "token", "timestamp"} <= set(findings(dirty))
    fixed = clean(dirty)
    assert fixed["cells"][0]["outputs"] == [] and fixed["cells"][0]["execution_count"] is None
    assert fixed["cells"][0]["metadata"] == {} and "widgets" not in fixed["metadata"]

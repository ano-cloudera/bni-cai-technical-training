"""The demo notebooks in notebooks/demos/ are generated, stripped, and kept apart from the 13 labs."""

import ast
import json
from pathlib import Path

import pytest

from scripts.build_demo_notebooks import main as build_demos
from scripts.strip_notebooks import clean, findings

DEMOS = sorted(Path("notebooks/demos").glob("*.ipynb"))


def test_the_committed_demo_notebooks_match_their_sources() -> None:
    assert build_demos(["--check"]) == 0, "run scripts/build_demo_notebooks.py"


def test_demos_are_not_counted_as_labs() -> None:
    assert not list(Path("notebooks").glob("*.ipynb"))
    assert len(list(Path("notebooks/templates").glob("*.ipynb"))) == 13


@pytest.mark.parametrize("path", DEMOS, ids=lambda p: p.name)
def test_demo_is_stripped_clean_and_valid_python(path: Path) -> None:
    original = path.read_text()
    document = json.loads(original)
    assert json.dumps(clean(json.loads(original)), indent=1) + "\n" == original
    assert findings(document) == []
    for cell in document["cells"]:
        if cell["cell_type"] == "code":
            assert cell["outputs"] == [] and cell["execution_count"] is None
            ast.parse("".join(cell["source"]))


def test_the_download_demo_never_prints_the_token_and_names_a_demo_folder() -> None:
    source = Path("notebooks/demos/hf_model_download.py").read_text()
    for call in ast.walk(ast.parse("\n".join(line for line in source.splitlines() if not line.startswith("#")))):
        if isinstance(call, ast.Call) and getattr(call.func, "id", "") == "print":
            text = ast.unparse(call).replace("bool(HF_TOKEN)", "")
            assert "HF_TOKEN" not in text, "the token must never be printed"
    assert "hf-demo-models" in source and "TARGET.parent == DEMO_ROOT" in source

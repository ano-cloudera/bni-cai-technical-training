from __future__ import annotations

import pytest

nbformat = pytest.importorskip("nbformat")
from nbformat.v4 import new_code_cell, new_notebook  # noqa: E402

from scripts.execute_notebooks import verify  # noqa: E402


def executed(source: str, text: str | None):
    cell = new_code_cell(source)
    cell.execution_count = 1
    cell.outputs = [nbformat.v4.new_output("stream", name="stdout", text=text)] if text else []
    return cell


STATUS = "LAB_STATUS: lab=07 mode=local status=PASS passed=3 skipped=1 failed=0"


def test_verify_accepts_one_status_line() -> None:
    result = verify(new_notebook(cells=[executed("print(1)", STATUS)]), "ok.ipynb")
    assert result["result"] == "PASS" and result["skipped"] == 1


@pytest.mark.parametrize(
    "cell, expected",
    [
        (executed("print(1)", None), "expected exactly one LAB_STATUS"),
        (executed("print(1)", STATUS.replace("PASS", "FAIL", 1)), "status=FAIL"),
        (executed("# TODO finish this\nprint(1)", STATUS), "unfinished-work marker"),
        (executed("raise NotImplementedError", STATUS), "unfinished-work marker"),
    ],
)
def test_verify_rejects_silent_or_unfinished_notebooks(cell, expected: str) -> None:
    result = verify(new_notebook(cells=[cell]), "bad.ipynb")
    assert result["result"] == "FAIL"
    assert any(expected in problem for problem in result["problems"]), result["problems"]


def test_verify_rejects_unexecuted_code_cells() -> None:
    cell = new_code_cell("print(1)")
    result = verify(new_notebook(cells=[cell, executed("print(2)", STATUS)]), "skipped-cell.ipynb")
    assert any("was not executed" in problem for problem in result["problems"])

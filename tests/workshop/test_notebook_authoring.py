from __future__ import annotations

from pathlib import Path

import pytest

from bni_training.workshop.notebook_support import lab_status, participant_settings
from scripts.build_notebooks import AuthoringError, parse_percent_source


def test_percent_source_becomes_stripped_notebook_cells(tmp_path: Path) -> None:
    source = tmp_path / "sample.py"
    source.write_text(
        "# %% [markdown]\n"
        "# # Teaching title\n"
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

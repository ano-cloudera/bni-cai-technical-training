from __future__ import annotations

import pytest
from helpers import last_json, write_templates

from scripts.archive_group_outputs import main as archive_main
from scripts.prepare_group_workspaces import main as prepare_main
from scripts.reset_group_workspace import main as reset_main
from scripts.validate_group_workspaces import main as validate_main


@pytest.fixture
def args(tmp_path):
    write_templates(tmp_path / "templates")
    return ["--runtime-dir", str(tmp_path / "rt"), "--templates-dir", str(tmp_path / "templates")]


def test_prepare_is_a_dry_run_unless_apply_is_given(args, tmp_path, capsys) -> None:
    assert prepare_main(args) == 0
    out = last_json(capsys.readouterr().out)
    assert "dry-run" in out["mode"] and out["summary"]["copy_notebook"] == 30
    assert not (tmp_path / "rt").exists()
    assert prepare_main([*args, "--apply"]) == 0
    assert (tmp_path / "rt" / "groups" / "group_10" / "config" / "group.env").is_file()
    assert validate_main(args) == 0
    assert prepare_main([*args, "--apply"]) == 0
    assert last_json(capsys.readouterr().out)["summary"] == {"unchanged": 60}


def test_prepare_overwrite_without_yes_is_refused(args, capsys) -> None:
    prepare_main([*args, "--apply"])
    assert prepare_main([*args, "--apply", "--overwrite"]) == 2
    assert "requires --yes" in capsys.readouterr().err


def test_validate_fails_on_an_empty_runtime(args) -> None:
    assert validate_main(args) == 1


def test_reset_needs_an_explicit_group_and_yes(args, tmp_path, capsys) -> None:
    prepare_main([*args, "--apply"])
    (tmp_path / "rt/groups/group_01/output/a.json").write_text("{}")
    with pytest.raises(SystemExit) as no_group:
        reset_main(args)
    assert no_group.value.code == 2
    assert reset_main([*args, "--group-id", "group_01"]) == 0
    assert (tmp_path / "rt/groups/group_01/output/a.json").exists(), "dry run by default"
    assert reset_main([*args, "--group-id", "group_01", "--yes"]) == 0
    assert not (tmp_path / "rt/groups/group_01/output/a.json").exists()
    assert reset_main([*args, "--group-id", "../group_02", "--yes"]) == 2
    assert "REFUSED" in capsys.readouterr().err


def test_archive_dry_run_then_apply(args, tmp_path, capsys) -> None:
    prepare_main([*args, "--apply"])
    (tmp_path / "rt/groups/group_02/output/a.json").write_text("{}")
    with pytest.raises(SystemExit):
        archive_main(args)
    assert archive_main([*args, "--group-id", "group_02"]) == 0
    assert not (tmp_path / "rt/shared/state/archives").exists()
    assert archive_main([*args, "--all", "--apply"]) == 0
    assert len(list((tmp_path / "rt/shared/state/archives").glob("group_*.zip"))) == 10
    assert archive_main([*args, "--group-id", "group_99"]) == 2

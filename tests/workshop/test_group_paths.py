from __future__ import annotations

import os

import pytest

from bni_training.workshop import group_paths
from bni_training.workshop.group_paths import UnsafePathError, check_filename, safe_join


@pytest.mark.parametrize(
    "segment",
    ["..", ".", "", "../x", "a/b", "a\\b", "/abs", "x\x00y", "a..b", ".hidden", "é́", "C:", "a" * 200],
)
def test_unsafe_segments_are_rejected(tmp_path, segment) -> None:
    with pytest.raises(UnsafePathError):
        safe_join(tmp_path, segment)


@pytest.mark.parametrize("name", ["../x", ".hidden", "a/b", "a\\b", "x\x00", "", "a" * 90, "sp ace.json"])
def test_unsafe_file_names_are_rejected(name) -> None:
    with pytest.raises(UnsafePathError):
        check_filename(name)


def test_safe_names_resolve_inside_the_base(tmp_path) -> None:
    path = safe_join(tmp_path, "groups", "group_01", "output")
    assert path == (tmp_path / "groups" / "group_01" / "output").resolve()
    assert check_filename("answer-001.json") == "answer-001.json"


def test_symlinks_are_rejected_even_when_they_point_inside(tmp_path) -> None:
    (tmp_path / "real").mkdir()
    os.symlink(tmp_path / "real", tmp_path / "link")
    with pytest.raises(UnsafePathError, match="Symlinks"):
        safe_join(tmp_path, "link")


def test_a_symlink_to_another_groups_folder_cannot_be_used(tmp_path) -> None:
    root = tmp_path / "runtime"
    (root / "groups" / "group_02" / "output").mkdir(parents=True)
    (root / "groups" / "group_01").mkdir(parents=True)
    os.symlink(root / "groups" / "group_02" / "output", root / "groups" / "group_01" / "output")
    with pytest.raises(UnsafePathError):
        group_paths.session_output_dir(root, "group_01", "a" * 32)


def test_session_directories_live_under_their_own_group(tmp_path) -> None:
    out = group_paths.session_output_dir(tmp_path, "group_03", "b" * 32)
    tmp = group_paths.session_tmp_dir(tmp_path, "group_03", "b" * 32)
    base = (tmp_path / "groups" / "group_03").resolve()
    assert base in out.parents and base in tmp.parents
    assert "group_04" not in str(out)


def test_runtime_root_comes_from_the_environment_and_has_a_repo_default(tmp_path) -> None:
    assert group_paths.runtime_root({"WORKSHOP_RUNTIME_DIR": str(tmp_path)}) == tmp_path
    assert group_paths.runtime_root({}).parts[-2:] == ("workshop", "runtime")

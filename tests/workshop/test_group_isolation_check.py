from __future__ import annotations

from bni_training.workshop.isolation_check import NOTE, run_probes
from scripts.check_group_isolation import main


def test_every_isolation_probe_passes() -> None:
    probes = run_probes()
    assert len(probes) >= 15
    assert all(p.passed for p in probes), [p.name for p in probes if not p.passed]


def test_the_probes_cover_ids_traversal_symlinks_and_cross_group_writes() -> None:
    names = " | ".join(p.name for p in run_probes())
    for expected in (
        "ten valid group ids",
        "'group_11'",
        "'../group_01'",
        "../../group_02",
        "symlink",
        "other group's folder",
    ):
        assert expected in names, expected


def test_the_script_states_that_this_is_not_os_level_security(capsys) -> None:
    assert main() == 0
    out = capsys.readouterr().out
    assert "RESULT: PASS" in out and "not OS-level" in NOTE and "NOTE:" in out


def test_the_probes_never_touch_real_workspaces(tmp_path, monkeypatch) -> None:
    monkeypatch.setenv("WORKSHOP_RUNTIME_DIR", str(tmp_path / "must-stay-empty"))
    run_probes()
    assert not (tmp_path / "must-stay-empty").exists()

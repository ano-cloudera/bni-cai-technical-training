from __future__ import annotations

import json

import pytest

from bni_training.labs import EXIT_CODES, FAIL, PASS, SKIPPED, LabReport, default_mode, run_lab


def test_lab_report_status_rules() -> None:
    assert LabReport("x", "local").status == FAIL  # no checks is a failure, never a silent pass
    report = LabReport("x", "local")
    report.skipped("gpu", "no gpu")
    assert report.status == SKIPPED and report.exit_code == EXIT_CODES[SKIPPED]
    report.passed("a")
    assert report.status == PASS
    report.failed("b", "boom")
    assert report.status == FAIL and report.exit_code == 1


def test_run_lab_reports_exceptions_as_failures(capsys: pytest.CaptureFixture[str]) -> None:
    def body(_args, _report):
        raise RuntimeError("boom")

    assert run_lab("99", "demo", body, ["--mode", "local"]) == 1
    out = capsys.readouterr().out
    assert "LAB_STATUS: lab=99 mode=local status=FAIL" in out
    assert json.loads(out.split("\nLAB_STATUS")[0])["checks"][0]["name"] == "unhandled-exception"


def test_run_lab_rejects_unknown_mode() -> None:
    with pytest.raises(SystemExit):
        run_lab("99", "demo", lambda a, r: None, ["--mode", "production"])


def test_default_mode_comes_from_environment() -> None:
    assert default_mode({"LAB_MODE": "cai"}) == "cai"
    assert default_mode({"LAB_MODE": "bogus"}) == "local"
    assert default_mode({}) == "local"

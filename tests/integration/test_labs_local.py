"""Every canonical lab must run its complete code path in --mode local and must never fail silently."""

from __future__ import annotations

import importlib.util
import json
from pathlib import Path

import pytest

LABS = sorted(Path("scripts").glob("[0-1][0-9]_*.py"))


def load(path: Path):
    spec = importlib.util.spec_from_file_location(f"lab_{path.stem}", path)
    module = importlib.util.module_from_spec(spec)
    assert spec and spec.loader
    spec.loader.exec_module(module)
    return module


def report_of(output: str) -> dict:
    """Extract the lab's JSON report; frameworks such as CrewAI may print their own text before it."""
    start = output.rindex('{\n  "lab"')
    return json.loads(output[start : output.rindex("\nLAB_STATUS")])


def status_of(output: str) -> dict:
    line = next(item for item in reversed(output.splitlines()) if item.startswith("LAB_STATUS:"))
    return dict(part.split("=") for part in line.split()[1:])


def test_there_are_thirteen_labs() -> None:
    assert [p.name[:2] for p in LABS] == [f"{i:02d}" for i in range(13)]


@pytest.mark.parametrize("path", LABS, ids=lambda p: p.name[:2])
def test_lab_runs_in_local_mode(
    path: Path, capsys: pytest.CaptureFixture[str], monkeypatch: pytest.MonkeyPatch
) -> None:
    if path.name.startswith("09"):
        pytest.importorskip("openinference.instrumentation.crewai", reason="needs trace clients")
    monkeypatch.setenv("GROUP_ID", "group_01")
    monkeypatch.setenv("CREWAI_DISABLE_TELEMETRY", "true")
    code = load(path).main(["--mode", "local"])
    out = capsys.readouterr().out
    status = status_of(out)
    assert code in (0, 3), out
    assert status["status"] in {"PASS", "SKIPPED"} and status["failed"] == "0", out
    checks = report_of(out)["checks"]
    for check in checks:
        if check["status"] == "SKIPPED":
            assert check["detail"].strip(), f"SKIPPED without an explanation in {check['name']}"


@pytest.mark.parametrize("path", LABS, ids=lambda p: p.name[:2])
def test_every_lab_accepts_both_modes(path: Path) -> None:
    source = path.read_text()
    assert "def main(argv=None)" in source and "run_lab(" in source, path.name


@pytest.mark.parametrize("number", ["03", "04", "07", "08", "09", "10"])
def test_cai_mode_without_prerequisites_fails_instead_of_mocking(
    number: str, capsys: pytest.CaptureFixture[str], monkeypatch: pytest.MonkeyPatch
) -> None:
    for name in (
        "VLLM_BASE_URL",
        "QDRANT_URL",
        "EMBEDDING_MODEL_PATH",
        "PHOENIX_ENDPOINT",
        "LITELLM_BASE_URL",
    ):
        monkeypatch.delenv(name, raising=False)
    path = next(p for p in LABS if p.name.startswith(number))
    if number == "07":
        pytest.importorskip("qdrant_client")
    code = load(path).main(["--mode", "cai"])
    out = capsys.readouterr().out
    assert code == 1, out
    assert "status=FAIL" in out


def test_cai_mode_reports_missing_gpu_as_failure_not_skip(
    capsys: pytest.CaptureFixture[str], monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.delenv("RUNTIME_PROFILE", raising=False)
    code = load(Path("scripts/00_environment_check.py")).main(["--mode", "cai"])
    out = capsys.readouterr().out
    assert code == 1
    checks = {c["name"]: c["status"] for c in report_of(out)["checks"]}
    assert checks["gpu"] == "FAIL" and checks["runtime_profile"] == "FAIL"


def test_impala_failure_does_not_fall_back_to_csv(
    capsys: pytest.CaptureFixture[str], monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setenv("GROUP_ID", "group_01")
    monkeypatch.setenv("DATA_MODE", "impala_gssapi")
    monkeypatch.setenv("IMPALA_HOST", "impala.invalid")
    monkeypatch.setenv("VLLM_BASE_URL", "http://example.invalid/v1")
    code = load(Path("scripts/05_impala_ask_data.py")).main(["--mode", "cai"])
    out = capsys.readouterr().out
    assert code == 1 and "csv_query" not in out

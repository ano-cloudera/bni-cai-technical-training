"""Every canonical lab must run its complete code path in --mode local and must never fail silently."""

from __future__ import annotations

import importlib.util
import json
from pathlib import Path

import pytest

from bni_training.lab_registry import canonical_labs, legacy_only_scripts, legacy_wrappers

CANONICAL = [Path(lab.script) for lab in canonical_labs()]
WRAPPERS = [Path(p) for p in legacy_wrappers()]
LEGACY_ONLY = [Path(p) for p in legacy_only_scripts()]
LABS = [*CANONICAL, *WRAPPERS, *LEGACY_ONLY]  # every script that must run, wherever its number falls


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


def test_the_registry_defines_thirteen_canonical_labs_in_order() -> None:
    assert [lab.id for lab in canonical_labs()] == [f"{i:02d}" for i in range(13)]
    assert all(path.is_file() for path in LABS)
    assert len(CANONICAL) == 13 and len(WRAPPERS) == 8 and len(LEGACY_ONLY) == 3


@pytest.mark.parametrize("path", LABS, ids=lambda p: p.name)
def test_lab_runs_in_local_mode(
    path: Path, capsys: pytest.CaptureFixture[str], monkeypatch: pytest.MonkeyPatch
) -> None:
    if path.name.startswith(("09", "07")):
        pytest.importorskip("openinference.instrumentation.crewai", reason="needs trace clients")
    monkeypatch.setenv("GROUP_ID", "group_01")
    monkeypatch.setenv("CREWAI_DISABLE_TELEMETRY", "true")
    code = load(path).main(["--mode", "local"])
    out = capsys.readouterr().out
    status = status_of(out)
    assert code in (0, 3), out
    assert status["status"] in {"PASS", "SKIPPED"} and status["failed"] == "0", out
    for check in report_of(out)["checks"]:
        if check["status"] == "SKIPPED":
            assert check["detail"].strip(), f"SKIPPED without an explanation in {check['name']}"


@pytest.mark.parametrize("path", CANONICAL + WRAPPERS, ids=lambda p: p.name)
def test_every_lab_accepts_both_modes(path: Path) -> None:
    source = path.read_text()
    assert "def main(argv=None)" in source and ("run_lab(" in source or "delegate(" in source), path.name
    assert load(path).main  # importable without side effects


@pytest.mark.parametrize("path", WRAPPERS, ids=lambda p: p.name)
def test_rc1_wrappers_are_thin_and_point_at_the_canonical_lab(path: Path) -> None:
    source = path.read_text()
    lab = legacy_wrappers()[str(path)]
    assert len(source.splitlines()) < 20 and lab.script.split("/")[-1] in source


@pytest.mark.parametrize(
    "lab",
    [
        lab
        for lab in canonical_labs()
        if lab.id in {"03", "04", "05", "06", "07", "08", "09", "10", "11", "12"}
    ],
    ids=lambda lab: lab.id,
)
def test_cai_mode_without_prerequisites_fails_instead_of_mocking(
    lab, capsys: pytest.CaptureFixture[str], monkeypatch: pytest.MonkeyPatch
) -> None:
    for name in (
        "VLLM_BASE_URL", "QDRANT_URL", "EMBEDDING_MODEL_PATH", "PHOENIX_ENDPOINT", "LITELLM_BASE_URL",
        "PORTAL_URL", "GROUP_ID", "GROUP_WORKSPACE", "GROUP_ENV_FILE", "DATASET_ID", "MISSION_ID",
    ):  # fmt: skip
        monkeypatch.delenv(name, raising=False)
    if lab.id == "07":
        pytest.importorskip("qdrant_client")
    code = load(Path(lab.script)).main(["--mode", "cai"])
    out = capsys.readouterr().out
    assert code == 1 and "status=FAIL" in out
    assert "GROUP_ID is not set" in out, "participant labs refuse to guess the group in cai mode"


def test_lab_00_requires_a_gpu_only_when_the_trainer_asks_for_it(
    capsys: pytest.CaptureFixture[str], monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.delenv("RUNTIME_PROFILE", raising=False)
    monkeypatch.setenv("WORKSHOP_ROLE", "trainer")
    path = Path("scripts/00_environment_validation.py")
    assert load(path).main(["--mode", "cai"]) == 1  # runtime_profile and shared endpoint are missing
    checks = {c["name"]: c["status"] for c in report_of(capsys.readouterr().out)["checks"]}
    assert checks["gpu"] == "SKIPPED" and checks["runtime_profile"] == "FAIL"
    assert load(path).main(["--mode", "cai", "--expect-gpu"]) == 1
    checks = {c["name"]: c["status"] for c in report_of(capsys.readouterr().out)["checks"]}
    assert checks["gpu"] == "FAIL" and checks["cuda_runtime"] == "FAIL"


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

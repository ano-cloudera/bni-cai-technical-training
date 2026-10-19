from __future__ import annotations

import importlib.util
import json
import sys
from pathlib import Path

import pytest

from bni_training.lab_registry import canonical_labs

ROOT = Path(__file__).resolve().parents[2]
FORBIDDEN_IN_NOTEBOOKS = (
    "subprocess", "Popen", "os.system", "os.popen", "TRAINER_EXECUTE_VLLM", "vllm.entrypoints",
    "snapshot_download", "--download", "WORKSHOP_ROLE'] =", 'WORKSHOP_ROLE"] =',
)  # fmt: skip


def load(name: str):
    spec = importlib.util.spec_from_file_location(name, ROOT / "scripts" / f"{name}.py")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def report_of(output: str) -> dict:
    return json.loads(output[output.rindex('{\n  "lab"') : output.rindex("\nLAB_STATUS")])


def make_model(path: Path) -> Path:
    path.mkdir()
    (path / "config.json").write_text("{}")
    (path / "model.safetensors").write_bytes(b"x")
    return path


@pytest.mark.parametrize("lab", canonical_labs(), ids=lambda lab: lab.id)
def test_no_notebook_can_start_vllm_download_a_model_or_become_a_trainer(lab) -> None:
    sources = "\n".join(
        "".join(c["source"])
        for c in json.loads(lab.notebook_path.read_text())["cells"]
        if c["cell_type"] == "code"
    )
    for forbidden in FORBIDDEN_IN_NOTEBOOKS:
        assert forbidden not in sources, (lab.id, forbidden)


def test_executing_the_vllm_notebook_logic_never_launches_a_process(monkeypatch, capsys) -> None:
    import subprocess

    launched = []
    monkeypatch.setattr(subprocess, "call", lambda *a, **k: launched.append(a) or 0)
    monkeypatch.setattr(subprocess, "Popen", lambda *a, **k: launched.append(a))
    monkeypatch.delenv("TRAINER_EXECUTE_VLLM", raising=False)
    assert load("02_vllm_deployment").main(["--mode", "local"]) == 0
    assert launched == [] and "vllm_server_start" in capsys.readouterr().out


def test_a_participant_cannot_start_vllm_even_by_setting_the_trainer_flag(
    monkeypatch, tmp_path, capsys
) -> None:
    import subprocess

    launched = []
    monkeypatch.setattr(subprocess, "call", lambda *a, **k: launched.append(a) or 0)
    monkeypatch.setenv("TRAINER_EXECUTE_VLLM", "true")
    monkeypatch.setenv("MODEL_PATH", str(make_model(tmp_path / "model")))
    monkeypatch.setenv("GPU_PROFILE", "l40s")
    monkeypatch.setenv("CDSW_APP_PORT", "8080")
    monkeypatch.delenv("WORKSHOP_ROLE", raising=False)
    for mode in ("local", "cai"):
        assert load("02_vllm_deployment").main(["--mode", mode]) == 1
        assert "participant_start_refused" in capsys.readouterr().out
    assert launched == []


def test_only_the_trainer_role_can_start_vllm_and_only_in_cai_mode(monkeypatch, tmp_path, capsys) -> None:
    import subprocess

    launched = []
    monkeypatch.setattr(subprocess, "call", lambda command, *a, **k: launched.append(command) or 0)
    monkeypatch.setenv("TRAINER_EXECUTE_VLLM", "true")
    monkeypatch.setenv("WORKSHOP_ROLE", "trainer")
    monkeypatch.setenv("MODEL_PATH", str(make_model(tmp_path / "model")))
    monkeypatch.setenv("GPU_PROFILE", "l40s")
    monkeypatch.setenv("CDSW_APP_PORT", "8080")
    assert load("02_vllm_deployment").main(["--mode", "local"]) == 0 and launched == []
    capsys.readouterr()
    assert load("02_vllm_deployment").main(["--mode", "cai"]) == 0
    assert len(launched) == 1 and "--tensor-parallel-size" in launched[0] and "127.0.0.1" in launched[0]


def test_the_model_is_never_downloaded_by_default_and_never_for_participants(
    monkeypatch, tmp_path, capsys
) -> None:
    calls = []
    fake = type(sys)("huggingface_hub")
    fake.snapshot_download = lambda *a, **k: calls.append((a, k))
    monkeypatch.setitem(sys.modules, "huggingface_hub", fake)
    model = make_model(tmp_path / "model")
    monkeypatch.setenv("MODEL_PATH", str(model))
    monkeypatch.setenv("WORKSHOP_ROLE", "trainer")
    assert load("01_model_artifact_validation").main(["--mode", "cai"]) == 0
    assert calls == [] and "no download requested" in capsys.readouterr().out
    monkeypatch.delenv("WORKSHOP_ROLE")
    assert load("01_model_artifact_validation").main(["--mode", "cai", "--download"]) == 1
    assert "participants never download" in capsys.readouterr().out and calls == []
    assert load("01_model_artifact_validation").main(["--mode", "cai"]) == 3, "participants only read the lab"
    monkeypatch.setenv("WORKSHOP_ROLE", "trainer")
    assert load("01_model_artifact_validation").main(["--mode", "cai", "--download"]) == 0
    assert len(calls) == 1


def test_lab_01_writes_nothing_into_the_model_directory_unless_asked(monkeypatch, tmp_path) -> None:
    model = make_model(tmp_path / "model")
    monkeypatch.setenv("MODEL_PATH", str(model))
    monkeypatch.setenv("WORKSHOP_ROLE", "trainer")
    before = sorted(p.name for p in model.iterdir())
    assert load("01_model_artifact_validation").main(["--mode", "cai"]) == 0
    assert sorted(p.name for p in model.iterdir()) == before
    assert load("01_model_artifact_validation").main(["--mode", "cai", "--write-manifest"]) == 0
    assert (model / "training-manifest.json").is_file()

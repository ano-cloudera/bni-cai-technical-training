from __future__ import annotations

from pathlib import Path
from zipfile import ZipFile

from scripts.acceptance_test import local_checks
from scripts.package_release import build_release


def test_local_acceptance_requires_python_cai_entrypoints() -> None:
    result = local_checks(Path("."))
    checks = {item["name"]: item["passed"] for item in result["checks"]}
    assert checks["python_cai_entrypoints"] is True
    assert result["status"] == "ready_for_cai_validation"


def test_release_zip_is_clean_and_complete(tmp_path: Path) -> None:
    archive = build_release(Path("."), tmp_path, "0.2.0-rc1")
    with ZipFile(archive) as zf:
        names = zf.namelist()
    assert "bni-cai-technical-training/deployments/cai/vllm/app.py" in names
    assert "bni-cai-technical-training/requirements/gpu-h200.lock" in names
    assert "bni-cai-technical-training/notebooks/12_agent_studio_client.ipynb" in names
    assert not any("/.venv/" in name or "__pycache__" in name or name.endswith(".pyc") for name in names)
    assert not any(name.endswith(".safetensors") for name in names)

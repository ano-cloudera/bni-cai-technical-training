from __future__ import annotations

from pathlib import Path
from zipfile import ZipFile

from scripts.acceptance_test import local_checks
from scripts.package_release import approved, build_release


def test_local_acceptance_requires_python_cai_entrypoints() -> None:
    result = local_checks(Path("."))
    checks = {item["name"]: item["passed"] for item in result["checks"]}
    assert checks["python_cai_entrypoints"] is True
    assert result["status"] == "local_validation_passed"


def test_release_zip_is_clean_and_complete(tmp_path: Path) -> None:
    archive = build_release(Path("."), tmp_path, "0.2.0-rc1")
    with ZipFile(archive) as zf:
        names = zf.namelist()
    assert "bni-cai-technical-training/deployments/cai/vllm/app.py" in names
    assert "bni-cai-technical-training/requirements/gpu-h200.lock" in names
    assert "bni-cai-technical-training/notebooks/12_agent_studio_client.ipynb" in names
    assert not any("/.venv/" in name or "__pycache__" in name or name.endswith(".pyc") for name in names)
    assert not any(name.endswith(".safetensors") for name in names)


def test_release_includes_workspace_templates_and_notebook_templates(tmp_path: Path) -> None:
    archive = build_release(Path("."), tmp_path, "0.2.0-test")
    with ZipFile(archive) as zf:
        names = zf.namelist()
    prefix = "bni-cai-technical-training/"
    assert prefix + "workshop/templates/group/group.env.example" in names
    assert prefix + "workshop/templates/roster.example.csv" in names
    assert prefix + "notebooks/templates/00_environment_validation.ipynb" in names
    assert prefix + "scripts/prepare_group_workspaces.py" in names
    assert prefix + "config/workshop/labs.yaml" in names
    assert not any("workshop/runtime" in n or n.endswith("group.env") for n in names)


def test_generated_workspaces_and_group_env_files_are_never_approved_for_packaging() -> None:
    root = Path(".").resolve()
    for relative in (
        "workshop/runtime/groups/group_01/config/group.env",
        "workshop/runtime/groups/group_01/output/s1/answer.json",
        "workshop/runtime/shared/state/roster.json",
        "somewhere/else/group.env",
    ):
        assert approved(root / relative, root) is False, relative
    assert approved(root / "workshop/templates/group/group.env.example", root) is True

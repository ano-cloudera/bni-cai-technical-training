from __future__ import annotations

import importlib.util
from pathlib import Path

import yaml

ROOT = Path(__file__).resolve().parents[2]


def load_launcher():
    spec = importlib.util.spec_from_file_location(
        "portal_launcher", ROOT / "deployments/cai/workshop-portal/app.py"
    )
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def test_launcher_is_a_python_entrypoint_bound_to_the_cai_port() -> None:
    command = load_launcher().build_command({"CDSW_APP_PORT": "8123"})
    assert command[:4] == ["python", "-m", "streamlit", "run"]
    assert Path(command[4]) == ROOT / "apps/workshop-portal/app.py" and Path(command[4]).is_file()
    assert command[command.index("--server.port") + 1] == "8123"
    assert command[command.index("--server.address") + 1] == "127.0.0.1"
    assert command[command.index("--server.headless") + 1] == "true"
    assert command[command.index("--server.enableXsrfProtection") + 1] == "true"
    assert not (ROOT / "deployments/cai/workshop-portal/app.py").suffix == ".sh"


def test_five_shared_applications_with_portal_sized_for_forty_users() -> None:
    config = yaml.safe_load((ROOT / "config/workshop/applications.yaml").read_text())
    apps = {a["key"]: a for a in config["applications"]}
    assert config["max_active_applications"] == 5 and len(apps) == 5
    assert set(apps) == {"vllm", "qdrant", "phoenix", "litellm", "workshop-portal"}
    portal = apps["workshop-portal"]
    assert portal["resources"]["cpu"] == 4
    assert portal["resources"]["memory_gb"] == 8 and portal["resources"]["memory_gb_max"] == 16
    assert portal["resources"]["nvidia_gpu"] == 0 and portal["validation"] == "cai-validation-pending"
    # the inference semaphore is process-local: one Streamlit process and one replica are required
    assert portal["replicas"] == 1 and portal["streamlit_processes"] == 1
    assert portal["scaling"] == "single_replica_required"
    assert all(apps[k]["resources"]["nvidia_gpu"] == 0 for k in apps if k != "vllm")
    for app in apps.values():
        assert app["script"].endswith("/app.py") and (ROOT / app["script"]).is_file()


def test_the_default_inference_limit_is_three_in_the_documentation_and_code() -> None:
    from bni_training.workshop.portal.config import DEFAULT_MAX_CONCURRENT

    assert DEFAULT_MAX_CONCURRENT == 3
    assert "PORTAL_MAX_CONCURRENT_INFERENCE" in (ROOT / "apps/workshop-portal/README.md").read_text()


def test_the_streamlit_script_is_resolved_from_the_repository_not_the_working_directory(
    tmp_path, monkeypatch
) -> None:
    """A CAI Application starts in /home/cdsw; a relative path used to fail with File does not exist."""
    monkeypatch.chdir(tmp_path)
    launcher = load_launcher()
    command = launcher.build_command({"CDSW_APP_PORT": "8123"})
    assert Path(command[4]).is_absolute() and Path(command[4]).is_file()
    custom = launcher.build_command({"CDSW_APP_PORT": "8123", "PORTAL_APP": "/opt/x/app.py"})
    assert custom[4] == "/opt/x/app.py"
    relative = launcher.resolve_app_path({"PORTAL_APP": "apps/workshop-portal/app.py"})
    assert relative == ROOT / "apps/workshop-portal/app.py"


def test_the_launcher_runs_from_the_repository_and_names_a_missing_script(monkeypatch) -> None:
    import pytest

    launcher = load_launcher()
    seen = {}
    monkeypatch.setattr(launcher, "run_supervised", lambda command, **kw: seen.update(kw) or 0)
    monkeypatch.setenv("CDSW_APP_PORT", "8123")
    monkeypatch.delenv("PORTAL_APP", raising=False)
    assert launcher.main() == 0 and seen["cwd"] == launcher.REPO_ROOT == ROOT
    monkeypatch.setenv("PORTAL_APP", str(ROOT / "apps/missing/app.py"))
    with pytest.raises(FileNotFoundError, match="Streamlit script not found"):
        launcher.main()

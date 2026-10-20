from __future__ import annotations

import sys

import pytest

from deployments.cai.common import resolve_cai_port, run_supervised


def test_resolve_cai_port_prefers_application_port() -> None:
    assert resolve_cai_port({"CDSW_APP_PORT": "8090", "CDSW_READONLY_PORT": "8091"}) == 8090


def test_resolve_cai_port_uses_readonly_only_when_selected() -> None:
    env = {"CAI_PORT_MODE": "readonly", "CDSW_APP_PORT": "8090", "CDSW_READONLY_PORT": "8091"}
    assert resolve_cai_port(env) == 8091


@pytest.mark.parametrize("env", [{}, {"CDSW_APP_PORT": "abc"}, {"CDSW_APP_PORT": "70000"}])
def test_resolve_cai_port_rejects_missing_or_invalid_port(env: dict[str, str]) -> None:
    with pytest.raises(ValueError, match="CAI Application port"):
        resolve_cai_port(env)


def test_run_supervised_returns_child_exit_code() -> None:
    command = [sys.executable, "-c", "raise SystemExit(7)"]
    assert run_supervised(command, readiness=None) == 7


def test_run_supervised_rejects_string_command() -> None:
    with pytest.raises(TypeError, match="argument list"):
        run_supervised("python -V", readiness=None)  # type: ignore[arg-type]


def test_run_supervised_stops_after_readiness_timeout() -> None:
    command = [sys.executable, "-c", "import time; time.sleep(30)"]
    with pytest.raises(TimeoutError, match="readiness"):
        run_supervised(command, readiness=lambda: False, startup_timeout=0.05, poll_interval=0.01)


def test_every_launcher_runs_in_a_kernel_where_file_is_not_defined() -> None:
    """CAI executes the Application script cell by cell, so __file__ is undefined (it caused a NameError)."""
    from pathlib import Path

    root = Path(__file__).resolve().parents[2]
    scripts = sorted((root / "deployments/cai").glob("*/app.py"))
    assert len(scripts) == 6
    for script in scripts:
        namespace: dict = {"__name__": "cai_kernel_cell"}  # no __file__, like a kernel cell
        exec(compile(script.read_text(), str(script), "exec"), namespace)  # noqa: S102
        assert callable(namespace["build_command"]) and "__file__" not in namespace, script.name


def test_the_streamlit_launchers_take_the_repository_root_from_the_common_module() -> None:
    from pathlib import Path

    from deployments.cai import common

    root = Path(__file__).resolve().parents[2]
    assert common.REPO_ROOT == root
    for name in ("workshop-portal", "streamlit"):
        source = (root / f"deployments/cai/{name}/app.py").read_text()
        assert "from deployments.cai.common import REPO_ROOT" in source
        assert "Path(__file__)" not in source

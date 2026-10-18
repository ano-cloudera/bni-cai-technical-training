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

"""Phoenix launcher: `phoenix serve` has no --host or --port option; it reads environment variables."""

from __future__ import annotations

import subprocess
import sys

from deployments.cai.phoenix import app


def test_the_command_passes_no_unsupported_cli_options() -> None:
    command = app.build_command({})
    assert command[1:] == ["-m", "phoenix.server.main", "serve"]
    assert "--host" not in command and "--port" not in command


def test_the_environment_binds_the_platform_port_on_loopback(tmp_path) -> None:
    env = app.build_environment({"CDSW_APP_PORT": "8100", "PHOENIX_WORKING_DIR": str(tmp_path / "w")})
    assert env["PHOENIX_PORT"] == "8100" and env["PHOENIX_HOST"] == "127.0.0.1"
    assert env["PHOENIX_WORKING_DIR"] == str(tmp_path / "w") and (tmp_path / "w").is_dir()


def test_host_and_working_directory_can_be_overridden(tmp_path) -> None:
    env = app.build_environment(
        {"CDSW_APP_PORT": "9000", "PHOENIX_HOST": "0.0.0.0", "PHOENIX_WORKING_DIR": str(tmp_path)}
    )
    assert env["PHOENIX_HOST"] == "0.0.0.0" and env["PHOENIX_PORT"] == "9000"


def test_a_missing_platform_port_is_an_error(tmp_path) -> None:
    import pytest

    with pytest.raises(ValueError, match="CAI Application port"):
        app.build_environment({"PHOENIX_WORKING_DIR": str(tmp_path)})


def test_the_installed_phoenix_cli_really_has_no_host_or_port_option() -> None:
    """Guards the root cause: the old command failed with 'unrecognized arguments: --host --port'."""
    result = subprocess.run(
        [sys.executable, "-m", "phoenix.server.main", "serve", "--help"], capture_output=True, text=True
    )
    if result.returncode != 0 and "No module named phoenix" in result.stderr:
        import pytest

        pytest.skip("phoenix is not installed in this profile")
    assert "--host" not in result.stdout and "--port" not in result.stdout

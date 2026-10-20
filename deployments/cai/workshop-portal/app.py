from __future__ import annotations

import os
from collections.abc import Mapping
from pathlib import Path

from deployments.cai.common import http_ready, resolve_cai_port, run_supervised

# A CAI Application starts in the project root (/home/cdsw), not the repository: resolve paths here.
REPO_ROOT = Path(__file__).resolve().parents[3]


def resolve_app_path(env: Mapping[str, str]) -> Path:
    """The Streamlit script as an absolute path; a relative path is relative to the repo."""
    path = Path(env.get("PORTAL_APP", "apps/workshop-portal/app.py"))
    return path if path.is_absolute() else REPO_ROOT / path


def build_command(env: Mapping[str, str]) -> list[str]:
    port = resolve_cai_port(env)
    return [
        env.get("PYTHON_EXECUTABLE", "python"),
        "-m",
        "streamlit",
        "run",
        str(resolve_app_path(env)),
        "--server.port",
        str(port),
        "--server.address",
        "127.0.0.1",
        "--server.headless",
        "true",
        "--server.fileWatcherType",
        "none",
        "--server.enableXsrfProtection",
        "true",
        "--browser.gatherUsageStats",
        "false",
    ]


def main() -> int:
    env = dict(os.environ)
    port = resolve_cai_port(env)
    app = resolve_app_path(env)
    if not app.is_file():
        raise FileNotFoundError(
            f"Streamlit script not found: {app}. Check the repository path and the app setting."
        )
    return run_supervised(
        build_command(env),
        env=env,
        cwd=REPO_ROOT,
        readiness=lambda: http_ready(f"http://127.0.0.1:{port}/_stcore/health"),
        startup_timeout=float(env.get("APP_STARTUP_TIMEOUT_MINUTES", "5")) * 60,
    )


if __name__ == "__main__":
    raise SystemExit(main())

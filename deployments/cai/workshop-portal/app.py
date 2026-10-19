from __future__ import annotations

import os
from collections.abc import Mapping

from deployments.cai.common import http_ready, resolve_cai_port, run_supervised


def build_command(env: Mapping[str, str]) -> list[str]:
    port = resolve_cai_port(env)
    return [
        env.get("PYTHON_EXECUTABLE", "python"),
        "-m",
        "streamlit",
        "run",
        env.get("PORTAL_APP", "apps/workshop-portal/app.py"),
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
    return run_supervised(
        build_command(env),
        env=env,
        readiness=lambda: http_ready(f"http://127.0.0.1:{port}/_stcore/health"),
        startup_timeout=float(env.get("APP_STARTUP_TIMEOUT_MINUTES", "5")) * 60,
    )


if __name__ == "__main__":
    raise SystemExit(main())

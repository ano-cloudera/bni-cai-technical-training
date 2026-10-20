from __future__ import annotations

import os
from collections.abc import Mapping
from pathlib import Path

from deployments.cai.common import http_ready, resolve_cai_port, run_supervised


def build_command(env: Mapping[str, str]) -> list[str]:
    """`phoenix serve` has no --host or --port option; the server reads PHOENIX_HOST and PHOENIX_PORT."""
    return [env.get("PYTHON_EXECUTABLE", "python"), "-m", "phoenix.server.main", "serve"]


def build_environment(env: Mapping[str, str]) -> dict[str, str]:
    """Child environment: bind the platform port (CDSW_APP_PORT); keep data in the working directory."""
    working = Path(env.get("PHOENIX_WORKING_DIR", "/tmp/bni-phoenix"))
    working.mkdir(parents=True, exist_ok=True)
    child = dict(env)
    child.update(
        {
            "PHOENIX_HOST": env.get("PHOENIX_HOST", "127.0.0.1"),
            "PHOENIX_PORT": str(resolve_cai_port(env)),
            "PHOENIX_WORKING_DIR": str(working),
        }
    )
    return child


def main() -> int:
    env = dict(os.environ)
    port = resolve_cai_port(env)
    return run_supervised(
        build_command(env),
        env=build_environment(env),
        readiness=lambda: http_ready(f"http://127.0.0.1:{port}/healthz"),
        startup_timeout=float(env.get("APP_STARTUP_TIMEOUT_MINUTES", "5")) * 60,
    )


if __name__ == "__main__":
    raise SystemExit(main())

from __future__ import annotations

import os
from collections.abc import Mapping
from pathlib import Path

from deployments.cai.common import http_ready, resolve_cai_port, run_supervised


def build_command(env: Mapping[str, str]) -> list[str]:
    return [
        env.get("PYTHON_EXECUTABLE", "python"),
        "-m",
        "phoenix.server.main",
        "serve",
        "--host",
        "127.0.0.1",
        "--port",
        str(resolve_cai_port(env)),
    ]


def main() -> int:
    env = dict(os.environ)
    port = resolve_cai_port(env)
    working = Path(env.get("PHOENIX_WORKING_DIR", "/tmp/bni-phoenix"))
    working.mkdir(parents=True, exist_ok=True)
    env["PHOENIX_WORKING_DIR"] = str(working)
    return run_supervised(
        build_command(env),
        env=env,
        readiness=lambda: http_ready(f"http://127.0.0.1:{port}/healthz"),
        startup_timeout=float(env.get("APP_STARTUP_TIMEOUT_MINUTES", "5")) * 60,
    )


if __name__ == "__main__":
    raise SystemExit(main())

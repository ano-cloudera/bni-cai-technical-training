from __future__ import annotations

import os
from collections.abc import Mapping

from deployments.cai.common import http_ready, resolve_cai_port, run_supervised


def build_command(env: Mapping[str, str]) -> list[str]:
    return [
        env.get("LITELLM_EXECUTABLE", "litellm"),
        "--config",
        env.get("LITELLM_CONFIG", "config/litellm.yaml"),
        "--host",
        "127.0.0.1",
        "--port",
        str(resolve_cai_port(env)),
    ]


def main() -> int:
    env = dict(os.environ)
    port = resolve_cai_port(env)
    return run_supervised(
        build_command(env),
        env=env,
        readiness=lambda: http_ready(f"http://127.0.0.1:{port}/health/liveliness"),
        startup_timeout=float(env.get("APP_STARTUP_TIMEOUT_MINUTES", "5")) * 60,
    )


if __name__ == "__main__":
    raise SystemExit(main())

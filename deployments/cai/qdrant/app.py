from __future__ import annotations

import os
from collections.abc import Mapping
from pathlib import Path

from deployments.cai.common import http_ready, resolve_cai_port, run_supervised


def build_command(env: Mapping[str, str]) -> list[str]:
    binary = env.get("QDRANT_BINARY", "")
    if not binary:
        raise ValueError("QDRANT_BINARY is required")
    return [binary]


def check_binary(env: Mapping[str, str]) -> Path:
    """The binary must already exist: the Application never downloads it."""
    path = Path(env.get("QDRANT_BINARY", ""))
    if not path.is_file() or not os.access(path, os.X_OK):
        raise ValueError(
            f"Qdrant binary not found or not executable at {path}. Prepare it once from a Session: "
            f"bash scripts/prepare_qdrant_binary.sh {path}"
        )
    return path


def build_environment(env: Mapping[str, str]) -> dict[str, str]:
    port = resolve_cai_port(env)
    storage = Path(env.get("QDRANT_STORAGE_PATH", "/tmp/bni-qdrant"))
    storage.mkdir(parents=True, exist_ok=True)
    child = dict(env)
    child.update(
        {
            "QDRANT__SERVICE__HOST": "127.0.0.1",
            "QDRANT__SERVICE__HTTP_PORT": str(port),
            "QDRANT__SERVICE__GRPC_PORT": "0",
            "QDRANT__STORAGE__STORAGE_PATH": str(storage),
        }
    )
    if env.get("QDRANT_API_KEY"):
        child["QDRANT__SERVICE__API_KEY"] = env["QDRANT_API_KEY"]
    return child


def main() -> int:
    env = dict(os.environ)
    build_command(env)
    check_binary(env)
    port = resolve_cai_port(env)
    return run_supervised(
        build_command(env),
        env=build_environment(env),
        readiness=lambda: http_ready(f"http://127.0.0.1:{port}/readyz"),
        startup_timeout=float(env.get("APP_STARTUP_TIMEOUT_MINUTES", "5")) * 60,
    )


if __name__ == "__main__":
    raise SystemExit(main())

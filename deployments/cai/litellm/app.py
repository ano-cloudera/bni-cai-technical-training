from __future__ import annotations

import os
import re
import sys
from collections.abc import Mapping
from pathlib import Path

from deployments.cai.common import REPO_ROOT, http_ready, resolve_cai_port, run_supervised

# A CAI Application starts in /home/cdsw, not the repository: resolve a relative config from REPO_ROOT.
_ENV_REFERENCE = re.compile(r"os\.environ/([A-Za-z_][A-Za-z0-9_]*)")


def resolve_config_path(env: Mapping[str, str]) -> Path:
    path = Path(env.get("LITELLM_CONFIG", "config/litellm.yaml"))
    return path if path.is_absolute() else REPO_ROOT / path


def missing_config_variables(config: Path, env: Mapping[str, str]) -> list[str]:
    """Variables the config reads as os.environ/NAME that are unset (an unset one can mislead the router)."""
    names = sorted(set(_ENV_REFERENCE.findall(config.read_text(encoding="utf-8"))))
    return [name for name in names if not env.get(name)]


def build_command(env: Mapping[str, str]) -> list[str]:
    return [
        env.get("LITELLM_EXECUTABLE", "litellm"),
        "--config",
        str(resolve_config_path(env)),
        "--host",
        "127.0.0.1",
        "--port",
        str(resolve_cai_port(env)),
    ]


def main() -> int:
    env = dict(os.environ)
    port = resolve_cai_port(env)
    config = resolve_config_path(env)
    if not config.is_file():
        raise FileNotFoundError(
            f"LiteLLM config not found: {config}. Check LITELLM_CONFIG and the repository path."
        )
    missing = missing_config_variables(config, env)
    if missing:
        print(
            f"WARNING: {config.name} reads variables that are not set: {', '.join(missing)}", file=sys.stderr
        )
    return run_supervised(
        build_command(env),
        env=env,
        cwd=REPO_ROOT,
        readiness=lambda: http_ready(f"http://127.0.0.1:{port}/health/liveliness"),
        startup_timeout=float(env.get("APP_STARTUP_TIMEOUT_MINUTES", "5")) * 60,
    )


if __name__ == "__main__":
    raise SystemExit(main())

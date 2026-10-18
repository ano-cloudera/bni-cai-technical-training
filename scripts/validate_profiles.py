"""Validate each dependency profile in its own temporary Python 3.10 virtual environment.

For every non-GPU profile this script:
  1. creates a fresh venv (never reused between profiles),
  2. installs ONLY that profile's lock file,
  3. runs ``pip check``,
  4. imports the profile's key libraries and runs the lab/Application smoke checks it serves.

GPU profiles are reported as SKIPPED: they cannot be validated on macOS and stay
``cai-validation-pending`` until Lab 00 runs in the CAI runtime.
"""

from __future__ import annotations

import argparse
import json
import os
import shutil
import socket
import subprocess
import sys
import tempfile
import time
import urllib.request
from pathlib import Path

import yaml

ROOT = Path(__file__).resolve().parents[1]
PROFILES = yaml.safe_load((ROOT / "requirements" / "profiles.yaml").read_text())["profiles"]
GPU_PROFILES = {name for name in PROFILES if name.startswith("gpu-")}

IMPORTS = {
    "participant": [
        "pydantic",
        "yaml",
        "pandas",
        "duckdb",
        "sqlglot",
        "httpx",
        "openai",
        "crewai",
        "impala.dbapi",
        "thrift_sasl",
        "streamlit",
        "dotenv",
        "huggingface_hub",
        "safetensors",
        "opentelemetry.sdk.trace",
        "opentelemetry.exporter.otlp.proto.http.trace_exporter",
        "openinference.instrumentation.crewai",
        "openinference.instrumentation.openai",
    ],
    "rag": ["qdrant_client", "sentence_transformers", "crewai", "streamlit"],
    "observability": ["phoenix", "phoenix.server.main", "strawberry", "graphql"],
    "gateway": ["litellm", "fastapi", "uvicorn"],
    "guardrails": ["pydantic", "yaml", "guardrails", "presidio_analyzer", "presidio_anonymizer"],
    "dev-test": [
        "pytest",
        "ruff",
        "nbformat",
        "nbclient",
        "ipykernel",
        "qdrant_client",
        "phoenix",
        "crewai",
        "streamlit",
    ],
}
# Lab scripts (run with --mode local) that each profile must be able to execute.
LABS = {
    "participant": ["00", "03", "04", "05", "06", "08", "09", "10", "11", "12"],
    "rag": ["07"],
    "observability": [],
    "gateway": [],
    "guardrails": ["11"],
    "dev-test": [f"{i:02d}" for i in range(13)],
}


def run(cmd, *, env=None, cwd=ROOT, timeout=1500):
    started = time.monotonic()
    proc = subprocess.run(cmd, cwd=cwd, env=env, capture_output=True, text=True, timeout=timeout)
    return proc.returncode, (proc.stdout + proc.stderr).strip(), round(time.monotonic() - started, 1)


def lab_script(number: str) -> Path:
    return next((ROOT / "scripts").glob(f"{number}_*.py"))


def tmp_log() -> Path:
    handle = tempfile.NamedTemporaryFile(prefix="bni-server-", suffix=".log", delete=False)
    handle.close()
    return Path(handle.name)


def free_port() -> int:
    with socket.socket() as sock:
        sock.bind(("127.0.0.1", 0))
        return sock.getsockname()[1]


def smoke_env(tmp: Path) -> dict[str, str]:
    env = {k: v for k, v in os.environ.items() if k not in {"VIRTUAL_ENV", "PYTHONPATH", "PYTHONHOME"}}
    env.update(
        HOME=str(tmp / "home"),
        PYTHONPATH=f"{ROOT / 'src'}{os.pathsep}{ROOT}",
        PYTHONDONTWRITEBYTECODE="1",
        CREWAI_DISABLE_TELEMETRY="true",
        OTEL_SDK_DISABLED="false",
        GROUP_ID="group_01",
        LAB_MODE="local",
        DATA_MODE="csv",
        VLLM_BASE_URL="http://example.invalid/v1",
        VLLM_API_KEY="local-placeholder",
    )
    (tmp / "home").mkdir(exist_ok=True)
    return env


def phoenix_server_smoke(py: Path, env: dict[str, str], tmp: Path) -> dict:
    """Start the real Phoenix server from the observability profile alone and wait for /healthz."""
    port, grpc_port = free_port(), free_port()
    working = tmp / "phoenix-working"
    working.mkdir(exist_ok=True)
    child_env = dict(
        env,
        PHOENIX_HOST="127.0.0.1",
        PHOENIX_PORT=str(port),
        PHOENIX_GRPC_PORT=str(grpc_port),
        PHOENIX_WORKING_DIR=str(working),
    )
    cmd = [str(py), "-m", "phoenix.server.main", "serve"]
    log_path = tmp_log()
    log_handle = log_path.open("w")
    proc = subprocess.Popen(
        cmd, cwd=ROOT, env=child_env, stdout=log_handle, stderr=subprocess.STDOUT, text=True
    )
    try:
        deadline = time.monotonic() + 180
        while time.monotonic() < deadline:
            if proc.poll() is not None:
                return {
                    "name": "phoenix_server_healthz",
                    "status": "FAIL",
                    "detail": log_path.read_text()[-600:],
                }
            try:
                with urllib.request.urlopen(f"http://127.0.0.1:{port}/healthz", timeout=2) as response:
                    if response.status == 200:
                        return {
                            "name": "phoenix_server_healthz",
                            "status": "PASS",
                            "detail": f"HTTP 200 on port {port}",
                        }
            except OSError:
                time.sleep(1)
        return {"name": "phoenix_server_healthz", "status": "FAIL", "detail": "timed out after 180 s"}
    finally:
        log_handle.close()
        proc.terminate()
        try:
            proc.wait(timeout=15)
        except subprocess.TimeoutExpired:
            proc.kill()


def gateway_proxy_smoke(py: Path, env: dict[str, str]) -> dict:
    """Start the real LiteLLM proxy with config/litellm.yaml and wait for /health/liveliness."""
    port = free_port()
    # The proxy refuses to start without a master key; use a throwaway one that never leaves this process.
    child_env = dict(
        env,
        MOCK_FALLBACK_BASE_URL="http://127.0.0.1:9/v1",
        LITELLM_MASTER_KEY="sk-" + os.urandom(16).hex(),
    )
    bin_dir = py.parent
    cmd = [
        str(bin_dir / "litellm"),
        "--config",
        str(ROOT / "config" / "litellm.yaml"),
        "--host",
        "127.0.0.1",
        "--port",
        str(port),
    ]
    log_path = tmp_log()
    log_handle = log_path.open("w")
    proc = subprocess.Popen(
        cmd, cwd=ROOT, env=child_env, stdout=log_handle, stderr=subprocess.STDOUT, text=True
    )
    try:
        deadline = time.monotonic() + 120
        while time.monotonic() < deadline:
            if proc.poll() is not None:
                return {
                    "name": "litellm_proxy_liveliness",
                    "status": "FAIL",
                    "detail": log_path.read_text()[-600:],
                }
            try:
                with urllib.request.urlopen(
                    f"http://127.0.0.1:{port}/health/liveliness", timeout=2
                ) as response:
                    if response.status == 200:
                        return {
                            "name": "litellm_proxy_liveliness",
                            "status": "PASS",
                            "detail": f"HTTP 200 on port {port}",
                        }
            except OSError:
                time.sleep(1)
        return {"name": "litellm_proxy_liveliness", "status": "FAIL", "detail": "timed out after 120 s"}
    finally:
        log_handle.close()
        proc.terminate()
        try:
            proc.wait(timeout=10)
        except subprocess.TimeoutExpired:
            proc.kill()


def _isolation_step(py: Path) -> dict:
    """The Phoenix server environment must not contain CrewAI or OpenAI."""
    code = (
        "import importlib.util as u, sys; "
        "bad=[m for m in ('crewai','openai','litellm') if u.find_spec(m)]; "
        "sys.exit(','.join(bad) if bad else 0)"
    )
    exit_code, out, _ = run([str(py), "-c", code])
    return {
        "name": "no_crewai_openai_in_phoenix_env",
        "status": "PASS" if exit_code == 0 else "FAIL",
        "detail": out or "crewai, openai and litellm are not installed",
    }


def validate(profile: str, python: str, keep: bool) -> dict:
    result: dict = {"profile": profile, "python": None, "steps": []}
    if profile in GPU_PROFILES:
        result["status"] = "SKIPPED"
        result["reason"] = (
            "GPU profile: cannot be validated on macOS; cai-validation-pending until Lab 00 runs in CAI"
        )
        return result
    tmp = Path(tempfile.mkdtemp(prefix=f"bni-profile-{profile}-"))
    try:
        venv = tmp / "venv"
        code, out, _ = run([python, "-m", "venv", str(venv)])
        py = venv / "bin" / "python"
        if code:
            return {**result, "status": "FAIL", "reason": "venv creation failed: " + out[-300:]}
        result["python"] = run([str(py), "-c", "import platform; print(platform.python_version())"])[1]
        if not result["python"].startswith("3.10."):
            return {**result, "status": "FAIL", "reason": f"expected Python 3.10, got {result['python']}"}

        def step(name, cmd, env=None, timeout=1500):
            code, out, secs = run(cmd, env=env, timeout=timeout)
            result["steps"].append(
                {
                    "name": name,
                    "status": "PASS" if code == 0 else "FAIL",
                    "seconds": secs,
                    "detail": out[-700:] if code else out[-200:],
                }
            )
            return code == 0

        lock = ROOT / PROFILES[profile]["lock"]
        pip_env = dict(os.environ, PIP_DISABLE_PIP_VERSION_CHECK="1")
        if not step(
            "pip_install_lock_only", [str(py), "-m", "pip", "install", "--quiet", "-r", str(lock)], pip_env
        ):
            return {**result, "status": "FAIL"}
        if not step("pip_check", [str(py), "-m", "pip", "check"]):
            return {**result, "status": "FAIL"}
        env = smoke_env(tmp)
        imports = "; ".join(f"import {name}" for name in IMPORTS[profile])
        step("imports", [str(py), "-c", imports], env)
        for number in LABS[profile]:
            code, out, secs = run([str(py), str(lab_script(number)), "--mode", "local"], env=env)
            lines = out.splitlines()
            status_line = next(
                (item for item in reversed(lines) if item.startswith("LAB_STATUS:")), "no LAB_STATUS line"
            )
            ok = code in (0, 3) and "status=FAIL" not in status_line
            result["steps"].append(
                {
                    "name": f"lab_{number}_local",
                    "status": "PASS" if ok else "FAIL",
                    "seconds": secs,
                    "detail": status_line if ok else out[-700:],
                }
            )
        if profile == "observability":
            result["steps"].append(phoenix_server_smoke(py, env, tmp))
            result["steps"].append(_isolation_step(py))
        if profile == "gateway":
            result["steps"].append(gateway_proxy_smoke(py, env))
        if profile == "dev-test":
            step(
                "ruff",
                [
                    str(py),
                    "-m",
                    "ruff",
                    "check",
                    "--no-cache",
                    "src",
                    "automation",
                    "scripts",
                    "tests",
                    "deployments",
                    "apps",
                    "data",
                ],
                env,
            )
            step("pytest", [str(py), "-m", "pytest", "-q", "-p", "no:cacheprovider"], env, timeout=1800)
        failed = [s["name"] for s in result["steps"] if s["status"] == "FAIL"]
        result["status"] = "FAIL" if failed else "PASS"
        if failed:
            result["failed_steps"] = failed
        return result
    finally:
        if keep:
            result["kept"] = str(tmp)
        else:
            shutil.rmtree(tmp, ignore_errors=True)


def main(argv=None) -> int:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--profile", action="append", help="Profile to validate (repeatable). Default: all")
    parser.add_argument("--python", default=shutil.which("python3.10") or "python3.10")
    parser.add_argument("--report", type=Path, default=ROOT / "build" / "profile-validation.json")
    parser.add_argument("--keep", action="store_true", help="Keep temporary virtual environments")
    args = parser.parse_args(argv)
    names = args.profile or list(PROFILES)
    unknown = set(names) - set(PROFILES)
    if unknown:
        parser.error(f"unknown profiles: {sorted(unknown)}")
    results = []
    for name in names:
        outcome = validate(name, args.python, args.keep)
        results.append(outcome)
        print(
            f"[{outcome['status']}] {name}"
            + (f" - {outcome.get('reason', '')}" if outcome.get("reason") else "")
        )
        for item in outcome["steps"]:
            print(f"    [{item['status']}] {item['name']}: {str(item.get('detail', ''))[:160]}")
    args.report.parent.mkdir(parents=True, exist_ok=True)
    args.report.write_text(
        json.dumps({"python": sys.version.split()[0], "results": results}, indent=2) + "\n"
    )
    return 1 if any(r["status"] == "FAIL" for r in results) else 0


if __name__ == "__main__":
    raise SystemExit(main())

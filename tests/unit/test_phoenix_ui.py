"""The Phoenix UI page must render: /healthz alone hid a Starlette 1.x incompatibility."""

from __future__ import annotations

import os
import re
import subprocess
import sys
import time
import urllib.error
import urllib.request
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[2]


def locked_version(lock: str, name: str) -> list[str]:
    text = (ROOT / "requirements" / lock).read_text()
    return re.findall(rf"^{name}==([0-9.]+)", text, flags=re.M)


def test_the_observability_profile_keeps_starlette_below_one() -> None:
    source = (ROOT / "requirements/observability.in").read_text()
    assert re.search(r"^starlette>=0\.\d+,<1\s*$", source, flags=re.M)
    for lock in ("observability.lock", "dev-test.lock"):
        versions = locked_version(lock, "starlette")
        assert versions and all(v.startswith("0.") for v in versions), (lock, versions)


def test_the_phoenix_ui_page_returns_200_through_the_launcher_environment(tmp_path) -> None:
    pytest.importorskip("phoenix")
    pytest.importorskip("starlette")
    sys.path.insert(0, str(ROOT))
    from deployments.cai.phoenix import app

    with __import__("socket").socket() as probe:
        probe.bind(("127.0.0.1", 0))
        port = probe.getsockname()[1]
    env = {
        "CDSW_APP_PORT": str(port),
        "PHOENIX_WORKING_DIR": str(tmp_path / "phoenix"),
        "PYTHON_EXECUTABLE": sys.executable,
        "PATH": os.environ["PATH"],
        "HOME": str(tmp_path),
    }
    process = subprocess.Popen(
        app.build_command(env),
        env=app.build_environment(env),
        stdout=subprocess.DEVNULL,
        stderr=subprocess.DEVNULL,
    )
    try:
        for _ in range(90):
            try:
                urllib.request.urlopen(f"http://127.0.0.1:{port}/healthz", timeout=1)
                break
            except OSError:
                time.sleep(1)
        else:
            pytest.fail("Phoenix did not become healthy")
        try:
            status = urllib.request.urlopen(f"http://127.0.0.1:{port}/", timeout=10).status
        except urllib.error.HTTPError as error:
            status = error.code
        assert status == 200, f"the UI page returned HTTP {status}"
    finally:
        process.terminate()
        process.wait(timeout=30)

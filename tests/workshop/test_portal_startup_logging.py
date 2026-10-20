"""A failed Portal start-up shows a generic message to the participant and logs the cause for the trainer."""

from __future__ import annotations

import logging
from pathlib import Path

import pytest

st_testing = pytest.importorskip("streamlit.testing.v1")

APP = str(Path(__file__).resolve().parents[2] / "apps" / "workshop-portal" / "app.py")


def test_startup_failure_is_logged_but_not_shown(monkeypatch, caplog):
    from bni_training.workshop.portal import service as service_module
    from bni_training.workshop.portal.ui import get_service

    get_service.clear()

    def broken(*_args, **_kwargs):
        raise FileNotFoundError("missing-example-file")

    monkeypatch.setattr(service_module.PortalService, "from_env", classmethod(broken))
    with caplog.at_level(logging.ERROR):
        at = st_testing.AppTest.from_file(APP, default_timeout=60).run()
    get_service.clear()

    shown = " ".join(error.value for error in at.error)
    assert "FileNotFoundError" in shown
    assert "missing-example-file" not in shown
    assert "missing-example-file" in caplog.text
    assert "Portal start-up failed" in caplog.text

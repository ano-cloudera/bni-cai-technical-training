"""Portal missions: what a participant sees, the group lock, and test-only data staying hidden."""

from __future__ import annotations

from pathlib import Path

import pytest
from helpers import wait_done

st_testing = pytest.importorskip("streamlit.testing.v1")
AppTest = st_testing.AppTest

APP = str(Path(__file__).resolve().parents[2] / "apps" / "workshop-portal" / "app.py")


@pytest.fixture(autouse=True)
def local_portal(monkeypatch, tmp_path):
    monkeypatch.setenv("PORTAL_MODE", "local")
    monkeypatch.setenv("PORTAL_MAX_RETRIES", "0")
    monkeypatch.setenv("WORKSHOP_RUNTIME_DIR", str(tmp_path / "runtime"))
    monkeypatch.delenv("LITELLM_BASE_URL", raising=False)
    monkeypatch.delenv("VLLM_BASE_URL", raising=False)
    from bni_training.workshop.portal.ui import get_service

    get_service.clear()
    yield
    service = get_service()
    get_service.clear()
    service.close()


def open_group(group: str) -> AppTest:
    at = AppTest.from_file(APP, default_timeout=120).run()
    at.sidebar.selectbox[0].select(group).run()
    assert not at.exception, at.exception
    return at


def page_text(at: AppTest) -> str:
    parts = [m.value for m in at.markdown] + [c.value for c in at.caption] + [s.value for s in at.subheader]
    parts += [b.label for b in at.button] + [c.value for c in at.code] + [w.value for w in at.warning]
    return "\n".join(str(p) for p in parts)


@pytest.mark.parametrize("group", [f"group_{i:02d}" for i in range(1, 11)])
def test_each_group_sees_its_mission_objective_tables_and_sample_questions(group) -> None:
    from bni_training.data.bundles import BundleCatalog

    bundle = BundleCatalog.load().for_group(group)
    text = page_text(open_group(group))
    assert bundle.mission_title in text and bundle.mission_objective in text
    assert "**Tables:** " + ", ".join(bundle.tables) in text
    for question in bundle.sample_questions:
        assert question in text
    for other in BundleCatalog.load().bundles.values():
        if other.group_id != group:
            assert other.mission_title not in text, "another group's mission must not appear"


def test_the_portal_never_shows_test_only_data() -> None:
    for group in ("group_06", "group_10"):
        text = page_text(open_group(group)).lower()
        assert "anomaly" not in text and "seeded" not in text


def test_clicking_a_sample_question_runs_it_locks_the_group_and_reset_is_needed_to_change() -> None:
    at = open_group("group_06")
    first = next(b for b in at.button if b.label.startswith("Show transaction count by account id"))
    first.click().run()
    ticket_key = next(k for k in at.session_state.to_dict() if k.endswith("::active_ticket"))
    wait_done(at.session_state[ticket_key], 30)
    at.run()
    assert at.sidebar.selectbox[0].disabled is True
    assert any("Locked to group_06" in c.value for c in at.sidebar.caption)
    assert len(at.chat_message) == 2 and "SELECT" in " ".join(c.value for c in at.code)


def test_participants_cannot_read_dataset_manifests_through_the_output_api(make_service) -> None:
    from bni_training.workshop.group_paths import UnsafePathError

    service = make_service()
    ctx = service.open_session("group_06")
    for name in ("dataset_manifest.json", "../../../../data/manifests/dataset_manifest.json"):
        with pytest.raises((UnsafePathError, FileNotFoundError)):
            service.read_output(ctx, name)

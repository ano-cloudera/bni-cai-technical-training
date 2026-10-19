from __future__ import annotations

import contextvars
import threading
import time
import urllib.error

import pytest

from bni_training.workshop.portal.config import PortalConfig, PortalConfigError
from bni_training.workshop.portal.gate import InferenceGate, TicketState


@pytest.fixture
def gate():
    created = []

    def make(**kwargs):
        g = InferenceGate(**{"retry_backoff_s": 0.0, **kwargs})
        created.append(g)
        return g

    yield make
    for g in created:
        g.close()


def submit(g, job, group="group_01", session="a" * 32):
    return g.submit(job, group_id=group, session_id=session)


def test_default_concurrency_is_three_and_configurable_from_the_environment() -> None:
    assert PortalConfig.from_env({}).max_concurrent_inference == 3
    assert PortalConfig.from_env({"PORTAL_MAX_CONCURRENT_INFERENCE": "5"}).max_concurrent_inference == 5
    for bad in ("0", "17", "abc"):
        with pytest.raises(PortalConfigError):
            PortalConfig.from_env({"PORTAL_MAX_CONCURRENT_INFERENCE": bad})
    assert InferenceGate().max_concurrent == 3


def test_never_more_than_the_limit_runs_at_once(gate) -> None:
    g = gate(max_concurrent=3)
    running, peak, lock = 0, 0, threading.Lock()

    def job(_token, _timeout):
        nonlocal running, peak
        with lock:
            running += 1
            peak = max(peak, running)
        time.sleep(0.03)
        with lock:
            running -= 1
        return "ok"

    tickets = [submit(g, job, session=f"{i:032x}") for i in range(24)]
    for t in tickets:
        assert t.wait(20)
    assert all(t.state is TicketState.COMPLETED for t in tickets)
    assert peak <= 3
    assert g.stats()["peak_processing"] <= 3


def test_queued_then_processing_then_completed_with_a_position(gate) -> None:
    g = gate(max_concurrent=1)
    release = threading.Event()
    first = submit(g, lambda t, to: release.wait(5) and "one")
    second = submit(g, lambda t, to: "two")
    third = submit(g, lambda t, to: "three")
    deadline = time.monotonic() + 5
    while first.state is not TicketState.PROCESSING and time.monotonic() < deadline:
        time.sleep(0.01)
    assert (first.state, second.state, third.state) == (
        TicketState.PROCESSING,
        TicketState.QUEUED,
        TicketState.QUEUED,
    )
    assert (second.position(), third.position()) == (1, 2)
    release.set()
    for t in (first, second, third):
        assert t.wait(5)
    assert [t.result for t in (first, second, third)] == ["one", "two", "three"]
    assert second.position() == 0


def test_overload_is_rejected_immediately_with_a_friendly_message(gate) -> None:
    g = gate(max_concurrent=1, max_queue=2)
    release = threading.Event()
    busy = submit(g, lambda t, to: release.wait(5))
    deadline = time.monotonic() + 5
    while busy.state is not TicketState.PROCESSING and time.monotonic() < deadline:
        time.sleep(0.01)
    queued = [submit(g, lambda t, to: 1) for _ in range(2)]
    rejected = submit(g, lambda t, to: 1)
    assert rejected.state is TicketState.REJECTED and rejected.done
    assert "busy" in rejected.message.lower() and "traceback" not in rejected.message.lower()
    release.set()
    for t in [busy, *queued]:
        assert t.wait(5)


def test_a_request_that_waits_too_long_in_the_queue_times_out(gate) -> None:
    g = gate(max_concurrent=1, queue_timeout_s=0.05)
    release = threading.Event()
    submit(g, lambda t, to: release.wait(5))
    waiting = submit(g, lambda t, to: "never")
    time.sleep(0.2)
    release.set()
    assert waiting.wait(5)
    assert waiting.state is TicketState.TIMED_OUT and "again" in waiting.message


def test_timeouts_and_server_errors_are_retried_then_succeed(gate) -> None:
    g = gate(max_retries=2)
    attempts = []

    def flaky(_t, _timeout):
        attempts.append(1)
        if len(attempts) == 1:
            raise TimeoutError()
        if len(attempts) == 2:
            raise urllib.error.HTTPError("http://x", 503, "unavailable", {}, None)
        return "finally"

    ticket = submit(g, flaky)
    assert ticket.wait(5)
    assert (ticket.state, ticket.result, ticket.attempts) == (TicketState.COMPLETED, "finally", 3)


def test_persistent_timeouts_end_as_timed_out_and_client_errors_are_not_retried(gate) -> None:
    g = gate(max_retries=2)

    def slow(_t, _timeout):
        raise TimeoutError()

    t1 = submit(g, slow)
    assert t1.wait(5) and (t1.state, t1.attempts) == (TicketState.TIMED_OUT, 3)

    def bad(_t, _timeout):
        raise urllib.error.HTTPError("http://x", 400, "bad request", {}, None)

    t2 = submit(g, bad)
    assert t2.wait(5) and (t2.state, t2.attempts) == (TicketState.FAILED, 1)
    assert "HTTPError" not in t2.message  # friendly text, not an exception name


def test_the_per_attempt_timeout_is_passed_to_the_job(gate) -> None:
    g = gate(request_timeout_s=7.5)
    t = submit(g, lambda token, timeout: timeout)
    assert t.wait(5) and t.result == 7.5


def test_cancel_a_queued_request_removes_it(gate) -> None:
    g = gate(max_concurrent=1)
    release = threading.Event()
    submit(g, lambda t, to: release.wait(5))
    queued = submit(g, lambda t, to: "x")
    assert queued.cancel() is True
    assert queued.state is TicketState.CANCELLED and queued.position() == 0
    assert queued.cancel() is False
    release.set()


def test_cancel_a_running_request_discards_its_answer(gate) -> None:
    g = gate(max_concurrent=1)
    started, release = threading.Event(), threading.Event()

    def job(_token, _timeout):
        started.set()
        release.wait(5)
        return "late answer"

    ticket = submit(g, job)
    assert started.wait(5)
    assert ticket.cancel() is True
    release.set()
    assert ticket.wait(5)
    assert ticket.state is TicketState.CANCELLED and ticket.result is None


def test_a_crashing_job_does_not_kill_the_worker(gate) -> None:
    g = gate(max_concurrent=1, max_retries=0)

    def boom(_t, _timeout):
        raise RuntimeError("secret internal detail")

    bad = submit(g, boom)
    good = submit(g, lambda t, to: "alive")
    assert bad.wait(5) and good.wait(5)
    assert bad.state is TicketState.FAILED and "secret" not in bad.message
    assert good.result == "alive"


def test_the_callers_context_variables_reach_the_worker(gate) -> None:
    g = gate()
    var = contextvars.ContextVar("who", default="nobody")
    var.set("group_07")
    t = submit(g, lambda token, timeout: var.get())
    assert t.wait(5) and t.result == "group_07"


def test_stats_expose_counts_only(gate) -> None:
    g = gate()
    assert set(g.stats()) == {"queued", "processing", "max_concurrent", "peak_processing"}

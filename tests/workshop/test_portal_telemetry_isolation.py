from __future__ import annotations

import json
import threading

import pytest
from helpers import wait_done

pytest.importorskip("opentelemetry.sdk")

from opentelemetry.sdk.trace import TracerProvider  # noqa: E402
from opentelemetry.sdk.trace.export import SimpleSpanProcessor  # noqa: E402
from opentelemetry.sdk.trace.export.in_memory_span_exporter import InMemorySpanExporter  # noqa: E402

from bni_training.workshop.group_context import SessionContext  # noqa: E402
from bni_training.workshop.portal.telemetry import trace_attributes  # noqa: E402

GROUPS = [f"group_{i:02d}" for i in range(1, 11)]


def test_trace_attributes_always_carry_group_and_session() -> None:
    ctx = SessionContext("group_07", "c" * 32)
    attrs = trace_attributes(ctx, "customer_segmentation")
    assert attrs["group_id"] == "group_07" and attrs["session.id"] == "c" * 32
    assert json.loads(attrs["metadata"]) == {"group_id": "group_07", "scenario_id": "customer_segmentation"}


def test_concurrent_groups_never_mix_span_metadata(make_service) -> None:
    exporter = InMemorySpanExporter()
    provider = TracerProvider()
    provider.add_span_processor(SimpleSpanProcessor(exporter))
    service = make_service(tracer=provider.get_tracer("test"), max_concurrent=3)
    sessions = []
    for group in GROUPS:
        for _ in range(2):
            sessions.append(service.state({}, service.open_session(group)))
    tickets: dict[str, object] = {}

    def run(state):
        tickets[state.ctx.session_id] = service.submit_question(
            state, f"Show account count by region for {state.ctx.group_id}"
        )

    threads = [threading.Thread(target=run, args=(s,)) for s in sessions]
    for t in threads:
        t.start()
    for t in threads:
        t.join()
    for ticket in tickets.values():
        wait_done(ticket, 30)
    spans = [s for s in exporter.get_finished_spans() if s.name == "portal.ask"]
    assert len(spans) == len(sessions) == 20
    owner = {s.ctx.session_id: s.ctx.group_id for s in sessions}
    for span in spans:
        attrs = dict(span.attributes)
        assert attrs["group_id"] == owner[attrs["session.id"]]
        assert json.loads(attrs["metadata"])["group_id"] == attrs["group_id"]
        other_groups = [g for g in GROUPS if g != attrs["group_id"]]
        assert not any(g in json.dumps(attrs) for g in other_groups)


def test_every_session_records_only_its_own_span_session_ids(make_service) -> None:
    exporter = InMemorySpanExporter()
    provider = TracerProvider()
    provider.add_span_processor(SimpleSpanProcessor(exporter))
    service = make_service(tracer=provider.get_tracer("test"))
    a = service.state({}, service.open_session("group_01"))
    b = service.state({}, service.open_session("group_02"))
    for state in (a, b):
        wait_done(service.submit_question(state, "Show account count by region"))
    by_session = {
        dict(s.attributes)["session.id"]: dict(s.attributes)["group_id"]
        for s in exporter.get_finished_spans()
    }
    assert by_session == {a.ctx.session_id: "group_01", b.ctx.session_id: "group_02"}

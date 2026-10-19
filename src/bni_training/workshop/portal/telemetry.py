from __future__ import annotations

import contextlib
import json
from collections.abc import Iterator, Mapping
from typing import Any

from bni_training.workshop.group_context import SessionContext


def trace_attributes(ctx: SessionContext, scenario_id: str) -> dict[str, Any]:
    """Span attributes for one request. Every portal span carries group_id and the session id."""
    return {
        "group_id": ctx.group_id,
        "session.id": ctx.session_id,
        "scenario_id": scenario_id,
        "openinference.span.kind": "CHAIN",
        "metadata": json.dumps({"group_id": ctx.group_id, "scenario_id": scenario_id}),
    }


class NoopTracer:
    @contextlib.contextmanager
    def start_as_current_span(self, name: str, attributes: Mapping[str, Any] | None = None) -> Iterator[None]:
        yield None


def build_tracer(
    endpoint: str, headers: Mapping[str, str] | None = None, project: str = "bni-workshop-portal"
):
    """OTLP/HTTP tracer for the shared Phoenix. No global provider is installed."""
    from opentelemetry.exporter.otlp.proto.http.trace_exporter import OTLPSpanExporter
    from opentelemetry.sdk.resources import Resource
    from opentelemetry.sdk.trace import TracerProvider
    from opentelemetry.sdk.trace.export import BatchSpanProcessor

    url = endpoint.rstrip("/")
    url = url if url.endswith("/v1/traces") else url + "/v1/traces"
    provider = TracerProvider(resource=Resource.create({"openinference.project.name": project}))
    provider.add_span_processor(
        BatchSpanProcessor(OTLPSpanExporter(endpoint=url, headers=dict(headers or {}) or None))
    )
    return provider.get_tracer("bni.workshop.portal")

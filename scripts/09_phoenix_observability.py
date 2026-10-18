from __future__ import annotations

import contextlib
import importlib.util
import json
import os
import socket
import subprocess
import sys
import tempfile
import time
import urllib.parse
import urllib.request

from bni_training.crew import run_crewai_question
from bni_training.labs import build_data_tool, build_settings, crewai_llm, require_env, run_lab
from bni_training.mock_llm import MockOpenAIServer
from bni_training.observability import safe_trace_attributes

DESCRIPTION = "Lab 09: generate real OpenInference traces and verify them in Phoenix."
PROJECT = "bni-credit-insight-lab09"
QUESTION = "What is the outstanding balance by region?"
SPAN_KINDS = {"AGENT", "CHAIN", "LLM", "TOOL"}


def free_port() -> int:
    with socket.socket() as sock:
        sock.bind(("127.0.0.1", 0))
        return sock.getsockname()[1]


def http_json(url: str, headers: dict | None = None, timeout: float = 10):
    with urllib.request.urlopen(
        urllib.request.Request(url, headers=headers or {}), timeout=timeout
    ) as response:
        return json.load(response)


@contextlib.contextmanager
def local_phoenix():
    """Start a real, temporary Phoenix server for local mode (needs the observability profile)."""
    port, grpc_port = free_port(), free_port()
    with tempfile.TemporaryDirectory() as working:
        env = dict(
            os.environ,
            PHOENIX_HOST="127.0.0.1",
            PHOENIX_PORT=str(port),
            PHOENIX_GRPC_PORT=str(grpc_port),
            PHOENIX_WORKING_DIR=working,
        )
        proc = subprocess.Popen(
            [sys.executable, "-m", "phoenix.server.main", "serve"],
            env=env,
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL,
        )
        try:
            deadline = time.monotonic() + 120
            while time.monotonic() < deadline:
                if proc.poll() is not None:
                    raise RuntimeError(f"Phoenix exited with code {proc.returncode} during startup")
                try:
                    with urllib.request.urlopen(f"http://127.0.0.1:{port}/healthz", timeout=2):
                        break
                except OSError:
                    time.sleep(1)
            else:
                raise RuntimeError("Phoenix did not become healthy within 120 s")
            yield f"http://127.0.0.1:{port}"
        finally:
            proc.terminate()
            try:
                proc.wait(timeout=15)
            except subprocess.TimeoutExpired:
                proc.kill()


@contextlib.contextmanager
def optional_local_phoenix():
    """Yield a temporary Phoenix URL, or None when the Phoenix server profile is not installed."""
    if importlib.util.find_spec("phoenix") is None:
        yield None
        return
    with local_phoenix() as url:
        yield url


def traces_url(base_url: str) -> str:
    return base_url.rstrip("/") + "/v1/traces"


def base_from_endpoint(endpoint: str) -> str:
    return endpoint.removesuffix("/").removesuffix("/v1/traces")


def fetch_spans(base_url: str, headers: dict, expected_min: int = 1, timeout: float = 45) -> list[dict]:
    url = f"{base_url}/v1/projects/{urllib.parse.quote(PROJECT)}/spans?limit=200"
    deadline = time.monotonic() + timeout
    spans: list[dict] = []
    while time.monotonic() < deadline:
        try:
            spans = http_json(url, headers).get("data", [])
        except OSError:
            spans = []
        if len(spans) >= expected_min:
            return spans
        time.sleep(1.5)
    return spans


def span_kind(span: dict) -> str:
    attributes = span.get("attributes") or {}
    flat = attributes.get("openinference.span.kind") or (attributes.get("openinference") or {}).get(
        "span", {}
    ).get("kind")
    return str(flat or span.get("span_kind") or "").upper()


def trace_workflow(endpoint_base: str | None, headers: dict, llm, settings, report, secret: str) -> None:
    from openinference.instrumentation import using_attributes
    from openinference.instrumentation.crewai import CrewAIInstrumentor
    from opentelemetry.exporter.otlp.proto.http.trace_exporter import OTLPSpanExporter
    from opentelemetry.sdk.resources import Resource
    from opentelemetry.sdk.trace import TracerProvider
    from opentelemetry.sdk.trace.export import SimpleSpanProcessor
    from opentelemetry.sdk.trace.export.in_memory_span_exporter import InMemorySpanExporter

    # Plain OpenTelemetry SDK + OTLP/HTTP, the protocol Phoenix ingests at /v1/traces. phoenix.otel.register()
    # is avoided on purpose: see docs/dependency-profiles.md.
    provider = TracerProvider(resource=Resource.create({"openinference.project.name": PROJECT}))
    if endpoint_base:
        provider.add_span_processor(
            SimpleSpanProcessor(OTLPSpanExporter(endpoint=traces_url(endpoint_base), headers=headers or None))
        )
    memory = InMemorySpanExporter()
    provider.add_span_processor(SimpleSpanProcessor(memory))
    CrewAIInstrumentor().instrument(tracer_provider=provider)
    try:
        from openinference.instrumentation.openai import OpenAIInstrumentor

        OpenAIInstrumentor().instrument(tracer_provider=provider)
    except ImportError:
        report.skipped("openai_instrumentation", "openinference-instrumentation-openai is not installed")
    attrs = safe_trace_attributes({"group_id": settings.group_id, "api_key": secret, "latency_ms": 12})
    try:
        with using_attributes(session_id=f"lab09-{settings.group_id}", metadata=attrs):
            result = run_crewai_question(build_data_tool(settings), llm, QUESTION)
    finally:
        provider.force_flush()
        CrewAIInstrumentor().uninstrument()
    local_spans = memory.get_finished_spans()
    (report.passed if local_spans else report.failed)(
        "spans_generated", f"{len(local_spans)} spans produced in-process"
    )
    (report.passed if result["tool_calls"] else report.failed)(
        "agent_called_tool", f"{len(result['tool_calls'])} data tool call(s)"
    )
    if endpoint_base:
        spans = fetch_spans(endpoint_base, headers, expected_min=len(local_spans))
        (report.passed if spans else report.failed)(
            "spans_in_phoenix", f"{len(spans)} spans stored in Phoenix project {PROJECT}"
        )
    else:
        spans = [{"attributes": dict(span.attributes or {})} for span in local_spans]
        report.skipped(
            "spans_in_phoenix",
            "The Phoenix server profile is not installed here; spans were verified in-process only",
        )
    kinds = sorted({k for k in map(span_kind, spans) if k})
    (report.passed if SPAN_KINDS & set(kinds) else report.failed)(
        "openinference_span_kinds", f"kinds: {kinds}"
    )
    dump = json.dumps(spans, default=str)
    group_ok = settings.group_id in dump
    (report.passed if group_ok else report.failed)(
        "group_id_attribute", f"{settings.group_id} present on stored spans"
    )
    leaked = bool(secret) and len(secret) >= 8 and secret in dump
    (report.failed if leaked else report.passed)(
        "no_secret_in_traces", "api_key attribute was filtered before tracing"
    )


def body(args, report):
    try:
        import opentelemetry.exporter.otlp.proto.http.trace_exporter  # noqa: F401
        from openinference.instrumentation.crewai import CrewAIInstrumentor  # noqa: F401
    except ImportError as exc:
        raise RuntimeError("Install the observability (or dev-test) dependency profile for lab 09") from exc
    secret = "lab09-secret-token-value"
    if args.mode == "local":
        with (
            MockOpenAIServer(reply="Traced mock summary.") as server,
            optional_local_phoenix() as phoenix_url,
        ):
            settings = build_settings(report, server.base_url)
            trace_workflow(
                phoenix_url, {}, crewai_llm(server.base_url, "local-placeholder"), settings, report, secret
            )
        report.skipped(
            "shared_phoenix_application",
            "Local mode starts a temporary Phoenix server, not the shared CAI Application",
        )
        report.skipped("gpu_monitoring", "GPU utilization is trainer-led in CAI (vLLM Application metrics)")
        return
    env = require_env(["PHOENIX_ENDPOINT", "VLLM_BASE_URL"])
    settings = build_settings(report)
    headers = (
        {"Authorization": f"Bearer {os.environ['PHOENIX_API_KEY']}"} if os.getenv("PHOENIX_API_KEY") else {}
    )
    llm = crewai_llm(
        env["VLLM_BASE_URL"], os.getenv("VLLM_API_KEY", ""), os.getenv("SERVED_MODEL_NAME", "qwen3.5-9b")
    )
    trace_workflow(base_from_endpoint(env["PHOENIX_ENDPOINT"]), headers, llm, settings, report, secret)


def main(argv=None) -> int:
    return run_lab("09", DESCRIPTION, body, argv)


if __name__ == "__main__":
    raise SystemExit(main(sys.argv[1:]))

from __future__ import annotations

import json
import threading
from http.server import BaseHTTPRequestHandler, HTTPServer

import pytest
from helpers import last_json

from bni_training.workshop.service_checks import (
    SERVICES,
    SPECS,
    check_services,
    health_url,
    overall,
    phase_requirements,
    redact_url,
)
from scripts.check_shared_services import main


class Server:
    """A tiny local HTTP server whose answer per path is configurable."""

    def __init__(self, routes: dict[str, int]):
        self.routes, self.seen = routes, []
        owner = self

        class Handler(BaseHTTPRequestHandler):
            def log_message(self, *args):
                pass

            def do_GET(self):
                owner.seen.append((self.path, self.headers.get("Authorization"), self.headers.get("api-key")))
                self.send_response(owner.routes.get(self.path, 404))
                self.end_headers()

        self._server = HTTPServer(("127.0.0.1", 0), Handler)
        threading.Thread(target=self._server.serve_forever, daemon=True).start()

    @property
    def url(self) -> str:
        return f"http://127.0.0.1:{self._server.server_port}"

    def stop(self) -> None:
        self._server.shutdown()
        self._server.server_close()


@pytest.fixture
def server():
    created = []

    def make(routes):
        created.append(Server(routes))
        return created[-1]

    yield make
    for s in created:
        s.stop()


HEALTH = {"/health": 200, "/readyz": 200, "/healthz": 200, "/health/liveliness": 200, "/_stcore/health": 200}


def full_env(base: str, **extra) -> dict:
    return {
        "VLLM_BASE_URL": base + "/v1",
        "QDRANT_URL": base,
        "PHOENIX_ENDPOINT": base + "/v1/traces",
        "LITELLM_BASE_URL": base + "/v1",
        "PORTAL_URL": base,
        **extra,
    }


def by_service(results) -> dict:
    return {r.service: r for r in results}


def test_health_urls_are_derived_from_each_services_own_setting() -> None:
    assert health_url(SPECS["vllm"], "https://v.example.invalid/v1") == "https://v.example.invalid/health"
    assert health_url(SPECS["qdrant"], "https://q.example.invalid") == "https://q.example.invalid/readyz"
    assert (
        health_url(SPECS["phoenix"], "https://p.example.invalid/v1/traces")
        == "https://p.example.invalid/healthz"
    )
    assert (
        health_url(SPECS["litellm"], "https://l.example.invalid/v1/")
        == "https://l.example.invalid/health/liveliness"
    )
    assert (
        health_url(SPECS["workshop-portal"], "https://w.example.invalid")
        == "https://w.example.invalid/_stcore/health"
    )


def test_urls_are_redacted_of_credentials_and_query_strings() -> None:
    assert (
        redact_url("https://user:pw@host.example.invalid:8443/a/b?token=abc#frag")
        == "https://host.example.invalid:8443/a/b"
    )
    assert "pw" not in health_url(SPECS["qdrant"], "https://user:pw@host.example.invalid?x=1")


def test_all_healthy_services_pass(server) -> None:
    results = check_services(full_env(server(HEALTH).url))
    assert {r.service: r.status for r in results} == {s: "PASS" for s in SERVICES} and overall(
        results
    ) == "PASS"


def test_a_required_service_returning_an_error_fails(server) -> None:
    srv = server({**HEALTH, "/readyz": 503})
    results = by_service(check_services(full_env(srv.url)))
    assert results["qdrant"].status == "FAIL" and results["vllm"].status == "PASS"
    assert overall(list(results.values())) == "FAIL"


def test_an_unreachable_required_service_fails_but_an_optional_one_is_skipped() -> None:
    env = {"VLLM_BASE_URL": "http://127.0.0.1:9/v1", "PHOENIX_ENDPOINT": "http://127.0.0.1:9"}
    results = by_service(check_services(env, services=("vllm", "phoenix"), phase="day2_morning", mode="cai"))
    assert results["vllm"].status == "FAIL" and results["phoenix"].status == "SKIPPED"
    assert "optional" in results["phoenix"].detail


def test_services_not_active_in_a_phase_are_skipped_with_a_reason(server) -> None:
    results = by_service(check_services(full_env(server(HEALTH).url), phase="day1"))
    assert results["litellm"].status == "SKIPPED" and "not active in phase day1" in results["litellm"].detail
    assert {results[s].status for s in ("vllm", "qdrant", "phoenix", "workshop-portal")} == {"PASS"}
    assert phase_requirements("day2_morning")["phoenix"] == "optional"
    assert phase_requirements("agent_studio_publication")["workshop-portal"] == "inactive"
    with pytest.raises(ValueError, match="Unknown phase"):
        phase_requirements("lunch")


def test_unconfigured_services_are_skipped_locally_and_fail_in_cai_mode() -> None:
    local = check_services({}, mode="local")
    assert {r.status for r in local} == {"SKIPPED"} and overall(local) == "SKIPPED"
    cai = by_service(check_services({}, mode="cai", phase="day1"))
    assert cai["vllm"].status == "FAIL" and "VLLM_BASE_URL is not set" in cai["vllm"].detail
    assert cai["litellm"].status == "SKIPPED"


def test_credentials_are_sent_but_never_reported(server) -> None:
    srv = server(HEALTH)
    secret = "sk-this-must-never-appear-1234567890"
    env = full_env(srv.url, VLLM_API_KEY=secret, QDRANT_API_KEY=secret + "q")
    results = check_services(env)
    assert secret not in json.dumps([r.as_dict() for r in results])
    sent = {path: (auth, key) for path, auth, key in srv.seen}
    assert sent["/health"][0] == f"Bearer {secret}" and sent["/readyz"][1] == secret + "q"


def test_authentication_failures_are_reported_without_the_key(server) -> None:
    srv = server({**HEALTH, "/health": 401})
    result = by_service(
        check_services(full_env(srv.url, VLLM_API_KEY="sk-secret-value-123456"), services=("vllm",))
    )["vllm"]
    assert result.status == "FAIL" and "authentication" in result.detail and "secret" not in result.detail


def test_an_unknown_service_is_rejected() -> None:
    with pytest.raises(ValueError, match="Unknown service"):
        check_services({}, services=("mainframe",))


def test_the_script_returns_the_right_exit_codes_and_never_starts_anything(
    server, monkeypatch, capsys
) -> None:
    srv = server(HEALTH)
    for key, value in full_env(srv.url).items():
        monkeypatch.setenv(key, value)
    assert main(["--mode", "cai"]) == 0
    out = json.loads(capsys.readouterr().out)
    assert out["overall"] == "PASS" and len(out["services"]) == 5
    srv.routes["/healthz"] = 500
    assert main(["--mode", "cai", "--services", "phoenix"]) == 1
    assert main(["--phase", "lunch"]) == 2
    for key in full_env("x"):
        monkeypatch.delenv(key)
    assert main(["--mode", "local"]) == 0
    assert last_json(capsys.readouterr().out)["overall"] == "SKIPPED"

"""Read-only health checks of the shared services. Never deploys, starts, or stops anything."""

from __future__ import annotations

import types
import urllib.error
import urllib.request
from collections.abc import Callable, Mapping
from dataclasses import dataclass
from pathlib import Path
from urllib.parse import urlsplit, urlunsplit

import yaml

from bni_training.data.dictionary import REPO_ROOT

PASS, FAIL, SKIPPED = "PASS", "FAIL", "SKIPPED"
SERVICES = ("vllm", "qdrant", "phoenix", "litellm", "workshop-portal")
LIFECYCLE = REPO_ROOT / "config" / "workshop" / "application-lifecycle.yaml"


@dataclass(frozen=True)
class ServiceSpec:
    key: str
    url_env: str
    path: str
    strip_suffixes: tuple[str, ...] = ()
    key_env: str | None = None
    key_header: str = "Authorization"
    key_prefix: str = "Bearer "


SPECS = types.MappingProxyType(
    {
        "vllm": ServiceSpec("vllm", "VLLM_BASE_URL", "/health", ("/v1",), "VLLM_API_KEY"),
        "qdrant": ServiceSpec("qdrant", "QDRANT_URL", "/readyz", (), "QDRANT_API_KEY", "api-key", ""),
        "phoenix": ServiceSpec(
            "phoenix",
            "PHOENIX_UI_URL",
            "/healthz",
            (),
            "PHOENIX_API_KEY",
        ),
        "litellm": ServiceSpec(
            "litellm", "LITELLM_BASE_URL", "/health/liveliness", ("/v1",), "LITELLM_API_KEY"
        ),
        "workshop-portal": ServiceSpec(
            "workshop-portal", "WORKSHOP_PORTAL_URL", "/_stcore/health"
        ),
    }
)


@dataclass(frozen=True)
class ServiceResult:
    service: str
    status: str
    detail: str
    required: bool

    def as_dict(self) -> dict:
        return {
            "service": self.service,
            "status": self.status,
            "detail": self.detail,
            "required": self.required,
        }


def redact_url(url: str) -> str:
    """scheme://host[:port]/path only: no credentials, query string, or fragment."""
    parts = urlsplit(url)
    host = parts.hostname or ""
    netloc = f"{host}:{parts.port}" if parts.port else host
    return urlunsplit((parts.scheme, netloc, parts.path, "", ""))


def health_url(spec: ServiceSpec, base: str) -> str:
    parts = urlsplit(base.strip())
    path = parts.path.rstrip("/")
    for suffix in spec.strip_suffixes:
        if path.endswith(suffix):
            path = path[: -len(suffix)]
    return urlunsplit((parts.scheme, parts.netloc.split("@")[-1], path + spec.path, "", ""))


def default_fetch(url: str, headers: Mapping[str, str], timeout: float) -> int:
    request = urllib.request.Request(url, headers=dict(headers))
    with urllib.request.urlopen(request, timeout=timeout) as response:  # noqa: S310 - operator-supplied https URL
        return response.status


def phase_requirements(phase: str | None, lifecycle_path: Path = LIFECYCLE) -> dict[str, str]:
    """{service: required|optional|inactive} for a phase; every service is 'required' without one."""
    if phase is None:
        return {s: "required" for s in SERVICES}
    phases = yaml.safe_load(lifecycle_path.read_text(encoding="utf-8"))["phases"]
    if phase not in phases:
        raise ValueError(f"Unknown phase {phase!r}; choose one of {', '.join(phases)}")
    spec = phases[phase]
    levels = {s: "inactive" for s in SERVICES}
    for s in spec.get("optional", ()):
        levels[s] = "optional"
    for s in spec["active"]:
        levels[s] = "required"
    return levels


def check_services(
    env: Mapping[str, str],
    *,
    services: tuple[str, ...] = SERVICES,
    phase: str | None = None,
    mode: str = "cai",
    fetch: Callable[[str, Mapping[str, str], float], int] = default_fetch,
    timeout: float = 5.0,
    lifecycle_path: Path = LIFECYCLE,
) -> list[ServiceResult]:
    """PASS (reachable), FAIL (required but unreachable or unconfigured in cai mode), or SKIPPED."""
    levels = phase_requirements(phase, lifecycle_path)
    results = []
    for key in services:
        if key not in SPECS:
            raise ValueError(f"Unknown service {key!r}")
        spec, level = SPECS[key], levels[key]
        if level == "inactive":
            results.append(ServiceResult(key, SKIPPED, f"not active in phase {phase}", False))
            continue
        required = level == "required"
        base = env.get(spec.url_env, "")
        if not base:
            if required and mode == "cai":
                results.append(ServiceResult(key, FAIL, f"{spec.url_env} is not set", True))
            else:
                results.append(ServiceResult(key, SKIPPED, f"{spec.url_env} is not set", required))
            continue
        url = health_url(spec, base)
        headers = {}
        secret = env.get(spec.key_env, "") if spec.key_env else ""
        if secret:
            headers[spec.key_header] = f"{spec.key_prefix}{secret}"
        try:
            status = fetch(url, headers, timeout)
            ok = 200 <= status < 400
            detail = f"{redact_url(url)} -> HTTP {status}"
            results.append(ServiceResult(key, PASS if ok else FAIL, detail, required))
        except urllib.error.HTTPError as exc:
            kind = "authentication" if exc.code in (401, 403) else f"HTTP {exc.code}"
            results.append(
                ServiceResult(key, FAIL if required else SKIPPED, f"{redact_url(url)} -> {kind}", required)
            )
        except (urllib.error.URLError, OSError, TimeoutError) as exc:
            reason = type(exc).__name__
            status = FAIL if required else SKIPPED
            note = "" if required else " (optional in this phase)"
            results.append(
                ServiceResult(key, status, f"{redact_url(url)} unreachable: {reason}{note}", required)
            )
    return results


def overall(results: list[ServiceResult]) -> str:
    return (
        FAIL
        if any(r.status == FAIL for r in results)
        else (PASS if any(r.status == PASS for r in results) else SKIPPED)
    )

from __future__ import annotations

import os
from collections.abc import Mapping
from dataclasses import dataclass, field

DEFAULT_MAX_CONCURRENT = 3


class PortalConfigError(ValueError):
    pass


def _number(env: Mapping[str, str], name: str, default: float, low: float, high: float, cast=float):
    raw = env.get(name)
    if raw in (None, ""):
        return cast(default)
    try:
        value = cast(raw)
    except ValueError as exc:
        raise PortalConfigError(f"{name} must be a number") from exc
    if not low <= value <= high:
        raise PortalConfigError(f"{name} must be between {low} and {high}")
    return value


@dataclass(frozen=True)
class PortalConfig:
    mode: str = "cai"
    llm_route: str = "auto"
    max_concurrent_inference: int = DEFAULT_MAX_CONCURRENT
    max_queue_depth: int = 60
    queue_timeout_s: float = 120.0
    request_timeout_s: float = 60.0
    max_retries: int = 2
    retry_backoff_s: float = 1.0
    max_tokens: int = 512
    enforce_single_instance: bool = True
    data_backend: str = "csv"
    llm_base_url: str = field(default="", repr=False)
    llm_model: str = "qwen3.5-9b"
    llm_api_key: str = field(default="", repr=False)
    disable_thinking: bool = (
        True  # the workshop model is Qwen3.5; its thinking text would fill the token budget
    )

    @classmethod
    def from_env(cls, env: Mapping[str, str] | None = None) -> PortalConfig:
        env = dict(os.environ if env is None else env)
        mode = env.get("PORTAL_MODE", "cai").lower()
        if mode not in {"local", "cai"}:
            raise PortalConfigError("PORTAL_MODE must be local or cai")
        route = env.get("PORTAL_LLM_ROUTE", "auto").lower()
        if route not in {"auto", "litellm", "vllm"}:
            raise PortalConfigError("PORTAL_LLM_ROUTE must be auto, litellm, or vllm")
        litellm_url, vllm_url = env.get("LITELLM_BASE_URL", ""), env.get("VLLM_BASE_URL", "")
        use_litellm = route == "litellm" or (route == "auto" and bool(litellm_url))
        if use_litellm:
            base, model, key = (
                litellm_url,
                env.get("PORTAL_LITELLM_MODEL", "qwen-primary"),
                env.get("LITELLM_API_KEY", ""),
            )
        else:
            base, model, key = (
                vllm_url,
                env.get("SERVED_MODEL_NAME", "qwen3.5-9b"),
                env.get("VLLM_API_KEY", ""),
            )
        backend = env.get("DATA_BACKEND", "csv").lower()
        if backend not in {"csv", "impala"}:
            raise PortalConfigError("DATA_BACKEND must be csv or impala")
        return cls(
            mode=mode,
            llm_route="litellm" if use_litellm else "vllm",
            max_concurrent_inference=_number(
                env, "PORTAL_MAX_CONCURRENT_INFERENCE", DEFAULT_MAX_CONCURRENT, 1, 16, int
            ),
            max_queue_depth=_number(env, "PORTAL_MAX_QUEUE_DEPTH", 60, 1, 500, int),
            queue_timeout_s=_number(env, "PORTAL_QUEUE_TIMEOUT_S", 120, 1, 3600),
            request_timeout_s=_number(env, "PORTAL_REQUEST_TIMEOUT_S", 60, 1, 600),
            max_retries=_number(env, "PORTAL_MAX_RETRIES", 2, 0, 5, int),
            retry_backoff_s=_number(env, "PORTAL_RETRY_BACKOFF_S", 1.0, 0, 60),
            max_tokens=_number(env, "PORTAL_MAX_TOKENS", 512, 16, 4096, int),
            enforce_single_instance=env.get("PORTAL_ENFORCE_SINGLE_INSTANCE", "true").lower() != "false",
            data_backend=backend,
            llm_base_url=base,
            llm_model=model,
            llm_api_key=key,
            disable_thinking=env.get("PORTAL_DISABLE_THINKING", "true").strip().lower() != "false",
        )

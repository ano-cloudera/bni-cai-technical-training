from __future__ import annotations

import json
import os
import re
from collections.abc import Iterator, Mapping
from urllib.parse import urlsplit, urlunsplit
from urllib.request import Request, urlopen


def model_request_extras(model: str, env: Mapping[str, str] | None = None) -> dict:
    """Extra request fields for a model.

    Qwen3.5 thinking is switched off so the token budget goes to the answer.

    VLLM_DISABLE_THINKING: "auto" (default, Qwen3.5 models only), "true" (always) or "false" (never).
    """
    source = os.environ if env is None else env
    setting = source.get("VLLM_DISABLE_THINKING", "auto").strip().lower()
    is_qwen35 = model.lower().replace("_", "-").startswith("qwen3.5")
    if setting == "true" or (setting == "auto" and is_qwen35):
        return {"chat_template_kwargs": {"enable_thinking": False}}
    return {}


_THINK_BLOCK = re.compile(r"<think>.*?</think>", re.S | re.I)


def visible_answer(text: str) -> str:
    """Text that may be shown to participants: no reasoning blocks, no leaked thinking transcript."""
    cleaned = _THINK_BLOCK.sub("", text or "").strip()
    if "</think>" in cleaned.lower():
        cleaned = re.split(r"</think>", cleaned, flags=re.I)[-1].strip()
    if cleaned.lower().startswith(("thinking process", "<think>")):
        return ""
    return cleaned


class OpenAICompatibleClient:
    def __init__(
        self,
        base_url: str,
        api_key: str,
        model: str = "qwen3.5-9b",
        transport=None,
        extra_body: dict | None = None,
    ):
        self.base_url = base_url.rstrip("/")
        self._api_key = api_key
        self.model = model
        self._transport = transport
        self.extra_body = dict(extra_body or {})

    def __repr__(self) -> str:
        return f"OpenAICompatibleClient(base_url={self.base_url!r}, model={self.model!r}, api_key='***')"

    def _headers(self) -> dict[str, str]:
        return {"Authorization": f"Bearer {self._api_key}", "Content-Type": "application/json"}

    def chat(
        self,
        messages: list[dict],
        temperature: float = 0.0,
        max_tokens: int = 512,
        timeout: float = 90,
        extra_body: dict | None = None,
    ) -> dict:
        payload = {
            "model": self.model,
            "messages": messages,
            "temperature": temperature,
            "max_tokens": max_tokens,
            **self.extra_body,
            **(extra_body or {}),
        }
        if self._transport:
            return self._transport("/chat/completions", payload)
        request = Request(
            self.base_url + "/chat/completions",
            data=json.dumps(payload).encode(),
            headers=self._headers(),
        )
        with urlopen(request, timeout=timeout) as response:
            return json.load(response)

    def stream_chat(
        self,
        messages: list[dict],
        temperature: float = 0.0,
        max_tokens: int = 512,
        extra_body: dict | None = None,
    ) -> Iterator[str]:
        """Yield content deltas from a streaming chat completion (server-sent events)."""
        payload = {
            "model": self.model,
            "messages": messages,
            "temperature": temperature,
            "max_tokens": max_tokens,
            **self.extra_body,
            **(extra_body or {}),
            "stream": True,
        }
        request = Request(
            self.base_url + "/chat/completions", data=json.dumps(payload).encode(), headers=self._headers()
        )
        with urlopen(request, timeout=90) as response:
            for raw in response:
                line = raw.decode().strip()
                if not line.startswith("data:"):
                    continue
                data = line[len("data:") :].strip()
                if data == "[DONE]":
                    return
                delta = json.loads(data)["choices"][0].get("delta", {})
                if delta.get("content"):
                    yield delta["content"]

    def health(self) -> dict:
        request = Request(self.base_url + "/models", headers={"Authorization": f"Bearer {self._api_key}"})
        with urlopen(request, timeout=15) as response:
            return json.load(response)

    def server_health(self) -> int:
        """Return the HTTP status of the server-level /health endpoint (outside the /v1 prefix)."""
        parts = urlsplit(self.base_url)
        root = urlunsplit((parts.scheme, parts.netloc, "/health", "", ""))
        with urlopen(Request(root, headers={"Authorization": f"Bearer {self._api_key}"}), timeout=15) as r:
            return r.status

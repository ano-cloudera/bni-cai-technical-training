from __future__ import annotations

import json
from collections.abc import Iterator
from urllib.parse import urlsplit, urlunsplit
from urllib.request import Request, urlopen


class OpenAICompatibleClient:
    def __init__(self, base_url: str, api_key: str, model: str = "qwen3.5-9b", transport=None):
        self.base_url = base_url.rstrip("/")
        self._api_key = api_key
        self.model = model
        self._transport = transport

    def __repr__(self) -> str:
        return f"OpenAICompatibleClient(base_url={self.base_url!r}, model={self.model!r}, api_key='***')"

    def _headers(self) -> dict[str, str]:
        return {"Authorization": f"Bearer {self._api_key}", "Content-Type": "application/json"}

    def chat(self, messages: list[dict], temperature: float = 0.0, max_tokens: int = 512) -> dict:
        payload = {
            "model": self.model,
            "messages": messages,
            "temperature": temperature,
            "max_tokens": max_tokens,
        }
        if self._transport:
            return self._transport("/chat/completions", payload)
        request = Request(
            self.base_url + "/chat/completions",
            data=json.dumps(payload).encode(),
            headers=self._headers(),
        )
        with urlopen(request, timeout=90) as response:
            return json.load(response)

    def stream_chat(
        self, messages: list[dict], temperature: float = 0.0, max_tokens: int = 512
    ) -> Iterator[str]:
        """Yield content deltas from a streaming chat completion (server-sent events)."""
        payload = {
            "model": self.model,
            "messages": messages,
            "temperature": temperature,
            "max_tokens": max_tokens,
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

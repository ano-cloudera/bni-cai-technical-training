from __future__ import annotations

import json
from urllib.request import Request, urlopen


class OpenAICompatibleClient:
    def __init__(self, base_url: str, api_key: str, model: str = "qwen3.5-9b", transport=None):
        self.base_url = base_url.rstrip("/")
        self._api_key = api_key
        self.model = model
        self._transport = transport

    def __repr__(self) -> str:
        return f"OpenAICompatibleClient(base_url={self.base_url!r}, model={self.model!r}, api_key='***')"

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
            headers={"Authorization": f"Bearer {self._api_key}", "Content-Type": "application/json"},
        )
        with urlopen(request, timeout=90) as response:
            return json.load(response)

    def health(self) -> dict:
        request = Request(self.base_url + "/models", headers={"Authorization": f"Bearer {self._api_key}"})
        with urlopen(request, timeout=15) as response:
            return json.load(response)

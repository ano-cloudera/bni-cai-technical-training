from __future__ import annotations

import json
import time
from urllib.request import Request, urlopen


class AgentStudioClient:
    def __init__(self, base_url: str, api_key: str, transport=None, sleep=time.sleep):
        self.base_url = base_url.rstrip("/")
        self._api_key = api_key
        self.transport = transport
        self.sleep = sleep

    def __repr__(self):
        return f"AgentStudioClient(base_url={self.base_url!r}, api_key='***')"

    def _call(self, method, path, body=None):
        if self.transport:
            return self.transport(method, path, body)
        request = Request(
            self.base_url + path,
            method=method,
            data=json.dumps(body).encode() if body else None,
            headers={"Authorization": f"Bearer {self._api_key}", "Content-Type": "application/json"},
        )
        with urlopen(request, timeout=60) as response:
            return json.load(response)

    def start(self, inputs: dict) -> str:
        result = self._call("POST", "/start", inputs)
        trace = result.get("trace_id") or result.get("id")
        if not trace:
            raise RuntimeError("Agent Studio response did not include a trace ID")
        return trace

    def poll(self, trace_id: str, timeout_seconds: int = 120, poll_seconds: float = 2):
        deadline = time.monotonic() + timeout_seconds
        while time.monotonic() < deadline:
            result = self._call("GET", f"/status/{trace_id}")
            status = str(result.get("status", "")).lower()
            if status in {"completed", "succeeded", "success"}:
                return result
            if status in {"failed", "error", "cancelled"}:
                raise RuntimeError(f"Agent Studio workflow ended with status {status}")
            self.sleep(poll_seconds)
        raise TimeoutError("Agent Studio workflow polling timed out")

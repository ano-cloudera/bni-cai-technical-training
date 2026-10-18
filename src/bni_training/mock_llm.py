"""In-process OpenAI-compatible mock server for LOCAL lab mode only.

It exists so that the complete client, CrewAI, and tracing code paths can run without a GPU. It is
never used in ``--mode cai``. Behavior is scripted and deterministic:

* ``GET /health`` and ``GET /v1/models`` return healthy responses.
* ``POST /v1/chat/completions`` supports non-streaming and ``stream=true`` (server-sent events).
* When the request offers ``tools`` and has no tool result yet, the mock asks for the first tool.
* ``fail_first`` makes the first N chat requests return HTTP 500 (used to exercise retry/fallback).
"""

from __future__ import annotations

import json
import re
import threading
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer

MODEL_NAME = "qwen3.5-9b"
_QUESTION = re.compile(r"participant question:\s*(.+?)\.\s", re.I | re.S)
DEFAULT_QUESTION = "What is the outstanding balance by region?"


class MockOpenAIServer:
    def __init__(
        self, model: str = MODEL_NAME, reply: str = "Mock reply: workshop endpoint ready", fail_first: int = 0
    ):
        self.model = model
        self.reply = reply
        self.fail_first = fail_first
        self.requests: list[dict] = []
        self._lock = threading.Lock()
        self._server: ThreadingHTTPServer | None = None
        self._thread: threading.Thread | None = None

    @property
    def base_url(self) -> str:
        assert self._server is not None, "server is not running"
        return f"http://127.0.0.1:{self._server.server_port}/v1"

    def _reply_for(self, body: dict) -> tuple[dict, str]:
        messages = body.get("messages", [])
        tools = body.get("tools") or []
        if tools and not any(m.get("role") == "tool" for m in messages):
            text = " ".join(str(m.get("content") or "") for m in messages if m.get("role") == "user")
            found = _QUESTION.search(text + " ")
            question = found.group(1).strip() if found else DEFAULT_QUESTION
            name = tools[0]["function"]["name"]
            return (
                {
                    "role": "assistant",
                    "content": None,
                    "tool_calls": [
                        {
                            "id": "call_mock_1",
                            "type": "function",
                            "function": {"name": name, "arguments": json.dumps({"question": question})},
                        }
                    ],
                },
                "tool_calls",
            )
        prompt = " ".join(str(m.get("content") or "") for m in messages)
        content = (
            f"Thought: I now know the final answer\nFinal Answer: {self.reply}"
            if "Final Answer" in prompt
            else self.reply
        )
        return {"role": "assistant", "content": content}, "stop"

    def start(self) -> "MockOpenAIServer":
        owner = self

        class Handler(BaseHTTPRequestHandler):
            def log_message(self, *args):  # silence request logging
                pass

            def _json(self, payload: dict, status: int = 200) -> None:
                data = json.dumps(payload).encode()
                self.send_response(status)
                self.send_header("Content-Type", "application/json")
                self.send_header("Content-Length", str(len(data)))
                self.end_headers()
                self.wfile.write(data)

            def do_GET(self):
                if self.path.endswith("/models"):
                    self._json({"object": "list", "data": [{"id": owner.model, "object": "model"}]})
                elif self.path == "/health":
                    self._json({"status": "ok"})
                else:
                    self._json({"error": "not found"}, 404)

            def do_POST(self):
                body = json.loads(self.rfile.read(int(self.headers.get("Content-Length", 0))) or b"{}")
                with owner._lock:
                    owner.requests.append(body)
                    failing = len(owner.requests) <= owner.fail_first
                if failing:
                    self._json({"error": "mock failure"}, 500)
                    return
                message, finish = owner._reply_for(body)
                if body.get("stream"):
                    self.send_response(200)
                    self.send_header("Content-Type", "text/event-stream")
                    self.end_headers()
                    for word in (message.get("content") or "").split(" "):
                        chunk = {"choices": [{"index": 0, "delta": {"content": word + " "}}]}
                        self.wfile.write(f"data: {json.dumps(chunk)}\n\n".encode())
                    self.wfile.write(b"data: [DONE]\n\n")
                    return
                self._json(
                    {
                        "id": "mock-1",
                        "object": "chat.completion",
                        "created": 0,
                        "model": owner.model,
                        "choices": [{"index": 0, "finish_reason": finish, "message": message}],
                        "usage": {"prompt_tokens": 8, "completion_tokens": 8, "total_tokens": 16},
                    }
                )

        self._server = ThreadingHTTPServer(("127.0.0.1", 0), Handler)
        self._thread = threading.Thread(target=self._server.serve_forever, daemon=True)
        self._thread.start()
        return self

    def stop(self) -> None:
        if self._server:
            self._server.shutdown()
            self._server.server_close()
            self._server = None

    def __enter__(self) -> "MockOpenAIServer":
        return self.start()

    def __exit__(self, *exc) -> None:
        self.stop()

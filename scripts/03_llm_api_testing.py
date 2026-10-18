from __future__ import annotations

import os
import sys
from urllib.error import URLError

from bni_training.labs import require_env, run_lab
from bni_training.llm_client import OpenAICompatibleClient
from bni_training.mock_llm import MockOpenAIServer

DESCRIPTION = "Lab 03: test /health, /v1/models, one non-streaming and one streaming chat request."


def exercise(client: OpenAICompatibleClient, report) -> None:
    try:
        status = client.server_health()
        (report.passed if status < 400 else report.failed)("health", f"/health returned {status}")
    except (URLError, OSError) as exc:
        report.failed("health", f"/health unreachable: {exc}")
    models = [item["id"] for item in client.health()["data"]]
    (report.passed if client.model in models else report.failed)("models", f"served models: {models}")
    reply = client.chat([{"role": "user", "content": "Reply with: workshop endpoint ready"}], max_tokens=32)
    text = reply["choices"][0]["message"]["content"]
    (report.passed if text else report.failed)("chat_non_streaming", text[:80])
    streamed = "".join(
        client.stream_chat(
            [{"role": "user", "content": "Reply with: workshop endpoint ready"}], max_tokens=32
        )
    )
    (report.passed if streamed.strip() else report.failed)("chat_streaming", streamed.strip()[:80])


def body(args, report):
    if args.mode == "local":
        with MockOpenAIServer() as server:
            exercise(OpenAICompatibleClient(server.base_url, "local-placeholder"), report)
        report.skipped(
            "real_vllm_endpoint", "Local mode tests the client against an in-process mock, not vLLM"
        )
        return
    env = require_env(["VLLM_BASE_URL"])
    client = OpenAICompatibleClient(
        env["VLLM_BASE_URL"], os.getenv("VLLM_API_KEY", ""), os.getenv("SERVED_MODEL_NAME", "qwen3.5-9b")
    )
    exercise(client, report)


def main(argv=None) -> int:
    return run_lab("03", DESCRIPTION, body, argv)


if __name__ == "__main__":
    raise SystemExit(main(sys.argv[1:]))

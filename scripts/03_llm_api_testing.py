from __future__ import annotations

import sys
from urllib.error import URLError

from bni_training.labs import run_lab, shared_llm_settings
from bni_training.llm_client import OpenAICompatibleClient, model_request_extras
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
    prompt = [{"role": "user", "content": "Reply with: workshop endpoint ready"}]
    text = client.chat(prompt, max_tokens=32)["choices"][0]["message"]["content"]
    (report.passed if text else report.failed)("chat_non_streaming", text[:80])
    streamed = "".join(client.stream_chat(prompt, max_tokens=32))
    (report.passed if streamed.strip() else report.failed)("chat_streaming", streamed.strip()[:80])


def body(args, report):
    if args.mode == "local":
        with MockOpenAIServer() as server:
            exercise(
                OpenAICompatibleClient(
                    server.base_url,
                    "local-placeholder",
                    extra_body=model_request_extras("qwen3.5-9b"),
                ),
                report,
            )
        report.skipped(
            "real_vllm_endpoint", "Local mode tests the client against an in-process mock, not vLLM"
        )
        return
    url, key, model = shared_llm_settings()
    exercise(OpenAICompatibleClient(url, key, model, extra_body=model_request_extras(model)), report)


def main(argv=None) -> int:
    return run_lab("03", DESCRIPTION, body, argv, participant=True)


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))

"""Qwen3.5 thinking is disabled in workshop requests; other models are left alone."""

from __future__ import annotations

import io
import json

import pytest

from bni_training import llm_client
from bni_training.llm_client import OpenAICompatibleClient, model_request_extras, visible_answer

NO_THINKING = {"chat_template_kwargs": {"enable_thinking": False}}
MESSAGES = [{"role": "user", "content": "hi"}]


def recording_client(model: str, **kwargs):
    sent: list[dict] = []

    def transport(path: str, payload: dict) -> dict:
        sent.append(payload)
        return {"choices": [{"message": {"content": "ok"}}]}

    return OpenAICompatibleClient("http://x/v1", "key", model, transport=transport, **kwargs), sent


def test_qwen35_requests_carry_enable_thinking_false_in_normal_chat() -> None:
    client, sent = recording_client("qwen3.5-9b", extra_body=model_request_extras("qwen3.5-9b", {}))
    client.chat(MESSAGES)
    assert sent[0]["chat_template_kwargs"] == {"enable_thinking": False}
    assert sent[0]["model"] == "qwen3.5-9b" and sent[0]["messages"] == MESSAGES


def test_the_exercise_style_call_with_per_call_extras_keeps_the_model_fields() -> None:
    client, sent = recording_client("qwen3.5-9b")
    client.chat(MESSAGES, max_tokens=80, extra_body=model_request_extras("qwen3.5-9b", {}))
    assert sent[0]["chat_template_kwargs"] == {"enable_thinking": False} and sent[0]["max_tokens"] == 80


class FakeResponse(io.BytesIO):
    def __enter__(self):
        return self

    def __exit__(self, *exc):
        return False


def test_qwen35_streaming_requests_carry_enable_thinking_false(monkeypatch) -> None:
    captured = {}

    def fake_urlopen(request, timeout=0):
        captured.update(json.loads(request.data))
        return FakeResponse(b'data: {"choices":[{"delta":{"content":"hello"}}]}\n\ndata: [DONE]\n\n')

    monkeypatch.setattr(llm_client, "urlopen", fake_urlopen)
    client = OpenAICompatibleClient(
        "http://x/v1", "key", "qwen3.5-9b", extra_body=model_request_extras("qwen3.5-9b", {})
    )
    assert "".join(client.stream_chat(MESSAGES)) == "hello"
    assert captured["stream"] is True and captured["chat_template_kwargs"] == {"enable_thinking": False}


@pytest.mark.parametrize("model", ["llama-3.1-8b", "gpt-4o-mini", "qwen2.5-7b", "mistral-7b"])
def test_unrelated_models_are_not_forced_into_qwen_configuration(model) -> None:
    assert model_request_extras(model, {}) == {}
    client, sent = recording_client(model, extra_body=model_request_extras(model, {}))
    client.chat(MESSAGES)
    assert "chat_template_kwargs" not in sent[0]


def test_the_behaviour_is_configurable() -> None:
    assert model_request_extras("qwen3.5-9b", {"VLLM_DISABLE_THINKING": "false"}) == {}
    assert model_request_extras("llama-3", {"VLLM_DISABLE_THINKING": "true"}) == NO_THINKING
    assert model_request_extras("Qwen3.5-9B", {"VLLM_DISABLE_THINKING": "auto"}) == NO_THINKING


def test_a_client_without_extras_sends_the_plain_payload() -> None:
    client, sent = recording_client("qwen3.5-9b")
    client.chat(MESSAGES)
    assert set(sent[0]) == {"model", "messages", "temperature", "max_tokens"}


def test_raw_reasoning_is_never_shown_to_participants() -> None:
    assert visible_answer("<think>secret plan</think>Final sentence.") == "Final sentence."
    assert visible_answer("Thinking Process:\n1. analyze the request") == ""
    assert visible_answer("plain answer") == "plain answer"
    assert visible_answer("hidden</think>shown") == "shown"

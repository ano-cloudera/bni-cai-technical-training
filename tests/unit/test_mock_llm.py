from __future__ import annotations

import pytest

from bni_training.llm_client import OpenAICompatibleClient
from bni_training.mock_llm import MockOpenAIServer


def test_mock_server_supports_health_models_chat_and_streaming() -> None:
    with MockOpenAIServer(reply="hello world") as server:
        client = OpenAICompatibleClient(server.base_url, "k")
        assert client.server_health() == 200
        assert client.health()["data"][0]["id"] == "qwen3.5-9b"
        assert (
            client.chat([{"role": "user", "content": "hi"}])["choices"][0]["message"]["content"]
            == "hello world"
        )
        assert "".join(client.stream_chat([{"role": "user", "content": "hi"}])).strip() == "hello world"


def test_mock_server_can_fail_first_requests() -> None:
    with MockOpenAIServer(fail_first=1) as server:
        client = OpenAICompatibleClient(server.base_url, "k")
        with pytest.raises(OSError):
            client.chat([{"role": "user", "content": "hi"}])
        assert client.chat([{"role": "user", "content": "hi"}])["choices"]

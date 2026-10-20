"""The Portal turns Qwen3.5 thinking off, also through the LiteLLM alias, and the switch is configurable."""

from __future__ import annotations

from types import SimpleNamespace

from bni_training.workshop.portal.config import PortalConfig
from bni_training.workshop.portal.service import PortalService

NO_THINKING = {"chat_template_kwargs": {"enable_thinking": False}}
VLLM = {"VLLM_BASE_URL": "http://vllm.invalid/v1", "PORTAL_LLM_ROUTE": "vllm"}
LITELLM = {"LITELLM_BASE_URL": "http://gateway.invalid/v1", "PORTAL_LLM_ROUTE": "litellm"}


def client_for(env: dict):
    return PortalService._default_llm(SimpleNamespace(config=PortalConfig.from_env(env)))


def test_thinking_is_disabled_by_default_on_the_direct_vllm_route() -> None:
    client = client_for(VLLM)
    assert client.model == "qwen3.5-9b" and client.extra_body == NO_THINKING


def test_thinking_is_disabled_on_the_litellm_route_even_though_the_model_is_an_alias() -> None:
    client = client_for(LITELLM)
    assert client.model == "qwen-primary" and client.extra_body == NO_THINKING


def test_the_switch_can_turn_it_off() -> None:
    config = PortalConfig.from_env({**VLLM, "PORTAL_DISABLE_THINKING": "false"})
    assert config.disable_thinking is False
    assert client_for({**VLLM, "PORTAL_DISABLE_THINKING": "false"}).extra_body == {}
    assert PortalConfig.from_env(VLLM).disable_thinking is True

"""config/litellm.yaml: every alias must ask its endpoint for a model that the endpoint serves."""

from __future__ import annotations

from pathlib import Path

import yaml

ROOT = Path(__file__).resolve().parents[2]
SERVED_MODEL = "qwen3.5-9b"


def models() -> dict[str, dict]:
    config = yaml.safe_load((ROOT / "config/litellm.yaml").read_text())
    return {m["model_name"]: m["litellm_params"] for m in config["model_list"]}


def test_both_teaching_aliases_exist() -> None:
    assert {"qwen-primary", "training-fallback"} <= set(models())


def test_every_alias_requests_the_served_model_name() -> None:
    """The fallback used to request a model called training-fallback, which vLLM rejects with 404."""
    for alias, params in models().items():
        assert params["model"] == f"openai/{SERVED_MODEL}", alias


def test_the_fallback_endpoint_is_configurable_and_holds_no_secret() -> None:
    fallback = models()["training-fallback"]
    assert fallback["api_base"] == "os.environ/MOCK_FALLBACK_BASE_URL"
    assert fallback["api_key"] == "workshop-only"

from __future__ import annotations

import os
import sys
import time

import yaml

from bni_training.labs import ROOT, require_env, run_lab
from bni_training.llm_client import OpenAICompatibleClient
from bni_training.mock_llm import MockOpenAIServer

DESCRIPTION = "Lab 10: route requests through the shared gateway with retry and controlled fallback."


def call_with_retry_and_fallback(primary, fallback, retries: int, backoff: float = 0.0) -> tuple[str, str]:
    """Mirror router_settings: retry the primary, then use the controlled workshop fallback."""
    messages = [{"role": "user", "content": "Return the active route name."}]
    for attempt in range(retries + 1):
        try:
            return "qwen-primary", primary.chat(messages, max_tokens=16)["choices"][0]["message"]["content"]
        except OSError:
            time.sleep(backoff * attempt)
    return "training-fallback", fallback.chat(messages, max_tokens=16)["choices"][0]["message"]["content"]


def check_config(report) -> dict:
    config = yaml.safe_load((ROOT / "config" / "litellm.yaml").read_text())
    names = {item["model_name"] for item in config["model_list"]}
    ok = {"qwen-primary", "training-fallback"} <= names and config["router_settings"]["num_retries"] == 2
    (report.passed if ok else report.failed)(
        "litellm_config", f"routes {sorted(names)}, retries={config['router_settings']['num_retries']}"
    )
    return config


def body(args, report):
    config = check_config(report)
    retries = config["router_settings"]["num_retries"]
    if args.mode == "local":
        with (
            MockOpenAIServer(reply="primary", fail_first=retries + 1) as primary,
            MockOpenAIServer(reply="fallback") as fallback,
        ):
            route, _ = call_with_retry_and_fallback(
                OpenAICompatibleClient(primary.base_url, "x"),
                OpenAICompatibleClient(fallback.base_url, "x"),
                retries,
            )
            (report.passed if route == "training-fallback" else report.failed)(
                "fallback_after_retries", f"route={route}; primary saw {len(primary.requests)} requests"
            )
        report.skipped(
            "litellm_proxy_live",
            "Local mode simulates retry and fallback; the real proxy is validated by the gateway "
            "profile smoke test and in CAI",
        )
        return
    env = require_env(["LITELLM_BASE_URL"])
    client = OpenAICompatibleClient(
        env["LITELLM_BASE_URL"], os.getenv("LITELLM_API_KEY", ""), model="qwen-primary"
    )
    text = client.chat([{"role": "user", "content": "Return the active route name."}], max_tokens=32)[
        "choices"
    ][0]["message"]["content"]
    (report.passed if text else report.failed)("litellm_route", text[:80])


def main(argv=None) -> int:
    return run_lab("10", DESCRIPTION, body, argv)


if __name__ == "__main__":
    raise SystemExit(main(sys.argv[1:]))

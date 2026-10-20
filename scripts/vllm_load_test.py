"""Trainer: load test of the shared vLLM endpoint with workshop-sized requests.

Sends ``--concurrency`` requests at the same moment (default 40: four per group), each asking for roughly a Portal-sized
answer with Qwen3.5 thinking switched off. Reports wall time, request and token throughput, and p50 / p95 / max latency.
Errors are counted, never hidden. It sends synthetic prompts only and prints no key.
"""

from __future__ import annotations

import argparse
import json
import statistics
import time
from concurrent.futures import ThreadPoolExecutor

from bni_training.llm_client import OpenAICompatibleClient, model_request_extras

PROMPT = (
    "You are a banking portfolio analyst working with fully synthetic data. In about 120 words, explain what "
    "delinquency ratio means and how a trainer could read it by risk band. This is request {n} of the load test."
)


def percentile(values: list[float], fraction: float) -> float:
    ordered = sorted(values)
    return ordered[min(len(ordered) - 1, int(round(fraction * (len(ordered) - 1))))]


def run(client: OpenAICompatibleClient, concurrency: int, max_tokens: int, timeout: float) -> dict:
    def call(n: int) -> dict:
        started = time.perf_counter()
        try:
            reply = client.chat(
                [{"role": "user", "content": PROMPT.format(n=n)}], max_tokens=max_tokens, timeout=timeout
            )
            tokens = int((reply.get("usage") or {}).get("completion_tokens", 0))
            return {"ok": True, "seconds": time.perf_counter() - started, "tokens": tokens}
        except Exception as exc:  # noqa: BLE001 - a load test reports every failure
            return {"ok": False, "seconds": time.perf_counter() - started, "error": type(exc).__name__}

    wall_start = time.perf_counter()
    with ThreadPoolExecutor(max_workers=concurrency) as pool:
        results = list(pool.map(call, range(1, concurrency + 1)))
    wall = time.perf_counter() - wall_start
    good = [item for item in results if item["ok"]]
    latencies = [item["seconds"] for item in good]
    tokens = sum(item["tokens"] for item in good)
    errors: dict[str, int] = {}
    for item in results:
        if not item["ok"]:
            errors[item["error"]] = errors.get(item["error"], 0) + 1
    summary = {
        "concurrency": concurrency,
        "max_tokens": max_tokens,
        "succeeded": len(good),
        "failed": len(results) - len(good),
        "errors": errors,
        "wall_seconds": round(wall, 2),
    }
    if good:
        summary.update(
            {
                "requests_per_second": round(len(good) / wall, 2),
                "output_tokens_per_second": round(tokens / wall, 1),
                "mean_output_tokens": round(tokens / len(good), 1),
                "latency_p50_seconds": round(statistics.median(latencies), 2),
                "latency_p95_seconds": round(percentile(latencies, 0.95), 2),
                "latency_max_seconds": round(max(latencies), 2),
            }
        )
    return summary


def main(argv=None) -> int:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--url", required=True, help="vLLM base URL ending in /v1")
    parser.add_argument("--api-key", default="EMPTY")
    parser.add_argument("--model", default="qwen3.5-9b")
    parser.add_argument("--concurrency", type=int, default=40)
    parser.add_argument("--max-tokens", type=int, default=200)
    parser.add_argument("--timeout", type=float, default=180)
    args = parser.parse_args(argv)
    client = OpenAICompatibleClient(
        args.url, args.api_key, args.model, extra_body=model_request_extras(args.model)
    )
    print(json.dumps(run(client, args.concurrency, args.max_tokens, args.timeout), indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

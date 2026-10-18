import os

from bni_training.observability import configure_phoenix, safe_trace_attributes


def main():
    attrs = safe_trace_attributes(
        {
            "group_id": os.getenv("GROUP_ID", "group_01"),
            "session_id": "demo-session",
            "latency_ms": 12,
            "api_key": os.getenv("VLLM_API_KEY", ""),
        }
    )
    print({"configured": configure_phoenix(os.getenv("PHOENIX_ENDPOINT", "")), "safe_attributes": attrs})
    print(
        "Inspect agent spans, tool spans, latency, token counts, status, logs, "
        "and trainer-led GPU utilization."
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

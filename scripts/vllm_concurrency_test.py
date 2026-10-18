import argparse
import time
from concurrent.futures import ThreadPoolExecutor

from bni_training.llm_client import OpenAICompatibleClient


def main():
    p = argparse.ArgumentParser()
    p.add_argument("--url", required=True)
    p.add_argument("--api-key", required=True)
    p.add_argument("--groups", type=int, default=10)
    args = p.parse_args()
    client = OpenAICompatibleClient(args.url, args.api_key)

    def call(i):
        start = time.perf_counter()
        client.chat([{"role": "user", "content": f"Reply only with group_{i:02d}"}], max_tokens=16)
        return time.perf_counter() - start

    with ThreadPoolExecutor(max_workers=args.groups) as pool:
        times = list(pool.map(call, range(1, args.groups + 1)))
    print(
        {
            "requests": len(times),
            "max_latency_seconds": max(times),
            "requests_per_second": len(times) / sum(times),
        }
    )


if __name__ == "__main__":
    main()

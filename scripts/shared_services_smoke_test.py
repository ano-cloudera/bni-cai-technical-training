import argparse
import json
from urllib.request import urlopen


def check(name, url):
    try:
        with urlopen(url, timeout=10) as response:
            return {"service": name, "healthy": response.status < 400}
    except Exception as exc:
        return {"service": name, "healthy": False, "error": str(exc)}


def main():
    p = argparse.ArgumentParser()
    p.add_argument("--vllm")
    p.add_argument("--qdrant")
    p.add_argument("--phoenix")
    p.add_argument("--litellm")
    args = p.parse_args()
    urls = {"vllm": args.vllm, "qdrant": args.qdrant, "phoenix": args.phoenix, "litellm": args.litellm}
    results = [check(k, v) for k, v in urls.items() if v]
    print(json.dumps(results, indent=2))
    return 0 if results and all(r["healthy"] for r in results) else 1


if __name__ == "__main__":
    raise SystemExit(main())

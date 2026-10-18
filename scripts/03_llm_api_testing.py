import os

from bni_training.llm_client import OpenAICompatibleClient


def main():
    url = os.getenv("VLLM_BASE_URL")
    key = os.getenv("VLLM_API_KEY", "")
    if not url:
        print("Set VLLM_BASE_URL to run the live API test.")
        return 0
    client = OpenAICompatibleClient(url, key)
    print(client.health())
    print(client.chat([{"role": "user", "content": "Reply with: workshop endpoint ready"}], max_tokens=32))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

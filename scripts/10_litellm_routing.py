import os

from bni_training.llm_client import OpenAICompatibleClient


def main():
    url = os.getenv("LITELLM_BASE_URL")
    if not url:
        print("LiteLLM route preview: qwen-primary -> controlled training-fallback, retries=2, timeout=60s.")
        return 0
    client = OpenAICompatibleClient(url, os.getenv("LITELLM_API_KEY", ""), model="qwen-primary")
    print(client.chat([{"role": "user", "content": "Return the active route name."}], max_tokens=32))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

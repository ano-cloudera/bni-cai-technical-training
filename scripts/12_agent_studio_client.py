import os

from bni_training.agent_studio import AgentStudioClient


def main():
    url = os.getenv("AGENT_STUDIO_WORKFLOW_URL")
    if not url:
        print(
            "Set AGENT_STUDIO_WORKFLOW_URL and AGENT_STUDIO_API_KEY after the trainer "
            "publishes one final workflow."
        )
        return 0
    client = AgentStudioClient(url, os.getenv("AGENT_STUDIO_API_KEY", ""))
    trace = client.start(
        {
            "question": "What is synthetic portfolio exposure by region?",
            "group_id": os.getenv("GROUP_ID", "group_01"),
        }
    )
    print(client.poll(trace))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

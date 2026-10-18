from __future__ import annotations

import os
import sys

from bni_training.agent_studio import AgentStudioClient
from bni_training.labs import run_lab

DESCRIPTION = "Lab 12: call the one published final Agent Studio workflow."
INPUTS = {"question": "What is synthetic portfolio exposure by region?"}


def body(args, report):
    if args.mode == "local":
        calls: list[tuple] = []

        def transport(method, path, payload):
            calls.append((method, path))
            if method == "POST":
                return {"trace_id": "local-trace-1"}
            return {"status": "completed", "output": "local fixture result"}

        client = AgentStudioClient(
            "http://local.invalid", "local-placeholder", transport=transport, sleep=lambda _s: None
        )
        result = client.poll(client.start({**INPUTS, "group_id": os.getenv("GROUP_ID", "group_01")}))
        ok = result["status"] == "completed" and [c[0] for c in calls] == ["POST", "GET"]
        (report.passed if ok else report.failed)("client_start_and_poll", f"calls={calls}")
        report.skipped(
            "published_workflow",
            "Local mode uses a fixture transport; the trainer publishes one workflow in CAI",
        )
        return
    url = os.getenv("AGENT_STUDIO_WORKFLOW_URL")
    if not url:
        report.skipped(
            "published_workflow",
            "AGENT_STUDIO_WORKFLOW_URL is not set: the trainer has not published the final workflow yet",
        )
        return
    client = AgentStudioClient(url, os.getenv("AGENT_STUDIO_API_KEY", ""))
    result = client.poll(client.start({**INPUTS, "group_id": os.getenv("GROUP_ID", "group_01")}))
    report.passed("published_workflow", str(result)[:200])


def main(argv=None) -> int:
    return run_lab("12", DESCRIPTION, body, argv)


if __name__ == "__main__":
    raise SystemExit(main(sys.argv[1:]))

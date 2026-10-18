from __future__ import annotations

import os
import sys

from bni_training.crew import kickoff_blocking
from bni_training.labs import crewai_llm, require_env, run_lab
from bni_training.mock_llm import MockOpenAIServer

DESCRIPTION = "Lab 04: a two-agent sequential CrewAI example against an OpenAI-compatible endpoint."


def run_crew(llm) -> str:
    from crewai import Agent, Crew, Process, Task

    researcher = Agent(
        role="Synthetic Banking Glossary Researcher",
        goal="Explain one supplied synthetic banking term accurately",
        backstory="You work only with workshop definitions and never use customer data.",
        llm=llm,
    )
    reviewer = Agent(
        role="Grounding Reviewer",
        goal="Review the explanation for clarity and unsupported claims",
        backstory="You make concise corrections without adding new facts.",
        llm=llm,
    )
    research = Task(
        description="Explain DPD 30 in two sentences for a workshop participant.",
        expected_output="A two-sentence synthetic glossary explanation.",
        agent=researcher,
    )
    review = Task(
        description="Review the previous explanation and return the approved final wording.",
        expected_output="A concise reviewed explanation without individual lending advice.",
        agent=reviewer,
    )
    crew = Crew(
        agents=[researcher, reviewer], tasks=[research, review], process=Process.sequential, verbose=False
    )
    return str(kickoff_blocking(crew))


def body(args, report):
    if args.mode == "local":
        with MockOpenAIServer(reply="DPD 30 marks an account at least 30 days past due.") as server:
            text = run_crew(crewai_llm(server.base_url, "local-placeholder"))
            requests = len(server.requests)
        (report.passed if text.strip() and requests >= 2 else report.failed)(
            "crewai_sequential", f"{requests} LLM requests; result: {text[:80]}"
        )
        report.skipped("real_vllm_endpoint", "Local mode uses the in-process mock LLM")
        return
    env = require_env(["VLLM_BASE_URL"])
    text = run_crew(
        crewai_llm(
            env["VLLM_BASE_URL"], os.getenv("VLLM_API_KEY", ""), os.getenv("SERVED_MODEL_NAME", "qwen3.5-9b")
        )
    )
    (report.passed if text.strip() else report.failed)("crewai_sequential", text[:200])


def main(argv=None) -> int:
    return run_lab("04", DESCRIPTION, body, argv)


if __name__ == "__main__":
    raise SystemExit(main(sys.argv[1:]))

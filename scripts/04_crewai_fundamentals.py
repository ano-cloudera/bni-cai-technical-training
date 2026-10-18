import os


def main():
    url = os.getenv("VLLM_BASE_URL")
    if not url:
        print("Set VLLM_BASE_URL and VLLM_API_KEY to run the CrewAI fundamentals lab.")
        return 0
    try:
        from crewai import LLM, Agent, Crew, Process, Task
    except ImportError as exc:
        raise RuntimeError("Install the base dependency profile before running CrewAI") from exc

    llm = LLM(
        model="openai/qwen3.5-9b",
        base_url=url,
        api_key=os.getenv("VLLM_API_KEY", ""),
        temperature=0,
    )
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
    result = Crew(
        agents=[researcher, reviewer],
        tasks=[research, review],
        process=Process.sequential,
        verbose=True,
    ).kickoff()
    print(result)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

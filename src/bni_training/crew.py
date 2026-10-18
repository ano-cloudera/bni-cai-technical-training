from __future__ import annotations

import asyncio
import contextvars
from concurrent.futures import ThreadPoolExecutor

from bni_training.schemas import AgentAnswer


class CreditInsightWorkflow:
    """Small deterministic service boundary used by the CrewAI lab and UI."""

    def __init__(self, data_tool, llm):
        self.data_tool = data_tool
        self.llm = llm

    def run(self, question: str) -> AgentAnswer:
        sql, result = self.data_tool.query(question)
        if hasattr(self.llm, "summarize"):
            text = self.llm.summarize(question, result)
        else:
            response = self.llm.chat(
                [
                    {
                        "role": "system",
                        "content": (
                            "Summarize only the supplied synthetic portfolio result. Do not invent numbers."
                        ),
                    },
                    {
                        "role": "user",
                        "content": f"Question: {question}\nColumns: {result.columns}\nRows: {result.rows}",
                    },
                ]
            )
            text = response["choices"][0]["message"]["content"]
        return AgentAnswer(answer=text, query=sql, data=result)


def build_crewai_crew(data_tool, llm_client):
    """Build the optional real CrewAI implementation when CrewAI is installed."""
    try:
        from crewai import Agent, Crew, Process, Task
        from crewai.tools import tool
    except ImportError as exc:
        raise RuntimeError("Install the CrewAI dependency profile to run this lab") from exc

    @tool("synthetic_credit_portfolio_query")
    def query_portfolio(question: str) -> str:
        """Query approved synthetic portfolio metrics through the semantic layer."""
        sql, result = data_tool.query(question)
        return result.model_dump_json() + f"\nSQL: {sql}"

    analyst = Agent(
        role="Synthetic Credit Portfolio Analyst",
        goal="Use approved tools for grounded portfolio facts",
        backstory="You analyze only the synthetic workshop portfolio.",
        llm=llm_client,
        tools=[query_portfolio],
        verbose=True,
    )
    narrator = Agent(
        role="Banking Insight Writer",
        goal="Explain tool results without changing numbers",
        backstory="You write concise, non-decisioning portfolio summaries.",
        llm=llm_client,
        verbose=True,
    )
    task1 = Task(
        description="Answer the participant question: {question}. Use the structured data tool.",
        expected_output="Structured facts and SQL",
        agent=analyst,
    )
    task2 = Task(
        description="Summarize the structured facts. Do not calculate credit scores.",
        expected_output="Grounded portfolio summary",
        agent=narrator,
    )
    return Crew(agents=[analyst, narrator], tasks=[task1, task2], process=Process.sequential, verbose=True)


def kickoff_blocking(crew, inputs: dict | None = None):
    """Run ``crew.kickoff`` from sync code, including inside a Jupyter kernel.

    CrewAI refuses a synchronous kickoff while an asyncio loop is running in the calling thread, and every
    JupyterLab kernel has one. In that case the kickoff runs on a worker thread that keeps the caller's
    context variables, so tracing attributes set by the caller still reach the spans.
    """
    try:
        asyncio.get_running_loop()
    except RuntimeError:
        return crew.kickoff(inputs=inputs)
    context = contextvars.copy_context()
    with ThreadPoolExecutor(max_workers=1) as pool:
        return pool.submit(context.run, lambda: crew.kickoff(inputs=inputs)).result()


class RecordingDataTool:
    """Wrap a data tool and record each query so a lab can prove the agent really called it."""

    def __init__(self, inner):
        self.inner = inner
        self.calls: list[dict] = []

    def query(self, question: str):
        sql, result = self.inner.query(question)
        self.calls.append({"question": question, "sql": sql, "row_count": result.row_count})
        return sql, result


def run_crewai_question(data_tool, llm_client, question: str) -> dict:
    """Run the two-agent CrewAI workflow for one question and report which tools were called."""
    recorder = RecordingDataTool(data_tool)
    crew = build_crewai_crew(recorder, llm_client)
    output = kickoff_blocking(crew, {"question": question})
    return {"answer": str(output), "tool_calls": recorder.calls}

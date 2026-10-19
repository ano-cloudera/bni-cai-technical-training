from __future__ import annotations

import json
import sys

from bni_training.crew import CreditInsightWorkflow, run_crewai_question
from bni_training.guardrails import validate_grounded_answer
from bni_training.labs import crewai_llm, run_lab, shared_llm_settings
from bni_training.llm_client import OpenAICompatibleClient
from bni_training.mock_llm import MockOpenAIServer

DESCRIPTION = "Lab 08: a lightweight CrewAI workflow with the shared LLM and your group's data tool."


def configure(parser):
    parser.add_argument("--question", help="Defaults to your mission's first sample question")


def run_workflow(ctx, llm_client, crew_llm, report, question: str) -> dict:
    tool = ctx.data_tool().bind(ctx.request())
    answer = CreditInsightWorkflow(tool, llm_client).run(question)
    ok = (
        answer.data.row_count > 0
        and bool(answer.answer.strip())
        and answer.query.upper().startswith("SELECT")
    )
    (report.passed if ok else report.failed)(
        "plain_workflow", f"{answer.data.row_count} rows; SQL: {answer.query}"
    )
    result = run_crewai_question(tool, crew_llm, question)
    (report.passed if result["tool_calls"] else report.failed)(
        "crewai_tool_call", f"{len(result['tool_calls'])} data tool call(s)"
    )
    (report.passed if result["answer"].strip() else report.failed)(
        "crewai_final_answer", result["answer"][:120]
    )
    try:
        validate_grounded_answer("The result has 5 rows.", [5.0])
        report.passed("grounding_check", "numbers must come from the tool result")
    except Exception as exc:  # noqa: BLE001
        report.failed("grounding_check", str(exc))
    return {
        "question": question,
        "sql": answer.query,
        "rows": answer.data.row_count,
        "crew_answer": result["answer"][:300],
    }


def body(args, report):
    ctx = report.context
    question = args.question or ctx.bundle.sample_questions[0]
    if args.mode == "local":
        with MockOpenAIServer(reply="The result is summarised without changing any number.") as server:
            summary = run_workflow(
                ctx,
                OpenAICompatibleClient(server.base_url, "local-placeholder"),
                crewai_llm(server.base_url, "local-placeholder"),
                report,
                question,
            )
        report.skipped(
            "real_vllm_endpoint", "Explicit mock mode: the LLM is an in-process mock; use --mode cai for vLLM"
        )
    else:
        url, key, model = shared_llm_settings()
        summary = run_workflow(
            ctx, OpenAICompatibleClient(url, key, model), crewai_llm(url, key, model), report, question
        )
    saved = ctx.write_output("08_workflow.json", json.dumps(summary, indent=2))
    report.passed("saved", f"groups/{ctx.group_id}/output/{saved.name}")


def main(argv=None) -> int:
    return run_lab("08", DESCRIPTION, body, argv, configure, participant=True)


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))

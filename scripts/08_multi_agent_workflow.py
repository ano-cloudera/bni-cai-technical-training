from __future__ import annotations

import os
import sys

from bni_training.crew import CreditInsightWorkflow, run_crewai_question
from bni_training.guardrails import validate_grounded_answer
from bni_training.labs import build_data_tool, build_settings, crewai_llm, require_env, run_lab
from bni_training.llm_client import OpenAICompatibleClient
from bni_training.mock_llm import MockOpenAIServer

DESCRIPTION = (
    "Lab 08: structured data + grounded narrative, as a deterministic workflow and as a CrewAI crew."
)
QUESTION = "What is the outstanding balance by region?"


def run_workflow(settings, llm_client, crew_llm, report) -> None:
    tool = build_data_tool(settings)
    answer = CreditInsightWorkflow(tool, llm_client).run(QUESTION)
    ok = (
        answer.data.row_count > 0
        and bool(answer.answer.strip())
        and answer.query.upper().startswith("SELECT")
    )
    (report.passed if ok else report.failed)(
        "two_step_workflow", f"{answer.data.row_count} rows; SQL: {answer.query}"
    )
    result = run_crewai_question(build_data_tool(settings), crew_llm, QUESTION)
    called = len(result["tool_calls"]) >= 1
    (report.passed if called else report.failed)(
        "crewai_tool_call", f"data tool calls: {result['tool_calls']}"
    )
    (report.passed if result["answer"].strip() else report.failed)(
        "crewai_final_answer", result["answer"][:120]
    )
    try:
        validate_grounded_answer("The portfolio has 5 regions.", [5.0])
        report.passed("grounding_guardrail", "numbers must come from the tool result")
    except Exception as exc:  # noqa: BLE001
        report.failed("grounding_guardrail", str(exc))


def body(args, report):
    if args.mode == "local":
        with MockOpenAIServer(reply="The synthetic portfolio exposure is summarized by region.") as server:
            settings = build_settings(report, server.base_url)
            llm_client = OpenAICompatibleClient(server.base_url, "local-placeholder")
            run_workflow(settings, llm_client, crewai_llm(server.base_url, "local-placeholder"), report)
            report.data["mock_llm_requests"] = len(server.requests)
        report.skipped(
            "real_vllm_endpoint", "Explicit mock mode: the LLM is an in-process mock; use --mode cai for vLLM"
        )
        return
    settings = build_settings(report)
    env = require_env(["VLLM_BASE_URL"])
    model = os.getenv("SERVED_MODEL_NAME", "qwen3.5-9b")
    key = os.getenv("VLLM_API_KEY", "")
    run_workflow(
        settings,
        OpenAICompatibleClient(env["VLLM_BASE_URL"], key, model),
        crewai_llm(env["VLLM_BASE_URL"], key, model),
        report,
    )


def main(argv=None) -> int:
    return run_lab("08", DESCRIPTION, body, argv)


if __name__ == "__main__":
    raise SystemExit(main(sys.argv[1:]))

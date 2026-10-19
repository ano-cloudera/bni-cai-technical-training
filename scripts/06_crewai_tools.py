from __future__ import annotations

import json
import sys

from bni_training.data.bundles import BundleCatalog
from bni_training.data.crewai_tool import answer_question, make_crewai_tool
from bni_training.data.tool import DataRequest
from bni_training.labs import run_lab

DESCRIPTION = "Lab 06: build and test a group-scoped banking data tool for an agent."


def body(args, report):
    ctx = report.context
    data_tool, request = ctx.data_tool(), ctx.request()
    agent_tool = make_crewai_tool(data_tool, request)
    report.passed("tool_built", f"{agent_tool.name} for {ctx.group_id}")

    question = ctx.bundle.sample_questions[0]
    answer = json.loads(agent_tool.run(question=question))
    (report.passed if answer["row_count"] > 0 else report.failed)(
        "tool_answers_mission_question", f"{answer['row_count']} rows"
    )

    restricted = next(
        (
            m
            for m in ("total_loans", "transaction_count", "total_customers")
            if m not in ctx.bundle.allowed_metrics
        ),
        None,
    )
    if restricted:
        text = agent_tool.run(question=f"Show {restricted.replace('_', ' ')}")
        ok = text.startswith("Not available:") and "Traceback" not in text
        (report.passed if ok else report.failed)("tool_refuses_politely", text[:120])
    else:
        report.skipped("tool_refuses_politely", "your mission may use these metrics")

    other = next(g for g in ("group_01", "group_02") if g != ctx.group_id)
    foreign = BundleCatalog.load().for_group(other)
    forged = DataRequest(foreign.group_id, ctx.run_id, foreign.dataset_id, foreign.mission_id)
    text = answer_question(data_tool, forged, question)
    ok = "not assigned to your group" in text
    (report.passed if ok else report.failed)("tool_rejects_another_groups_identity", text[:120])

    saved = ctx.write_output(
        "06_tool_test.json", json.dumps({"tool": agent_tool.name, "answer": answer}, indent=2, default=str)
    )
    report.passed("saved", f"groups/{ctx.group_id}/output/{saved.name}")


def main(argv=None) -> int:
    return run_lab("06", DESCRIPTION, body, argv, participant=True)


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))

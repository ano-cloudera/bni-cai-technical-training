from __future__ import annotations

import json
import sys

from bni_training.data.semantic_layer import SemanticError, SemanticModel
from bni_training.labs import run_lab
from bni_training.user_errors import UserFacingError

DESCRIPTION = "Lab 05: data dictionary, relationships, metrics and business terms for your mission."


def body(args, report):
    ctx = report.context
    semantic, tool, bundle = SemanticModel.load(), ctx.data_tool(), ctx.bundle
    dictionary = tool._engine.dictionary
    columns = {t: list(dictionary.tables[t].exposed_columns) for t in bundle.tables}
    report.passed(
        "data_dictionary", f"{sum(len(c) for c in columns.values())} columns in {len(columns)} tables"
    )
    joins = [
        f"{child}.{col} -> {parent}.{pcol}"
        for child, edges in semantic.parents.items()
        for col, parent, pcol in edges
        if child in bundle.tables and parent in bundle.tables
    ]
    report.passed("relationships", f"{len(joins)} joins inside your bundle")
    metrics = {m: semantic.metrics[m].description for m in bundle.allowed_metrics}
    report.passed("metrics", f"{len(metrics)} metrics available to you")
    terms = {t: semantic.terms[t] for t in ("dormant account", "digital transaction") if t in semantic.terms}
    report.passed("business_terms", f"{len(semantic.terms)} terms defined")
    compiled = []
    for question in bundle.sample_questions:
        sql, result = tool.query(question, ctx.request())
        compiled.append({"question": question, "sql": sql, "rows": result.row_count})
        (report.passed if result.row_count > 0 else report.failed)(
            f"question: {question}", f"{result.row_count} rows"
        )
    not_allowed = next((m for m in semantic.metrics if m not in bundle.allowed_metrics), None)
    if not_allowed:
        try:
            tool.query(f"Show {not_allowed.replace('_', ' ')}", ctx.request())
        except (SemanticError, UserFacingError) as exc:
            report.passed("metric_outside_mission_refused", str(exc))
        else:
            report.failed("metric_outside_mission_refused", f"{not_allowed} was accepted")
    else:
        report.skipped("metric_outside_mission_refused", "your mission may use every metric")
    summary = {"columns": columns, "joins": joins, "metrics": metrics, "terms": terms, "questions": compiled}
    saved = ctx.write_output("05_semantic_summary.json", json.dumps(summary, indent=2, default=str))
    report.passed("saved", f"groups/{ctx.group_id}/output/{saved.name}")


def main(argv=None) -> int:
    return run_lab("05", DESCRIPTION, body, argv, participant=True)


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))

"""A group-scoped CrewAI tool over the guarded data tool. Refusals are plain sentences, never crashes."""

from __future__ import annotations

import json

from bni_training.user_errors import UserFacingError

from .tool import DataRequest, WorkshopDataTool

MAX_ROWS_FOR_AGENT = 25


def answer_question(tool: WorkshopDataTool, request: DataRequest, question: str) -> str:
    """The text an agent receives: JSON with SQL and rows, or a short explanation of why not."""
    try:
        sql, result = tool.query(question, request)
    except UserFacingError as exc:
        return f"Not available: {exc}"
    return json.dumps(
        {
            "sql": sql,
            "columns": list(result.columns),
            "rows": [list(r) for r in result.rows[:MAX_ROWS_FOR_AGENT]],
            "row_count": result.row_count,
            "truncated": bool(getattr(result, "truncated", False)),
        },
        default=str,
    )


def make_crewai_tool(tool: WorkshopDataTool, request: DataRequest):
    """Build the CrewAI tool for ONE group. Needs the crewai package (participant profile)."""
    try:
        from crewai.tools import tool as crewai_tool
    except ImportError as exc:
        raise RuntimeError("Install the participant dependency profile to use CrewAI") from exc

    @crewai_tool("query_group_banking_data")
    def query_group_banking_data(question: str) -> str:
        """Answer one business question about the synthetic banking data assigned to this group.

        Returns JSON with the SQL, columns and rows, or a short explanation when the question is not allowed
        for this group's mission.
        """
        return answer_question(tool, request, question)

    return query_group_banking_data

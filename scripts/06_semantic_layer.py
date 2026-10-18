from __future__ import annotations

import sys

from bni_training.labs import SEMANTIC_MODEL, run_lab
from bni_training.semantic import SemanticCatalog, compile_question

DESCRIPTION = "Lab 06: map approved metrics and dimensions to constrained SQL."
CASES = {
    "What is the outstanding balance by region?": ("SUM(outstanding_balance)", "GROUP BY region"),
    "Show delinquency rate by product id": ("AVG(CASE WHEN dpd >= 30", "GROUP BY product_id"),
}


def body(args, report):
    catalog = SemanticCatalog.load(SEMANTIC_MODEL)
    for question, expected in CASES.items():
        sql = compile_question(question, catalog)
        ok = all(fragment in sql for fragment in expected)
        (report.passed if ok else report.failed)(question, sql)


def main(argv=None) -> int:
    return run_lab("06", DESCRIPTION, body, argv)


if __name__ == "__main__":
    raise SystemExit(main(sys.argv[1:]))

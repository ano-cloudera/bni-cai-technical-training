from __future__ import annotations

import sys

from bni_training.data.backend import BackendConfigError, impala_status
from bni_training.data.engine import RestrictedTableError
from bni_training.labs import run_lab

DESCRIPTION = "Lab 04: explore your group's assigned logical bundle of the synthetic banking dataset."
ALL_TABLES = ("branches", "customers", "accounts", "transactions", "loans")


def body(args, report):
    ctx = report.context
    tool = ctx.data_tool()
    request = ctx.request()
    bundle = ctx.bundle
    report.passed("bundle", f"{bundle.dataset_id}: tables {', '.join(bundle.tables)}")
    preview = {}
    for table in bundle.tables:
        count = tool.run_sql(f"SELECT COUNT(*) AS n FROM {table}", request).rows[0][0]
        sample = tool.run_sql(f"SELECT * FROM {table} LIMIT 3", request)
        preview[table] = {"rows": count, "columns": list(sample.columns), "sample": sample.rows}
        (report.passed if count > 0 else report.failed)(
            f"table_{table}", f"{count} rows, {len(sample.columns)} columns"
        )
    outside = [t for t in ALL_TABLES if t not in bundle.tables]
    if outside:
        try:
            tool.run_sql(f"SELECT * FROM {outside[0]} LIMIT 1", request)
        except RestrictedTableError as exc:
            report.passed("restricted_table_refused", str(exc))
        else:
            report.failed("restricted_table_refused", f"{outside[0]} was readable but is not in your bundle")
    else:
        report.skipped("restricted_table_refused", "your bundle contains all five tables")
    try:
        write = tool.run_sql("DELETE FROM customers")
        report.failed("write_refused", f"a write was accepted: {write}")
    except ValueError as exc:
        report.passed("write_refused", str(exc))
    try:
        status, detail = impala_status()
        report.skipped("impala", detail) if status == "SKIPPED" else report.skipped(
            "impala", "Impala is a trainer-controlled demonstration; participants use CSV"
        )
    except BackendConfigError as exc:
        report.failed("impala", str(exc))
    saved = ctx.write_output(
        "04_dataset_preview.json", __import__("json").dumps(preview, indent=2, default=str)
    )
    report.passed("saved", f"groups/{ctx.group_id}/output/{saved.name}")


def main(argv=None) -> int:
    return run_lab("04", DESCRIPTION, body, argv, participant=True)


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))

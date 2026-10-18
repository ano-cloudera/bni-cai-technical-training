from __future__ import annotations

import sys

from bni_training.backends.factory import create_backend
from bni_training.labs import build_settings, run_lab

DESCRIPTION = "Lab 05: ask the data through one explicit backend (csv, impala_gssapi, or impala_ldap)."
SQL = (
    "SELECT region, SUM(outstanding_balance) AS exposure "
    "FROM loan_accounts GROUP BY region ORDER BY exposure DESC LIMIT 10"
)


def body(args, report):
    settings = build_settings(report)
    backend = create_backend(settings)
    result = backend.execute(SQL, 30)
    name = f"{settings.data_mode.value}_query"
    (report.passed if result.row_count > 0 else report.failed)(name, f"{result.row_count} rows")
    report.data["result"] = result.model_dump()
    if settings.data_mode.value == "csv":
        report.skipped(
            "impala_live",
            "CSV mode was selected explicitly. Select DATA_MODE=impala_gssapi or impala_ldap to test Impala; "
            "an Impala failure never falls back to CSV",
        )


def main(argv=None) -> int:
    return run_lab("05", DESCRIPTION, body, argv)


if __name__ == "__main__":
    raise SystemExit(main(sys.argv[1:]))

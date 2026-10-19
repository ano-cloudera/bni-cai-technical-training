"""Backend selection: CSV is the default; Impala only when DATA_BACKEND=impala. Never a silent fallback."""

from __future__ import annotations

import os
from collections.abc import Mapping

CSV, IMPALA = "csv", "impala"
SKIPPED, READY = "SKIPPED", "READY"


class BackendConfigError(ValueError):
    pass


def resolve_data_backend(env: Mapping[str, str] | None = None) -> str:
    value = (os.environ if env is None else env).get("DATA_BACKEND", CSV).strip().lower() or CSV
    if value not in (CSV, IMPALA):
        raise BackendConfigError("DATA_BACKEND must be csv or impala")
    return value


def impala_status(env: Mapping[str, str] | None = None) -> tuple[str, str]:
    """(status, detail). Missing Impala configuration is SKIPPED unless Impala was explicitly selected."""
    source = os.environ if env is None else env
    backend = resolve_data_backend(source)
    configured = bool(source.get("IMPALA_HOST"))
    if backend == IMPALA:
        if not configured:
            raise BackendConfigError(
                "DATA_BACKEND=impala but IMPALA_HOST is not set. "
                "The workshop never falls back to CSV on its own; "
                "set the Impala variables or choose DATA_BACKEND=csv."
            )
        return READY, "Impala was selected explicitly and is configured"
    if configured:
        return SKIPPED, "Impala variables are present but DATA_BACKEND=csv, so Impala is not used"
    return SKIPPED, "Impala is optional and not configured; the CSV backend serves all participants"

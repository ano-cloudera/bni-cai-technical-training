from __future__ import annotations

import pytest

from bni_training.data.backend import BackendConfigError, impala_status, resolve_data_backend


def test_csv_is_the_default_and_needs_no_impala_variables() -> None:
    assert resolve_data_backend({}) == "csv"
    assert resolve_data_backend({"DATA_BACKEND": ""}) == "csv"
    status, detail = impala_status({})
    assert status == "SKIPPED" and "optional" in detail


def test_impala_variables_alone_do_not_switch_the_backend() -> None:
    status, detail = impala_status({"IMPALA_HOST": "impala.invalid"})
    assert status == "SKIPPED" and "DATA_BACKEND=csv" in detail


def test_impala_must_be_selected_explicitly_and_never_falls_back() -> None:
    assert resolve_data_backend({"DATA_BACKEND": "impala"}) == "impala"
    with pytest.raises(BackendConfigError, match="never falls back to CSV"):
        impala_status({"DATA_BACKEND": "impala"})
    assert impala_status({"DATA_BACKEND": "impala", "IMPALA_HOST": "impala.invalid"})[0] == "READY"
    with pytest.raises(BackendConfigError):
        resolve_data_backend({"DATA_BACKEND": "postgres"})


def test_the_participant_data_path_never_imports_impala() -> None:
    import sys

    from bni_training.data import engine, semantic_layer  # noqa: F401

    assert not any(name.startswith("impala") for name in sys.modules)

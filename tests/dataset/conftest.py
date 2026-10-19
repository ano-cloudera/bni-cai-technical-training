from __future__ import annotations

import pytest
import yaml

from bni_training.data.dictionary import DataDictionary
from bni_training.data.engine import AccessPolicy, CsvEngine
from bni_training.data.semantic_layer import SemanticModel


@pytest.fixture(scope="session")
def dictionary() -> DataDictionary:
    return DataDictionary.load()


@pytest.fixture(scope="session")
def engine():
    eng = CsvEngine()
    yield eng
    eng.close()


@pytest.fixture(scope="session")
def semantic() -> SemanticModel:
    return SemanticModel.load()


@pytest.fixture(scope="session")
def everything(dictionary) -> AccessPolicy:
    return AccessPolicy(frozenset(dictionary.table_names), {})


HIDDEN_TABLE, HIDDEN_COLUMN = "transactions", "merchant_category"


@pytest.fixture(scope="session")
def hidden_dictionary(tmp_path_factory) -> DataDictionary:
    """The real dictionary with one column marked hidden, to exercise the hidden-column guards.

    The shipped dictionary exposes every column; the guard is still part of the engine and is tested here.
    """
    from bni_training.data.dictionary import SEMANTIC_DIR

    raw = yaml.safe_load((SEMANTIC_DIR / "data_dictionary.yaml").read_text(encoding="utf-8"))
    raw["tables"][HIDDEN_TABLE]["columns"][HIDDEN_COLUMN]["participant_exposed"] = False
    path = tmp_path_factory.mktemp("dictionary") / "data_dictionary.yaml"
    path.write_text(yaml.safe_dump(raw, sort_keys=False), encoding="utf-8")
    return DataDictionary.load(path)


@pytest.fixture(scope="session")
def hidden_engine(hidden_dictionary):
    eng = CsvEngine(dictionary=hidden_dictionary)
    yield eng
    eng.close()

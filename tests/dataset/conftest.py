from __future__ import annotations

import pytest

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

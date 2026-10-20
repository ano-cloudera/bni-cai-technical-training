"""The CAI notebooks embed questions with the same model the trainer indexed with, not the local hashing stand-in."""

from __future__ import annotations

import sys
import types

import pytest

from bni_training.rag import HashingEmbedder, SentenceTransformerEmbedder


class FakeModel:
    def __init__(self, path, device):
        self.path, self.device = path, device

    def get_sentence_embedding_dimension(self) -> int:
        return 1024

    def encode(self, texts, normalize_embeddings=False):
        assert normalize_embeddings is True
        return [[0.5] * 1024 for _ in texts]


def test_the_embedder_wraps_a_sentence_transformers_model(monkeypatch) -> None:
    monkeypatch.setitem(sys.modules, "sentence_transformers", types.SimpleNamespace(SentenceTransformer=FakeModel))
    embedder = SentenceTransformerEmbedder("/models/bge-m3/")
    assert embedder.name == "bge-m3" and embedder.dim == 1024
    assert len(embedder.embed("delinquency")) == 1024
    assert [len(vector) for vector in embedder.embed_many(["a", "b"])] == [1024, 1024]


def test_a_missing_package_says_which_kernel_to_choose(monkeypatch) -> None:
    monkeypatch.setitem(sys.modules, "sentence_transformers", None)
    with pytest.raises(RuntimeError, match="BNI rag"):
        SentenceTransformerEmbedder("/models/bge-m3")


def test_the_local_stand_in_has_another_dimension_than_bge_m3() -> None:
    """The reason the notebook must not use it against the shared collection."""
    assert HashingEmbedder().dim == 256

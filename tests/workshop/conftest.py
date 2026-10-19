from __future__ import annotations

from pathlib import Path

import pytest
from helpers import FakeLLM

from bni_training.data.engine import CsvEngine
from bni_training.workshop.group_registry import GroupRegistry
from bni_training.workshop.portal.config import PortalConfig
from bni_training.workshop.portal.gate import InferenceGate
from bni_training.workshop.portal.service import PortalService

ROOT = Path(__file__).resolve().parents[2]


@pytest.fixture(scope="session")
def registry() -> GroupRegistry:
    return GroupRegistry.load()


@pytest.fixture(scope="session")
def shared_engine():
    """One real in-memory copy of the physical dataset shared by all tests (loaded once for speed)."""
    engine = CsvEngine()
    yield engine
    engine.close()


@pytest.fixture
def make_service(tmp_path, registry, shared_engine):
    created: list[PortalService] = []

    def factory(
        llm=None, registry_override=None, gate=None, tracer=None, qdrant=None, embed=None, **gate_args
    ):
        gate = gate or InferenceGate(**{"retry_backoff_s": 0.0, **gate_args})
        service = PortalService(
            registry_override or registry,
            PortalConfig(mode="local", llm_base_url="http://unused.invalid/v1"),
            gate,
            llm_factory=lambda: llm or FakeLLM(),
            csv_engine=shared_engine,
            tracer=tracer,
            qdrant_client=qdrant,
            embed=embed,
            runtime_dir=tmp_path / "runtime",
        )
        created.append(service)
        return service

    yield factory
    for service in created:
        service.gate.close()

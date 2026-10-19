from __future__ import annotations

from pathlib import Path

import pytest
from helpers import FakeLLM

from bni_training.workshop.group_registry import GroupRegistry
from bni_training.workshop.portal.config import PortalConfig
from bni_training.workshop.portal.gate import InferenceGate
from bni_training.workshop.portal.service import PortalService, default_data_tool_factory

ROOT = Path(__file__).resolve().parents[2]


@pytest.fixture(scope="session")
def registry() -> GroupRegistry:
    return GroupRegistry.load()


@pytest.fixture(scope="session")
def shared_tool(registry):
    """One real CSV tool shared by all tests (loading 230k rows once keeps the suite fast)."""
    return default_data_tool_factory(registry.dataset("credit_portfolio"))


@pytest.fixture
def make_service(tmp_path, registry, shared_tool):
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
            data_tool_factory=lambda dataset: shared_tool,
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

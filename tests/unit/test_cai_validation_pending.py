from __future__ import annotations

from pathlib import Path

import yaml

REQUIRED = {
    "gpu-dependency-matrix",
    "cpu-only-torch-linux-rag",
    "live-qdrant-server",
    "vllm-qwen-model-loading",
    "cai-api-v2-fields",
    "live-impala-authentication",
}


def items() -> dict:
    data = yaml.safe_load(Path("config/cai-validation-pending.yaml").read_text())
    return {item["id"]: item for item in data["items"]}


def test_every_cai_only_item_is_registered_and_pending() -> None:
    registered = items()
    assert REQUIRED <= set(registered)
    assert "workshop-portal-capacity" in registered
    for item in registered.values():
        assert item["status"] == "cai-validation-pending", item["id"]
        assert item["evidence_needed"].strip() and item["validated_in"], item["id"]


def test_profiles_registry_keeps_gpu_and_rag_items_pending() -> None:
    profiles = yaml.safe_load(Path("requirements/profiles.yaml").read_text())["profiles"]
    for name in ("gpu-l40s", "gpu-h200"):
        assert profiles[name]["validation_status"] == "cai-validation-pending"
    assert profiles["rag"]["cpu_only_torch_strategy"] == "cai-validation-pending"
    assert profiles["rag"]["live_qdrant_server"] == "cai-validation-pending"


def test_api_schema_doc_and_project_state_state_the_pending_items() -> None:
    assert "validation pending" in Path("automation/cai_api_v2/api_schema.md").read_text().lower()
    state = Path("PROJECT_STATE.md").read_text()
    assert "CAI readiness is NOT claimed" in state
    for phrase in ("GPU", "CPU-only torch", "live Qdrant", "Qwen", "API v2", "Impala"):
        assert phrase.lower() in state.lower(), phrase

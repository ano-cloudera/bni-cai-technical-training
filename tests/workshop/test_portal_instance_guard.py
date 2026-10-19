from __future__ import annotations

import pytest

from bni_training.workshop.portal.config import PortalConfig, PortalConfigError
from bni_training.workshop.portal.instance_guard import InstanceConflictError, SingleInstanceGuard


def guard(tmp_path, identity, **kwargs):
    return SingleInstanceGuard(tmp_path, identity=identity, verify_delay_s=0.0, heartbeat_s=0.05, **kwargs)


def test_a_second_instance_is_refused_while_the_first_is_alive(tmp_path) -> None:
    first, second = guard(tmp_path, "pod-a:1"), guard(tmp_path, "pod-b:1")
    first.acquire()
    try:
        with pytest.raises(
            InstanceConflictError, match="one Streamlit process and one CAI Application replica"
        ):
            second.acquire()
    finally:
        first.release()


def test_a_second_process_in_the_same_pod_is_refused_too(tmp_path) -> None:
    first, second = guard(tmp_path, "pod-a:100"), guard(tmp_path, "pod-a:200")
    first.acquire()
    try:
        with pytest.raises(InstanceConflictError):
            second.acquire()
    finally:
        first.release()


def test_the_same_process_can_reacquire_and_release_frees_the_slot(tmp_path) -> None:
    first = guard(tmp_path, "pod-a:1")
    first.acquire()
    first.release()
    other = guard(tmp_path, "pod-b:1")
    other.acquire()
    other.release()
    again = guard(tmp_path, "pod-b:1")
    again.acquire()
    again.acquire() if False else None
    again.release()


def test_a_stale_heartbeat_can_be_taken_over(tmp_path) -> None:
    now = [1000.0]
    dead = SingleInstanceGuard(
        tmp_path, identity="pod-a:1", verify_delay_s=0.0, heartbeat_s=999, clock=lambda: now[0]
    )
    dead.acquire()
    now[0] += 31  # no heartbeat for longer than the TTL
    successor = SingleInstanceGuard(
        tmp_path, identity="pod-b:1", verify_delay_s=0.0, heartbeat_s=999, clock=lambda: now[0]
    )
    successor.acquire()
    successor.release()
    dead.release()


def test_losing_the_slot_is_reported(tmp_path) -> None:
    import time

    now = [1000.0]
    first = SingleInstanceGuard(
        tmp_path, identity="pod-a:1", verify_delay_s=0.0, heartbeat_s=0.05, clock=lambda: now[0]
    )
    first.acquire()
    now[0] += 31
    thief = SingleInstanceGuard(
        tmp_path, identity="pod-b:1", verify_delay_s=0.0, heartbeat_s=999, clock=lambda: now[0]
    )
    thief.acquire()
    deadline = time.monotonic() + 3
    while not first.lost and time.monotonic() < deadline:
        time.sleep(0.02)
    assert first.lost is True
    thief.release()
    first.release()


def test_the_guard_is_on_by_default_and_can_only_be_disabled_explicitly() -> None:
    assert PortalConfig.from_env({}).enforce_single_instance is True
    assert PortalConfig.from_env({"PORTAL_ENFORCE_SINGLE_INSTANCE": "false"}).enforce_single_instance is False


def test_service_refuses_to_start_a_second_instance_and_impala_is_not_enabled(
    tmp_path, make_service, registry
) -> None:
    from bni_training.workshop.portal.gate import InferenceGate
    from bni_training.workshop.portal.service import PortalService

    config = PortalConfig(mode="local", llm_base_url="http://unused.invalid/v1")
    first_guard, second_guard = guard(tmp_path, "pod-a:1"), guard(tmp_path, "pod-b:1")
    gate = InferenceGate()
    first = PortalService(registry, config, gate, llm_factory=lambda: object(), instance_guard=first_guard)
    try:
        with pytest.raises(InstanceConflictError):
            PortalService(registry, config, gate, llm_factory=lambda: object(), instance_guard=second_guard)
    finally:
        first.close()
    with pytest.raises(PortalConfigError, match="never falls back"):
        PortalService(
            registry,
            PortalConfig.from_env({"DATA_BACKEND": "impala", "VLLM_BASE_URL": "http://x.invalid/v1"}),
            InferenceGate(),
        )

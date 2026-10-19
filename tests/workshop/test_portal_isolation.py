"""Two or more groups (and two sessions of one group) must not see each other's data."""

from __future__ import annotations

import ast
import json
from pathlib import Path

import pytest
from helpers import two_dataset_registry, wait_done

from bni_training.workshop import group_paths
from bni_training.workshop.group_context import SessionContext
from bni_training.workshop.group_paths import UnsafePathError
from bni_training.workshop.group_registry import GroupAccessError
from bni_training.workshop.portal.state import PortalSessionState

Q1 = "Show account count by region marker-alpha"
Q2 = "Show outstanding balance by region marker-bravo"


def ask(service, state, question):
    ticket = service.submit_question(state, question)
    wait_done(ticket)
    return service.collect(state)


def test_chat_history_is_private_even_when_the_backing_store_is_shared(make_service) -> None:
    service = make_service()
    shared_backing: dict = {}  # worst case: the same mapping is (wrongly) used for every session
    one = service.state(shared_backing, service.open_session("group_01"))
    two = service.state(shared_backing, service.open_session("group_02"))
    ask(service, one, Q1)
    ask(service, two, Q2)
    assert [m["content"] for m in one.chat() if m["role"] == "user"] == [Q1]
    assert [m["content"] for m in two.chat() if m["role"] == "user"] == [Q2]
    assert "marker-bravo" not in json.dumps(one.chat()) and "marker-alpha" not in json.dumps(two.chat())


def test_two_sessions_of_the_same_group_do_not_share_chat_or_outputs(make_service) -> None:
    service = make_service()
    backing: dict = {}
    first = service.state(backing, service.open_session("group_05"))
    second = service.state(backing, service.open_session("group_05"))
    ask(service, first, Q1)
    assert second.chat() == []
    assert service.list_outputs(second.ctx) == []
    assert first.ctx.session_id != second.ctx.session_id


def test_a_forged_context_with_another_session_id_sees_nothing(make_service) -> None:
    service = make_service()
    backing: dict = {}
    victim = service.state(backing, service.open_session("group_01"))
    ask(service, victim, Q1)
    forged = PortalSessionState(backing, SessionContext("group_02", victim.ctx.session_id))
    assert forged.chat() == [] and forged.events() == [] and forged.dataset_id is None
    with pytest.raises(FileNotFoundError):
        service.read_output(forged.ctx, "answer-001.json")


def test_dataset_and_scenario_selection_is_per_session_and_only_assigned_ones(make_service, registry) -> None:
    service = make_service(registry_override=two_dataset_registry(registry))
    backing: dict = {}
    g1 = service.state(backing, service.open_session("group_01"))
    g2 = service.state(backing, service.open_session("group_02"))
    service.select_dataset(g1, "credit_portfolio_b")
    assert g1.dataset_id == "credit_portfolio_b" and g2.dataset_id == "credit_portfolio"
    with pytest.raises(GroupAccessError):
        service.select_dataset(g2, "credit_portfolio_b")
    with pytest.raises(GroupAccessError):
        service.select_scenario(g2, registry.group("group_01").scenario_ids[0])
    assert g2.scenario_id == registry.group("group_02").scenario_ids[0]


def test_outputs_land_only_in_the_owning_group_and_session_folder(make_service, tmp_path) -> None:
    service = make_service()
    backing: dict = {}
    one = service.state(backing, service.open_session("group_01"))
    two = service.state(backing, service.open_session("group_02"))
    ask(service, one, Q1)
    root = tmp_path / "runtime" / "groups"
    written = [p.relative_to(root) for p in root.rglob("*") if p.is_file()]
    assert written and all(p.parts[0] == "group_01" and one.ctx.session_id in p.parts for p in written)
    assert service.list_outputs(two.ctx) == [] and service.list_outputs(one.ctx)
    leaked = [p for p in (root / "group_02").rglob("*")] if (root / "group_02").exists() else []
    assert leaked == []


@pytest.mark.parametrize("name", ["../x", "../../group_02/output/x", "/etc/passwd", "a/b", ".hidden", ""])
def test_output_names_cannot_escape_the_session_folder(make_service, name) -> None:
    service = make_service()
    ctx = service.open_session("group_01")
    with pytest.raises(UnsafePathError):
        service.write_output(ctx, name, "x")
    with pytest.raises((UnsafePathError, FileNotFoundError)):
        service.read_output(ctx, name)


def test_oversized_output_is_refused(make_service) -> None:
    service = make_service()
    with pytest.raises(ValueError):
        service.write_output(
            service.open_session("group_01"), "big.txt", "x" * (group_paths.MAX_OUTPUT_BYTES + 1)
        )


def test_telemetry_events_are_per_session_and_carry_only_their_own_identity(make_service) -> None:
    service = make_service()
    backing: dict = {}
    one = service.state(backing, service.open_session("group_01"))
    two = service.state(backing, service.open_session("group_02"))
    ask(service, one, Q1)
    ask(service, two, Q2)
    for state, other in ((one, two), (two, one)):
        events = state.events()
        assert events and all(e["group_id"] == state.ctx.group_id for e in events)
        assert all(e["session_id"] == state.ctx.session_id for e in events)
        assert other.ctx.session_id not in json.dumps(events)


def test_leaving_a_group_clears_everything_that_session_owned(make_service) -> None:
    service = make_service()
    backing: dict = {}
    state = service.state(backing, service.open_session("group_01"))
    ask(service, state, Q1)
    state.clear()
    assert [k for k in backing if k.startswith(state.ctx.key_prefix)] == []


def test_session_ids_are_unguessable_and_unique(make_service) -> None:
    service = make_service()
    ids = {service.open_session("group_01").session_id for _ in range(200)}
    assert len(ids) == 200 and all(len(i) == 32 for i in ids)


def test_group_ids_are_validated_before_a_session_exists(make_service) -> None:
    service = make_service()
    for bad in ("group_00", "group_99", "../group_01", ""):
        with pytest.raises(ValueError):
            service.open_session(bad)


MUTABLE_CALLS = {"list", "dict", "set", "defaultdict", "deque", "Counter", "OrderedDict", "bytearray"}


def test_no_mutable_module_level_state_in_the_workshop_packages() -> None:
    offenders = []
    for path in Path("src/bni_training/workshop").rglob("*.py"):
        for node in ast.parse(path.read_text()).body:
            if not isinstance(node, (ast.Assign, ast.AnnAssign)) or node.value is None:
                continue
            value = node.value
            mutable = isinstance(
                value, (ast.List, ast.Dict, ast.Set, ast.ListComp, ast.DictComp, ast.SetComp)
            )
            if isinstance(value, ast.Call) and isinstance(value.func, ast.Name):
                mutable = mutable or value.func.id in MUTABLE_CALLS
            if mutable:
                offenders.append(f"{path}:{node.lineno}")
    assert offenders == [], offenders

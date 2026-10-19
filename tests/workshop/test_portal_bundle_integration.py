"""The shared Portal serves each group's logical bundle and mission from the one physical dataset."""

from __future__ import annotations

import json

import pytest
from helpers import question_for, wait_done

from bni_training.data.tool import CrossGroupAccessError, DataRequest
from bni_training.workshop.portal.gate import TicketState

GROUPS = [f"group_{i:02d}" for i in range(1, 11)]


def test_every_groups_first_sample_question_is_answered_with_data_from_its_own_bundle(
    make_service, tmp_path
) -> None:
    service = make_service()
    for group_id in GROUPS:
        state = service.state({}, service.open_session(group_id))
        wait_done(service.submit_question(state, question_for(group_id)))
        assert service.collect(state)["state"] == "completed", group_id
        saved = json.loads(service.read_output(state.ctx, "answer-001.json"))
        assert saved["row_count"] > 0 and saved["rows"], group_id


def test_every_data_request_carries_group_session_dataset_and_mission(make_service) -> None:
    service = make_service()
    state = service.state({}, service.open_session("group_06"))
    wait_done(service.submit_question(state, question_for("group_06")))
    service.collect(state)
    saved = json.loads(service.read_output(state.ctx, "answer-001.json"))
    dataset = service.registry.dataset(state.dataset_id)
    assert saved["group_id"] == "group_06" and saved["session_id"] == state.ctx.session_id
    assert saved["dataset_id"] == dataset.dataset_id and saved["mission_id"] == "unusual_transaction_patterns"


def test_asking_for_a_metric_outside_the_mission_fails_with_a_friendly_message(make_service) -> None:
    service = make_service()
    state = service.state({}, service.open_session("group_02"))
    ticket = service.submit_question(state, "Show total loans")
    wait_done(ticket)
    assert ticket.state is TicketState.FAILED and ticket.attempts == 1, "a refusal is never retried"
    assert "not part of your mission" in ticket.message or "needs the table" in ticket.message
    service.collect(state)
    assert state.chat()[-1]["role"] == "system" and "Traceback" not in state.chat()[-1]["content"]
    assert service.list_outputs(state.ctx) == []


def test_a_breakdown_that_needs_another_groups_table_is_refused(make_service) -> None:
    service = make_service()
    state = service.state({}, service.open_session("group_02"))
    ticket = service.submit_question(state, "Show transaction count by segment")
    wait_done(ticket)
    assert ticket.state is TicketState.FAILED and "cannot be broken down" in ticket.message


def test_a_tool_bound_to_one_group_rejects_requests_naming_another(make_service, registry) -> None:
    service = make_service()
    dataset_one = registry.dataset(registry.group("group_01").dataset_ids[0])
    tool = service._tool_for("group_01", dataset_one)
    own = DataRequest("group_01", "a" * 32, dataset_one.dataset_id, dataset_one.mission_id)
    assert tool.query("Show total customers by segment", own)[1].row_count == 5
    other = registry.dataset(registry.group("group_02").dataset_ids[0])
    for forged in (
        DataRequest("group_02", "a" * 32, dataset_one.dataset_id, dataset_one.mission_id),
        DataRequest("group_01", "a" * 32, other.dataset_id, other.mission_id),
        DataRequest("group_01", "a" * 32, dataset_one.dataset_id, other.mission_id),
    ):
        with pytest.raises(CrossGroupAccessError):
            tool.query("Show total customers by segment", forged)


def test_there_is_one_tool_per_group_but_one_engine(make_service, registry) -> None:
    service = make_service()
    tools = [service._tool_for(g, registry.dataset(registry.group(g).dataset_ids[0])) for g in GROUPS]
    assert len({id(t) for t in tools}) == 10
    assert len({id(t._engine) for t in tools}) == 1


def test_csv_mode_needs_no_impala_variables(make_service, monkeypatch) -> None:
    for name in (
        "IMPALA_HOST",
        "IMPALA_USERNAME",
        "IMPALA_PASSWORD",
        "IMPALA_KERBEROS_SERVICE_NAME",
        "DATA_BACKEND",
    ):
        monkeypatch.delenv(name, raising=False)
    service = make_service()
    state = service.state({}, service.open_session("group_01"))
    wait_done(service.submit_question(state, question_for("group_01")))
    assert service.collect(state)["state"] == "completed"
    assert service.config.data_backend == "csv"

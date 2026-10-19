from __future__ import annotations

import pytest

from bni_training.workshop.group_registry import GroupAccessError, UnknownGroupError

GROUP_IDS = [f"group_{i:02d}" for i in range(1, 11)]


def test_ten_groups_each_with_one_distinct_scenario_and_the_synthetic_dataset(registry) -> None:
    assert list(registry.group_ids) == GROUP_IDS
    scenarios = [registry.group(g).scenario_ids for g in GROUP_IDS]
    assert all(len(s) == 1 for s in scenarios)
    assert len({s[0] for s in scenarios}) == 10
    assert all(registry.group(g).dataset_ids == ("credit_portfolio",) for g in GROUP_IDS)


@pytest.mark.parametrize("group_id", GROUP_IDS)
def test_valid_groups_are_accepted(registry, group_id) -> None:
    assert registry.validate(group_id) == group_id


@pytest.mark.parametrize(
    "bad",
    [
        "",
        "group_00",
        "group_11",
        "GROUP_01",
        "group_01 ",
        " group_01",
        "group_1",
        "../group_01",
        "group_01/x",
        None,
        1,
    ],
)
def test_invalid_or_unknown_groups_are_rejected(registry, bad) -> None:
    with pytest.raises(UnknownGroupError):
        registry.validate(bad)


def test_a_group_cannot_select_another_groups_scenario_or_dataset(registry) -> None:
    with pytest.raises(GroupAccessError):
        registry.require_scenario("group_01", registry.group("group_02").scenario_ids[0])
    with pytest.raises(GroupAccessError):
        registry.require_dataset("group_01", "some_other_dataset")


def test_every_scenario_sample_question_runs_on_the_synthetic_data(registry, shared_tool) -> None:
    for group_id in GROUP_IDS:
        scenario = registry.scenario(registry.group(group_id).scenario_ids[0])
        assert scenario.sample_questions, group_id
        for question in scenario.sample_questions:
            _sql, result = shared_tool.query(question)
            assert result.row_count > 0, (group_id, question)

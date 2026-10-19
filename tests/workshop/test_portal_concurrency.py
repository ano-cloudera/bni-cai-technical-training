"""About 40 participants (ten groups of four) using one shared portal at the same time."""

from __future__ import annotations

import json
import threading

from helpers import FakeLLM, question_for, wait_done

GROUPS = [f"group_{i:02d}" for i in range(1, 11)]


def test_forty_concurrent_sessions_get_only_their_own_answers_and_files(make_service, tmp_path) -> None:
    llm = FakeLLM(delay=0.01)
    service = make_service(llm=llm, max_concurrent=3, max_queue=60)
    backing: dict = {}  # one deliberately shared mapping for all 40 sessions
    sessions = [(g, i, service.state(backing, service.open_session(g))) for g in GROUPS for i in range(1, 5)]
    assert len(sessions) == 40
    errors: list[BaseException] = []

    def participant(group, index, state):
        try:
            marker = f"marker-{group}-p{index}"
            ticket = service.submit_question(state, question_for(group, marker))
            wait_done(ticket, 60)
            service.collect(state)
        except BaseException as exc:  # noqa: BLE001
            errors.append(exc)

    threads = [threading.Thread(target=participant, args=s) for s in sessions]
    for t in threads:
        t.start()
    for t in threads:
        t.join(90)
    assert errors == []
    assert service.gate.stats()["peak_processing"] <= 3
    assert llm.calls == 40
    runtime = tmp_path / "runtime" / "groups"
    for group, index, state in sessions:
        marker = f"marker-{group}-p{index}"
        chat = json.dumps(state.chat())
        assert marker in chat
        for other_group, other_index, _ in sessions:
            other = f"marker-{other_group}-p{other_index}"
            assert other == marker or other not in chat
        files = [p for p in (runtime / group).rglob("*.json") if state.ctx.session_id in p.parts]
        assert len(files) == 1 and marker in files[0].read_text()
    assert sorted(p.name for p in runtime.iterdir()) == GROUPS

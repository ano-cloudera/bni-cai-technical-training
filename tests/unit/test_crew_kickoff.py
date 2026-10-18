from __future__ import annotations

import asyncio

from bni_training.crew import kickoff_blocking


class FakeCrew:
    def __init__(self):
        self.loop_running_in_thread = None

    def kickoff(self, inputs=None):
        try:
            asyncio.get_running_loop()
            self.loop_running_in_thread = True
        except RuntimeError:
            self.loop_running_in_thread = False
        if self.loop_running_in_thread:
            raise RuntimeError("Agent execution was invoked synchronously from within a running event loop")
        return f"done:{inputs}"


def test_kickoff_blocking_works_without_a_loop() -> None:
    assert kickoff_blocking(FakeCrew(), {"a": 1}) == "done:{'a': 1}"


def test_kickoff_blocking_works_inside_a_running_loop_like_jupyter() -> None:
    async def inside_loop():
        crew = FakeCrew()
        return kickoff_blocking(crew, {"q": "x"}), crew.loop_running_in_thread

    result, loop_in_worker = asyncio.run(inside_loop())
    assert result == "done:{'q': 'x'}" and loop_in_worker is False

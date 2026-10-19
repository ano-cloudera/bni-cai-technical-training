from __future__ import annotations

import threading
import time
from pathlib import Path

from bni_training.workshop.group_registry import GroupRegistry

ROOT = Path(__file__).resolve().parents[2]


class FakeLLM:
    """Echoes the user's question so tests can see exactly which text reached which session."""

    def __init__(self, delay: float = 0.0, fail: BaseException | None = None):
        self.delay, self.fail = delay, fail
        self.calls = 0
        self._lock = threading.Lock()

    def chat(self, messages, temperature=0.0, max_tokens=512, timeout=90):
        with self._lock:
            self.calls += 1
        time.sleep(self.delay)
        if self.fail is not None:
            raise self.fail
        question = next(m["content"] for m in messages if m["role"] == "user").splitlines()[0]
        return {"choices": [{"message": {"content": f"ANSWER<{question}>"}}]}


def two_dataset_registry(registry: GroupRegistry) -> GroupRegistry:
    """The real registry plus a second dataset bundle that only group_01 is assigned."""
    import dataclasses

    from bni_training.workshop.group_registry import GroupSpec

    extra = dataclasses.replace(
        registry.dataset("customer_portfolio_bundle"), dataset_id="customer_portfolio_bundle_b"
    )
    datasets = {d: registry.dataset(d) for g in registry.group_ids for d in registry.group(g).dataset_ids}
    datasets[extra.dataset_id] = extra
    scenarios = {s: registry.scenario(s) for g in registry.group_ids for s in registry.group(g).scenario_ids}
    groups = []
    for group_id in registry.group_ids:
        spec = registry.group(group_id)
        dataset_ids = (*spec.dataset_ids, extra.dataset_id) if group_id == "group_01" else spec.dataset_ids
        groups.append(GroupSpec(group_id, spec.scenario_ids, dataset_ids))
    return GroupRegistry(datasets, scenarios, groups)


def question_for(group_id: str, marker: str = "") -> str:
    """A question valid for the group's own bundle (its first sample question) plus an optional marker."""
    from bni_training.data.bundles import BundleCatalog

    question = BundleCatalog.load().for_group(group_id).sample_questions[0]
    return f"{question} {marker}".strip()


def wait_done(ticket, timeout: float = 15.0) -> None:
    assert ticket.wait(timeout), f"ticket still {ticket.state}"

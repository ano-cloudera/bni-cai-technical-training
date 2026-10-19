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
    """The real registry plus a second dataset that only group_01 is assigned."""
    import yaml

    raw = yaml.safe_load((ROOT / "config" / "workshop" / "groups.yaml").read_text())
    base = registry.dataset("credit_portfolio")
    raw["datasets"]["credit_portfolio_b"] = {
        "title": "Second synthetic dataset",
        "csv_dir": str(base.csv_dir),
        "semantic_model": str(base.semantic_model),
    }
    raw["groups"][0]["datasets"] = ["credit_portfolio", "credit_portfolio_b"]
    return GroupRegistry(raw)


def wait_done(ticket, timeout: float = 15.0) -> None:
    assert ticket.wait(timeout), f"ticket still {ticket.state}"

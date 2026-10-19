from __future__ import annotations

import copy
from collections.abc import MutableMapping
from typing import Any

from bni_training.workshop.group_context import NamespacedState, SessionContext

MAX_EVENTS = 200


class PortalSessionState:
    """Everything one browser session owns. All keys are namespaced by group_id and session_id."""

    def __init__(self, backing: MutableMapping[str, Any], ctx: SessionContext):
        self._ns = NamespacedState(backing, ctx)

    @property
    def ctx(self) -> SessionContext:
        return self._ns.ctx

    # chat -----------------------------------------------------------------------------------------
    def chat(self) -> list[dict]:
        return copy.deepcopy(self._ns.get("chat", []))

    def add_message(self, role: str, content: str, **meta: Any) -> None:
        messages = self._ns.get("chat", [])
        self._ns.set("chat", [*messages, {"role": role, "content": content, **meta}])

    # group lock ------------------------------------------------------------------------------------
    @property
    def locked(self) -> bool:
        return bool(self._ns.get("locked", False))

    def lock(self) -> None:
        """Called on the first chat or workflow action; the group can then only change via reset."""
        self._ns.set("locked", True)

    # selections -----------------------------------------------------------------------------------
    @property
    def dataset_id(self) -> str | None:
        return self._ns.get("dataset_id")

    @dataset_id.setter
    def dataset_id(self, value: str) -> None:
        self._ns.set("dataset_id", value)

    @property
    def scenario_id(self) -> str | None:
        return self._ns.get("scenario_id")

    @scenario_id.setter
    def scenario_id(self, value: str) -> None:
        self._ns.set("scenario_id", value)

    # in-flight request ----------------------------------------------------------------------------
    @property
    def active_ticket(self):
        return self._ns.get("active_ticket")

    @active_ticket.setter
    def active_ticket(self, ticket) -> None:
        self._ns.set("active_ticket", ticket)

    def next_answer_number(self) -> int:
        number = self._ns.get("answer_count", 0) + 1
        self._ns.set("answer_count", number)
        return number

    # telemetry metadata of this session only --------------------------------------------------------
    def events(self) -> list[dict]:
        return copy.deepcopy(self._ns.get("events", []))

    def add_event(self, **event: Any) -> None:
        events = [
            *self._ns.get("events", []),
            {"group_id": self.ctx.group_id, "session_id": self.ctx.session_id, **event},
        ]
        self._ns.set("events", events[-MAX_EVENTS:])

    def clear(self) -> None:
        self._ns.clear()

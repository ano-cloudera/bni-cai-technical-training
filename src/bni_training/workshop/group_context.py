from __future__ import annotations

import re
import uuid
from collections.abc import MutableMapping
from dataclasses import dataclass
from typing import Any

from bni_training.config import validate_group_id

_SESSION_ID = re.compile(r"^[0-9a-f]{32}$")


def new_session_id() -> str:
    return uuid.uuid4().hex


@dataclass(frozen=True)
class SessionContext:
    """Immutable identity of one browser session inside one group."""

    group_id: str
    session_id: str

    def __post_init__(self) -> None:
        validate_group_id(self.group_id)
        if not isinstance(self.session_id, str) or not _SESSION_ID.fullmatch(self.session_id):
            raise ValueError("session_id must be 32 lowercase hex characters")

    @property
    def key_prefix(self) -> str:
        return f"portal::{self.group_id}::{self.session_id}::"


class NamespacedState:
    """A view of a mutable mapping whose keys are always prefixed by group_id and session_id.

    The backing mapping may even be shared between sessions (a bug elsewhere); this view still cannot read or
    write another session's keys because it only ever builds keys from its own context.
    """

    def __init__(self, backing: MutableMapping[str, Any], ctx: SessionContext):
        self._backing = backing
        self._ctx = ctx

    @property
    def ctx(self) -> SessionContext:
        return self._ctx

    def get(self, name: str, default: Any = None) -> Any:
        return self._backing.get(self._ctx.key_prefix + name, default)

    def set(self, name: str, value: Any) -> None:
        self._backing[self._ctx.key_prefix + name] = value

    def clear(self) -> None:
        prefix = self._ctx.key_prefix
        for key in [k for k in list(self._backing) if isinstance(k, str) and k.startswith(prefix)]:
            del self._backing[key]

"""Shared inference gate: a bounded FIFO queue served by a fixed number of workers.

Every LLM request of every group passes through one gate, so the shared vLLM endpoint never sees more than
``max_concurrent`` simultaneous portal requests (default 3). The gate holds tickets only while they are in
flight; it stores no chat, dataset, output, or telemetry content.
"""

from __future__ import annotations

import contextvars
import socket
import threading
import time
import types
import urllib.error
from collections import deque
from collections.abc import Callable
from enum import Enum
from typing import Any


class TicketState(str, Enum):
    QUEUED = "queued"
    PROCESSING = "processing"
    COMPLETED = "completed"
    FAILED = "failed"
    CANCELLED = "cancelled"
    TIMED_OUT = "timed_out"
    REJECTED = "rejected"


TERMINAL = frozenset(
    {
        TicketState.COMPLETED,
        TicketState.FAILED,
        TicketState.CANCELLED,
        TicketState.TIMED_OUT,
        TicketState.REJECTED,
    }
)


class RequestCancelled(Exception):
    pass


class CancelToken:
    def __init__(self) -> None:
        self._event = threading.Event()

    def cancel(self) -> None:
        self._event.set()

    @property
    def cancelled(self) -> bool:
        return self._event.is_set()

    def wait(self, seconds: float) -> bool:
        return self._event.wait(seconds)

    def raise_if_cancelled(self) -> None:
        if self.cancelled:
            raise RequestCancelled()


def is_timeout(exc: BaseException) -> bool:
    return isinstance(exc, (TimeoutError, socket.timeout)) or (
        isinstance(exc, urllib.error.URLError) and isinstance(exc.reason, (TimeoutError, socket.timeout))
    )


def is_retryable(exc: BaseException) -> bool:
    if isinstance(exc, urllib.error.HTTPError):
        return exc.code == 429 or exc.code >= 500
    return is_timeout(exc) or isinstance(exc, (urllib.error.URLError, ConnectionError))


_MESSAGES = types.MappingProxyType(
    {
        TicketState.QUEUED: "Waiting for a free slot on the shared model.",
        TicketState.PROCESSING: "The shared model is working on your request.",
        TicketState.COMPLETED: "Done.",
        TicketState.CANCELLED: "Request cancelled.",
        TicketState.TIMED_OUT: "The model took too long to answer. Please try again in a moment.",
        TicketState.REJECTED: (
            "The workshop model is very busy right now. Please wait a few seconds and try again."
        ),
        TicketState.FAILED: (
            "The request could not be completed. Please try again; tell the trainer if it keeps failing."
        ),
    }
)


class Ticket:
    """One request. Created by the gate; owned by the submitting session."""

    def __init__(self, gate: InferenceGate, group_id: str, session_id: str, now: float):
        self.group_id = group_id
        self.session_id = session_id
        self.submitted_at = now
        self.attempts = 0
        self._gate = gate
        self._state = TicketState.QUEUED
        self._result: Any = None
        self._detail = ""
        self._done = threading.Event()
        self.token = CancelToken()

    @property
    def state(self) -> TicketState:
        return self._state

    @property
    def done(self) -> bool:
        return self._state in TERMINAL

    @property
    def result(self) -> Any:
        return self._result

    @property
    def detail(self) -> str:
        return self._detail

    @property
    def message(self) -> str:
        return _MESSAGES[self._state]

    def position(self) -> int:
        """1-based place in the queue, or 0 when not queued."""
        return self._gate._position(self)

    def wait(self, timeout: float | None = None) -> bool:
        return self._done.wait(timeout)

    def cancel(self) -> bool:
        return self._gate._cancel(self)

    def _finish(self, state: TicketState, result: Any = None, detail: str = "") -> None:
        self._state, self._result, self._detail = state, result, detail
        self._done.set()


Job = Callable[[CancelToken, float], Any]


class InferenceGate:
    def __init__(
        self,
        max_concurrent: int = 3,
        max_queue: int = 60,
        queue_timeout_s: float = 120.0,
        request_timeout_s: float = 60.0,
        max_retries: int = 2,
        retry_backoff_s: float = 1.0,
        clock: Callable[[], float] = time.monotonic,
    ):
        if max_concurrent < 1 or max_queue < 1:
            raise ValueError("max_concurrent and max_queue must be at least 1")
        self.max_concurrent = max_concurrent
        self.max_queue = max_queue
        self.queue_timeout_s = queue_timeout_s
        self.request_timeout_s = request_timeout_s
        self.max_retries = max_retries
        self.retry_backoff_s = retry_backoff_s
        self._clock = clock
        self._cond = threading.Condition()
        self._queue: deque[tuple[Ticket, Job, contextvars.Context]] = deque()
        self._processing = 0
        self._peak = 0
        self._closed = False
        self._workers = [
            threading.Thread(target=self._work, name=f"inference-gate-{i}", daemon=True)
            for i in range(max_concurrent)
        ]
        for worker in self._workers:
            worker.start()

    def submit(self, job: Job, *, group_id: str, session_id: str) -> Ticket:
        ticket = Ticket(self, group_id, session_id, self._clock())
        context = contextvars.copy_context()  # keeps the caller's tracing attributes in the worker
        with self._cond:
            if self._closed or len(self._queue) >= self.max_queue:
                ticket._finish(TicketState.REJECTED, detail="queue full")
                return ticket
            self._queue.append((ticket, job, context))
            self._cond.notify()
        return ticket

    def stats(self) -> dict[str, int]:
        """Aggregate counts only; nothing about who is in the queue."""
        with self._cond:
            return {
                "queued": len(self._queue),
                "processing": self._processing,
                "max_concurrent": self.max_concurrent,
                "peak_processing": self._peak,
            }

    def close(self) -> None:
        with self._cond:
            self._closed = True
            self._cond.notify_all()
        for worker in self._workers:
            worker.join(timeout=2)

    def _position(self, ticket: Ticket) -> int:
        with self._cond:
            for index, (queued, _job, _ctx) in enumerate(self._queue, start=1):
                if queued is ticket:
                    return index
        return 0

    def _cancel(self, ticket: Ticket) -> bool:
        with self._cond:
            for item in list(self._queue):
                if item[0] is ticket:
                    self._queue.remove(item)
                    ticket._finish(TicketState.CANCELLED)
                    return True
        if ticket.done:
            return False
        ticket.token.cancel()  # a running request stops at its next checkpoint and is discarded
        return True

    def _work(self) -> None:
        while True:
            with self._cond:
                while not self._queue and not self._closed:
                    self._cond.wait()
                if self._closed and not self._queue:
                    return
                ticket, job, context = self._queue.popleft()
                if self._clock() - ticket.submitted_at > self.queue_timeout_s:
                    ticket._finish(TicketState.TIMED_OUT, detail="waited too long in the queue")
                    continue
                ticket._state = TicketState.PROCESSING
                self._processing += 1
                self._peak = max(self._peak, self._processing)
            try:
                context.run(self._run, ticket, job)
            finally:
                with self._cond:
                    self._processing -= 1

    def _run(self, ticket: Ticket, job: Job) -> None:
        last: BaseException | None = None
        for attempt in range(self.max_retries + 1):
            ticket.attempts = attempt + 1
            if ticket.token.cancelled:
                ticket._finish(TicketState.CANCELLED)
                return
            try:
                result = job(ticket.token, self.request_timeout_s)
            except RequestCancelled:
                ticket._finish(TicketState.CANCELLED)
                return
            except Exception as exc:  # noqa: BLE001 - classify, never crash a worker
                last = exc
                if attempt < self.max_retries and is_retryable(exc) and not ticket.token.cancelled:
                    ticket.token.wait(self.retry_backoff_s * (2**attempt))
                    continue
                break
            if ticket.token.cancelled:
                ticket._finish(TicketState.CANCELLED)  # discard the late answer
            else:
                ticket._finish(TicketState.COMPLETED, result=result)
            return
        state = TicketState.TIMED_OUT if last is not None and is_timeout(last) else TicketState.FAILED
        ticket._finish(state, detail=f"{type(last).__name__}")

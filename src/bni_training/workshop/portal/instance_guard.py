"""Best-effort guard that only one Portal process serves the workshop.

The inference gate (a semaphore) is process-local. Two Streamlit processes, or two CAI replicas, would each
allow their own 3 concurrent requests and silently double the load on the shared model. The authoritative
control is the CAI Application setting of exactly one replica; this guard makes a violation visible and
refuses to start a second instance while the first one's heartbeat is fresh. It is not a distributed lock.
"""

from __future__ import annotations

import json
import os
import socket
import threading
import time
from pathlib import Path

STATE_FILE = "portal-instance.json"


class InstanceConflictError(RuntimeError):
    pass


def default_identity() -> str:
    return f"{socket.gethostname()}:{os.getpid()}"


class SingleInstanceGuard:
    def __init__(
        self,
        state_dir: Path,
        *,
        identity: str | None = None,
        ttl_s: float = 30.0,
        heartbeat_s: float = 10.0,
        verify_delay_s: float = 0.2,
        clock=time.time,
    ):
        self.path = Path(state_dir) / STATE_FILE
        self.identity = identity or default_identity()
        self.ttl_s, self.heartbeat_s, self.verify_delay_s, self._clock = (
            ttl_s,
            heartbeat_s,
            verify_delay_s,
            clock,
        )
        self._stop = threading.Event()
        self._thread: threading.Thread | None = None
        self.lost = False

    def _read(self) -> dict | None:
        try:
            return json.loads(self.path.read_text(encoding="utf-8"))
        except (OSError, ValueError):
            return None

    def _write(self) -> None:
        self.path.parent.mkdir(parents=True, exist_ok=True)
        tmp = self.path.with_name(f".{STATE_FILE}.{os.getpid()}.tmp")
        tmp.write_text(json.dumps({"identity": self.identity, "heartbeat": self._clock()}), encoding="utf-8")
        os.replace(tmp, self.path)

    def acquire(self) -> None:
        current = self._read()
        if current and current.get("identity") != self.identity:
            if self._clock() - float(current.get("heartbeat", 0)) < self.ttl_s:
                raise InstanceConflictError(
                    "Another Workshop Portal instance is already running. The training topology requires "
                    "exactly one Streamlit process and one CAI Application replica "
                    "(the concurrency limit is process-local)."
                )
        self._write()
        time.sleep(self.verify_delay_s)  # a concurrent starter may have written after us: re-check
        after = self._read()
        if not after or after.get("identity") != self.identity:
            raise InstanceConflictError("Another Workshop Portal instance started at the same time.")
        self._stop.clear()
        self._thread = threading.Thread(target=self._beat, name="portal-instance-heartbeat", daemon=True)
        self._thread.start()

    def _beat(self) -> None:
        while not self._stop.wait(self.heartbeat_s):
            current = self._read()
            if current and current.get("identity") != self.identity:
                self.lost = True
                return
            try:
                self._write()
            except OSError:
                pass

    def release(self) -> None:
        self._stop.set()
        if self._thread:
            self._thread.join(timeout=2)
        current = self._read()
        if current and current.get("identity") == self.identity:
            try:
                self.path.unlink()
            except OSError:
                pass

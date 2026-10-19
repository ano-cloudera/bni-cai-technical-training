"""Application-level isolation probes. They prove the helpers refuse cross-group writes (not OS security)."""

from __future__ import annotations

import os
import tempfile
from dataclasses import dataclass
from pathlib import Path

from bni_training.data.bundles import GROUP_IDS

from . import group_paths
from .group_context import new_session_id
from .group_paths import UnsafePathError
from .group_registry import GroupRegistry, UnknownGroupError

NOTE = (
    "Application-level operational isolation only. All participants are collaborators in one CAI project; "
    "this is not OS-level or user-level security."
)


@dataclass
class Probe:
    name: str
    passed: bool
    detail: str = ""


def run_probes(registry: GroupRegistry | None = None) -> list[Probe]:
    """Run every probe inside a throwaway runtime directory. Real workspaces are never touched."""
    registry = registry or GroupRegistry.load()
    probes: list[Probe] = []

    def expect_rejected(name: str, fn, *exc_types) -> None:
        try:
            fn()
        except exc_types as exc:
            probes.append(Probe(name, True, type(exc).__name__))
        except Exception as exc:  # noqa: BLE001 - a different error type is still a failed probe
            probes.append(Probe(name, False, f"unexpected {type(exc).__name__}"))
        else:
            probes.append(Probe(name, False, "was accepted"))

    accepted = []
    for group in GROUP_IDS:
        try:
            registry.validate(group)
            accepted.append(group)
        except UnknownGroupError:
            pass
    probes.append(
        Probe(
            "the ten valid group ids are accepted", accepted == list(GROUP_IDS), f"{len(accepted)} accepted"
        )
    )
    for bad in (
        "group_00",
        "group_11",
        "GROUP_01",
        "group_1",
        "../group_01",
        "group_01/../group_02",
        "",
        "group_01 ",
    ):
        expect_rejected(
            f"group id {bad!r} is rejected", lambda b=bad: registry.validate(b), UnknownGroupError
        )
    with tempfile.TemporaryDirectory() as tmp:
        root = Path(tmp) / "runtime"
        session = new_session_id()
        (root / "groups" / "group_01" / "output").mkdir(parents=True)
        (root / "groups" / "group_02" / "output").mkdir(parents=True)
        for name in ("../x", "../../group_02/output/x", "/etc/passwd", "a/b", ".hidden", "x\x00y"):
            expect_rejected(
                f"file name {name!r} cannot leave the group folder",
                lambda n=name: group_paths.write_session_file(root, "group_01", session, n, "x"),
                UnsafePathError,
            )
        written = group_paths.write_session_file(root, "group_01", session, "ok.json", "{}")
        probes.append(
            Probe(
                "a valid write lands in the owning group's folder only",
                (root / "groups" / "group_01").resolve() in written.parents
                and not any((root / "groups" / "group_02").rglob("ok.json")),
            )
        )
        os.symlink(root / "groups" / "group_02" / "output", root / "groups" / "group_01" / "output" / "link")
        expect_rejected(
            "a symlink into another group's folder cannot be used",
            lambda: group_paths.safe_join(root / "groups" / "group_01", "output", "link"),
            UnsafePathError,
        )
        leaked = [p for p in (root / "groups" / "group_02").rglob("*") if p.is_file()]
        probes.append(Probe("nothing was written into the other group's folder", not leaked))
    return probes

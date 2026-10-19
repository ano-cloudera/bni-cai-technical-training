"""Shared runner for the canonical lab scripts: ``--mode local`` and ``--mode cai``.

Rules enforced here so that a lab can never pass silently:

* Every lab reports explicit checks with a status of PASS, SKIPPED, or FAIL.
* ``--mode local`` may use mocks or local services, but runs the complete code path of the lab.
  Checks that need a GPU, CAI, Impala, or the NFS model are reported as SKIPPED with a reason.
* ``--mode cai`` never uses mocks. A missing prerequisite is a FAIL, not a skip.
* The last output line is ``LAB_STATUS: ...`` and the exit code is 0 (PASS), 3 (SKIPPED), or 1 (FAIL).
"""

from __future__ import annotations

import argparse
import json
import os
import sys
import traceback
from collections.abc import Callable, Sequence
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

PASS, SKIPPED, FAIL = "PASS", "SKIPPED", "FAIL"
EXIT_CODES = {PASS: 0, FAIL: 1, SKIPPED: 3}
MODES = ("local", "cai")


class PrerequisiteMissing(RuntimeError):
    """Raised in cai mode when a required environment variable or service is absent."""


@dataclass
class Check:
    name: str
    status: str
    detail: str = ""


@dataclass
class LabReport:
    lab: str
    mode: str
    checks: list[Check] = field(default_factory=list)
    data: dict[str, Any] = field(default_factory=dict)
    context: Any = field(default=None, repr=False)

    def passed(self, name: str, detail: str = "") -> None:
        self.checks.append(Check(name, PASS, detail))

    def skipped(self, name: str, reason: str) -> None:
        self.checks.append(Check(name, SKIPPED, reason))

    def failed(self, name: str, detail: str) -> None:
        self.checks.append(Check(name, FAIL, detail))

    @property
    def status(self) -> str:
        statuses = {check.status for check in self.checks}
        if not self.checks or FAIL in statuses:
            return FAIL
        return PASS if PASS in statuses else SKIPPED

    @property
    def exit_code(self) -> int:
        return EXIT_CODES[self.status]

    def render(self) -> str:
        counts = {s: sum(c.status == s for c in self.checks) for s in (PASS, SKIPPED, FAIL)}
        body = {
            "lab": self.lab,
            "mode": self.mode,
            "checks": [vars(check) for check in self.checks],
            "data": self.data,
        }
        summary = (
            f"LAB_STATUS: lab={self.lab} mode={self.mode} status={self.status} "
            f"passed={counts[PASS]} skipped={counts[SKIPPED]} failed={counts[FAIL]}"
        )
        return json.dumps(body, indent=2, default=str) + "\n" + summary


def default_mode(env: dict[str, str] | None = None) -> str:
    value = (env if env is not None else os.environ).get("LAB_MODE", "local").lower()
    return value if value in MODES else "local"


def require_env(names: Sequence[str], env: dict[str, str] | None = None) -> dict[str, str]:
    source = env if env is not None else os.environ
    missing = [name for name in names if not source.get(name)]
    if missing:
        raise PrerequisiteMissing("Missing required environment variables: " + ", ".join(missing))
    return {name: source[name] for name in names}


def build_parser(description: str) -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description=description)
    parser.add_argument(
        "--mode",
        choices=MODES,
        default=default_mode(),
        help="local: mocks or local services, complete code path, no cluster. "
        "cai: real services from environment variables, no mocks. Default: $LAB_MODE or local.",
    )
    return parser


def run_lab(
    lab: str,
    description: str,
    body: Callable[[argparse.Namespace, LabReport], None],
    argv: Sequence[str] | None = None,
    configure: Callable[[argparse.ArgumentParser], None] | None = None,
    participant: bool | str = False,
) -> int:
    """Run a lab body and print its report.

    Participant labs (``participant=True``) resolve GROUP_ID, DATASET_ID, MISSION_ID and GROUP_WORKSPACE first
    (``report.context``) and save the finished report inside that group's own output folder.
    """
    parser = build_parser(description)
    if configure:
        configure(parser)
    args = parser.parse_args(list(argv) if argv is not None else None)
    report = LabReport(lab=lab, mode=args.mode)
    context = None
    try:
        if participant:
            from .workshop.lab_context import LabContextError, resolve_lab_context

            try:
                context = resolve_lab_context(args.mode)
            except LabContextError as exc:
                if participant != "optional":
                    raise PrerequisiteMissing(str(exc)) from exc
                report.data["group_error"] = str(exc)  # the trainer may run without a group
            else:
                report.context = context
                report.data["group"] = context.describe()
        body(args, report)
    except PrerequisiteMissing as exc:
        report.failed("prerequisites", str(exc))
    except Exception as exc:  # noqa: BLE001 - a lab must report, never crash silently
        report.failed("unhandled-exception", f"{type(exc).__name__}: {exc}")
        report.data["traceback"] = traceback.format_exc(limit=6)
    if context is not None:
        try:
            saved = context.write_output(f"lab-{lab}-{args.mode}.json", report.render())
            report.data["saved_to"] = f"groups/{context.group_id}/output/{saved.name}"
        except Exception as exc:  # noqa: BLE001
            report.failed("save-output", f"{type(exc).__name__}: {exc}")
        finally:
            context.close()
    print(report.render())
    return report.exit_code


# --- shared lab helpers -------------------------------------------------------------------------

ROOT = Path(__file__).resolve().parents[2]
SEMANTIC_MODEL = ROOT / "semantic" / "credit_portfolio.yaml"
GLOSSARY = ROOT / "data" / "glossary" / "banking_glossary.jsonl"

if str(ROOT) not in sys.path:  # lets labs import the repository-level deployments package
    sys.path.insert(0, str(ROOT))


def resolve_repo_path(value: str | Path) -> Path:
    path = Path(value)
    return path if path.is_absolute() or path.exists() else ROOT / path


def build_settings(report: LabReport, mock_base_url: str | None = None):
    """Build Settings. Local mode forces explicit CSV; cai mode requires every variable."""
    from .config import Settings

    env = dict(os.environ)
    if report.mode == "local":
        env.update(
            GROUP_ID=env.get("GROUP_ID", "group_01"),
            DATA_MODE="csv",
            VLLM_BASE_URL=mock_base_url or env.get("VLLM_BASE_URL") or "http://example.invalid/v1",
            VLLM_API_KEY=env.get("VLLM_API_KEY", "local-placeholder"),
            CSV_DATA_DIR=str(resolve_repo_path(env.get("CSV_DATA_DIR", "data/csv"))),
        )
    else:
        require_env(["GROUP_ID", "DATA_MODE", "VLLM_BASE_URL"])
        if env["DATA_MODE"].lower() == "csv":
            env["CSV_DATA_DIR"] = str(resolve_repo_path(env.get("CSV_DATA_DIR", "data/csv")))
    return Settings.load(env)


def build_data_tool(settings):
    from .backends.factory import create_backend
    from .semantic import SemanticCatalog
    from .tools.data_tool import DataQueryTool

    return DataQueryTool(create_backend(settings), SemanticCatalog.load(SEMANTIC_MODEL))


def crewai_llm(base_url: str, api_key: str, model: str = "qwen3.5-9b"):
    try:
        from crewai import LLM
    except ImportError as exc:
        raise RuntimeError(
            "CrewAI is not installed. Install the participant (or rag/observability/dev-test) profile"
        ) from exc
    return LLM(model=f"openai/{model}", base_url=base_url, api_key=api_key or "none", temperature=0)


def shared_llm_settings(env: dict[str, str] | None = None) -> tuple[str, str, str]:
    """(base_url, api_key, model) of the ONE shared vLLM endpoint for labs 03-09. Never mocked in cai mode."""
    source = dict(os.environ if env is None else env)
    url = require_env(["VLLM_BASE_URL"], source)["VLLM_BASE_URL"]
    model = source.get("VLLM_MODEL") or source.get("SERVED_MODEL_NAME", "qwen3.5-9b")
    return url, source.get("VLLM_API_KEY", ""), model


def workshop_role(env: dict[str, str] | None = None) -> str:
    """'participant' (default) or 'trainer'. Trainer-only steps refuse to run for anyone else in cai mode."""
    value = (dict(os.environ if env is None else env)).get("WORKSHOP_ROLE", "participant").strip().lower()
    return value if value in ("participant", "trainer") else "participant"

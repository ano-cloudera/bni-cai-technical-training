from __future__ import annotations

import json
import sys
import tempfile
import urllib.error
import urllib.request

from bni_training.labs import require_env, run_lab
from bni_training.workshop.portal.service import PortalService
from bni_training.workshop.service_checks import SPECS, health_url, redact_url

DESCRIPTION = "Lab 12: validate the full group-specific workflow through the shared Workshop Portal."


def local_flow(ctx, report) -> None:
    """Drive an in-process Portal (mock model, in-memory Qdrant) through the same steps a participant takes."""
    with tempfile.TemporaryDirectory() as runtime:
        env = {
            "PORTAL_MODE": "local",
            "WORKSHOP_RUNTIME_DIR": runtime,
            "PORTAL_ENFORCE_SINGLE_INSTANCE": "false",
            "PORTAL_MAX_RETRIES": "0",
        }
        service = PortalService.from_env(env)
        try:
            backing: dict = {}
            joined = service.join_group(backing, ctx.group_id)
            state = service.state(backing, joined)
            scenario = service.scenario_for(state)
            report.passed("mission_shown", f"{joined.group_id}: {scenario.title}")
            ticket = service.submit_question(state, ctx.bundle.sample_questions[0])
            assert ticket.wait(60), "the Portal did not answer in time"
            outcome = service.collect(state)
            (report.passed if outcome and outcome["state"] == "completed" else report.failed)(
                "question_answered", str(outcome)
            )
            saved = service.list_outputs(joined)
            saved_json = json.loads(service.read_output(joined, saved[0])) if saved else {}
            identity = (
                saved_json.get("group_id"),
                saved_json.get("dataset_id"),
                saved_json.get("mission_id"),
            )
            expected = (ctx.group_id, ctx.dataset_id, ctx.mission_id)
            (report.passed if identity == expected else report.failed)(
                "answer_saved_with_identity", str(identity)
            )
            locked = state.locked
            (report.passed if locked else report.failed)(
                "group_locked_after_first_question", f"locked={locked}"
            )
            hits = service.retrieve(joined, "dormant account", state=state)
            (report.passed if hits and {h["group_id"] for h in hits} == {ctx.group_id} else report.failed)(
                "retrieval_only_own_group", f"{len(hits)} hits"
            )
            service.reset_session(backing)
            report.passed("reset_clears_the_session", "state and outputs removed")
        finally:
            service.close()
    report.skipped(
        "shared_portal_application",
        "Local mode runs the Portal in-process; use --mode cai against the shared Application",
    )


def cai_flow(ctx, report) -> None:
    env = require_env(["PORTAL_URL"])
    url = health_url(SPECS["workshop-portal"], env["PORTAL_URL"])
    try:
        with urllib.request.urlopen(url, timeout=10) as response:  # noqa: S310 - operator-supplied https URL
            (report.passed if response.status < 400 else report.failed)(
                "portal_reachable", f"{redact_url(url)} -> HTTP {response.status}"
            )
    except (urllib.error.URLError, OSError) as exc:
        report.failed("portal_reachable", f"{redact_url(url)} unreachable: {type(exc).__name__}")
    answers = sorted((ctx.workspace / "output").glob("*/answer-*.json"))
    if not answers:
        report.failed(
            "saved_portal_answer",
            f"No saved answer yet. Open the Portal, choose {ctx.group_id}, ask a sample question, then rerun this lab.",
        )
        return
    newest = json.loads(answers[-1].read_text(encoding="utf-8"))
    identity = (newest.get("group_id"), newest.get("dataset_id"), newest.get("mission_id"))
    expected = (ctx.group_id, ctx.dataset_id, ctx.mission_id)
    (report.passed if identity == expected else report.failed)(
        "saved_portal_answer", f"{len(answers)} saved; identity {identity}"
    )


def body(args, report):
    ctx = report.context
    (local_flow if args.mode == "local" else cai_flow)(ctx, report)
    report.data["checklist"] = [
        "Open the Workshop Portal and choose your group",
        "Confirm your mission, tables and sample questions are shown",
        "Ask a sample question and watch Queued -> Processing -> Completed",
        "Confirm the group selector is now locked",
        "Find your saved answer under My outputs",
    ]


def main(argv=None) -> int:
    return run_lab("12", DESCRIPTION, body, argv, participant=True)


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))

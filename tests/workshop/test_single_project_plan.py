from __future__ import annotations

import json
import os
import subprocess
import sys
from pathlib import Path

import pytest

from automation.cai_api_v2.planner import PlanError, build_single_project_plan, lifecycle_report

ROOT = Path(__file__).resolve().parents[2]
CONFIG = ROOT / "config" / "env.sandbox-l40s.example.yaml"


def test_the_default_single_project_plan_has_one_project_and_one_portal() -> None:
    plan = build_single_project_plan(CONFIG, env={})
    assert plan["dry_run"] is True and plan["topology"] == "single_project"
    assert plan["project_count"] == 1 and plan["projects"] == ["bni-ai-training-workshop"]
    assert plan["group_count"] == plan["group_workspace_count"] == 10
    assert plan["requested_session_count"] == 10 and plan["max_concurrent_session_count"] == 10
    assert plan["participant_mode"] == "group_driver"
    assert plan["per_group_streamlit_applications"] == 0 and "group_application_waves" not in plan
    assert plan["application_count"] == 5 and set(plan["applications"]) == {
        "vllm", "qdrant", "phoenix", "litellm", "workshop-portal",
    }  # fmt: skip
    assert plan["workshop_portal"]["replicas"] == 1 and plan["workshop_portal"]["streamlit_processes"] == 1
    assert plan["estimated_participant_cpu"] == 20 and plan["estimated_participant_memory_gb"] == 80
    assert plan["gpu_requirement"] == {"nvidia_gpu": 1, "applications": ["vllm"], "participant_sessions": 0}
    assert plan["data_backend"] == "csv" and plan["isolation"]["security_boundary"] is False


def test_individual_learning_is_explicit_and_remains_capacity_pending() -> None:
    plan = build_single_project_plan(CONFIG, env={"PARTICIPANT_MODE": "individual_learning"})

    assert plan["requested_session_count"] == 40
    assert plan["max_concurrent_session_count"] == 10
    assert plan["waves_needed"] == 4
    assert plan["individual_learning_status"] == "cai-validation-pending"
    assert plan["session_waves"][0][0] == "group_01/participant_01"


def test_the_plan_reports_unresolved_items_and_never_invents_a_runtime_identifier() -> None:
    plan = build_single_project_plan(CONFIG, env={})
    assert plan["required_runtime_identifier"]["resolved"] is False
    assert plan["required_runtime_identifier"]["value"].startswith("SET_FROM")
    assert {
        "gpu-dependency-matrix",
        "live-qdrant-server",
        "cai-api-v2-fields",
        "workshop-portal-capacity",
    } <= set(plan["unresolved_cai_validation_items"])


def test_the_application_count_never_exceeds_five_in_any_phase() -> None:
    phases = build_single_project_plan(CONFIG, env={})["active_applications_by_phase"]
    assert (
        phases["day1"]["active"] == ["phoenix", "qdrant", "vllm", "workshop-portal"]
        and phases["day1"]["active_count"] == 4
    )
    assert "litellm" not in phases["day1"]["active"]
    assert phases["day2_morning"]["active_count"] == 4 and phases["day2_morning"]["worst_case_count"] == 5
    publication = phases["agent_studio_publication"]
    assert set(publication["stop_before"]) == {"phoenix", "workshop-portal"}
    assert publication["worst_case_count"] <= 5
    assert all(p["worst_case_count"] <= 5 for p in phases.values())


def test_a_phase_over_the_limit_is_refused() -> None:
    lifecycle = {
        "phases": {
            "too_many": {"active": ["a", "b", "c"], "optional": ["d"], "reserved_agent_studio_slots": 2}
        }
    }
    with pytest.raises(PlanError, match="exceeds the limit"):
        lifecycle_report(lifecycle, {"a", "b", "c", "d"}, 5)
    with pytest.raises(PlanError, match="unknown applications"):
        lifecycle_report({"phases": {"x": {"active": ["zzz"]}}}, {"a"}, 5)


def test_session_waves_only_change_scheduling() -> None:
    full = build_single_project_plan(CONFIG, env={"MAX_CONCURRENT_GROUP_SESSIONS": "10"})
    halves = build_single_project_plan(CONFIG, env={"MAX_CONCURRENT_GROUP_SESSIONS": "5"})
    assert [len(w) for w in halves["session_waves"]] == [5, 5] and halves["session_waves"][0][0] == "group_01"
    assert halves["estimated_participant_cpu"] == 10
    for key in (
        "project_count",
        "group_count",
        "group_workspace_count",
        "application_count",
        "requested_session_count",
    ):
        assert halves[key] == full[key]
    for bad in ("0", "11", "many"):
        with pytest.raises(PlanError):
            build_single_project_plan(CONFIG, env={"MAX_CONCURRENT_GROUP_SESSIONS": bad})


def run_cli(*args: str, env: dict | None = None) -> dict:
    out = ROOT / "build" / "test-plan.json"
    command = [sys.executable, "-m", "automation.cai_api_v2.cli", "--config", str(CONFIG)]
    command += ["plan", *args, "--output", str(out)]
    environment = {**os.environ, "PYTHONPATH": "src:.", **(env or {})}
    subprocess.run(command, cwd=ROOT, env=environment, check=True, capture_output=True)
    return json.loads(out.read_text())


def test_multi_project_mode_still_produces_the_rc1_plan() -> None:
    plan = run_cli("--topology", "multi_project")
    assert len(plan["projects"]) == 11 and len(plan["group_application_waves"]) == 4
    assert run_cli(env={"WORKSHOP_TOPOLOGY": "multi_project"})["projects"] == plan["projects"]


def test_without_any_setting_the_cli_plans_single_project() -> None:
    plan = run_cli(env={"WORKSHOP_TOPOLOGY": ""})
    assert plan["topology"] == "single_project" and plan["dry_run"] is True
    assert plan["project_count"] == 1 and plan["group_workspace_count"] == 10
    assert plan["application_count"] == 5 and plan["per_group_streamlit_applications"] == 0
    assert plan["requested_session_count"] <= 10


def test_the_explicit_multi_project_plan_is_the_legacy_one() -> None:
    plan = run_cli("--topology", "multi_project", env={"WORKSHOP_TOPOLOGY": "single_project"})
    assert plan["topology"] == "multi_project" and len(plan["projects"]) == 11
    assert len(plan["group_application_waves"]) == 4


def cli_result(*args: str, env: dict | None = None) -> subprocess.CompletedProcess:
    command = [sys.executable, "-m", "automation.cai_api_v2.cli", "--config", str(CONFIG), *args]
    environment = {k: v for k, v in os.environ.items() if k != "WORKSHOP_TOPOLOGY"}
    environment.update({"PYTHONPATH": "src:.", **(env or {})})
    return subprocess.run(command, cwd=ROOT, env=environment, capture_output=True, text=True)


def test_an_invalid_topology_fails_clearly_and_writes_nothing(tmp_path) -> None:
    out = tmp_path / "plan.json"
    for env in ({"WORKSHOP_TOPOLOGY": "three_projects"},):
        result = cli_result("plan", "--output", str(out), env=env)
        assert result.returncode == 2 and "Unknown workshop topology 'three_projects'" in result.stderr
        assert "single_project" in result.stderr and "multi_project" in result.stderr
    assert not out.exists()


def test_the_rc1_commands_need_an_explicit_multi_project_topology() -> None:
    for command in ("apply-projects", "stop-wave --inventory x.json --wave 1"):
        result = cli_result(*command.split())
        assert result.returncode == 2 and "multi_project" in result.stderr


def test_planning_is_a_dry_run_and_needs_no_credentials(tmp_path) -> None:
    env = {"CAI_API_BASE_URL": "", "CAI_API_KEY": "", "HTTPS_PROXY": "http://127.0.0.1:9"}
    result = cli_result("plan", "--output", str(tmp_path / "p.json"), env=env)
    assert result.returncode == 0
    assert json.loads((tmp_path / "p.json").read_text())["dry_run"] is True


def test_the_cli_selects_single_project_by_flag_or_environment() -> None:
    assert run_cli("--topology", "single_project")["project_count"] == 1
    assert run_cli(env={"WORKSHOP_TOPOLOGY": "single_project"})["topology"] == "single_project"


def test_the_portal_is_configured_for_exactly_one_replica() -> None:
    import yaml

    apps = yaml.safe_load((ROOT / "config/workshop/applications.yaml").read_text())["applications"]
    portal = next(a for a in apps if a["key"] == "workshop-portal")
    portal["replicas"] = 2
    import automation.cai_api_v2.planner as planner

    original = planner._load
    try:
        planner._load = lambda path: (
            {"max_active_applications": 5, "applications": apps}
            if str(path).endswith("applications.yaml")
            else original(path)
        )
        with pytest.raises(PlanError, match="one Streamlit process and one replica"):
            build_single_project_plan(CONFIG, env={})
    finally:
        planner._load = original

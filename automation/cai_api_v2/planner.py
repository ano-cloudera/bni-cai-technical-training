"""Dry-run planner for the single_project topology. It reads local files only and never calls the CAI API."""

from __future__ import annotations

import math
import os
from pathlib import Path

import yaml

from .config import load_environment

REPO_ROOT = Path(__file__).resolve().parents[2]
WORKSHOP_DIR = REPO_ROOT / "config" / "workshop"
DEFAULT_MAX_SESSIONS = 10


class PlanError(ValueError):
    pass


def _load(path: Path) -> dict:
    return yaml.safe_load(Path(path).read_text(encoding="utf-8"))


def lifecycle_report(lifecycle: dict, application_keys: set[str], limit: int) -> dict:
    """Active Application counts per phase (mandatory and worst case). Raises PlanError above the limit."""
    report = {}
    for phase, spec in lifecycle["phases"].items():
        active, optional = set(spec["active"]), set(spec.get("optional", ()))
        unknown = (active | optional | set(spec.get("stop_before", ()))) - application_keys
        if unknown:
            raise PlanError(f"{phase}: unknown applications {sorted(unknown)}")
        reserved = int(spec.get("reserved_agent_studio_slots", 0))
        required = len(active) + reserved
        worst = len(active | optional) + reserved
        if worst > limit:
            raise PlanError(f"{phase}: {worst} active Applications exceeds the limit of {limit}")
        report[phase] = {
            "active": sorted(active),
            "optional": sorted(optional),
            "stop_before": sorted(spec.get("stop_before", ())),
            "reserved_agent_studio_slots": reserved,
            "active_count": required,
            "worst_case_count": worst,
        }
    return report


def build_single_project_plan(
    config_path: Path, env: dict | None = None, workshop_dir: Path = WORKSHOP_DIR
) -> dict:
    environment = load_environment(config_path)
    topology = _load(workshop_dir / "topology.single-project.yaml")
    applications = _load(REPO_ROOT / topology["applications"]["source"])
    lifecycle = _load(REPO_ROOT / topology["lifecycle"]["source"])
    assignments = _load(REPO_ROOT / topology["groups"]["source"])["assignments"]
    source = os.environ if env is None else env
    try:
        max_sessions = int(
            source.get("MAX_CONCURRENT_GROUP_SESSIONS", topology["sessions"]["default_max_concurrent"])
        )
    except ValueError as exc:
        raise PlanError("MAX_CONCURRENT_GROUP_SESSIONS must be a whole number") from exc
    if not 1 <= max_sessions <= len(assignments):
        raise PlanError(f"MAX_CONCURRENT_GROUP_SESSIONS must be between 1 and {len(assignments)}")
    groups = [a["group_id"] for a in assignments]
    waves = [groups[i : i + max_sessions] for i in range(0, len(groups), max_sessions)]
    apps = {a["key"]: a for a in applications["applications"]}
    limit = int(applications["max_active_applications"])
    if len(apps) > limit:
        raise PlanError(f"{len(apps)} shared Applications exceed the limit of {limit}")
    portal = apps["workshop-portal"]
    if portal.get("replicas") != 1 or portal.get("streamlit_processes") != 1:
        raise PlanError("The Workshop Portal must run as one Streamlit process and one replica")
    phases = lifecycle_report(lifecycle, set(apps), limit)
    session = topology["sessions"]
    concurrent_cpu = max_sessions * session["cpu"]
    concurrent_memory = max_sessions * session["memory_gb"]
    runtime = environment.get("runtime_identifier", "")
    pending = [i["id"] for i in _load(REPO_ROOT / "config" / "cai-validation-pending.yaml")["items"]]
    return {
        "dry_run": True,
        "topology": "single_project",
        "environment": environment["environment"],
        "project_count": 1,
        "projects": [topology["project"]["name"]],
        "group_count": len(groups),
        "group_workspace_count": len(groups),
        "participants_per_group": topology["groups"]["participants_per_group"],
        "requested_session_count": len(groups) * session["per_group"],
        "max_concurrent_session_count": max_sessions,
        "session_waves": waves,
        "per_group_streamlit_applications": 0,
        "application_count": len(apps),
        "applications": sorted(apps),
        "max_active_applications": limit,
        "workshop_portal": {
            "replicas": portal["replicas"],
            "streamlit_processes": portal["streamlit_processes"],
            "resources": portal["resources"],
            "reason": "the inference semaphore is process-local",
        },
        "active_applications_by_phase": phases,
        "estimated_participant_cpu": concurrent_cpu,
        "estimated_participant_memory_gb": concurrent_memory,
        "estimated_participant_sessions_per_wave": max_sessions,
        "gpu_requirement": {"nvidia_gpu": 1, "applications": ["vllm"], "participant_sessions": 0},
        "required_runtime_identifier": {
            "value": runtime,
            "resolved": bool(runtime) and not runtime.startswith("SET_FROM"),
            "note": "Taken from the target runtime catalog; never hard-coded in this repository.",
        },
        "data_backend": topology["data"]["backend"],
        "isolation": topology["isolation"],
        "unresolved_cai_validation_items": pending,
        "waves_needed": math.ceil(len(groups) / max_sessions),
    }

from __future__ import annotations

import argparse
import json
import os
from pathlib import Path

import yaml

from .cleanup import cleanup_plan
from .client import CaiApiClient
from .config import load_environment
from .deploy import reconcile_applications
from .deploy import deployment_waves
from .discovery import application_items, by_name, project_items
from .inventory import read_inventory, write_inventory
from .models import WorkshopSpec
from .project_files import approved_project_files
from .provision import provision


def build_plan(config_path: Path) -> dict:
    env = load_environment(config_path)
    spec = WorkshopSpec.load(Path(env["groups_config"]), Path(env["resources_config"]))
    return {
        "dry_run": True,
        "environment": env["environment"],
        "training_label": spec.label,
        "projects": [p.name for p in spec.projects],
        "group_application_waves": deployment_waves(
            [p.application for p in spec.projects[1:]], spec.max_concurrent_apps
        ),
        "resources": spec.resources,
    }


def build_parser() -> argparse.ArgumentParser:
    p = argparse.ArgumentParser()
    p.add_argument("--config", type=Path, required=True)
    sub = p.add_subparsers(dest="command", required=True)
    plan = sub.add_parser("plan")
    plan.add_argument("--output", type=Path, required=True)
    for name in ("discover", "validate", "apply-projects", "status", "inventory"):
        command = sub.add_parser(name)
        command.add_argument("--output", type=Path)
        if name == "apply-projects":
            command.add_argument("--execute", action="store_true")
        if name == "status":
            command.add_argument("--project-id")
    upload = sub.add_parser("upload-files")
    upload.add_argument("--project-id", required=True)
    upload.add_argument("--execute", action="store_true")
    upload.add_argument("--output", type=Path)
    applications = sub.add_parser("apply-applications")
    applications.add_argument("--project-id", required=True)
    applications.add_argument("--runtime-identifier", required=True)
    applications.add_argument("--wave", choices=("shared", "1", "2", "3", "4"), required=True)
    applications.add_argument("--execute", action="store_true")
    applications.add_argument("--output", type=Path)
    for name in ("stop-wave", "start-wave"):
        command = sub.add_parser(name)
        command.add_argument("--inventory", type=Path, required=True)
        command.add_argument("--wave", choices=("1", "2", "3", "4"), required=True)
        command.add_argument("--execute", action="store_true")
    cleanup_preview = sub.add_parser("cleanup-plan")
    cleanup_preview.add_argument("--inventory", type=Path, required=True)
    cleanup_preview.add_argument("--delete-apps", action="store_true")
    cleanup_apply = sub.add_parser("cleanup-apply")
    cleanup_apply.add_argument("--inventory", type=Path, required=True)
    cleanup_apply.add_argument("--delete-apps", action="store_true")
    cleanup_apply.add_argument("--confirm-label", required=True)
    return p


def _client(env: dict) -> CaiApiClient:
    return CaiApiClient(
        env["api_base_url"], env["api_key"], env.get("api_prefix", "/api/v2"), env.get("ca_bundle")
    )


def _emit(data: object, output: Path | None = None) -> None:
    rendered = json.dumps(data, indent=2, sort_keys=True) + "\n"
    if output:
        output.parent.mkdir(parents=True, exist_ok=True)
        output.write_text(rendered)
        print(output)
    else:
        print(rendered, end="")


def _load_manifests() -> list[dict]:
    return yaml.safe_load(Path("deployments/cai/manifests/applications.yaml").read_text())["applications"]


def _wave_manifest(spec: WorkshopSpec, wave: str) -> list[dict]:
    manifests = _load_manifests()
    if wave == "shared":
        return [item for item in manifests if item["key"] != "streamlit-group"]
    group_template = next(item for item in manifests if item["key"] == "streamlit-group")
    wave_size = spec.max_concurrent_apps
    start = (int(wave) - 1) * wave_size
    selected = spec.projects[1 + start : 1 + start + wave_size]
    result = []
    for project in selected:
        manifest = dict(group_template)
        manifest["name"] = project.application
        manifest["subdomain"] = project.application
        manifest["environment"] = {
            "GROUP_ID": project.group_id,
            "DATA_MODE": os.getenv("DATA_MODE", "csv"),
            "CSV_DATA_DIR": "data/csv",
        }
        result.append(manifest)
    return result


def main(argv=None):
    p = build_parser()
    args = p.parse_args(argv)
    env = load_environment(args.config)
    spec = WorkshopSpec.load(Path(env["groups_config"]), Path(env["resources_config"]))
    if args.command == "plan":
        result = build_plan(args.config)
        _emit(result, args.output)
        return 0
    if args.command == "validate":
        result = {
            "api_base_url_set": bool(env["api_base_url"]),
            "api_key_set": bool(env["api_key"]),
            "config": str(args.config),
            "ready": bool(env["api_base_url"] and env["api_key"]),
        }
        _emit(result, args.output)
        return 0 if result["ready"] else 2
    client = _client(env)
    if args.command == "discover":
        _emit({"runtimes": client.list_runtimes(), "projects": client.list_projects()}, args.output)
        return 0
    if args.command == "apply-projects":
        _emit(provision(client, spec, dry_run=not args.execute), args.output)
        return 0
    if args.command == "upload-files":
        files = approved_project_files(Path.cwd())
        actions = [{"path": path.relative_to(Path.cwd()).as_posix(), "action": "upload"} for path in files]
        if args.execute:
            for path in files:
                client.upload_file(args.project_id, Path.cwd(), path)
        _emit({"project_id": args.project_id, "executed": args.execute, "files": actions}, args.output)
        return 0
    if args.command == "apply-applications":
        manifests = _wave_manifest(spec, args.wave)
        environment = {"TRAINING_LABEL": spec.label}
        actions = reconcile_applications(
            client,
            project_id=args.project_id,
            manifests=manifests,
            runtime_identifier=args.runtime_identifier,
            environment=environment,
            dry_run=not args.execute,
        )
        _emit({"wave": args.wave, "actions": actions}, args.output)
        return 0
    if args.command == "status":
        if args.project_id:
            data = client.list_applications(args.project_id)
        else:
            data = client.list_projects()
        _emit(data, args.output)
        return 0
    if args.command == "inventory":
        projects = project_items(client.list_projects())
        applications = []
        for project in projects:
            if project.get("name", "").startswith("bni-ai-training-"):
                for app in application_items(client.list_applications(project["id"])):
                    applications.append({**app, "project_id": project["id"]})
        data = {"training_label": spec.label, "projects": projects, "applications": applications}
        if args.output:
            write_inventory(args.output, data)
            print(args.output)
        else:
            _emit(data)
        return 0
    if args.command in {"start-wave", "stop-wave"}:
        inventory = read_inventory(args.inventory)
        wave_size = spec.max_concurrent_apps
        start = (int(args.wave) - 1) * wave_size
        names = {p.application for p in spec.projects[1 + start : 1 + start + wave_size]}
        actions = []
        for app in inventory.get("applications", []):
            if app.get("name") not in names:
                continue
            action = "start" if args.command == "start-wave" else "stop"
            actions.append({"action": action, "name": app["name"], "id": app["id"]})
            if args.execute:
                method = client.start_application if action == "start" else client.stop_application
                method(app["project_id"], app["id"])
        _emit({"executed": args.execute, "actions": actions})
        return 0
    if args.command in {"cleanup-plan", "cleanup-apply"}:
        inventory = read_inventory(args.inventory)
        actions = cleanup_plan(inventory, delete_apps=args.delete_apps)
        execute = args.command == "cleanup-apply"
        if execute and args.confirm_label != spec.label:
            raise ValueError("cleanup confirmation label does not match")
        if execute:
            for action in actions:
                if action["kind"] == "application":
                    if action["action"] == "delete":
                        client.delete_application(action["project_id"], action["id"])
                    else:
                        client.stop_application(action["project_id"], action["id"])
        _emit({"executed": execute, "actions": actions})
        return 0
    return 2


if __name__ == "__main__":
    raise SystemExit(main())

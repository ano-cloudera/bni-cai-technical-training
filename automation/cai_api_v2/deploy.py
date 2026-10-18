from __future__ import annotations

from .discovery import application_items, by_name


def deployment_waves(names: list[str], wave_size: int = 5) -> list[list[str]]:
    if wave_size < 1:
        raise ValueError("wave_size must be positive")
    return [names[i : i + wave_size] for i in range(0, len(names), wave_size)]


def application_body(manifest: dict, runtime_identifier: str, environment: dict[str, str]) -> dict:
    profile = manifest["resources"]
    merged_environment = {**environment, **manifest.get("environment", {})}
    return {
        "name": manifest["name"],
        "subdomain": manifest.get("subdomain", manifest["name"]),
        "script": manifest["script"],
        "kernel": manifest.get("kernel", "python3"),
        "runtime_identifier": runtime_identifier,
        "cpu": profile["cpu"],
        "memory": profile["memory_gb"],
        "nvidia_gpu": profile.get("nvidia_gpu", 0),
        "environment": merged_environment,
    }


def reconcile_applications(
    client,
    *,
    project_id: str,
    manifests: list[dict],
    runtime_identifier: str,
    environment: dict[str, str],
    dry_run: bool = False,
) -> list[dict]:
    existing = application_items(client.list_applications(project_id))
    actions: list[dict] = []
    for manifest in manifests:
        found = by_name(existing, manifest["name"])
        if found:
            actions.append(
                {"action": "keep_application", "name": manifest["name"], "id": found.get("id")}
            )
            continue
        body = application_body(manifest, runtime_identifier, environment)
        if dry_run:
            actions.append({"action": "create_application", "name": manifest["name"], "dry_run": True})
            continue
        created = client.create_application(project_id, body)
        actions.append(
            {"action": "created_application", "name": manifest["name"], "id": created.get("id")}
        )
    return actions

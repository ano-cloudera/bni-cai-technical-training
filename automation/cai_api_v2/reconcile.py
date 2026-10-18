from .discovery import by_name, project_items


def reconcile_projects(client, spec, dry_run: bool = True):
    existing = project_items(client.list_projects()) if not dry_run else []
    actions = []
    for project in spec.projects:
        found = by_name(existing, project.name)
        if found:
            actions.append({"action": "keep_project", "name": project.name, "id": found.get("id")})
        elif dry_run:
            actions.append({"action": "create_project", "name": project.name, "dry_run": True})
        else:
            created = client.create_project(
                {"name": project.name, "visibility": "private", "environment": {"TRAINING_LABEL": spec.label}}
            )
            actions.append({"action": "created_project", "name": project.name, "id": created["id"]})
    return actions

class CleanupRefused(RuntimeError):
    pass


def cleanup_plan(inventory: dict, delete_apps: bool = False, delete_projects: bool = False):
    if inventory.get("training_label") != "bni-cai-training-2026":
        raise CleanupRefused("Inventory training label is missing or invalid")
    allowed_prefixes = ("bni-vllm-", "bni-qdrant", "bni-phoenix", "bni-litellm", "bni-credit-insight-g")
    apps = inventory.get("applications", [])
    if not apps and (delete_apps or delete_projects):
        raise CleanupRefused("No exact Application inventory is available")
    if any(not str(app.get("name", "")).startswith(allowed_prefixes) or not app.get("id") for app in apps):
        raise CleanupRefused("Inventory contains an unscoped Application")
    actions = [{"action": "delete" if delete_apps else "stop", "kind": "application", **app} for app in apps]
    if delete_projects:
        projects = inventory.get("projects", [])
        if any(not p.get("name", "").startswith("bni-ai-training-") or not p.get("id") for p in projects):
            raise CleanupRefused("Inventory contains an unscoped project")
        actions += [{"action": "delete", "kind": "project", **p} for p in projects]
    return actions

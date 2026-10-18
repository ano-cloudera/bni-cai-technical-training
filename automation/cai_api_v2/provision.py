from .reconcile import reconcile_projects


def provision(client, spec, dry_run=True):
    return {
        "training_label": spec.label,
        "projects": reconcile_projects(client, spec, dry_run),
        "dry_run": dry_run,
    }

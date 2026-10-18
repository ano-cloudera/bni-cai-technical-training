from __future__ import annotations

from automation.cai_api_v2.cli import build_parser
from automation.cai_api_v2.deploy import application_body, deployment_waves, reconcile_applications


def test_application_body_contains_python_script_and_runtime() -> None:
    manifest = {
        "name": "bni-phoenix",
        "subdomain": "bni-phoenix",
        "script": "deployments/cai/phoenix/app.py",
        "kernel": "python3",
        "resources": {"cpu": 4, "memory_gb": 16, "nvidia_gpu": 0},
        "environment": {"GROUP_ID": "group_01"},
    }
    body = application_body(manifest, runtime_identifier="pbj-python310-standard", environment={"A": "B"})
    assert body["script"].endswith("app.py")
    assert body["kernel"] == "python3"
    assert body["runtime_identifier"] == "pbj-python310-standard"
    assert body["environment"] == {"A": "B", "GROUP_ID": "group_01"}


def test_application_waves_respect_global_five_application_limit() -> None:
    waves = deployment_waves([f"g{i:02d}" for i in range(1, 11)], wave_size=3)
    assert [len(wave) for wave in waves] == [3, 3, 3, 1]


def test_reconcile_applications_is_idempotent() -> None:
    class Client:
        def __init__(self):
            self.created = []

        def list_applications(self, _project_id):
            return {"applications": [{"id": "a-1", "name": "bni-phoenix"}]}

        def create_application(self, _project_id, body):
            self.created.append(body)
            return {"id": "new", **body}

    manifests = [
        {
            "name": "bni-phoenix",
            "subdomain": "bni-phoenix",
            "script": "deployments/cai/phoenix/app.py",
            "kernel": "python3",
            "resources": {"cpu": 4, "memory_gb": 16, "nvidia_gpu": 0},
        },
        {
            "name": "bni-litellm",
            "subdomain": "bni-litellm",
            "script": "deployments/cai/litellm/app.py",
            "kernel": "python3",
            "resources": {"cpu": 2, "memory_gb": 4, "nvidia_gpu": 0},
        },
    ]
    client = Client()
    actions = reconcile_applications(
        client,
        project_id="p-1",
        manifests=manifests,
        runtime_identifier="pbj-python310-standard",
        environment={},
    )
    assert actions[0] == {"action": "keep_application", "name": "bni-phoenix", "id": "a-1"}
    assert actions[1]["action"] == "created_application"
    assert len(client.created) == 1


def test_cli_exposes_complete_automation_lifecycle() -> None:
    parser = build_parser()
    subparsers = next(action for action in parser._actions if action.dest == "command")
    assert set(subparsers.choices) == {
        "plan",
        "discover",
        "validate",
        "apply-projects",
        "upload-files",
        "apply-applications",
        "status",
        "stop-wave",
        "start-wave",
        "inventory",
        "cleanup-plan",
        "cleanup-apply",
    }

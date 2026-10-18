import time


def wait_for_application(client, project_id, application_id, timeout_seconds=900):
    deadline = time.monotonic() + timeout_seconds
    while time.monotonic() < deadline:
        app = client.get_application(project_id, application_id)
        status = str(app.get("status", "")).lower()
        if status in {"running", "started", "ready"}:
            return app
        if status in {"failed", "error", "stopped"}:
            raise RuntimeError(f"Application entered terminal status: {status}")
        time.sleep(5)
    raise TimeoutError("Application did not become ready before timeout")

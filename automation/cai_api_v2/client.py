from __future__ import annotations

import json
import ssl
import base64
from pathlib import Path
from urllib.error import HTTPError
from urllib.request import Request, urlopen

from .errors import CaiApiError


class CaiApiClient:
    def __init__(
        self,
        base_url: str,
        api_key: str,
        api_prefix: str = "/api/v2",
        ca_bundle: str | None = None,
        transport=None,
    ):
        if not base_url or not api_key:
            raise ValueError("CAI_API_BASE_URL and CAI_API_KEY are required")
        self.base_url = base_url.rstrip("/")
        self.api_prefix = api_prefix.rstrip("/")
        self._api_key = api_key
        self.ca_bundle = ca_bundle
        self.transport = transport

    def __repr__(self):
        return f"CaiApiClient(base_url={self.base_url!r}, api_key='***')"

    def request(self, method: str, path: str, body: dict | None = None):
        url = self.base_url + self.api_prefix + "/" + path.lstrip("/")
        headers = {"Accept": "application/json", "Authorization": f"Bearer {self._api_key}"}
        if body is not None:
            headers["Content-Type"] = "application/json"
        if self.transport:
            return self.transport(method, url, headers, body, self.ca_bundle)
        request = Request(
            url, method=method, headers=headers, data=json.dumps(body).encode() if body is not None else None
        )
        context = (
            ssl.create_default_context(cafile=self.ca_bundle)
            if self.ca_bundle
            else ssl.create_default_context()
        )
        try:
            with urlopen(request, timeout=60, context=context) as response:
                raw = response.read()
                return json.loads(raw) if raw else {}
        except HTTPError as exc:
            raise CaiApiError(f"CAI API request failed with HTTP {exc.code} for {method} {path}") from exc

    def list_projects(self):
        return self.request("GET", "/projects")

    def create_project(self, body):
        return self.request("POST", "/projects", body)

    def list_runtimes(self):
        return self.request("GET", "/runtimes")

    def list_applications(self, project_id):
        return self.request("GET", f"/projects/{project_id}/applications")

    def create_application(self, project_id, body):
        return self.request("POST", f"/projects/{project_id}/applications", body)

    def get_application(self, project_id, application_id):
        return self.request("GET", f"/projects/{project_id}/applications/{application_id}")

    def stop_application(self, project_id, application_id):
        return self.request("POST", f"/projects/{project_id}/applications/{application_id}/stop", {})

    def start_application(self, project_id, application_id):
        return self.request("POST", f"/projects/{project_id}/applications/{application_id}/start", {})

    def delete_application(self, project_id, application_id):
        return self.request("DELETE", f"/projects/{project_id}/applications/{application_id}")

    def delete_project(self, project_id):
        return self.request("DELETE", f"/projects/{project_id}")

    def upload_file(self, project_id: str, root: Path, path: Path):
        relative = path.relative_to(root).as_posix()
        return self.request(
            "PUT",
            f"/projects/{project_id}/files/{relative}",
            {"content_base64": base64.b64encode(path.read_bytes()).decode("ascii")},
        )

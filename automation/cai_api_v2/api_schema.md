> **CAI API v2 field validation pending.** Nothing in this repository has been compared with a live Swagger or called against CAI. The runtime identifier is never hard-coded; see `config/cai-validation-pending.yaml`.

# CAI API v2 Contract Notes

The client uses `Authorization: Bearer <API key>` and the `/api/v2` prefix. Project endpoints use `/projects`; Application endpoints use `/projects/{project_id}/applications`. Validate request fields against the target workbench Swagger document at `/api/v2/swagger.html` before any live write because runtime and resource profile identifiers are environment-specific.


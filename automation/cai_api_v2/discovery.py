def by_name(items: list[dict], name: str) -> dict | None:
    return next((item for item in items if item.get("name") == name), None)


def project_items(response: dict) -> list[dict]:
    return response.get("projects", response.get("items", []))


def application_items(response: dict) -> list[dict]:
    return response.get("applications", response.get("items", []))

from pathlib import Path


def approved_project_files(root: Path) -> list[Path]:
    excluded = {".git", ".venv", "dist", "build", "wheelhouse"}
    return [
        p
        for p in root.rglob("*")
        if p.is_file() and not any(part in excluded for part in p.parts) and p.name != ".env"
    ]

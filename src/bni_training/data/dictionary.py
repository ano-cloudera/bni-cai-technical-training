from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path

import yaml

REPO_ROOT = Path(__file__).resolve().parents[3]
SEMANTIC_DIR = REPO_ROOT / "semantic"
DEFAULT_RAW_DIR = REPO_ROOT / "data" / "raw"
DEFAULT_MANIFEST_DIR = REPO_ROOT / "data" / "manifests"
SQLITE_TYPES = {"text": "TEXT", "date": "TEXT", "integer": "INTEGER", "real": "REAL"}


@dataclass(frozen=True)
class ColumnSpec:
    name: str
    description: str
    type: str
    role: str
    sensitivity: str
    participant_exposed: bool = True
    pattern: str | None = None
    allowed_values: tuple = ()
    minimum: float | None = None
    references: str | None = None


@dataclass(frozen=True)
class TableSpec:
    name: str
    description: str
    primary_key: str
    columns: tuple[ColumnSpec, ...] = field(default_factory=tuple)

    @property
    def column_names(self) -> tuple[str, ...]:
        return tuple(c.name for c in self.columns)

    @property
    def exposed_columns(self) -> tuple[str, ...]:
        return tuple(c.name for c in self.columns if c.participant_exposed)

    def column(self, name: str) -> ColumnSpec:
        return next(c for c in self.columns if c.name == name)


class DataDictionary:
    def __init__(self, raw: dict):
        self.raw = raw
        self.reference_date: str = raw["reference_date"]
        self.tables: dict[str, TableSpec] = {}
        for table_name, table in raw["tables"].items():
            columns = tuple(
                ColumnSpec(
                    name=col_name,
                    description=col["description"],
                    type=col["type"],
                    role=col["role"],
                    sensitivity=col.get("sensitivity", "synthetic_attribute"),
                    participant_exposed=col.get("participant_exposed", True),
                    pattern=col.get("pattern"),
                    allowed_values=tuple(col.get("allowed_values", ())),
                    minimum=col.get("min"),
                    references=col.get("references"),
                )
                for col_name, col in table["columns"].items()
            )
            self.tables[table_name] = TableSpec(
                table_name, table["description"], table["primary_key"], columns
            )

    @classmethod
    def load(cls, path: Path | None = None) -> DataDictionary:
        path = Path(path) if path else SEMANTIC_DIR / "data_dictionary.yaml"
        return cls(yaml.safe_load(path.read_text(encoding="utf-8")))

    @property
    def table_names(self) -> tuple[str, ...]:
        return tuple(self.tables)

    def foreign_keys(self) -> list[tuple[str, str, str, str]]:
        """(child_table, child_column, parent_table, parent_column) for every foreign key."""
        result = []
        for table in self.tables.values():
            for column in table.columns:
                if column.references:
                    parent_table, parent_column = column.references.split(".")
                    result.append((table.name, column.name, parent_table, parent_column))
        return result

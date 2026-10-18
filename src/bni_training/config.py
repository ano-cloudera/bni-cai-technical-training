from __future__ import annotations

import os
import re
from dataclasses import dataclass, field
from enum import Enum
from pathlib import Path
from typing import Mapping


class DataMode(str, Enum):
    CSV = "csv"
    IMPALA_GSSAPI = "impala_gssapi"
    IMPALA_LDAP = "impala_ldap"


_GROUP_RE = re.compile(r"^group_(0[1-9]|10)$")


def validate_group_id(value: str) -> str:
    if not _GROUP_RE.fullmatch(value or ""):
        raise ValueError("GROUP_ID must be group_01 through group_10")
    return value


@dataclass(frozen=True)
class Settings:
    group_id: str
    data_mode: DataMode
    vllm_base_url: str
    vllm_api_key: str = field(repr=False)
    csv_data_dir: Path = Path("data/csv")
    impala_host: str | None = None
    impala_port: int = 21050
    impala_database: str = "bni_training"
    impala_username: str | None = field(default=None, repr=False)
    impala_password: str | None = field(default=None, repr=False)
    impala_kerberos_service_name: str = "impala"
    impala_ca_cert: str | None = None
    qdrant_url: str | None = None
    qdrant_api_key: str | None = field(default=None, repr=False)
    phoenix_endpoint: str | None = None
    litellm_base_url: str | None = None

    @classmethod
    def load(cls, env: Mapping[str, str] | None = None) -> "Settings":
        values = dict(os.environ if env is None else env)
        missing = [key for key in ("GROUP_ID", "DATA_MODE", "VLLM_BASE_URL") if not values.get(key)]
        if missing:
            raise ValueError("Missing required environment variables: " + ", ".join(missing))
        mode = DataMode(values["DATA_MODE"].lower())
        return cls(
            group_id=validate_group_id(values["GROUP_ID"]),
            data_mode=mode,
            vllm_base_url=values["VLLM_BASE_URL"].rstrip("/"),
            vllm_api_key=values.get("VLLM_API_KEY", ""),
            csv_data_dir=Path(values.get("CSV_DATA_DIR", "data/csv")),
            impala_host=values.get("IMPALA_HOST") or None,
            impala_port=int(values.get("IMPALA_PORT", "21050")),
            impala_database=values.get("IMPALA_DATABASE", "bni_training"),
            impala_username=values.get("IMPALA_USERNAME") or None,
            impala_password=values.get("IMPALA_PASSWORD") or None,
            impala_kerberos_service_name=values.get("IMPALA_KERBEROS_SERVICE_NAME", "impala"),
            impala_ca_cert=values.get("IMPALA_CA_CERT") or None,
            qdrant_url=values.get("QDRANT_URL") or None,
            qdrant_api_key=values.get("QDRANT_API_KEY") or None,
            phoenix_endpoint=values.get("PHOENIX_ENDPOINT") or None,
            litellm_base_url=values.get("LITELLM_BASE_URL") or None,
        )

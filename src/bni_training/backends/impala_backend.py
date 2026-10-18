from __future__ import annotations

import time
from typing import Callable

from bni_training.schemas import HealthStatus, QueryResult


class ImpalaBackend:
    def __init__(self, settings, connect_factory: Callable | None = None):
        self.settings = settings
        self._connect_factory = connect_factory or self._default_connect
        if not settings.impala_host:
            raise ValueError("IMPALA_HOST is required for Impala mode")
        if settings.data_mode.value == "impala_ldap" and (
            not settings.impala_username or not settings.impala_password
        ):
            raise ValueError("IMPALA_USERNAME and IMPALA_PASSWORD are required for LDAP mode")

    def _default_connect(self):
        try:
            from impala.dbapi import connect
        except ImportError as exc:
            raise RuntimeError("Install the impala dependency profile before using Impala") from exc
        kwargs = {
            "host": self.settings.impala_host,
            "port": self.settings.impala_port,
            "database": self.settings.impala_database,
            "use_ssl": bool(self.settings.impala_ca_cert),
        }
        if self.settings.data_mode.value == "impala_gssapi":
            kwargs.update(
                auth_mechanism="GSSAPI", kerberos_service_name=self.settings.impala_kerberos_service_name
            )
        else:
            kwargs.update(
                auth_mechanism="LDAP",
                user=self.settings.impala_username,
                password=self.settings.impala_password,
            )
        return connect(**kwargs)

    def execute(self, sql: str, timeout_seconds: int = 30) -> QueryResult:
        start = time.perf_counter()
        try:
            conn = self._connect_factory()
            cursor = conn.cursor()
            cursor.execute(sql)
            rows = [list(row) for row in cursor.fetchall()]
            columns = [item[0] for item in cursor.description]
            return QueryResult(
                columns=columns,
                rows=rows,
                row_count=len(rows),
                elapsed_ms=(time.perf_counter() - start) * 1000,
            )
        except Exception as exc:
            raise RuntimeError(
                "Impala query failed. Verify authentication, TLS, DNS, and permissions."
            ) from exc

    def healthcheck(self) -> HealthStatus:
        self.execute("SELECT 1", 10)
        return HealthStatus(healthy=True, service="impala")

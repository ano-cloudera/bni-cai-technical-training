from __future__ import annotations

_DENY = {"api_key", "password", "token", "authorization", "connection_string", "keytab"}


def safe_trace_attributes(values: dict) -> dict:
    return {key: value for key, value in values.items() if key.lower() not in _DENY}


def configure_phoenix(endpoint: str, service_name: str = "bni-credit-insight") -> bool:
    if not endpoint:
        return False
    try:
        from phoenix.otel import register

        register(project_name=service_name, endpoint=endpoint)
        return True
    except ImportError:
        return False

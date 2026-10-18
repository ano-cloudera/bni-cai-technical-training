from __future__ import annotations

import re


class GuardrailError(ValueError):
    pass


_TABLE_PATTERN = re.compile(r"\b(?:from|join)\s+([a-zA-Z_][\w.]*)", re.IGNORECASE)
_FORBIDDEN = re.compile(
    r"\b(insert|update|delete|drop|alter|create|truncate|grant|revoke|merge|call)\b", re.I
)


def validate_input(text: str, max_length: int = 1000) -> str:
    value = text.strip()
    if not value:
        raise GuardrailError("Question cannot be empty")
    if len(value) > max_length:
        raise GuardrailError(f"Question exceeds {max_length} characters")
    if re.search(r"ignore\s+(all\s+)?previous|reveal\s+(the\s+)?system\s+prompt", value, re.I):
        raise GuardrailError("Prompt-injection pattern detected")
    return value


def validate_sql(sql: str, allowed_tables: set[str], default_limit: int = 100) -> str:
    text = sql.strip()
    if not re.match(r"^(select|with)\b", text, re.I):
        raise GuardrailError("Only SELECT or WITH queries are allowed")
    if "--" in text or "/*" in text or "*/" in text:
        raise GuardrailError("SQL comments are not allowed")
    if ";" in text.rstrip(";"):
        raise GuardrailError("Only one SQL statement is allowed")
    text = text.rstrip(";").strip()
    if _FORBIDDEN.search(text):
        raise GuardrailError("DDL and DML statements are not allowed")
    tables = {match.split(".")[-1].lower() for match in _TABLE_PATTERN.findall(text)}
    unknown = tables - {item.lower() for item in allowed_tables}
    if unknown:
        raise GuardrailError("Table is not in the semantic allowlist: " + ", ".join(sorted(unknown)))
    if not re.search(r"\blimit\s+\d+\b", text, re.I):
        text += f" LIMIT {int(default_limit)}"
    return text


def validate_grounded_answer(answer: str, known_numbers: list[float]) -> str:
    mentioned = [float(x.replace(",", "")) for x in re.findall(r"\b\d[\d,]*(?:\.\d+)?\b", answer)]
    allowed = {round(float(x), 4) for x in known_numbers}
    if any(round(x, 4) not in allowed for x in mentioned):
        raise GuardrailError("Answer contains a number not present in the tool result")
    return answer

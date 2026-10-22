from __future__ import annotations

import re


class GuardrailError(ValueError):
    pass


class PiiDetectedError(GuardrailError):
    """Raised when text holds personal data; `kinds` names the types found, never the values."""

    def __init__(self, kinds: list[str]):
        self.kinds = kinds
        super().__init__("Personal data detected (" + ", ".join(kinds) + "). Remove it and try again.")


_EMAIL = re.compile(r"[A-Za-z0-9._%+-]+@[A-Za-z0-9-]+(?:\.[A-Za-z0-9-]+)+")
_NIK = re.compile(r"(?<!\d)\d{2}[ .-]?\d{2}[ .-]?\d{2}[ .-]?\d{6}[ .-]?\d{4}(?!\d)")
_CARD = re.compile(r"(?<!\d)(?:\d[ -]?){12,18}\d(?!\d)")
_IBAN = re.compile(r"\b[A-Z]{2}\d{2}(?: ?[A-Z0-9]{4}){2,7}(?: ?[A-Z0-9]{1,3})?\b")
_PHONE = re.compile(r"(?<![\w])(?:\+62|62|0)8\d{8,11}(?!\d)")


def _luhn(digits: str) -> bool:
    total = 0
    for index, char in enumerate(reversed(digits)):
        number = int(char)
        if index % 2:
            number = number * 2 - 9 if number > 4 else number * 2
        total += number
    return total % 10 == 0


def detect_pii(text: str) -> list[str]:
    """Return the PII types found in text (KTP/NIK, card, IBAN, email, phone). Values are never returned."""
    kinds: list[str] = []
    if _EMAIL.search(text):
        kinds.append("email address")
    for match in _NIK.finditer(text):
        if not _luhn(re.sub(r"\D", "", match.group())):  # a Luhn-valid 16-digit number is reported as a card
            kinds.append("KTP/NIK number")
            break
    for match in _CARD.finditer(text):
        digits = re.sub(r"\D", "", match.group())
        if 13 <= len(digits) <= 19 and _luhn(digits):
            kinds.append("card number")
            break
    if _IBAN.search(text):
        kinds.append("IBAN / account number")
    if _PHONE.search(re.sub(r"(?<=\d)[ -](?=\d)", "", text)):
        kinds.append("phone number")
    return kinds


def validate_no_pii(text: str) -> str:
    kinds = detect_pii(text)
    if kinds:
        raise PiiDetectedError(kinds)
    return text


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

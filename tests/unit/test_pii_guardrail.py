import pytest

from bni_training.guardrails import PiiDetectedError, detect_pii, validate_no_pii


@pytest.mark.parametrize(
    "text,kind",
    [
        ("KTP 3171234567890002", "KTP/NIK number"),
        ("nik 31.71.23.456789.0002", "KTP/NIK number"),
        ("mail budi.test@example.com now", "email address"),
        ("card 4111 1111 1111 1111", "card number"),
        ("call 081234567890", "phone number"),
        ("IBAN GB82 WEST 1234 5698 7654 32", "IBAN / account number"),
    ],
)
def test_pii_is_detected(text, kind):
    assert kind in detect_pii(text)


@pytest.mark.parametrize("text", ["Which segment has the highest NPL ratio in 2024?", "Total exposure 1234567 in Q3", "Top 5 branches by balance"])
def test_normal_questions_pass(text):
    assert detect_pii(text) == []
    assert validate_no_pii(text) == text


def test_error_names_types_not_values():
    with pytest.raises(PiiDetectedError) as err:
        validate_no_pii("KTP 3171234567890002")
    assert "3171234567890002" not in str(err.value)

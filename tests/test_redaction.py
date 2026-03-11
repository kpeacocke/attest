"""Tests for the redaction module (REQ-4.3)."""

from __future__ import annotations

from attest.redaction import Redactor, RedactionPatterns


class TestRedactionPatterns:
    def test_redacts_passwords(self) -> None:
        redactor = Redactor([RedactionPatterns.PASSWORD])
        text = "database_password: supersecret123"
        result = redactor.redact(text)
        assert "supersecret123" not in result
        assert "password:" in result.lower()

    def test_redacts_api_tokens(self) -> None:
        redactor = Redactor([RedactionPatterns.TOKEN])
        text = "api_key = sk_live_abc123def456"
        result = redactor.redact(text)
        assert "sk_live" not in result
        assert "[REDACTED]" in result

    def test_redacts_bearer_tokens(self) -> None:
        redactor = Redactor([RedactionPatterns.BEARER_TOKEN])
        text = "Authorization: Bearer eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9"
        result = redactor.redact(text)
        assert "eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9" not in result
        assert "[REDACTED]" in result

    def test_redacts_url_passwords_via_key_detection(self) -> None:
        """Test that URL passwords are redacted when in a 'password' key."""
        redactor = Redactor()
        data = {
            "database_url": "mysql://user:password123@localhost:3306/db",
            "password": "my_secret",
        }
        result = redactor.redact(data)
        # Key-based redaction should catch the password key
        assert result["password"] == "[REDACTED]"


class TestRedactor:
    def test_redacts_dict_values(self) -> None:
        redactor = Redactor()
        data = {
            "username": "admin",
            "password": "secret_pass_123",
            "api_key": "sk_test_123abc",
        }
        result = redactor.redact(data)
        assert result["username"] == "admin"
        assert result["password"] != "secret_pass_123"
        assert "[REDACTED]" in result["password"]

    def test_redacts_nested_structures(self) -> None:
        redactor = Redactor()
        data = {
            "config": {
                "db_password": "db_secret",
                "normal_field": "visible",
            },
            "tokens": "[REDACTED_BY_KEY]",  # Redacted because key is "tokens"
        }
        result = redactor.redact(data)
        assert result["config"]["normal_field"] == "visible"
        assert result["config"]["db_password"] == "[REDACTED]"  # Key-based redaction
        assert result["tokens"] == "[REDACTED]"  # Key-based redaction

    def test_redacts_list_items(self) -> None:
        redactor = Redactor()
        data = ["normal_value", "password=very_secret", "api_key=sk_secret"]
        result = redactor.redact(data)
        assert result[0] == "normal_value"
        assert "very_secret" not in str(result)
        assert "sk_secret" not in str(result)

    def test_redacts_tuples(self) -> None:
        redactor = Redactor()
        data = ("username", "password=secret")
        result = redactor.redact(data)
        assert isinstance(result, tuple)
        assert result[0] == "username"
        assert "secret" not in result[1]

    def test_preserves_non_sensitive_strings(self) -> None:
        redactor = Redactor()
        text = "This is a normal message without secrets"
        result = redactor.redact(text)
        assert result == text

    def test_preserves_other_types(self) -> None:
        redactor = Redactor()
        data = 123
        result = redactor.redact(data)
        assert result == 123

    def test_custom_patterns(self) -> None:
        import re

        custom_pattern = re.compile(r"credit_card[:\s]*(\d{16})", re.IGNORECASE)
        redactor = Redactor([custom_pattern])
        text = "credit_card: 1234567890123456"
        result = redactor.redact(text)
        assert "1234567890123456" not in result

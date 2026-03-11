"""Redaction module for sensitive data (REQ-4.3)."""

from __future__ import annotations

import re
from typing import Any


class RedactionPatterns:
    """Built-in patterns for detecting and redacting sensitive data."""

    # Common sensitive patterns
    PASSWORD = re.compile(
        r"(password|passwd|pwd)\s*[:=]\s*['\"]?([^'\";\s]+)['\"]?",
        re.IGNORECASE,
    )
    TOKEN = re.compile(
        r"(token|apikey|api_key|secret|api_secret)\s*[:=]\s*['\"]?([^'\";\s]+)['\"]?",
        re.IGNORECASE,
    )
    API_KEY = re.compile(
        r"(api[-_]?key|apikey)\s*[:=]\s*['\"]?([a-zA-Z0-9\-_]{20,})['\"]?",
        re.IGNORECASE,
    )
    AWS_KEY = re.compile(r"AKIA[0-9A-Z]{16}", re.IGNORECASE)
    PRIVATE_KEY = re.compile(
        r"-----BEGIN\s+(RSA\s+)?PRIVATE\s+KEY",
        re.IGNORECASE,
    )
    BEARER_TOKEN = re.compile(
        r"(bearer|authorization)\s+([a-zA-Z0-9\-_.]+)",
        re.IGNORECASE,
    )
    URL_PASSWORD = re.compile(r"(https?://)[^:]+:([^@]+)@", re.IGNORECASE)
    EMAIL = re.compile(r"\b[A-Za-z0-9._%+\-]+@[A-Za-z0-9.\-]+\.[A-Z|a-z]{2,}\b")

    # Redaction marker
    REDACTED_MARKER = "[REDACTED]"


class Redactor:
    """Apply redaction rules to data structures."""

    # Sensitive key patterns
    SENSITIVE_KEYS = re.compile(
        r"(password|passwd|pwd|secret|token|apikey|api_key|api_secret|"
        r"private_key|access_key|secret_key|credential|auth)",
        re.IGNORECASE,
    )

    def __init__(self, patterns: list[re.Pattern[str]] | None = None):
        if patterns is None:
            patterns = [
                RedactionPatterns.PASSWORD,
                RedactionPatterns.TOKEN,
                RedactionPatterns.API_KEY,
                RedactionPatterns.AWS_KEY,
                RedactionPatterns.PRIVATE_KEY,
                RedactionPatterns.BEARER_TOKEN,
                RedactionPatterns.URL_PASSWORD,
            ]
        self.patterns = patterns

    def redact(self, data: Any) -> Any:
        """Recursively redact sensitive data from strings, dicts, and lists."""
        if isinstance(data, str):
            return self._redact_string(data)
        elif isinstance(data, dict):
            return {key: self._redact_dict_value(key, value) for key, value in data.items()}
        elif isinstance(data, list):
            return [self.redact(item) for item in data]
        elif isinstance(data, tuple):
            return tuple(self.redact(item) for item in data)
        else:
            return data

    def _redact_dict_value(self, key: str, value: Any) -> Any:
        """Redact dictionary values, checking both key sensitivity and value patterns."""
        # If key is sensitive, redact the value
        if isinstance(value, str) and self.SENSITIVE_KEYS.search(key):
            return RedactionPatterns.REDACTED_MARKER
        # Otherwise apply normal redaction
        return self.redact(value)

    def _redact_string(self, text: str) -> str:
        """Redact sensitive patterns in a single string."""
        result = text
        for pattern in self.patterns:
            result = pattern.sub(self._replacement, result)
        return result

    def _replacement(self, match: re.Match[str]) -> str:
        """Generate a replacement string preserving structure where possible."""
        matched_text = match.group(0)

        # For patterns with groups, try to preserve the prefix
        if match.lastindex and match.lastindex >= 1:
            # Key=value patterns
            if "=" in matched_text or ":" in matched_text:
                separator = "=" if "=" in matched_text else ":"
                prefix = matched_text.split(separator)[0] + separator
                return prefix + RedactionPatterns.REDACTED_MARKER

        # For simple matched patterns, just return the marker
        return RedactionPatterns.REDACTED_MARKER

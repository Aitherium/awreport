"""Secret and sensitive data redaction for feedback reports.

Fail-closed design: if redaction cannot complete, raises exception.
Caller must catch and handle redaction failures by NOT sending the report.
"""

import re
import os
from typing import Any, Optional
from pathlib import Path


class RedactionError(Exception):
    """Raised when redaction fails and we cannot guarantee safety."""
    pass


class Redactor:
    """Redacts secrets and sensitive data from strings and structured data."""

    # Secret patterns (fail-closed: catch more than we need)
    # Prefix-anchored, NOT length-gated.
    #
    # These carried {36,} / {48,} / {16} floors, copied from the vendors'
    # documented token lengths. That is the wrong rule for a redactor and it
    # failed live: `ghp_token1`, `sk-ant-key1` and a 13-char `AKIA...` all
    # sailed through with zero substitutions, in the one component whose whole
    # job is to not leak a credential into a PUBLIC issue.
    #
    # The prefix IS the signal. Two reasons the floor is wrong, not just
    # inconvenient: a credential that reaches a crash report has usually been
    # TRUNCATED by whatever logged it, so the real leak is short; and the cost
    # is asymmetric -- redacting a harmless string that happens to start with
    # `ghp_` costs a reader nothing, while one miss is unrecoverable once the
    # issue is public. Fail toward redacting.
    PATTERNS = {
        "anthropic_sk": re.compile(r"sk-ant-[A-Za-z0-9_\-]+"),
        "openai_sk": re.compile(r"sk-(?!ant-)[A-Za-z0-9_\-]{4,}"),
        "github_pat": re.compile(r"gh[pousr]_[A-Za-z0-9_]+"),
        "aws_access_key": re.compile(r"\b(?:AKIA|ASIA)[0-9A-Z]{4,}"),
        "slack_token": re.compile(r"xox[abprs]-[A-Za-z0-9\-]+"),
        "stripe_live": re.compile(r"[ps]k_live_[A-Za-z0-9]+"),
        "google_api": re.compile(r"AIza[0-9A-Za-z_\-]{10,}"),
        "private_key_block": re.compile(
            r"-----BEGIN [A-Z ]*PRIVATE KEY-----[\s\S]*?-----END [A-Z ]*PRIVATE KEY-----"
        ),
        "bearer_token": re.compile(r"Bearer\s+[A-Za-z0-9._\-]+"),
        "authorization_hdr": re.compile(
            r"(authorization['\"]?\s*[:=]\s*['\"]?)[^\s'\",}]+", re.IGNORECASE
        ),
        "api_key": re.compile(
            r"(api[_-]?key['\"]?\s*[:=]\s*['\"]?)[A-Za-z0-9_\-]{8,}", re.IGNORECASE
        ),
        "token_kv": re.compile(
            r"((?:access|secret|auth)[_-]?token['\"]?\s*[:=]\s*['\"]?)[^\s'\",}]{8,}",
            re.IGNORECASE,
        ),
        "password": re.compile(
            r"(password['\"]?\s*[:=]\s*['\"]?)[^\s'\",}]{4,}", re.IGNORECASE
        ),
    }

    # High-entropy detector (base64-like strings >40 chars)
    HIGH_ENTROPY_MIN_LEN = 40
    HIGH_ENTROPY_CHARSET_SIZE = 16  # rough minimum for b64 alphabet

    def __init__(self) -> None:
        """Initialize redactor."""
        self.home_dir = str(Path.home())
        # This machine's own home, matched literally...
        self.home_dir_pattern = re.compile(re.escape(self.home_dir), re.IGNORECASE)
        # ...and home-SHAPED paths belonging to anyone else.
        #
        # Only the local home was covered, which is the one path that least
        # needs it: a crash report is written on the REPORTER's machine and read
        # on ours, so every username in it is someone else's. Live proof --
        # "/home/user/.config/app.conf" passed through untouched on Windows,
        # where Path.home() is C:\\Users\\<me> and matches nothing.
        self.foreign_home_patterns = [
            re.compile(r"(?:/home/|/Users/)[^/\\\s:'\"]+", re.IGNORECASE),
            # `\\\\` in a raw string is regex for TWO literal backslashes; a
            # Windows path has one. That off-by-one escape let
            # C:\Users\carol\... through while every other case was covered --
            # found by an adversarial pass, not by the suite.
            re.compile(r"[A-Za-z]:\\Users\\[^\\/\s:'\"]+", re.IGNORECASE),
        ]

    def redact_string(self, value: str) -> str:
        """
        Redact a single string value.

        Raises RedactionError if redaction cannot complete safely.
        """
        if not isinstance(value, str):
            return value

        try:
            result = value
            # Apply all patterns
            for pattern_name, pattern in self.PATTERNS.items():
                result = pattern.sub("[REDACTED]", result)

            # Redact home directory paths
            result = self.home_dir_pattern.sub("[HOME]", result)
            for _hp in self.foreign_home_patterns:
                result = _hp.sub("[HOME]", result)

            # Redact high-entropy strings
            result = self._redact_high_entropy(result)

            return result
        except Exception as e:
            raise RedactionError(f"String redaction failed: {e}") from e

    def redact_dict(self, data: dict) -> dict:
        """
        Recursively redact a dictionary.

        Raises RedactionError if redaction cannot complete safely.
        """
        try:
            result = {}
            for key, value in data.items():
                result[key] = self.redact_value(value)
            return result
        except RedactionError:
            raise
        except Exception as e:
            raise RedactionError(f"Dict redaction failed: {e}") from e

    def redact_list(self, data: list) -> list:
        """
        Recursively redact a list.

        Raises RedactionError if redaction cannot complete safely.
        """
        try:
            return [self.redact_value(item) for item in data]
        except RedactionError:
            raise
        except Exception as e:
            raise RedactionError(f"List redaction failed: {e}") from e

    def redact_value(self, value: Any) -> Any:
        """
        Recursively redact a value of any type.

        Raises RedactionError if redaction cannot complete safely.
        """
        try:
            if isinstance(value, str):
                return self.redact_string(value)
            elif isinstance(value, dict):
                return self.redact_dict(value)
            elif isinstance(value, (list, tuple)):
                return self.redact_list(value)
            else:
                return value
        except RedactionError:
            raise
        except Exception as e:
            raise RedactionError(f"Value redaction failed: {e}") from e

    def redact_feedback(self, title: str, description: str, environment: Optional[dict] = None) -> dict:
        """
        Redact feedback fields.

        Returns dict with redacted fields.
        Raises RedactionError if any redaction fails.
        """
        try:
            redacted = {
                "title": self.redact_string(title),
                "description": self.redact_string(description),
            }
            if environment:
                redacted["environment"] = self.redact_dict(environment)
            return redacted
        except RedactionError:
            raise
        except Exception as e:
            raise RedactionError(f"Feedback redaction failed: {e}") from e

    def _redact_high_entropy(self, text: str) -> str:
        """Redact high-entropy substrings that look like tokens."""
        # Match sequences that look like base64/urlsafe-base64 and are long
        # Pattern: sequences of alphanumeric + common safe chars, >40 chars
        pattern = re.compile(r"[a-zA-Z0-9._\-]{40,}")

        def maybe_redact(match: re.Match) -> str:
            token = match.group(0)
            # Skip if it looks like a normal word (no mixed case or numbers)
            if self._looks_like_normal_text(token):
                return token
            # Skip if it matches known good patterns
            if self._is_known_good_pattern(token):
                return token
            return "[REDACTED]"

        return pattern.sub(maybe_redact, text)

    def _looks_like_normal_text(self, text: str) -> bool:
        """Check if text looks like normal English words, not a token."""
        # Common words or file paths with extensions shouldn't be redacted
        if "." in text and len(text.split(".")) > 1:
            # Looks like a filename or domain
            ext = text.split(".")[-1]
            if len(ext) <= 4 and ext.isalpha():
                return True
        return False

    def _is_known_good_pattern(self, text: str) -> bool:
        """Check if text is a known good pattern we should NOT redact."""
        # Hex hashes (git commits, checksums)
        if re.match(r"^[a-f0-9]{40,}$", text):
            return True
        # Semantic versions and similar
        if re.match(r"^[\d.]+[\w\-]*$", text):
            return True
        return False


def redact_feedback(
    title: str,
    description: str,
    environment: Optional[dict] = None,
    stack_trace: Optional[str] = None,
) -> dict:
    """
    Top-level redaction function.

    Redacts feedback data comprehensively. Fails CLOSED: raises on any error.

    Args:
        title: Issue title
        description: Issue description
        environment: Optional environment dict (sys info, env vars, etc.)
        stack_trace: Optional stack trace string

    Returns:
        dict with redacted fields: title, description, environment, stack_trace

    Raises:
        RedactionError: if redaction fails for any reason
    """
    redactor = Redactor()

    result = redactor.redact_feedback(title, description, environment)

    if stack_trace:
        result["stack_trace"] = redactor.redact_string(stack_trace)

    return result

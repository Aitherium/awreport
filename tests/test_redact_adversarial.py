"""Adversarial redaction tests -- the inputs nobody thought of.

The rest of the suite proves the cases someone wrote down. These are the ones
that got past it: a truncated token, a token in a URL query, another user's
home directory on a different OS. Two real leaks were found here after the
suite was fully green, including a Windows path that survived because
`\\` in a raw string is regex for TWO literal backslashes and a path has one.

Every entry asserts a substring is GONE, not that something was replaced --
"it returned a string" is exactly the assertion an inert redactor passes.
"""
import pytest
from awreport.redact import Redactor, RedactionError

CASES = [
    # (label, input, the substring that must NOT survive)
    ("github PAT, realistic length", "token=ghp_16C7e42F292c6912E7710c838347Ae178B4a", "ghp_16C7e42F"),
    ("github PAT, truncated in a log", "auth failed for ghp_16C7e42", "ghp_16C7e42"),
    ("anthropic key", "ANTHROPIC_API_KEY=sk-ant-api03-abcDEF123456", "sk-ant-api03"),
    ("openai key", "using sk-proj-abcdefghijklmnop", "sk-proj-abcdef"),
    ("aws access key", "AWS_ACCESS_KEY_ID=AKIAIOSFODNN7EXAMPLE", "AKIAIOSFODNN7"),
    ("aws session key", "ASIAY34FZKBOKMUTVV7A rotated", "ASIAY34FZKBOK"),
    ("slack bot token", "xoxb-1234567890-abcdefghijkl", "xoxb-1234567890"),
    ("stripe live key", "sk_live_51H8xQ2eZvKYlo2C", "sk_live_51H8x"),
    ("google api key", "AIzaSyD-1234567890abcdefghij", "AIzaSyD-1234"),
    ("bearer header", "Authorization: Bearer eyJhbGciOiJIUzI1NiJ9.abc", "eyJhbGciOiJIUzI1NiJ9"),
    ("json authorization", '{"authorization": "tok_abc123def456"}', "tok_abc123def456"),
    ("password kv", "password: hunter2hunter2", "hunter2hunter2"),
    ("access_token kv", "access_token=abcdef1234567890", "abcdef1234567890"),
    ("private key block", "-----BEGIN RSA PRIVATE KEY-----\nMIIEow\n-----END RSA PRIVATE KEY-----", "MIIEow"),
    ("posix home of ANOTHER user", "at /home/alice/.ssh/config", "/home/alice"),
    ("macos home", "at /Users/bob/Library/app.log", "/Users/bob"),
    ("windows home", r"at C:\Users\carol\AppData\x.log", r"Users\carol"),
    ("token inside a URL query", "GET https://api.x/v1?api_key=abcdef1234567890xyz", "abcdef1234567890xyz"),
    ("key in a stack frame", 'File "app.py", line 3, in send\n    ghp_AAAABBBBCCCCDDDDEEEE', "ghp_AAAABBBB"),
]

@pytest.mark.parametrize("label,raw,must_die", CASES, ids=[c[0] for c in CASES])
def test_secret_does_not_survive(label: str, raw: str, must_die: str) -> None:
    out = Redactor().redact_string(raw)
    assert must_die not in out, f"{label}: {must_die!r} survived redaction -> {out!r}"


def test_redaction_fails_closed_when_a_pattern_explodes() -> None:
    """An internal failure must RAISE, never return the unredacted text.

    This is the whole contract: the caller is expected to not send on
    RedactionError. A redactor that returns the original on an exception is
    strictly worse than no redactor, because the caller believes it ran.
    """
    class Exploder:
        def sub(self, *a, **k):
            raise RuntimeError("regex engine died")

    r = Redactor()
    r.PATTERNS = dict(r.PATTERNS)
    r.PATTERNS["boom"] = Exploder()
    with pytest.raises(RedactionError):
        r.redact_string("carrying sk-ant-secret")

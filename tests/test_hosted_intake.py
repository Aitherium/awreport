"""The zero-config path: report without owning a GitHub repo.

Measured 2026-09-20: every awreport path demanded the caller's own GITHUB_TOKEN
and GITHUB_REPO, including `verify`. A customer who runs `pip install awreport`
has neither, so "tell us what broke" either failed outright or filed into the
customer's own repository where nobody who could fix it would see it.

These tests pin the wire that fixed it, and the two things that would quietly
un-fix it: a retired hostname baked into the default, and a failure path that
tells the caller nothing.
"""

from __future__ import annotations

import json
import urllib.error

import pytest

from awreport import hosted

RETIRED_HOSTS = ("portal.aitherium.com", "veil.aitherium.com")


def test_default_surface_is_not_a_retired_host():
    """portal.* and veil.* are GONE (owner 2026-08-31, portal retired 09-06) and
    the apex is a static Pages export that answers 405 to a POST. Pinning one of
    those is how this integration rots without anyone noticing."""
    assert not any(h in hosted.DEFAULT_BASE_URL for h in RETIRED_HOSTS)
    assert hosted.DEFAULT_BASE_URL.startswith("https://")


def test_base_url_is_overridable(monkeypatch):
    monkeypatch.setenv("AITHER_BASE_URL", "https://example.test/")
    assert hosted.base_url() == "https://example.test"
    monkeypatch.delenv("AITHER_BASE_URL")
    assert hosted.base_url() == hosted.DEFAULT_BASE_URL


def test_token_comes_from_env_first(monkeypatch):
    monkeypatch.setenv("AITHER_TOKEN", "tok-abc")
    assert hosted.find_token() == "tok-abc"
    assert hosted.available() is True


def test_no_credential_is_an_actionable_message(monkeypatch, tmp_path):
    for var in ("AITHER_TOKEN", "AITHER_BEARER", "AITHER_SESSION_BEARER"):
        monkeypatch.delenv(var, raising=False)
    monkeypatch.setattr(hosted, "BEARER_FILE", tmp_path / "absent")
    ok, message = hosted.submit("bug", "t", "d")
    assert ok is False
    # It must name BOTH routes forward, or the person with no repo is stuck.
    assert "AITHER_TOKEN" in message
    assert "--token" in message and "GitHub" in message


def test_payload_matches_the_genesis_contract():
    payload = hosted.build_payload("feature", "Title", "Body", {"cli": "1.2"})
    for field in ("title", "description", "category", "severity", "metadata"):
        assert field in payload, f"Genesis BugReportRequest needs {field}"
    assert payload["metadata"]["kind"] == "feature"
    assert payload["metadata"]["source"] == "awreport"
    assert payload["metadata"]["cli"] == "1.2"
    json.dumps(payload)  # must serialise


def test_success_reports_the_ticket(monkeypatch):
    monkeypatch.setenv("AITHER_TOKEN", "tok")

    class _Resp:
        def read(self):
            return b'{"status":"ok","ticket_id":"tkt_1234"}'

        def __enter__(self):
            return self

        def __exit__(self, *a):
            return False

    monkeypatch.setattr(hosted.urllib.request, "urlopen", lambda *a, **k: _Resp())
    ok, message = hosted.submit("bug", "t", "d")
    assert ok is True
    assert "tkt_1234" in message


@pytest.mark.parametrize("code, needle", [(401, "credential"), (403, "credential")])
def test_rejected_credential_says_what_to_do(monkeypatch, code, needle):
    monkeypatch.setenv("AITHER_TOKEN", "tok")

    def _raise(*a, **k):
        raise urllib.error.HTTPError("u", code, "no", {}, None)

    monkeypatch.setattr(hosted.urllib.request, "urlopen", _raise)
    ok, message = hosted.submit("bug", "t", "d")
    assert ok is False
    assert needle in message.lower()


def test_unreachable_never_raises_and_says_it_was_not_filed(monkeypatch):
    """A reporting tool that crashes on a network error is worse than useless:
    the person is already trying to tell us something is broken."""
    monkeypatch.setenv("AITHER_TOKEN", "tok")

    def _boom(*a, **k):
        raise OSError("no route to host")

    monkeypatch.setattr(hosted.urllib.request, "urlopen", _boom)
    ok, message = hosted.submit("bug", "t", "d")
    assert ok is False
    assert "NOT" in message and "github.com/Aitherium" in message

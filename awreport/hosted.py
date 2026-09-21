"""Hosted intake — file a report without owning a GitHub repo.

WHY THIS EXISTS. Measured 2026-09-20: `awreport` required the caller's own
GITHUB_TOKEN and GITHUB_REPO for every path, including `verify`. A customer who
runs `pip install awreport` has neither, so the advertised "tell us what broke"
either failed outright or filed the report into the customer's OWN repository,
where the people who could fix it never saw it. The shop row promising "it lands
as a real GitHub issue" was false for the person reading it.

The platform already had the receiving half: Genesis `POST /feedback/bug-report`
stores a Strata record, auto-creates a support ticket and emits a Flux event,
which the feedback/triage routines already consume. Nothing connected the two.

SURFACE. The base URL is configurable and defaults to the Veil app surface,
because host names here get retired: `portal.aitherium.com` and
`veil.aitherium.com` are GONE (owner, 2026-08-31, portal retired 09-06) and the
apex is a static GitHub Pages export that answers 405 to a POST. Pinning a
retired name is exactly how this integration would rot, so `AITHER_BASE_URL`
overrides it and the default is asserted live by a checker rather than trusted.
"""

from __future__ import annotations

import json
import os
import urllib.error
import urllib.request
from pathlib import Path
from typing import Any, Dict, Optional, Tuple

# The Veil app surface. NOT portal.* (retired) and NOT the apex (static Pages).
DEFAULT_BASE_URL = "https://desktop.aitherium.com"
BUG_PATH = "/api/feedback/bug-report"
BEARER_FILE = Path.home() / ".aither" / "session-bearer"

CATEGORY_BY_KIND = {"bug": "general", "feature": "general", "feedback": "general"}


def base_url() -> str:
    return (os.environ.get("AITHER_BASE_URL") or DEFAULT_BASE_URL).rstrip("/")


def find_token() -> Optional[str]:
    """The caller's Aitherium credential: env first, then the session bearer file.

    Never logged, never echoed -- only its presence is ever reported.
    """
    for var in ("AITHER_TOKEN", "AITHER_BEARER", "AITHER_SESSION_BEARER"):
        value = (os.environ.get(var) or "").strip()
        if value:
            return value
    try:
        if BEARER_FILE.is_file():
            value = BEARER_FILE.read_text(encoding="utf-8").strip()
            if value:
                return value
    except OSError:
        # An unreadable bearer file is "no credential", not a crash -- but say
        # so rather than swallowing it, or the caller sees "not signed in" with
        # no idea their file is there and unreadable.
        return None
    return None


def available() -> bool:
    """Can this transport be used at all? (A credential exists.)"""
    return find_token() is not None


def build_payload(kind: str, title: str, description: str,
                  extra: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
    """Genesis BugReportRequest. `kind` rides in metadata so triage can split
    a feature request from a crash without a second endpoint."""
    payload: Dict[str, Any] = {
        "title": title or "(no title)",
        "description": description or "",
        "category": CATEGORY_BY_KIND.get(kind, "general"),
        "severity": "medium",
        "steps_to_reproduce": "",
        "metadata": {"source": "awreport", "kind": kind},
    }
    if extra:
        payload["metadata"].update(extra)
    return payload


def submit(kind: str, title: str, description: str,
           extra: Optional[Dict[str, Any]] = None,
           timeout: int = 25) -> Tuple[bool, str]:
    """POST the report. Returns (ok, message) and NEVER raises at the caller.

    A failure must say what to do next: the whole point of this path is the
    person who has no GitHub repo, and "Error" with no route forward puts them
    back where they started.
    """
    token = find_token()
    if not token:
        return False, (
            "no Aitherium credential found. Set AITHER_TOKEN, or sign in so that "
            f"{BEARER_FILE} exists. (Or use --token/--repo to file into your own "
            "GitHub repository instead.)"
        )
    url = f"{base_url()}{BUG_PATH}"
    request = urllib.request.Request(
        url,
        data=json.dumps(build_payload(kind, title, description, extra)).encode("utf-8"),
        headers={
            "Content-Type": "application/json",
            "Authorization": f"Bearer {token}",
            "User-Agent": "awreport",
        },
        method="POST",
    )
    try:
        with urllib.request.urlopen(request, timeout=timeout) as response:
            body = response.read().decode("utf-8", "replace")
        try:
            data = json.loads(body)
        except json.JSONDecodeError:
            data = {}
        ticket = data.get("ticket_id") or data.get("id") or ""
        return True, (f"filed with Aitherium support (ticket {ticket})" if ticket
                      else "filed with Aitherium support")
    except urllib.error.HTTPError as exc:
        if exc.code in (401, 403):
            return False, (
                "your Aitherium credential was rejected (HTTP "
                f"{exc.code}). Sign in again, or use --token/--repo to file into "
                "your own GitHub repository."
            )
        detail = exc.read().decode("utf-8", "replace")[:200] if exc.fp else ""
        return False, f"the intake refused the report (HTTP {exc.code}) {detail}".strip()
    except Exception as exc:  # noqa: BLE001 — a report must never crash the caller
        return False, (
            f"could not reach {url} ({type(exc).__name__}). Your report was NOT "
            "filed; try again, or open an issue at github.com/Aitherium."
        )

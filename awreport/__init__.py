"""
awreport - File structured bug reports and feedback to GitHub.

Aither World Report: automated feedback and bug reporting that files proper
GitHub issues for bug reports AND feature requests. Works standalone with just
a GitHub token and repository.

Example:

    from awreport import ReportClient

    client = ReportClient(
        token="ghp_...",
        repo="owner/repo"
    )

    # Report a bug
    result = client.report_bug(
        title="Login fails with special characters",
        description="When using email@example.com with accents...",
        environment={"os": "Linux", "python": "3.10"},
        stack_trace="Traceback: ..."
    )

    if result.is_success():
        print(f"Issue #{result.issue_number} filed at {result.issue_url}")
    elif result.was_duplicate:
        print(f"Duplicate of issue #{result.duplicate_issue_number}")

    # Report a feature request
    result = client.report_feature(
        title="Add dark mode",
        description="Please add a dark mode toggle to the UI"
    )

    # Send general feedback
    result = client.report_feedback(
        message="Great product, would love X feature",
        tags=["praise", "feature-request"]
    )
"""

__version__ = "0.1.0"
__author__ = "AitherOS Contributors"

from .client import ReportClient
from .models import (
    Feedback,
    FeedbackKind,
    ReportResult,
    ReportStatus,
    Issue,
)
from .redact import redact_feedback, RedactionError

__all__ = [
    "ReportClient",
    "Feedback",
    "FeedbackKind",
    "ReportResult",
    "ReportStatus",
    "Issue",
    "redact_feedback",
    "RedactionError",
]

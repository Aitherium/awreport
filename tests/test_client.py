"""Tests for ReportClient."""

import pytest
from unittest.mock import Mock, patch, MagicMock

from awreport.client import ReportClient
from awreport.models import (
    FeedbackKind,
    ReportStatus,
    Issue,
)


def test_report_client_init_success() -> None:
    """Test ReportClient initialization."""
    client = ReportClient(token="ghp_test", repo="owner/repo")
    assert client.token == "ghp_test"
    assert client.repo == "owner/repo"


def test_report_client_init_with_collector() -> None:
    """Test ReportClient with collector endpoint."""
    client = ReportClient(
        token="ghp_test",
        repo="owner/repo",
        collector_endpoint="https://collect.example.com",
    )
    assert client.collector_endpoint == "https://collect.example.com"


@patch("awreport.client.GitHubClient.verify_access")
def test_report_client_verify_access_success(mock_verify: Mock) -> None:
    """Test verify_access returns success when GitHub access is valid."""
    mock_verify.return_value = True
    client = ReportClient(token="ghp_test", repo="owner/repo")
    result = client.verify_access()
    assert result.status == ReportStatus.SUCCESS


@patch("awreport.client.GitHubClient.verify_access")
def test_report_client_verify_access_failure(mock_verify: Mock) -> None:
    """Test verify_access returns error when GitHub access fails."""
    from awreport.github import GitHubError
    mock_verify.side_effect = GitHubError("401 Unauthorized")
    client = ReportClient(token="ghp_test", repo="owner/repo")
    result = client.verify_access()
    assert result.status == ReportStatus.ERROR


@patch("awreport.client.GitHubClient.create_issue")
@patch("awreport.client.GitHubClient.search_issues")
def test_report_bug_creates_issue(
    mock_search: Mock,
    mock_create: Mock,
) -> None:
    """Test report_bug creates an issue."""
    mock_search.return_value = []
    mock_issue = Mock()
    mock_issue.number = 42
    mock_issue.html_url = "https://github.com/owner/repo/issues/42"
    mock_create.return_value = mock_issue

    client = ReportClient(token="ghp_test", repo="owner/repo")
    result = client.report_bug(
        title="Login fails",
        description="Cannot log in with special characters",
    )

    assert result.status == ReportStatus.SUCCESS
    assert result.issue_number == 42
    assert result.issue_url is not None


@patch("awreport.client.GitHubClient.create_issue")
@patch("awreport.client.GitHubClient.search_issues")
def test_report_bug_includes_redaction(
    mock_search: Mock,
    mock_create: Mock,
) -> None:
    """Test report_bug redacts secrets before filing."""
    mock_search.return_value = []
    mock_issue = Mock()
    mock_issue.number = 42
    mock_issue.html_url = "https://github.com/owner/repo/issues/42"
    mock_create.return_value = mock_issue

    client = ReportClient(token="ghp_test", repo="owner/repo")
    result = client.report_bug(
        title="API key sk-ant-secret is leaked",
        description="Found in /home/user/.config",
    )

    # Check that the create_issue was called
    assert mock_create.called
    # Get the title that was passed
    call_args = mock_create.call_args
    title_arg = call_args.kwargs.get("title") or call_args.args[0]
    # Secret should be redacted
    assert "[REDACTED]" in title_arg or "secret" not in title_arg.lower()


@patch("awreport.client.GitHubClient.create_issue")
@patch("awreport.client.GitHubClient.search_issues")
def test_report_feature_creates_issue(
    mock_search: Mock,
    mock_create: Mock,
) -> None:
    """Test report_feature creates an issue."""
    mock_search.return_value = []
    mock_issue = Mock()
    mock_issue.number = 99
    mock_issue.html_url = "https://github.com/owner/repo/issues/99"
    mock_create.return_value = mock_issue

    client = ReportClient(token="ghp_test", repo="owner/repo")
    result = client.report_feature(
        title="Add dark mode",
        description="Users have requested dark mode",
    )

    assert result.status == ReportStatus.SUCCESS
    assert result.issue_number == 99
    # Check that enhancement label was used
    call_args = mock_create.call_args
    labels = call_args.kwargs.get("labels") or []
    assert "enhancement" in labels or "feature" in labels


@patch("awreport.client.GitHubClient.create_issue")
@patch("awreport.client.GitHubClient.search_issues")
def test_report_feedback_creates_issue(
    mock_search: Mock,
    mock_create: Mock,
) -> None:
    """Test report_feedback creates an issue."""
    mock_search.return_value = []
    mock_issue = Mock()
    mock_issue.number = 50
    mock_issue.html_url = "https://github.com/owner/repo/issues/50"
    mock_create.return_value = mock_issue

    client = ReportClient(token="ghp_test", repo="owner/repo")
    result = client.report_feedback(
        message="Great app! Love the new UI.",
        tags=["praise"],
    )

    assert result.status == ReportStatus.SUCCESS
    assert result.issue_number == 50


@patch("awreport.client.GitHubClient.search_issues")
def test_report_bug_with_empty_title_fails(mock_search: Mock) -> None:
    """Test report_bug fails with empty title."""
    client = ReportClient(token="ghp_test", repo="owner/repo")
    result = client.report_bug(title="", description="Some description")

    assert result.status == ReportStatus.ERROR
    assert "validation" in result.message.lower()


@patch("awreport.client.GitHubClient.search_issues")
def test_report_bug_with_empty_description_fails(mock_search: Mock) -> None:
    """Test report_bug fails with empty description."""
    client = ReportClient(token="ghp_test", repo="owner/repo")
    result = client.report_bug(title="Title", description="")

    assert result.status == ReportStatus.ERROR
    assert "validation" in result.message.lower()


@patch("awreport.client.GitHubClient.create_issue")
@patch("awreport.client.GitHubClient.search_issues")
def test_report_bug_detects_duplicate(
    mock_search: Mock,
    mock_create: Mock,
) -> None:
    """Test report_bug detects duplicates."""
    duplicate_issue = Mock()
    duplicate_issue.number = 123
    duplicate_issue.title = "login fails"
    duplicate_issue.html_url = "https://github.com/owner/repo/issues/123"
    duplicate_issue.body = "Same issue description"
    mock_search.return_value = [duplicate_issue]

    client = ReportClient(token="ghp_test", repo="owner/repo")
    result = client.report_bug(
        title="Login fails",
        description="Cannot log in",
    )

    assert result.status == ReportStatus.DUPLICATE
    assert result.was_duplicate is True
    assert result.duplicate_issue_number == 123


@patch("awreport.client.GitHubClient.add_comment")
@patch("awreport.client.GitHubClient.create_issue")
@patch("awreport.client.GitHubClient.search_issues")
def test_report_bug_adds_comment_to_duplicate(
    mock_search: Mock,
    mock_create: Mock,
    mock_comment: Mock,
) -> None:
    """Test report_bug adds comment to duplicate issue."""
    duplicate_issue = Mock()
    duplicate_issue.number = 123
    duplicate_issue.title = "login fails"
    duplicate_issue.html_url = "https://github.com/owner/repo/issues/123"
    duplicate_issue.body = "Same issue"
    mock_search.return_value = [duplicate_issue]
    mock_comment.return_value = True

    client = ReportClient(token="ghp_test", repo="owner/repo")
    result = client.report_bug(
        title="Login fails",
        description="Cannot log in",
        environment={"os": "Linux"},
    )

    # Comment should have been added
    assert mock_comment.called


@patch("awreport.client.GitHubClient.create_issue")
@patch("awreport.client.GitHubClient.search_issues")
def test_report_bug_with_stack_trace_in_body(
    mock_search: Mock,
    mock_create: Mock,
) -> None:
    """Test report_bug includes stack trace in issue body."""
    mock_search.return_value = []
    mock_issue = Mock()
    mock_issue.number = 42
    mock_issue.html_url = "https://github.com/owner/repo/issues/42"
    mock_create.return_value = mock_issue

    client = ReportClient(token="ghp_test", repo="owner/repo")
    stack = "Traceback:\n  File app.py\n  IndexError: list index out of range"
    result = client.report_bug(
        title="Index error",
        description="List access failed",
        stack_trace=stack,
    )

    assert result.status == ReportStatus.SUCCESS
    # Check that body contains stack trace
    call_args = mock_create.call_args
    body = call_args.kwargs.get("body") or call_args.args[1]
    assert "Stack Trace" in body
    assert "IndexError" in body


@patch("awreport.client.GitHubClient.create_issue")
@patch("awreport.client.GitHubClient.search_issues")
def test_report_bug_with_environment_in_body(
    mock_search: Mock,
    mock_create: Mock,
) -> None:
    """Test report_bug includes environment in issue body."""
    mock_search.return_value = []
    mock_issue = Mock()
    mock_issue.number = 42
    mock_issue.html_url = "https://github.com/owner/repo/issues/42"
    mock_create.return_value = mock_issue

    client = ReportClient(token="ghp_test", repo="owner/repo")
    result = client.report_bug(
        title="Bug",
        description="Description",
        environment={"os": "Linux", "python": "3.10"},
    )

    assert result.status == ReportStatus.SUCCESS
    call_args = mock_create.call_args
    body = call_args.kwargs.get("body") or call_args.args[1]
    assert "Environment" in body
    assert "Linux" in body
    assert "3.10" in body

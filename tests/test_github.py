"""Tests for GitHub integration."""

import pytest
from unittest.mock import Mock, patch, MagicMock

from awreport.github import (
    GitHubClient,
    GitHubError,
    fingerprint_for_dedup,
)
from awreport.models import (
    FeedbackKind,
    Issue,
)


def test_github_client_init_validates_token() -> None:
    """Test GitHubClient requires a token."""
    with pytest.raises(ValueError, match="token"):
        GitHubClient(token="", repo="owner/repo")


def test_github_client_init_validates_repo_format() -> None:
    """Test GitHubClient requires repo in owner/repo format."""
    with pytest.raises(ValueError, match="owner/repo"):
        GitHubClient(token="token", repo="invalid")


def test_github_client_init_success() -> None:
    """Test valid GitHubClient initialization."""
    client = GitHubClient(token="ghp_test", repo="owner/repo")
    assert client.token == "ghp_test"
    assert client.repo == "owner/repo"


def test_github_client_api_url_construction() -> None:
    """Test API URL is constructed correctly."""
    client = GitHubClient(token="ghp_test", repo="owner/repo")
    url = client._api_url("/repos/owner/repo")
    assert "https://api.github.com" in url
    assert "repos/owner/repo" in url


@patch("awreport.github.requests.Session.get")
def test_github_client_search_issues_returns_issues(mock_get: Mock) -> None:
    """Test search_issues returns Issue objects."""
    mock_response = Mock()
    mock_response.json.return_value = {
        "items": [
            {
                "id": 1,
                "number": 42,
                "title": "Test Issue",
                "body": "Description",
                "labels": [{"name": "bug"}],
                "state": "open",
                "html_url": "https://github.com/owner/repo/issues/42",
            }
        ]
    }
    mock_get.return_value = mock_response

    client = GitHubClient(token="ghp_test", repo="owner/repo")
    issues = client.search_issues("test", FeedbackKind.BUG)

    assert len(issues) == 1
    assert issues[0].number == 42
    assert issues[0].title == "Test Issue"
    assert "bug" in issues[0].labels


@patch("awreport.github.requests.Session.post")
def test_github_client_create_issue_returns_issue(mock_post: Mock) -> None:
    """Test create_issue returns a created Issue."""
    mock_response = Mock()
    mock_response.json.return_value = {
        "id": 1,
        "number": 99,
        "title": "New Issue",
        "body": "Issue body",
        "labels": [{"name": "bug"}],
        "state": "open",
        "html_url": "https://github.com/owner/repo/issues/99",
    }
    mock_post.return_value = mock_response

    client = GitHubClient(token="ghp_test", repo="owner/repo")
    issue = client.create_issue(
        title="New Issue",
        body="Issue body",
        labels=["bug"],
    )

    assert issue.number == 99
    assert issue.title == "New Issue"
    assert issue.html_url is not None


def test_github_client_create_issue_validates_title() -> None:
    """Test create_issue requires non-empty title."""
    client = GitHubClient(token="ghp_test", repo="owner/repo")
    with pytest.raises(ValueError, match="title"):
        client.create_issue(title="", body="Body")


def test_github_client_create_issue_validates_body() -> None:
    """Test create_issue requires non-empty body."""
    client = GitHubClient(token="ghp_test", repo="owner/repo")
    with pytest.raises(ValueError, match="body"):
        client.create_issue(title="Title", body="")


@patch("awreport.github.requests.Session.post")
def test_github_client_add_comment_success(mock_post: Mock) -> None:
    """Test add_comment returns True on success."""
    mock_response = Mock()
    mock_response.json.return_value = {"id": 1}
    mock_post.return_value = mock_response

    client = GitHubClient(token="ghp_test", repo="owner/repo")
    result = client.add_comment(42, "Test comment")

    assert result is True


def test_github_client_add_comment_validates_comment() -> None:
    """Test add_comment requires non-empty comment."""
    client = GitHubClient(token="ghp_test", repo="owner/repo")
    with pytest.raises(ValueError, match="comment"):
        client.add_comment(42, "")


@patch("awreport.github.requests.Session.get")
def test_github_client_verify_access_success(mock_get: Mock) -> None:
    """Test verify_access returns True on success."""
    mock_response = Mock()
    mock_response.json.return_value = {"id": 1}
    mock_get.return_value = mock_response

    client = GitHubClient(token="ghp_test", repo="owner/repo")
    result = client.verify_access()

    assert result is True


@patch("awreport.github.requests.Session.get")
def test_github_client_verify_access_raises_on_http_error(mock_get: Mock) -> None:
    """Test verify_access raises GitHubError on HTTP failure."""
    mock_response = Mock()
    mock_response.raise_for_status.side_effect = Exception("404")
    mock_get.return_value = mock_response

    client = GitHubClient(token="ghp_test", repo="owner/repo")
    with pytest.raises(GitHubError):
        client.verify_access()


def test_fingerprint_for_dedup_bug() -> None:
    """Test fingerprint creation for bug reports."""
    fp = fingerprint_for_dedup(
        kind=FeedbackKind.BUG,
        title="Login Fails With Accents",
        stack_trace="Traceback: ...",
    )
    assert fp.kind == FeedbackKind.BUG
    assert "login fails" in fp.normalized_title
    assert fp.normalized_stack_hash is not None


def test_fingerprint_for_dedup_feature() -> None:
    """Test fingerprint creation for feature requests."""
    fp = fingerprint_for_dedup(
        kind=FeedbackKind.FEATURE,
        title="Add Dark Mode",
    )
    assert fp.kind == FeedbackKind.FEATURE
    assert "add dark mode" in fp.normalized_title
    assert fp.normalized_stack_hash is None


def test_fingerprint_normalizes_whitespace() -> None:
    """Test fingerprint normalizes extra whitespace."""
    fp1 = fingerprint_for_dedup(
        kind=FeedbackKind.BUG,
        title="Login   Fails    With   Accents",
    )
    fp2 = fingerprint_for_dedup(
        kind=FeedbackKind.BUG,
        title="Login Fails With Accents",
    )
    assert fp1.normalized_title == fp2.normalized_title


def test_fingerprint_to_string() -> None:
    """Test fingerprint can be converted to searchable string."""
    fp = fingerprint_for_dedup(
        kind=FeedbackKind.BUG,
        title="Test Issue",
    )
    s = fp.to_string()
    assert "bug" in s
    assert "test issue" in s


def test_issue_from_github_api() -> None:
    """Test Issue can be constructed from GitHub API response."""
    api_data = {
        "id": 123,
        "number": 42,
        "title": "Test Issue",
        "body": "Description",
        "labels": [{"name": "bug"}, {"name": "urgent"}],
        "state": "open",
        "html_url": "https://github.com/owner/repo/issues/42",
    }
    issue = Issue.from_github_api(api_data)
    assert issue.number == 42
    assert issue.title == "Test Issue"
    assert "bug" in issue.labels
    assert "urgent" in issue.labels

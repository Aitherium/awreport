"""GitHub API integration for filing issues."""

import hashlib
from typing import Optional
from urllib.parse import urljoin
import requests

from .models import Issue, IssueFingerprint, FeedbackKind


class GitHubError(Exception):
    """Raised when GitHub API calls fail."""
    pass


class GitHubClient:
    """Client for GitHub API (no monorepo imports, pure HTTP)."""

    BASE_URL = "https://api.github.com"

    def __init__(self, token: str, repo: str) -> None:
        """
        Initialize GitHub client.

        Args:
            token: GitHub personal access token (or similar)
            repo: Repository in format "owner/repo"

        Raises:
            ValueError: if repo format is invalid
        """
        if not token or not token.strip():
            raise ValueError("token is required")
        if not repo or repo.count("/") != 1:
            raise ValueError("repo must be in format 'owner/repo'")

        self.token = token
        self.repo = repo
        self.session = requests.Session()
        self.session.headers.update(
            {
                "Authorization": f"token {token}",
                "Accept": "application/vnd.github.v3+json",
                "User-Agent": "awreport/0.1.0",
            }
        )

    def _api_url(self, path: str) -> str:
        """Build full API URL."""
        return urljoin(self.BASE_URL, path)

    def search_issues(self, query: str, kind: FeedbackKind) -> list[Issue]:
        """
        Search for existing issues.

        Args:
            query: Search query string
            kind: Issue kind (bug, feature, etc.) to filter by label

        Returns:
            List of matching issues

        Raises:
            GitHubError: if API call fails
        """
        try:
            # Build search query with repo and label filter
            label_map = {
                FeedbackKind.BUG: "bug",
                FeedbackKind.FEATURE: "enhancement",
                FeedbackKind.FEEDBACK: "feedback",
            }
            label = label_map.get(kind, "")

            search_q = f"repo:{self.repo} {query}"
            if label:
                search_q += f" label:{label}"
            search_q += " state:open"

            response = self.session.get(
                self._api_url("/search/issues"),
                params={"q": search_q, "per_page": 10},
                timeout=10,
            )
            response.raise_for_status()

            data = response.json()
            issues = [
                Issue.from_github_api(item) for item in data.get("items", [])
            ]
            return issues
        except requests.RequestException as e:
            raise GitHubError(f"Search failed: {e}") from e
        except Exception as e:
            raise GitHubError(f"Search parsing failed: {e}") from e

    def create_issue(
        self,
        title: str,
        body: str,
        labels: Optional[list[str]] = None,
    ) -> Issue:
        """
        Create a new GitHub issue.

        Args:
            title: Issue title
            body: Issue body/description
            labels: Optional list of label names

        Returns:
            Created Issue object

        Raises:
            GitHubError: if issue creation fails
        """
        if not title or not title.strip():
            raise ValueError("title is required")
        if not body or not body.strip():
            raise ValueError("body is required")

        try:
            payload: dict = {
                "title": title,
                "body": body,
            }
            if labels:
                payload["labels"] = labels

            response = self.session.post(
                self._api_url(f"/repos/{self.repo}/issues"),
                json=payload,
                timeout=10,
            )
            response.raise_for_status()

            return Issue.from_github_api(response.json())
        except requests.RequestException as e:
            raise GitHubError(f"Create issue failed: {e}") from e
        except Exception as e:
            raise GitHubError(f"Create issue parsing failed: {e}") from e

    def add_comment(self, issue_number: int, comment: str) -> bool:
        """
        Add a comment to an existing issue.

        Args:
            issue_number: GitHub issue number
            comment: Comment text

        Returns:
            True if successful

        Raises:
            GitHubError: if adding comment fails
        """
        if not comment or not comment.strip():
            raise ValueError("comment is required")

        try:
            response = self.session.post(
                self._api_url(
                    f"/repos/{self.repo}/issues/{issue_number}/comments"
                ),
                json={"body": comment},
                timeout=10,
            )
            response.raise_for_status()
            return True
        except requests.RequestException as e:
            raise GitHubError(f"Add comment failed: {e}") from e
        except Exception as e:
            raise GitHubError(f"Add comment parsing failed: {e}") from e

    def verify_access(self) -> bool:
        """
        Verify that credentials and repo access are valid.

        Returns:
            True if access verified

        Raises:
            GitHubError: if verification fails
        """
        try:
            response = self.session.get(
                self._api_url(f"/repos/{self.repo}"),
                timeout=10,
            )
            response.raise_for_status()
            return True
        except Exception as e:
            # Deliberately broad, and NOT a swallow -- it re-raises as the typed
            # error every caller already handles. Catching only RequestException
            # let anything else escape as an untyped exception past a caller's
            # `except GitHubError`, so a credential check could fail in a way
            # that read as a crash rather than as "no access". For a gate whose
            # answer decides whether we transmit, unknown must mean NO.
            raise GitHubError(f"Access verification failed: {e}") from e


def fingerprint_for_dedup(
    kind: FeedbackKind,
    title: str,
    stack_trace: Optional[str] = None,
) -> IssueFingerprint:
    """
    Create a fingerprint for deduplication.

    Normalizes title and optionally stack trace for matching similar issues.

    Args:
        kind: Kind of feedback
        title: Issue title
        stack_trace: Optional stack trace for fingerprinting

    Returns:
        IssueFingerprint object
    """
    # Normalize title: lowercase, strip, remove extra whitespace
    normalized_title = " ".join(title.lower().strip().split())

    # Fingerprint stack trace if provided
    normalized_stack_hash = None
    if stack_trace:
        # Hash the stack trace after normalizing line separators
        normalized_trace = "\n".join(
            line.strip() for line in stack_trace.split("\n") if line.strip()
        )
        # Take only last 5 frames to avoid noise from leading context
        frames = normalized_trace.split("\n")[-5:]
        hashable = "\n".join(frames)
        stack_hash = hashlib.sha256(hashable.encode()).hexdigest()
        normalized_stack_hash = stack_hash[:16]  # Use first 16 chars

    return IssueFingerprint(
        kind=kind,
        normalized_title=normalized_title,
        normalized_stack_hash=normalized_stack_hash,
    )

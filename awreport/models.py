"""Type models for awreport feedback and issue reporting."""

from dataclasses import dataclass, field
from typing import Optional
from enum import Enum


class FeedbackKind(str, Enum):
    """Type of feedback being reported."""
    BUG = "bug"
    FEATURE = "feature"
    FEEDBACK = "feedback"


class ReportStatus(str, Enum):
    """Status of a report submission."""
    SUCCESS = "success"
    DUPLICATE = "duplicate"
    ERROR = "error"
    REDACTION_FAILED = "redaction_failed"


@dataclass
class Feedback:
    """Input feedback data from user."""
    kind: FeedbackKind
    title: str
    description: str
    environment: Optional[dict] = None
    stack_trace: Optional[str] = None
    tags: Optional[list[str]] = None
    user_agent: Optional[str] = None

    def validate(self) -> tuple[bool, Optional[str]]:
        """Validate feedback has required fields. Returns (is_valid, error_msg)."""
        if not self.title or not self.title.strip():
            return False, "title is required and cannot be empty"
        if not self.description or not self.description.strip():
            return False, "description is required and cannot be empty"
        if len(self.title) > 200:
            return False, "title must be <= 200 characters"
        if len(self.description) > 10000:
            return False, "description must be <= 10000 characters"
        return True, None


@dataclass
class RedactionResult:
    """Result of redacting sensitive data."""
    success: bool
    data: Optional[dict] = None
    error: Optional[str] = None


@dataclass
class IssueFingerprint:
    """Fingerprint for deduplication."""
    kind: FeedbackKind
    normalized_title: str
    normalized_stack_hash: Optional[str] = None

    def to_string(self) -> str:
        """Convert to searchable string."""
        parts = [self.kind.value, self.normalized_title]
        if self.normalized_stack_hash:
            parts.append(self.normalized_stack_hash)
        return " ".join(parts)


@dataclass
class Issue:
    """GitHub issue representation."""
    id: int
    number: int
    title: str
    body: str
    labels: list[str] = field(default_factory=list)
    state: str = "open"
    html_url: Optional[str] = None

    @classmethod
    def from_github_api(cls, data: dict) -> "Issue":
        """Parse GitHub API response into Issue."""
        return cls(
            id=data.get("id", 0),
            number=data.get("number", 0),
            title=data.get("title", ""),
            body=data.get("body", ""),
            labels=[label.get("name", "") for label in data.get("labels", [])],
            state=data.get("state", "open"),
            html_url=data.get("html_url"),
        )


@dataclass
class ReportResult:
    """Result of submitting a report."""
    status: ReportStatus
    message: str
    issue_number: Optional[int] = None
    issue_url: Optional[str] = None
    was_duplicate: bool = False
    duplicate_issue_number: Optional[int] = None
    error_details: Optional[str] = None

    def is_success(self) -> bool:
        """Check if report was successfully filed."""
        return self.status in (ReportStatus.SUCCESS, ReportStatus.DUPLICATE)

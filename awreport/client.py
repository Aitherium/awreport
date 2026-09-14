"""Main client for reporting bugs and feedback to GitHub."""

import json
from typing import Optional
from dataclasses import asdict

from .models import (
    Feedback,
    FeedbackKind,
    ReportResult,
    ReportStatus,
)
from .redact import redact_feedback, RedactionError
from .github import (
    GitHubClient,
    GitHubError,
    fingerprint_for_dedup,
)


class ReportClient:
    """
    Client for filing structured bug reports and feedback to GitHub.

    This is the main public interface. Usage:

        client = ReportClient(
            token="ghp_...",
            repo="owner/repo"
        )

        result = client.report_bug(
            title="Login fails with special characters",
            description="When using email@example.com with accents...",
            environment={"os": "Linux"},
            stack_trace="Traceback: ..."
        )

        if result.is_success():
            print(f"Issue #{result.issue_number} filed")
    """

    def __init__(
        self,
        token: str,
        repo: str,
        collector_endpoint: Optional[str] = None,
    ) -> None:
        """
        Initialize ReportClient.

        Args:
            token: GitHub personal access token (required)
            repo: Repository in format "owner/repo" (required)
            collector_endpoint: Optional endpoint to POST feedback to instead of/in addition to GitHub

        Raises:
            ValueError: if token or repo are invalid
        """
        self.token = token
        self.repo = repo
        self.collector_endpoint = collector_endpoint
        self.github = GitHubClient(token, repo)

    def verify_access(self) -> ReportResult:
        """
        Verify credentials and repository access.

        Returns:
            ReportResult with status and details

        Returns:
            ReportResult: status indicates if access is valid
        """
        try:
            self.github.verify_access()
            return ReportResult(
                status=ReportStatus.SUCCESS,
                message=f"Access verified for {self.repo}",
            )
        except GitHubError as e:
            return ReportResult(
                status=ReportStatus.ERROR,
                message="Access verification failed",
                error_details=str(e),
            )

    def report_bug(
        self,
        title: str,
        description: str,
        environment: Optional[dict] = None,
        stack_trace: Optional[str] = None,
    ) -> ReportResult:
        """
        Report a bug.

        Args:
            title: Bug title/summary
            description: Detailed description of the bug
            environment: Optional dict with system info, env vars, etc.
            stack_trace: Optional stack trace or error log

        Returns:
            ReportResult with status and issue details
        """
        feedback = Feedback(
            kind=FeedbackKind.BUG,
            title=title,
            description=description,
            environment=environment,
            stack_trace=stack_trace,
            tags=["bug"],
        )
        return self._process_feedback(feedback)

    def report_feature(
        self,
        title: str,
        description: str,
    ) -> ReportResult:
        """
        Report a feature request.

        Args:
            title: Feature title/summary
            description: Description of desired feature

        Returns:
            ReportResult with status and issue details
        """
        feedback = Feedback(
            kind=FeedbackKind.FEATURE,
            title=title,
            description=description,
            tags=["enhancement"],
        )
        return self._process_feedback(feedback)

    def report_feedback(
        self,
        message: str,
        tags: Optional[list[str]] = None,
    ) -> ReportResult:
        """
        Report general feedback.

        Args:
            message: Feedback message
            tags: Optional list of tags

        Returns:
            ReportResult with status and issue details
        """
        feedback = Feedback(
            kind=FeedbackKind.FEEDBACK,
            title=message[:100],  # First 100 chars as title
            description=message,
            tags=tags or ["feedback"],
        )
        return self._process_feedback(feedback)

    def _process_feedback(self, feedback: Feedback) -> ReportResult:
        """
        Process feedback: validate, redact, deduplicate, file.

        Args:
            feedback: Feedback object

        Returns:
            ReportResult with status and details
        """
        # Step 1: Validate
        is_valid, error_msg = feedback.validate()
        if not is_valid:
            return ReportResult(
                status=ReportStatus.ERROR,
                message=f"Feedback validation failed: {error_msg}",
            )

        # Step 2: Redact (fail-closed)
        try:
            redacted = redact_feedback(
                title=feedback.title,
                description=feedback.description,
                environment=feedback.environment,
                stack_trace=feedback.stack_trace,
            )
        except RedactionError as e:
            return ReportResult(
                status=ReportStatus.REDACTION_FAILED,
                message="Could not safely redact sensitive data",
                error_details=str(e),
            )

        # Step 3: Build issue body
        body = self._build_issue_body(feedback, redacted)

        # Step 4: Search for duplicates
        fingerprint = fingerprint_for_dedup(
            kind=feedback.kind,
            title=redacted["title"],
            stack_trace=redacted.get("stack_trace"),
        )

        try:
            duplicates = self.github.search_issues(
                query=redacted["title"],
                kind=feedback.kind,
            )
        except GitHubError as e:
            # Don't fail on search error; just proceed to create
            duplicates = []

        # Step 5: Handle dedup
        for dup in duplicates:
            if self._fingerprints_match(fingerprint, dup):
                # Found a duplicate
                try:
                    comment = (
                        f"Another report of this issue has been filed.\n\n"
                        f"Environment: {json.dumps(redacted.get('environment', {}))}\n\n"
                        f"(Duplicate detection via awreport)"
                    )
                    self.github.add_comment(dup.number, comment)
                except GitHubError:
                    pass  # Comment failed, but we'll still report success

                return ReportResult(
                    status=ReportStatus.DUPLICATE,
                    message=f"Duplicate of issue #{dup.number}",
                    issue_number=dup.number,
                    issue_url=dup.html_url,
                    was_duplicate=True,
                    duplicate_issue_number=dup.number,
                )

        # Step 6: Create new issue
        try:
            issue = self.github.create_issue(
                title=redacted["title"],
                body=body,
                labels=feedback.tags or [],
            )
            return ReportResult(
                status=ReportStatus.SUCCESS,
                message=f"Issue #{issue.number} created",
                issue_number=issue.number,
                issue_url=issue.html_url,
            )
        except GitHubError as e:
            return ReportResult(
                status=ReportStatus.ERROR,
                message="Failed to create GitHub issue",
                error_details=str(e),
            )

    def _build_issue_body(self, feedback: Feedback, redacted: dict) -> str:
        """
        Build GitHub issue body from feedback and redacted data.

        Args:
            feedback: Original feedback
            redacted: Redacted feedback dict

        Returns:
            Formatted issue body string
        """
        body_parts = [
            redacted["description"],
            "",
        ]

        if redacted.get("stack_trace"):
            body_parts.append("## Stack Trace")
            body_parts.append("```")
            body_parts.append(redacted["stack_trace"])
            body_parts.append("```")
            body_parts.append("")

        if redacted.get("environment"):
            body_parts.append("## Environment")
            body_parts.append("```json")
            body_parts.append(json.dumps(redacted["environment"], indent=2))
            body_parts.append("```")
            body_parts.append("")

        body_parts.append("---")
        body_parts.append("_Filed via awreport_")

        return "\n".join(body_parts)

    def _fingerprints_match(self, fp1: "IssueFingerprint", issue: "Issue") -> bool:
        """
        Check if two fingerprints match (for dedup).

        Args:
            fp1: Fingerprint to search for
            issue: GitHub issue to check

        Returns:
            True if fingerprints match (likely duplicate)
        """
        # Match on normalized title (fuzzy)
        if fp1.normalized_title not in issue.title.lower():
            return False

        # If we have a stack hash, that's a stronger match
        if fp1.normalized_stack_hash:
            # Look for the hash in the issue body
            return fp1.normalized_stack_hash in issue.body

        # No stack hash on this report: the title match above is all we have,
        # and it is enough.
        #
        # This read `return fp1.kind != FeedbackKind.BUG`, which made a BUG with
        # no stack trace UNABLE to be a duplicate -- the exact case dedup exists
        # for. Most human reports have no stack ("login fails", typed by hand),
        # so a hundred users hitting one crash opened a hundred issues while the
        # feature reported itself as working. The strong signal is still
        # preferred: when a stack hash IS present it must match, above.
        return True

    def _send_to_collector(self, feedback: Feedback, redacted: dict) -> bool:
        """
        Send feedback to collector endpoint (optional).

        Args:
            feedback: Original feedback
            redacted: Redacted data

        Returns:
            True if successful (or not configured)
        """
        if not self.collector_endpoint:
            return True

        # Placeholder for collector integration
        # Would POST to collector_endpoint with redacted data
        return True

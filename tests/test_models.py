"""Tests for models."""

import pytest
from awreport.models import (
    Feedback,
    FeedbackKind,
    ReportStatus,
    ReportResult,
)


def test_feedback_validation_success() -> None:
    """Test valid feedback passes validation."""
    feedback = Feedback(
        kind=FeedbackKind.BUG,
        title="Login fails",
        description="Cannot login with email@example.com",
    )
    is_valid, error = feedback.validate()
    assert is_valid is True
    assert error is None


def test_feedback_validation_missing_title() -> None:
    """Test empty title is caught."""
    feedback = Feedback(
        kind=FeedbackKind.BUG,
        title="",
        description="Some description",
    )
    is_valid, error = feedback.validate()
    assert is_valid is False
    assert "title" in error.lower()


def test_feedback_validation_missing_description() -> None:
    """Test empty description is caught."""
    feedback = Feedback(
        kind=FeedbackKind.BUG,
        title="Title",
        description="",
    )
    is_valid, error = feedback.validate()
    assert is_valid is False
    assert "description" in error.lower()


def test_feedback_validation_title_too_long() -> None:
    """Test oversized title is caught."""
    feedback = Feedback(
        kind=FeedbackKind.BUG,
        title="x" * 201,
        description="Description",
    )
    is_valid, error = feedback.validate()
    assert is_valid is False
    assert "title" in error.lower() and "200" in error


def test_feedback_validation_description_too_long() -> None:
    """Test oversized description is caught."""
    feedback = Feedback(
        kind=FeedbackKind.BUG,
        title="Title",
        description="x" * 10001,
    )
    is_valid, error = feedback.validate()
    assert is_valid is False
    assert "description" in error.lower() and "10000" in error


def test_report_result_is_success_on_success_status() -> None:
    """Test is_success() returns True for SUCCESS."""
    result = ReportResult(
        status=ReportStatus.SUCCESS,
        message="Issue filed",
        issue_number=42,
    )
    assert result.is_success() is True


def test_report_result_is_success_on_duplicate_status() -> None:
    """Test is_success() returns True for DUPLICATE."""
    result = ReportResult(
        status=ReportStatus.DUPLICATE,
        message="Duplicate found",
        was_duplicate=True,
    )
    assert result.is_success() is True


def test_report_result_is_success_on_error_status() -> None:
    """Test is_success() returns False for ERROR."""
    result = ReportResult(
        status=ReportStatus.ERROR,
        message="Failed",
    )
    assert result.is_success() is False


def test_report_result_with_issue_url() -> None:
    """Test ReportResult captures issue URL."""
    url = "https://github.com/owner/repo/issues/123"
    result = ReportResult(
        status=ReportStatus.SUCCESS,
        message="Filed",
        issue_number=123,
        issue_url=url,
    )
    assert result.issue_url == url

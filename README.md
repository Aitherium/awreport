# awreport — Aither World Report

File structured bug reports and feature requests to GitHub, with automatic redaction of secrets and deduplication.

A standalone Python package for any application to file issues to GitHub:
- ✅ Works standalone — just a GitHub token and repo
- ✅ Automatic secret redaction (API keys, tokens, home paths, etc.)
- ✅ Duplicate detection with fingerprinting
- ✅ Supports bug reports, feature requests, and general feedback
- ✅ Zero monorepo dependencies — pure Python + requests
- ✅ Fully typed, comprehensive tests

## Installation

```bash
pip install awreport
```

Or install from source:

```bash
git clone <repo-url>
cd awreport
pip install -e .
```

## Quick Start

### Via Python API

```python
from awreport import ReportClient

# Initialize client with your GitHub token and target repo
client = ReportClient(
    token="ghp_...",
    repo="owner/repo"
)

# Verify access
result = client.verify_access()
if result.status.value != "success":
    print(f"Error: {result.message}")
    exit(1)

# Report a bug
result = client.report_bug(
    title="Login fails with special characters",
    description="When using email+tag@example.com, login is rejected",
    environment={"os": "Linux", "python": "3.10"},
    stack_trace="Traceback...",
)

if result.is_success():
    print(f"✓ Issue #{result.issue_number} filed")
    print(f"  {result.issue_url}")
elif result.was_duplicate:
    print(f"✓ Duplicate of issue #{result.duplicate_issue_number}")
else:
    print(f"✗ Error: {result.message}")
    if result.error_details:
        print(f"  {result.error_details}")

# Report a feature request
feature_result = client.report_feature(
    title="Add dark mode",
    description="Users have requested a dark mode toggle"
)

# Send general feedback
feedback_result = client.report_feedback(
    message="Great app! Love the new dashboard.",
    tags=["praise", "dashboard"]
)
```

### Via CLI

```bash
# Verify access
awreport --token ghp_... --repo owner/repo verify

# Report a bug (with optional stack trace file)
awreport --token ghp_... --repo owner/repo bug \
  "Login fails with special characters" \
  "Cannot log in with email+tag@example.com" \
  --env-json '{"os":"Linux","python":"3.10"}' \
  --stack-trace-file /path/to/traceback.txt

# Report a feature request
awreport --token ghp_... --repo owner/repo feature \
  "Add dark mode" \
  "Users want a dark mode toggle"

# Send feedback
awreport --token ghp_... --repo owner/repo feedback \
  "Great app! Love the UI." \
  --tags praise,ui
```

Or use environment variables:

```bash
export GITHUB_TOKEN="ghp_..."
export GITHUB_REPO="owner/repo"

awreport verify
awreport bug "Title" "Description"
```

## Secret Redaction

All feedback is automatically redacted before filing to GitHub. Secrets detected and redacted include:

- **API Keys**: Anthropic (`sk-ant-*`), OpenAI (`sk-*`), AWS (`AKIA*`)
- **Tokens**: GitHub PAT (`ghp_*`), Slack (`xoxb-*`, `xoxp-*`), Bearer tokens
- **Paths**: Home directory paths (`/home/user/`, `C:\Users\...`)
- **High-entropy strings**: Base64-like tokens >40 characters
- **Other patterns**: `api_key=`, `password=`, etc.

Redaction is **fail-closed**: if redaction cannot complete safely, the report is NOT filed:

```python
from awreport import RedactionError, ReportClient

client = ReportClient(token="...", repo="...")

try:
    result = client.report_bug(title, description, environment, stack_trace)
except RedactionError:
    print("Could not safely redact sensitive data. Report not filed.")
    # Application should log this and possibly alert a human
```

## Duplicate Detection

Feedback is fingerprinted and compared against existing issues:

1. **Title normalization**: lowercase, strip, remove extra whitespace
2. **Stack trace hashing**: last 5 frames, SHA-256 hash (first 16 chars)
3. **Existing issue search**: GitHub API search with filters
4. **Match logic**:
   - Bugs: must match title + stack trace hash (strong match)
   - Features/feedback: title match alone is sufficient

If a duplicate is found:
- The existing issue number is returned in `ReportResult.duplicate_issue_number`
- A comment is added to the existing issue with new environment info
- Status is `ReportStatus.DUPLICATE` but `is_success()` still returns `True`

```python
result = client.report_bug(title, description)
if result.was_duplicate:
    print(f"Already reported as issue #{result.duplicate_issue_number}")
```

## Return Values

Every report returns a `ReportResult` with:

- `status`: `SUCCESS`, `DUPLICATE`, `ERROR`, or `REDACTION_FAILED`
- `message`: Human-readable status message
- `issue_number`: GitHub issue number (if successful)
- `issue_url`: GitHub issue URL (if successful)
- `was_duplicate`: `True` if a duplicate was found
- `duplicate_issue_number`: Number of duplicate issue (if applicable)
- `error_details`: Error details (if `status == ERROR`)

```python
result = client.report_bug(...)

if result.is_success():
    # SUCCESS or DUPLICATE
    print(f"Issue: {result.issue_url}")
else:
    # ERROR or REDACTION_FAILED
    print(f"Failed: {result.message}")
    print(f"Details: {result.error_details}")
```

## Type Safety

All public functions are fully typed for IDE autocomplete:

```python
from awreport import ReportClient, ReportResult, FeedbackKind

def handle_bug(client: ReportClient, title: str, desc: str) -> ReportResult:
    return client.report_bug(title, desc)

# IDE provides full autocomplete and type checking
```

## Testing

Run tests:

```bash
pip install -e ".[dev]"
pytest tests/
```

Tests include:
- **Redaction**: secrets are redacted, normal text is preserved
- **GitHub integration**: API calls are mocked, various scenarios tested
- **Deduplication**: fingerprints match similar issues, exact duplicates detected
- **CLI**: argument parsing, error handling

All tests use **positive assertions** — they verify that successful operations produce the expected output:

```python
def test_report_bug_creates_issue():
    """Test report_bug creates an issue."""
    result = client.report_bug(title, description)
    assert result.status == ReportStatus.SUCCESS
    assert result.issue_number == 42
    assert result.issue_url is not None
```

## Design Principles

1. **Standalone**: No monorepo imports, no internal dependencies. Just GitHub token + repo.
2. **Fail-closed**: If redaction fails, do NOT send. If verification fails, report it.
3. **Fully typed**: Every public function has type hints. Mypy-clean.
4. **Comprehensive redaction**: Better to over-redact than under-redact.
5. **Dedup prevents spam**: Same issue = one thread with new comments, not N issues.
6. **Graceful degradation**: Search failure doesn't block issue creation. Comment failure doesn't block duplicate detection.

## Environment Variables

- `GITHUB_TOKEN`: GitHub personal access token (required if `--token` not provided)
- `GITHUB_REPO`: Repository in format `owner/repo` (required if `--repo` not provided)

## Development

Install dev dependencies:

```bash
pip install -e ".[dev]"
```

Run linting:

```bash
ruff check awreport/ tests/
mypy awreport/
```

Format code:

```bash
black awreport/ tests/
```

## License

Apache-2.0

## Contributing

Contributions welcome! Please:
1. Write tests for new functionality
2. Run `pytest` and linting before submitting
3. Keep redaction comprehensive — err on the side of over-redacting
4. Maintain zero monorepo dependencies

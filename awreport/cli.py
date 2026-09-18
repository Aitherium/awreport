"""CLI entry point for awreport."""

import argparse
import json
import sys
from typing import Optional

from .client import ReportClient
from .models import ReportStatus


def main() -> int:
    """Main CLI entry point."""
    # GENERATED doctor intercept (gen_aw_doctor.py) -- do not edit
    _dv = locals().get("argv")
    if (_dv if _dv is not None else __import__("sys").argv[1:])[:1] == ["doctor"]:
        from ._doctor import report
        return report()
    # GENERATED repo-state intercept (gen_aw_doctor.py) -- do not edit
    try:
        from awgit import state as _aw_state
    except Exception:
        _aw_state = None
    if _aw_state is not None:
        _sv = locals().get("argv")
        if _aw_state.cli_banner(_sv if _sv is not None else __import__("sys").argv[1:]):
            return 0
    parser = argparse.ArgumentParser(
        description="File structured bug reports and feedback to GitHub"
    )

    # Required arguments
    parser.add_argument(
        "--token",
        required=False,
        help="GitHub personal access token (env: GITHUB_TOKEN)",
    )
    parser.add_argument(
        "--repo",
        required=False,
        help="Repository (owner/repo)",
    )

    # Subcommands
    subparsers = parser.add_subparsers(dest="command", help="Command to run")

    # bug command
    bug_parser = subparsers.add_parser("bug", help="Report a bug")
    bug_parser.add_argument("title", help="Bug title")
    bug_parser.add_argument("description", help="Bug description")
    bug_parser.add_argument(
        "--env-json",
        help="Environment info as JSON",
    )
    bug_parser.add_argument(
        "--stack-trace-file",
        help="Path to stack trace file",
    )

    # feature command
    feature_parser = subparsers.add_parser("feature", help="Request a feature")
    feature_parser.add_argument("title", help="Feature title")
    feature_parser.add_argument("description", help="Feature description")

    # feedback command
    feedback_parser = subparsers.add_parser("feedback", help="Send feedback")
    feedback_parser.add_argument("message", help="Feedback message")
    feedback_parser.add_argument(
        "--tags",
        help="Comma-separated tags",
    )

    # verify command
    subparsers.add_parser("verify", help="Verify GitHub access")

    args = parser.parse_args()

    # Load credentials
    import os
    token = args.token or os.getenv("GITHUB_TOKEN")
    repo = args.repo or os.getenv("GITHUB_REPO")

    if not token or not repo:
        print(
            "Error: --token and --repo required "
            "(or set GITHUB_TOKEN and GITHUB_REPO env vars)",
            file=sys.stderr,
        )
        return 1

    client = ReportClient(token=token, repo=repo)

    # Handle commands
    if args.command == "verify":
        result = client.verify_access()
        print(result.message)
        return 0 if result.status == ReportStatus.SUCCESS else 1

    elif args.command == "bug":
        env = None
        if args.env_json:
            try:
                env = json.loads(args.env_json)
            except json.JSONDecodeError as e:
                print(f"Error parsing --env-json: {e}", file=sys.stderr)
                return 1

        stack_trace = None
        if args.stack_trace_file:
            try:
                with open(args.stack_trace_file) as f:
                    stack_trace = f.read()
            except IOError as e:
                print(
                    f"Error reading stack trace file: {e}",
                    file=sys.stderr,
                )
                return 1

        result = client.report_bug(
            title=args.title,
            description=args.description,
            environment=env,
            stack_trace=stack_trace,
        )
        return _print_result(result)

    elif args.command == "feature":
        result = client.report_feature(
            title=args.title,
            description=args.description,
        )
        return _print_result(result)

    elif args.command == "feedback":
        tags = None
        if args.tags:
            tags = [t.strip() for t in args.tags.split(",")]

        result = client.report_feedback(
            message=args.message,
            tags=tags,
        )
        return _print_result(result)

    else:
        parser.print_help()
        return 1


def _print_result(result: "ReportResult") -> int:
    """Print result and return exit code."""
    print(result.message)

    if result.issue_url:
        print(f"Issue: {result.issue_url}")

    if result.status == ReportStatus.SUCCESS:
        return 0
    elif result.status == ReportStatus.DUPLICATE:
        print("(This is a duplicate of an existing issue)")
        return 0
    else:
        if result.error_details:
            print(f"Details: {result.error_details}", file=sys.stderr)
        return 1


if __name__ == "__main__":
    sys.exit(main())

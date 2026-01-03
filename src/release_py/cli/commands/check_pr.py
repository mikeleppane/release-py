"""Implementation of the 'check-pr' command.

The check-pr command validates PR titles follow conventional commit format.
It's designed to be used in CI pipelines.
"""

from __future__ import annotations

import os
from pathlib import Path
from typing import TYPE_CHECKING

from rich.panel import Panel

from release_py.core.commits import (
    DEFAULT_ALLOWED_TYPES,
    ValidationResult,
    validate_pr_title,
)

if TYPE_CHECKING:
    from rich.console import Console


def run_check_pr(
    title: str | None,
    path: str | None,
    require_scope: bool,
    console: Console,
    err_console: Console,
) -> None:
    """Run the check-pr command.

    Args:
        title: PR title to validate (or read from environment/config)
        path: Optional path to project directory
        require_scope: Whether to require a scope in the PR title
        console: Console for standard output
        err_console: Console for error output
    """
    # Get PR title from argument, environment, or GitHub Actions event
    pr_title = _get_pr_title(title)

    if not pr_title:
        err_console.print(
            "[red]Error:[/] No PR title provided.\n\n"
            "Provide a title via:\n"
            "  • [cyan]--title[/] argument\n"
            "  • [cyan]GITHUB_PR_TITLE[/] environment variable\n"
            "  • GitHub Actions event (automatic in GitHub Actions)"
        )
        raise SystemExit(1)

    # Load custom allowed types from config if available
    allowed_types = _load_allowed_types(path)

    # Validate the PR title
    result = validate_pr_title(
        pr_title,
        allowed_types=allowed_types,
        require_scope=require_scope,
    )

    # Display result
    if result.is_valid:
        _display_success(console, pr_title, result)
    else:
        _display_error(err_console, pr_title, result)
        raise SystemExit(1)


def _get_pr_title(title: str | None) -> str | None:
    """Get PR title from various sources.

    Priority:
    1. Command line argument
    2. GITHUB_PR_TITLE environment variable
    3. GitHub Actions event file
    """
    # 1. Command line argument
    if title:
        return title

    # 2. Environment variable
    if env_title := os.environ.get("GITHUB_PR_TITLE"):
        return env_title

    # 3. GitHub Actions event
    event_path = os.environ.get("GITHUB_EVENT_PATH")
    if event_path and Path(event_path).is_file():
        return _get_title_from_github_event(event_path)

    return None


def _get_title_from_github_event(event_path: str) -> str | None:
    """Extract PR title from GitHub Actions event file."""
    import json

    try:
        with Path(event_path).open() as f:
            event = json.load(f)
    except (json.JSONDecodeError, OSError):
        return None

    # Pull request event
    if pr := event.get("pull_request"):
        title = pr.get("title")
        return str(title) if title else None

    # Issue comment on PR (for /check-pr command)
    issue = event.get("issue")
    if issue and "pull_request" in issue:
        title = issue.get("title")
        return str(title) if title else None

    return None


def _load_allowed_types(path: str | None) -> frozenset[str]:
    """Load allowed commit types from project config."""
    try:
        from release_py.config import load_config

        project_path = Path(path) if path else Path.cwd()
        config = load_config(project_path)

        # Combine all configured commit types
        all_types = set(config.commits.types_major)
        all_types.update(config.commits.types_minor)
        all_types.update(config.commits.types_patch)

        # Add default types if config doesn't define any
        if not all_types:
            return DEFAULT_ALLOWED_TYPES

        # Also include common non-release types
        all_types.update(["docs", "style", "ci", "chore", "build", "revert", "test"])
        return frozenset(all_types)
    except Exception:
        return DEFAULT_ALLOWED_TYPES


def _display_success(
    console: Console,
    pr_title: str,
    result: ValidationResult,
) -> None:
    """Display successful validation result."""
    console.print()
    console.print(
        Panel(
            f"[bold green]✓ PR title is valid[/]\n\n"
            f"[bold]Title:[/] {pr_title}\n"
            f"[bold]Type:[/] {result.commit_type}\n"
            + (f"[bold]Scope:[/] {result.scope}\n" if result.scope else "")
            + f"[bold]Description:[/] {result.description}"
            + ("\n[bold yellow]Breaking change![/]" if result.is_breaking else ""),
            title="[bold green]PR Title Check[/]",
            border_style="green",
        )
    )


def _display_error(
    console: Console,
    pr_title: str,
    result: ValidationResult,
) -> None:
    """Display validation error."""
    console.print()
    console.print(
        Panel(
            f"[bold red]✗ PR title is invalid[/]\n\n"
            f"[bold]Title:[/] {pr_title}\n"
            f"[bold red]Error:[/] {result.error}\n\n"
            "[bold]Expected format:[/]\n"
            "  [cyan]<type>[(scope)]: <description>[/]\n\n"
            "[bold]Examples:[/]\n"
            "  [dim]feat: add user authentication[/]\n"
            "  [dim]fix(api): handle null responses[/]\n"
            "  [dim]feat!: redesign config format[/]",
            title="[bold red]PR Title Check Failed[/]",
            border_style="red",
        )
    )


def get_github_pr_number() -> int | None:
    """Get PR number from GitHub Actions environment."""
    import json

    # From GITHUB_REF (refs/pull/123/merge)
    ref = os.environ.get("GITHUB_REF")
    if ref and ref.startswith("refs/pull/"):
        parts = ref.split("/")
        if len(parts) >= 3:
            try:
                return int(parts[2])
            except ValueError:
                pass

    # From event file
    event_path = os.environ.get("GITHUB_EVENT_PATH")
    if event_path and Path(event_path).is_file():
        try:
            with Path(event_path).open() as f:
                event = json.load(f)
            if pr := event.get("pull_request"):
                number = pr.get("number")
                return int(number) if number is not None else None
        except (json.JSONDecodeError, OSError, ValueError, TypeError):
            pass

    return None

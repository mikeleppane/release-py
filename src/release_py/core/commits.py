"""Conventional commit parsing and version bump calculation.

This module parses git commits following the Conventional Commits
specification (https://www.conventionalcommits.org/) and determines
the appropriate version bump type.

Conventional Commit Format:
    <type>[(scope)][!]: <description>

    [optional body]

    [optional footer(s)]

Examples:
    feat: add user authentication
    fix(api): handle null responses
    feat!: redesign config format (breaking change)
    refactor(core): simplify version parsing

    BREAKING CHANGE: Config file format has changed.
"""

from __future__ import annotations

import re
from dataclasses import dataclass
from typing import TYPE_CHECKING

from release_py.core.version import BumpType

if TYPE_CHECKING:
    from release_py.config.models import CommitsConfig
    from release_py.vcs.git import Commit


# Regex for parsing conventional commit subjects
_CONVENTIONAL_COMMIT_PATTERN = re.compile(
    r"""
    ^
    (?P<type>[a-zA-Z]+)       # Type (feat, fix, etc.)
    (?:\((?P<scope>[^)]+)\))? # Optional scope in parentheses
    (?P<breaking>!)?          # Optional breaking change indicator
    :\s*                      # Colon and optional whitespace
    (?P<description>.+)       # Description
    $
    """,
    re.VERBOSE,
)


@dataclass(frozen=True, slots=True)
class ParsedCommit:
    """A parsed conventional commit.

    Attributes:
        commit: The original git commit
        commit_type: The commit type (feat, fix, etc.), or None if not conventional
        scope: Optional scope (e.g., 'api', 'core')
        description: The commit description
        is_breaking: Whether this is a breaking change
        is_conventional: Whether the commit follows conventional format
    """

    commit: Commit
    commit_type: str | None
    scope: str | None
    description: str
    is_breaking: bool
    is_conventional: bool

    @classmethod
    def from_commit(cls, commit: Commit, breaking_pattern: str) -> ParsedCommit:
        """Parse a git commit into a ParsedCommit.

        Args:
            commit: The git commit to parse
            breaking_pattern: Regex pattern to detect breaking changes in body

        Returns:
            ParsedCommit instance
        """
        subject = commit.subject
        body = commit.body

        # Try to match conventional commit format
        match = _CONVENTIONAL_COMMIT_PATTERN.match(subject)

        if not match:
            # Not a conventional commit
            return cls(
                commit=commit,
                commit_type=None,
                scope=None,
                description=subject,
                is_breaking=False,
                is_conventional=False,
            )

        commit_type = match.group("type").lower()
        scope = match.group("scope")
        description = match.group("description")
        breaking_indicator = bool(match.group("breaking"))

        # Check for breaking change in body
        breaking_in_body = False
        if body and breaking_pattern:
            breaking_in_body = bool(re.search(breaking_pattern, body, re.IGNORECASE))

        is_breaking = breaking_indicator or breaking_in_body

        return cls(
            commit=commit,
            commit_type=commit_type,
            scope=scope,
            description=description,
            is_breaking=is_breaking,
            is_conventional=True,
        )


def filter_skip_release_commits(
    commits: list[Commit],
    skip_patterns: list[str],
) -> list[Commit]:
    """Filter out commits that contain skip release markers.

    Args:
        commits: List of commits to filter
        skip_patterns: Patterns that indicate a commit should be skipped
                      (case-insensitive matching)

    Returns:
        Filtered list of commits without skip markers
    """
    if not skip_patterns:
        return commits

    filtered = []
    for commit in commits:
        message_lower = commit.message.lower()
        should_skip = any(pattern.lower() in message_lower for pattern in skip_patterns)
        if not should_skip:
            filtered.append(commit)

    return filtered


def parse_commits(
    commits: list[Commit],
    config: CommitsConfig,
) -> list[ParsedCommit]:
    """Parse a list of commits into ParsedCommits.

    Args:
        commits: List of git commits to parse
        config: Commit parsing configuration

    Returns:
        List of ParsedCommit instances
    """
    parsed = []
    for commit in commits:
        pc = ParsedCommit.from_commit(commit, config.breaking_pattern)

        # If scope filtering is enabled, skip non-matching commits
        if config.scope_regex and pc.scope and not re.match(config.scope_regex, pc.scope):
            continue

        parsed.append(pc)

    return parsed


def calculate_bump(
    parsed_commits: list[ParsedCommit],
    config: CommitsConfig,
) -> BumpType:
    """Calculate the version bump type from parsed commits.

    The bump type is determined by:
    1. Any breaking change → MAJOR (but MINOR for 0.x.y)
    2. Any type in types_major → MAJOR
    3. Any type in types_minor → MINOR
    4. Any type in types_patch → PATCH
    5. Otherwise → NONE

    Args:
        parsed_commits: List of parsed commits
        config: Commit parsing configuration

    Returns:
        The calculated bump type
    """
    if not parsed_commits:
        return BumpType.NONE

    # Track the highest bump type seen
    max_bump = BumpType.NONE

    for pc in parsed_commits:
        # Breaking changes always result in major bump
        if pc.is_breaking:
            return BumpType.MAJOR

        if not pc.is_conventional or not pc.commit_type:
            continue

        commit_type = pc.commit_type.lower()

        # Check configured bump types
        if commit_type in config.types_major:
            return BumpType.MAJOR
        if commit_type in config.types_minor:
            if max_bump.value in ("none", "patch"):
                max_bump = BumpType.MINOR
        elif commit_type in config.types_patch and max_bump == BumpType.NONE:
            max_bump = BumpType.PATCH

    return max_bump


def group_commits_by_type(
    parsed_commits: list[ParsedCommit],
) -> dict[str, list[ParsedCommit]]:
    """Group parsed commits by their type.

    Args:
        parsed_commits: List of parsed commits

    Returns:
        Dictionary mapping commit types to lists of commits
    """
    grouped: dict[str, list[ParsedCommit]] = {}

    for pc in parsed_commits:
        commit_type = pc.commit_type or "other"
        grouped.setdefault(commit_type, []).append(pc)

    return grouped


def get_breaking_changes(parsed_commits: list[ParsedCommit]) -> list[ParsedCommit]:
    """Get all breaking change commits.

    Args:
        parsed_commits: List of parsed commits

    Returns:
        List of breaking change commits
    """
    return [pc for pc in parsed_commits if pc.is_breaking]


def format_commit_for_changelog(
    pc: ParsedCommit,
    *,
    include_sha: bool = False,
    include_scope: bool = True,
) -> str:
    """Format a parsed commit for inclusion in a changelog.

    Args:
        pc: The parsed commit
        include_sha: Whether to include the commit SHA
        include_scope: Whether to include the scope

    Returns:
        Formatted string for changelog
    """
    parts = []

    if include_scope and pc.scope:
        parts.append(f"**{pc.scope}:** ")

    if pc.is_breaking:
        parts.append("[BREAKING] ")

    parts.append(pc.description)

    if include_sha:
        parts.append(f" ({pc.commit.short_sha})")

    return "".join(parts)


# =============================================================================
# PR Title Validation
# =============================================================================

# Default allowed commit types for PR titles
DEFAULT_ALLOWED_TYPES = frozenset(
    [
        "feat",
        "fix",
        "docs",
        "style",
        "refactor",
        "perf",
        "test",
        "build",
        "ci",
        "chore",
        "revert",
    ]
)


@dataclass(frozen=True, slots=True)
class ValidationResult:
    """Result of validating a PR title.

    Attributes:
        is_valid: Whether the title is valid
        error: Error message if invalid, None otherwise
        commit_type: Parsed commit type (if valid)
        scope: Parsed scope (if present)
        description: Parsed description (if valid)
        is_breaking: Whether marked as breaking change
    """

    is_valid: bool
    error: str | None
    commit_type: str | None = None
    scope: str | None = None
    description: str | None = None
    is_breaking: bool = False


def validate_pr_title(  # noqa: PLR0911
    title: str,
    allowed_types: frozenset[str] | None = None,
    require_scope: bool = False,
    max_length: int = 100,
) -> ValidationResult:
    """Validate a PR title follows conventional commit format.

    This is useful for enforcing PR title conventions in CI.

    Args:
        title: The PR title to validate
        allowed_types: Set of allowed commit types (default: standard types)
        require_scope: Whether a scope is required
        max_length: Maximum title length (default: 100)

    Returns:
        ValidationResult with validation details

    Examples:
        >>> result = validate_pr_title("feat: add new feature")
        >>> result.is_valid
        True
        >>> result.commit_type
        'feat'

        >>> result = validate_pr_title("added feature")
        >>> result.is_valid
        False
        >>> result.error
        "PR title must follow conventional commit format: <type>[(scope)]: <description>"
    """
    types = allowed_types or DEFAULT_ALLOWED_TYPES

    # Check empty title
    if not title or not title.strip():
        return ValidationResult(
            is_valid=False,
            error="PR title cannot be empty",
        )

    title = title.strip()

    # Check length
    if len(title) > max_length:
        return ValidationResult(
            is_valid=False,
            error=f"PR title exceeds {max_length} characters ({len(title)} chars)",
        )

    # Try to match conventional commit format
    match = _CONVENTIONAL_COMMIT_PATTERN.match(title)

    if not match:
        return ValidationResult(
            is_valid=False,
            error="PR title must follow conventional commit format: <type>[(scope)]: <description>",
        )

    commit_type = match.group("type").lower()
    scope = match.group("scope")
    description = match.group("description")
    is_breaking = bool(match.group("breaking"))

    # Check allowed types
    if commit_type not in types:
        allowed_list = ", ".join(sorted(types))
        return ValidationResult(
            is_valid=False,
            error=f"Invalid commit type '{commit_type}'. Allowed: {allowed_list}",
            commit_type=commit_type,
            scope=scope,
            description=description,
            is_breaking=is_breaking,
        )

    # Check scope requirement
    if require_scope and not scope:
        return ValidationResult(
            is_valid=False,
            error="PR title must include a scope: <type>(scope): <description>",
            commit_type=commit_type,
            scope=scope,
            description=description,
            is_breaking=is_breaking,
        )

    # Check description not empty
    if not description or not description.strip():
        return ValidationResult(
            is_valid=False,
            error="PR title must include a description after the colon",
            commit_type=commit_type,
            scope=scope,
            description=description,
            is_breaking=is_breaking,
        )

    return ValidationResult(
        is_valid=True,
        error=None,
        commit_type=commit_type,
        scope=scope,
        description=description.strip(),
        is_breaking=is_breaking,
    )


def validate_pr_titles_batch(
    titles: list[str],
    allowed_types: frozenset[str] | None = None,
    require_scope: bool = False,
) -> list[ValidationResult]:
    """Validate multiple PR titles.

    Args:
        titles: List of PR titles to validate
        allowed_types: Set of allowed commit types
        require_scope: Whether a scope is required

    Returns:
        List of ValidationResult for each title
    """
    return [validate_pr_title(title, allowed_types, require_scope) for title in titles]

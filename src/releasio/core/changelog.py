"""Changelog generation via git-cliff and native fallback.

This module wraps git-cliff for generating beautiful, customizable
changelogs from conventional commits. When git-cliff is unavailable,
a native fallback generator is used.

git-cliff is called as a subprocess and its output is captured
for further processing.

Key features:
- Changelog generation with GitHub integration (PR links, usernames)
- Automatic version bump detection via --bump flag
- Full Conventional Commits support
- Custom commit templates for flexible formatting
- Native fallback when git-cliff is not installed
"""

from __future__ import annotations

import shutil
import subprocess
from datetime import UTC, datetime
from typing import TYPE_CHECKING

from rich.console import Console  # Used at runtime for console.status()

from releasio.core.version import BumpType
from releasio.exceptions import ChangelogError, GitCliffError

if TYPE_CHECKING:
    from releasio.config.models import ChangelogConfig, ReleasePyConfig
    from releasio.core.version import Version
    from releasio.vcs.git import GitRepository

# ParsedCommit is used at runtime in generate_changelog, so import it conditionally
# to avoid circular imports
try:
    from releasio.core.commits import ParsedCommit
except ImportError:
    ParsedCommit = None  # type: ignore[misc,assignment]


def get_bump_from_git_cliff(
    repo: GitRepository,
    _config: ReleasePyConfig,
) -> BumpType:
    """Get the recommended version bump type from git-cliff.

    Uses git-cliff's --bump flag to analyze commits and determine
    the appropriate version bump (major, minor, patch).

    Args:
        repo: Git repository instance
        _config: Release configuration (reserved for future use)

    Returns:
        BumpType indicating the recommended version bump

    Raises:
        GitCliffError: If git-cliff command fails
    """
    args = [
        "git-cliff",
        "--repository",
        str(repo.path),
        "--bump",
        "--unreleased",
    ]

    # Use pyproject.toml config if available
    pyproject_path = repo.path / "pyproject.toml"
    if pyproject_path.exists():
        args.extend(["--config", str(pyproject_path)])

    try:
        result = subprocess.run(
            args,
            capture_output=True,
            text=True,
            check=True,
            cwd=repo.path,
        )

        # git-cliff --bump outputs the changelog with the bumped version
        # We check stderr for the bump type info
        output = (result.stdout + result.stderr).strip().lower()

        return _parse_bump_type(output)

    except subprocess.CalledProcessError as e:
        # If no commits to bump, git-cliff may return non-zero
        stderr_lower = e.stderr.lower()
        if "no commits" in stderr_lower or "nothing to bump" in stderr_lower:
            return BumpType.NONE
        raise GitCliffError(
            f"git-cliff --bump failed with exit code {e.returncode}",
            stderr=e.stderr,
        ) from e
    except FileNotFoundError as e:
        raise ChangelogError(
            "git-cliff not found. This may indicate a broken installation. "
            "Try reinstalling: pip install --force-reinstall releasio"
        ) from e


def _parse_bump_type(output: str) -> BumpType:
    """Parse bump type from git-cliff output."""
    if "major" in output:
        return BumpType.MAJOR
    if "minor" in output:
        return BumpType.MINOR
    if "patch" in output:
        return BumpType.PATCH
    return BumpType.NONE


def generate_changelog(
    repo: GitRepository,
    version: Version,
    config: ReleasePyConfig,
    *,
    unreleased_only: bool = True,
    github_repo: str | None = None,
    console: Console | None = None,
    parsed_commits: list[ParsedCommit] | None = None,
) -> str:
    """Generate changelog content using git-cliff with native fallback.

    Args:
        repo: Git repository instance
        version: Version being released
        config: Release configuration
        unreleased_only: Only generate for unreleased changes
        github_repo: GitHub repo in "owner/repo" format for enhanced changelog
                    (adds PR links, @usernames, first-time contributor badges)
        console: Rich console for progress indicators (optional)
        parsed_commits: Pre-parsed commits for native fallback (optional, will be
                       fetched and parsed if not provided and fallback needed)

    Returns:
        Generated changelog content as string

    Raises:
        GitCliffError: If git-cliff command fails
        ChangelogError: If changelog generation fails and native fallback is disabled
    """
    # Check if git-cliff is available
    if is_git_cliff_available():
        try:
            return _run_git_cliff(
                repo=repo,
                version=version,
                unreleased_only=unreleased_only,
                github_repo=github_repo,
                console=console,
            )
        except FileNotFoundError:
            # Shouldn't happen since we checked, but handle it anyway
            pass

    # git-cliff not available - use native fallback if enabled
    if not config.changelog.native_fallback:
        raise ChangelogError(
            "git-cliff not found and native_fallback is disabled. "
            "Install git-cliff or enable native_fallback in config."
        )

    # Get parsed commits if not provided
    if parsed_commits is None:
        from releasio.core.commits import parse_commits

        tag_pattern = f"{config.version.tag_prefix}*"
        latest_tag = repo.get_latest_tag(tag_pattern)
        commits = repo.get_commits_since_tag(latest_tag)
        parsed_commits = parse_commits(commits, config.commits)

    # Generate using native fallback
    first_time_contributors = None
    if config.changelog.show_first_time_contributors:
        first_time_contributors = get_first_time_contributors(repo, parsed_commits)

    dependency_updates = None
    if config.changelog.include_dependency_updates:
        tag_pattern = f"{config.version.tag_prefix}*"
        previous_tag = repo.get_latest_tag(tag_pattern)
        dependency_updates = parse_dependency_updates(repo, previous_tag)

    return generate_native_changelog(
        parsed_commits=parsed_commits,
        version=version,
        config=config.changelog,
        first_time_contributors=first_time_contributors,
        dependency_updates=dependency_updates,
    )


def _run_git_cliff(
    repo: GitRepository,
    version: Version,
    unreleased_only: bool,
    github_repo: str | None = None,
    console: Console | None = None,
) -> str:
    """Run git-cliff subprocess.

    Args:
        repo: Git repository
        version: Version for the release
        unreleased_only: Only unreleased changes
        github_repo: GitHub repo in "owner/repo" format for GitHub integration
        console: Rich console for progress indicators (optional)

    Returns:
        Changelog content
    """
    args = [
        "git-cliff",
        "--repository",
        str(repo.path),
        "--tag",
        str(version),
    ]

    if unreleased_only:
        args.append("--unreleased")

    # Enable GitHub integration if repo info provided
    # This adds PR links, @usernames, and first-time contributor markers
    if github_repo:
        args.extend(["--github-repo", github_repo])

    # Use pyproject.toml config if available
    pyproject_path = repo.path / "pyproject.toml"
    if pyproject_path.exists():
        args.extend(["--config", str(pyproject_path)])

    try:
        if console:
            with console.status("[bold blue]Generating changelog...", spinner="dots"):
                result = subprocess.run(
                    args,
                    capture_output=True,
                    text=True,
                    check=True,
                    cwd=repo.path,
                )
        else:
            result = subprocess.run(
                args,
                capture_output=True,
                text=True,
                check=True,
                cwd=repo.path,
            )
        return result.stdout.strip()
    except subprocess.CalledProcessError as e:
        raise GitCliffError(
            f"git-cliff failed with exit code {e.returncode}",
            stderr=e.stderr,
        ) from e


# =============================================================================
# First-Time Contributor Detection
# =============================================================================


def get_first_time_contributors(
    repo: GitRepository,
    parsed_commits: list[ParsedCommit],
) -> set[str]:
    """Identify first-time contributors from the parsed commits.

    Checks the git history to find authors who have not contributed before
    the earliest commit in parsed_commits.

    Args:
        repo: Git repository instance
        parsed_commits: List of commits in the current release

    Returns:
        Set of author names who are first-time contributors
    """
    if not parsed_commits:
        return set()

    # Get all unique authors from current commits
    current_authors = {pc.commit.author_name for pc in parsed_commits}

    # Get the earliest commit date in the release
    earliest_commit = min(parsed_commits, key=lambda pc: pc.commit.date)
    earliest_date = earliest_commit.commit.date

    # Get all historical authors before this release
    try:
        historical_authors = repo.get_authors_before_date(earliest_date)
    except (AttributeError, Exception):
        # If the method doesn't exist or fails, return empty set
        # This gracefully degrades if git history isn't available
        return set()

    # First-timers are those in current but not in historical
    return current_authors - historical_authors


# =============================================================================
# Dependency Update Detection
# =============================================================================


def parse_dependency_updates(
    repo: GitRepository,
    previous_tag: str | None,
) -> list[str]:
    """Parse dependency changes between versions.

    Compares lock files between the previous tag and HEAD to identify
    dependency changes.

    Args:
        repo: Git repository instance
        previous_tag: Previous version tag (None for first release)

    Returns:
        List of dependency update strings (e.g., "httpx: 0.27.0 → 0.28.0")
    """
    if previous_tag is None:
        return []

    updates: list[str] = []

    # Try different lock file formats
    lock_files = ["uv.lock", "poetry.lock", "pdm.lock", "requirements.txt"]

    for lock_file in lock_files:
        try:
            old_content = repo.get_file_at_ref(lock_file, previous_tag)
            new_content = repo.get_file_at_ref(lock_file, "HEAD")

            if old_content is None or new_content is None:
                continue

            file_updates = _parse_lock_file_diff(lock_file, old_content, new_content)
            updates.extend(file_updates)
            break  # Only use the first lock file found
        except (AttributeError, Exception):
            # If the method doesn't exist or fails, continue to next file
            continue

    return updates


def _parse_lock_file_diff(
    filename: str,
    old_content: str,
    new_content: str,
) -> list[str]:
    """Parse the diff between two versions of a lock file.

    Args:
        filename: Name of the lock file
        old_content: Content at previous version
        new_content: Content at current version

    Returns:
        List of dependency update strings
    """
    updates: list[str] = []

    if filename == "uv.lock":
        updates = _parse_uv_lock_diff(old_content, new_content)
    elif filename == "poetry.lock":
        updates = _parse_poetry_lock_diff(old_content, new_content)
    elif filename == "pdm.lock":
        updates = _parse_pdm_lock_diff(old_content, new_content)
    elif filename == "requirements.txt":
        updates = _parse_requirements_diff(old_content, new_content)

    return updates


def _compute_package_diff(
    old_packages: dict[str, str],
    new_packages: dict[str, str],
) -> list[str]:
    """Compute the difference between two package version dictionaries.

    Args:
        old_packages: Dictionary of package name -> version at old ref
        new_packages: Dictionary of package name -> version at new ref

    Returns:
        Sorted list of update strings
    """
    old_names = set(old_packages.keys())
    new_names = set(new_packages.keys())

    # Build updates list using list comprehensions
    added = [f"Added {name} {new_packages[name]}" for name in new_names - old_names]
    removed = [f"Removed {name} {old_packages[name]}" for name in old_names - new_names]
    updated = [
        f"{name}: {old_packages[name]} → {new_packages[name]}"
        for name in old_names & new_names
        if old_packages[name] != new_packages[name]
    ]

    return sorted(added + removed + updated)


def _parse_uv_lock_diff(old_content: str, new_content: str) -> list[str]:
    """Parse uv.lock file diff for dependency changes."""
    import re

    # Extract package versions from uv.lock format
    # Format: [[package]]\nname = "package-name"\nversion = "1.2.3"
    package_pattern = re.compile(
        r'\[\[package\]\]\s*name\s*=\s*"([^"]+)"\s*version\s*=\s*"([^"]+)"',
        re.MULTILINE,
    )

    old_packages = dict(package_pattern.findall(old_content))
    new_packages = dict(package_pattern.findall(new_content))

    return _compute_package_diff(old_packages, new_packages)


def _parse_poetry_lock_diff(old_content: str, new_content: str) -> list[str]:
    """Parse poetry.lock file diff for dependency changes."""
    import re

    # Extract package versions from poetry.lock format
    # Format: [[package]]\nname = "package-name"\nversion = "1.2.3"
    package_pattern = re.compile(
        r'\[\[package\]\]\s*name\s*=\s*"([^"]+)"\s*version\s*=\s*"([^"]+)"',
        re.MULTILINE | re.DOTALL,
    )

    old_packages = dict(package_pattern.findall(old_content))
    new_packages = dict(package_pattern.findall(new_content))

    return _compute_package_diff(old_packages, new_packages)


def _parse_pdm_lock_diff(old_content: str, new_content: str) -> list[str]:
    """Parse pdm.lock file diff for dependency changes."""
    import re

    # PDM lock format: [[package]]\nname = "package"\nversion = "1.0.0"
    package_pattern = re.compile(
        r'\[\[package\]\]\s*name\s*=\s*"([^"]+)"\s*version\s*=\s*"([^"]+)"',
        re.MULTILINE | re.DOTALL,
    )

    old_packages = dict(package_pattern.findall(old_content))
    new_packages = dict(package_pattern.findall(new_content))

    return _compute_package_diff(old_packages, new_packages)


def _parse_requirements_diff(old_content: str, new_content: str) -> list[str]:
    """Parse requirements.txt file diff for dependency changes."""
    import re

    # Simple pattern for package==version
    package_pattern = re.compile(r"^([a-zA-Z0-9_-]+)==([^\s]+)", re.MULTILINE)

    old_packages = dict(package_pattern.findall(old_content))
    new_packages = dict(package_pattern.findall(new_content))

    return _compute_package_diff(old_packages, new_packages)


# =============================================================================
# Native Changelog Generation (fallback when git-cliff unavailable)
# =============================================================================


def is_git_cliff_available() -> bool:
    """Check if git-cliff is installed and available.

    Returns:
        True if git-cliff is available, False otherwise
    """
    return shutil.which("git-cliff") is not None


def format_commit_entry(
    parsed_commit: ParsedCommit,
    config: ChangelogConfig,
    *,
    first_time_contributors: set[str] | None = None,
) -> str:
    """Format a single commit entry for the changelog.

    Uses the commit_template from config if provided, otherwise uses
    default formatting based on show_authors, show_commit_hash settings.

    Template variables:
        {description} - The commit description
        {scope} - The commit scope (or empty string)
        {author} - The commit author name
        {hash} - The short commit hash
        {body} - The commit body (or empty string)
        {type} - The commit type (feat, fix, etc.)

    Args:
        parsed_commit: The parsed commit to format
        config: Changelog configuration
        first_time_contributors: Set of author names who are first-time contributors

    Returns:
        Formatted commit entry string
    """
    pc = parsed_commit
    commit = pc.commit
    is_first_timer = (
        first_time_contributors is not None and commit.author_name in first_time_contributors
    )

    # If custom template is provided, use it
    if config.commit_template:
        entry = _apply_commit_template(
            template=config.commit_template,
            description=pc.description,
            scope=pc.scope or "",
            author=commit.author_name,
            commit_hash=commit.short_sha,
            body=commit.body or "",
            commit_type=pc.commit_type or "other",
        )
        # Add first-time contributor badge if applicable
        if config.show_first_time_contributors and is_first_timer:
            entry = f"{entry} {config.first_contributor_badge}"
        return entry

    # Default formatting
    parts = []

    # Add scope if present
    if pc.scope:
        parts.append(f"**{pc.scope}:** ")

    # Add breaking indicator if applicable
    if pc.is_breaking:
        parts.append("**BREAKING:** ")

    # Add description
    parts.append(pc.description)

    # Add author if enabled
    if config.show_authors:
        parts.append(f" (by {commit.author_name})")

    # Add commit hash if enabled
    if config.show_commit_hash:
        parts.append(f" ({commit.short_sha})")

    # Add first-time contributor badge if enabled and applicable
    if config.show_first_time_contributors and is_first_timer:
        parts.append(f" {config.first_contributor_badge}")

    return "".join(parts)


def _apply_commit_template(
    template: str,
    description: str,
    scope: str,
    author: str,
    commit_hash: str,
    body: str,
    commit_type: str,
) -> str:
    """Apply template variables to a commit template string.

    Args:
        template: The template string with {variable} placeholders
        description: Commit description
        scope: Commit scope (may be empty)
        author: Author name
        commit_hash: Short commit hash
        body: Commit body (may be empty)
        commit_type: Commit type (feat, fix, etc.)

    Returns:
        Formatted string with variables replaced
    """
    return (
        template.replace("{description}", description)
        .replace("{scope}", scope)
        .replace("{author}", author)
        .replace("{hash}", commit_hash)
        .replace("{body}", body)
        .replace("{type}", commit_type)
    )


def generate_native_changelog(
    parsed_commits: list[ParsedCommit],
    version: Version,
    config: ChangelogConfig,
    *,
    first_time_contributors: set[str] | None = None,
    dependency_updates: list[str] | None = None,
) -> str:
    """Generate changelog natively without git-cliff.

    Groups commits by type and formats them using the configured
    section_headers and commit_template settings.

    Args:
        parsed_commits: List of parsed commits
        version: Version being released
        config: Changelog configuration
        first_time_contributors: Set of author names who are first-time contributors
        dependency_updates: List of dependency update strings to include

    Returns:
        Generated changelog content as string
    """
    if not parsed_commits:
        return ""

    # Group commits by type (or custom changelog_group)
    grouped: dict[str, list[ParsedCommit]] = {}
    breaking: list[ParsedCommit] = []

    for pc in parsed_commits:
        if pc.is_breaking:
            breaking.append(pc)
        # Use custom group from parser if available, otherwise use type
        group_key = pc.changelog_group or pc.commit_type or "other"
        grouped.setdefault(group_key, []).append(pc)

    # Build changelog content
    lines: list[str] = []

    # Add custom header if configured
    if config.header:
        lines.append(config.header.rstrip())
        lines.append("")

    # Header with version and date
    today = datetime.now(tz=UTC).strftime("%Y-%m-%d")
    lines.append(f"## [{version}] - {today}")
    lines.append("")

    # Breaking changes section first (if any)
    if breaking:
        header = config.section_headers.get("breaking", "⚠️ Breaking Changes")
        lines.append(f"### {header}")
        lines.append("")
        for pc in breaking:
            entry = format_commit_entry(pc, config, first_time_contributors=first_time_contributors)
            lines.append(f"- {entry}")
        lines.append("")

    # Other sections in config order
    section_order = [
        "feat",
        "fix",
        "perf",
        "docs",
        "refactor",
        "test",
        "build",
        "ci",
        "style",
        "chore",
    ]

    for commit_type in section_order:
        commits = grouped.get(commit_type, [])
        if not commits:
            continue

        header = config.section_headers.get(commit_type, commit_type.title())
        lines.append(f"### {header}")
        lines.append("")
        for pc in commits:
            entry = format_commit_entry(pc, config, first_time_contributors=first_time_contributors)
            lines.append(f"- {entry}")
        lines.append("")

    # Any custom groups not in standard order
    custom_groups = set(grouped.keys()) - set(section_order) - {"breaking", "other"}
    for group_key in sorted(custom_groups):
        commits = grouped[group_key]
        # For custom groups from parsers, use the group name as header
        header = config.section_headers.get(group_key, group_key)
        lines.append(f"### {header}")
        lines.append("")
        for pc in commits:
            entry = format_commit_entry(pc, config, first_time_contributors=first_time_contributors)
            lines.append(f"- {entry}")
        lines.append("")

    # "Other" section last
    other_commits = grouped.get("other", [])
    if other_commits:
        header = config.section_headers.get("other", "📝 Other")
        lines.append(f"### {header}")
        lines.append("")
        for pc in other_commits:
            entry = format_commit_entry(pc, config, first_time_contributors=first_time_contributors)
            lines.append(f"- {entry}")
        lines.append("")

    # Dependency updates section (if enabled and updates available)
    if config.include_dependency_updates and dependency_updates:
        lines.append("### 📦 Dependencies")
        lines.append("")
        lines.extend(f"- {update}" for update in dependency_updates)
        lines.append("")

    return "\n".join(lines).rstrip() + "\n"


# =============================================================================
# git-cliff Config Generation
# =============================================================================


def generate_cliff_config(
    config: ReleasePyConfig,
    *,
    output_format: str = "toml",
) -> str:
    """Generate git-cliff configuration from releasio settings.

    Maps releasio section_headers and commit_parsers to git-cliff format.
    This allows users to use releasio config as the single source of truth
    while still leveraging git-cliff's powerful features.

    Args:
        config: The releasio configuration
        output_format: Output format ("toml" only currently supported)

    Returns:
        git-cliff configuration as a string

    Example:
        >>> config = ReleasePyConfig()
        >>> cliff_config = generate_cliff_config(config)
        >>> print(cliff_config)  # Outputs valid cliff.toml content
    """
    if output_format != "toml":
        raise ValueError(f"Unsupported output format: {output_format}")

    changelog_config = config.changelog
    commits_config = config.commits

    lines: list[str] = []

    # Header comment
    lines.append("# git-cliff configuration")
    lines.append("# Auto-generated from releasio settings")
    lines.append("# Do not edit manually if using releasio config generation")
    lines.append("")

    # [changelog] section
    lines.append("[changelog]")
    if changelog_config.header:
        lines.append(f'header = """{changelog_config.header}"""')
    else:
        lines.append('header = """# Changelog\n"""')

    # Body template
    body_template = changelog_config.cliff_body_template or _get_default_body_template()
    lines.append(f'body = """{body_template}"""')
    lines.append("trim = true")
    lines.append("")

    # [git] section
    lines.append("[git]")
    lines.append("conventional_commits = true")
    lines.append("filter_unconventional = true")
    lines.append("split_commits = false")

    # Add commit parsers
    lines.append("commit_parsers = [")

    # Add custom parsers first
    for parser in commits_config.commit_parsers:
        # Map custom parser to git-cliff format
        # git-cliff uses "message" regex and "group" for section
        pattern_escaped = _escape_toml(parser.pattern)
        group_escaped = _escape_toml(parser.group)
        lines.append(f'  {{ message = "{pattern_escaped}", group = "{group_escaped}" }},')

    # Add standard conventional commit mappings from section_headers
    standard_mappings = [
        ("^feat", "feat"),
        ("^fix", "fix"),
        ("^perf", "perf"),
        ("^doc", "docs"),
        ("^refactor", "refactor"),
        ("^test", "test"),
        ("^build", "build"),
        ("^ci", "ci"),
        ("^style", "style"),
        ("^chore", "chore"),
    ]

    for pattern, commit_type in standard_mappings:
        group = changelog_config.section_headers.get(commit_type, commit_type.title())
        lines.append(f'  {{ message = "{pattern}", group = "{_escape_toml(group)}" }},')

    # Skip patterns - commits to ignore
    skip_patterns = ["^Merge", "^WIP"]
    lines.extend(f'  {{ message = "{pattern}", skip = true }},' for pattern in skip_patterns)

    lines.append("]")
    lines.append("")

    # Filter commits section
    lines.append("filter_commits = true")

    # Tag pattern
    tag_prefix = config.version.tag_prefix
    if tag_prefix:
        lines.append(f'tag_pattern = "{tag_prefix}[0-9]*"')

    lines.append("")

    return "\n".join(lines)


def _get_default_body_template() -> str:
    """Get the default body template for git-cliff."""
    return """
{% for group, commits in commits | group_by(attribute="group") %}
### {{ group | upper_first }}
{% for commit in commits %}
- {{ commit.message | upper_first }}{% if commit.scope %} (**{{ commit.scope }}**){% endif %}
{%- endfor %}
{% endfor %}
"""


def _escape_toml(value: str) -> str:
    """Escape a string for TOML."""
    return value.replace("\\", "\\\\").replace('"', '\\"')

"""Changelog generation via git-cliff.

This module wraps git-cliff for generating beautiful, customizable
changelogs from conventional commits.

git-cliff is called as a subprocess and its output is captured
for further processing.
"""

from __future__ import annotations

import subprocess
from typing import TYPE_CHECKING

from release_py.exceptions import ChangelogError, GitCliffError

if TYPE_CHECKING:
    from release_py.config.models import ReleasePyConfig
    from release_py.core.version import Version
    from release_py.vcs.git import GitRepository


def generate_changelog(
    repo: GitRepository,
    version: Version,
    config: ReleasePyConfig,
    *,
    unreleased_only: bool = True,
) -> str:
    """Generate changelog content using git-cliff.

    Args:
        repo: Git repository instance
        version: Version being released
        config: Release configuration
        unreleased_only: Only generate for unreleased changes

    Returns:
        Generated changelog content as string

    Raises:
        GitCliffError: If git-cliff command fails
        ChangelogError: If changelog generation fails
    """
    try:
        return _run_git_cliff(
            repo=repo,
            version=version,
            _config=config,
            unreleased_only=unreleased_only,
        )
    except FileNotFoundError as e:
        raise ChangelogError("git-cliff not found. Install it with: pip install git-cliff") from e


def _run_git_cliff(
    repo: GitRepository,
    version: Version,
    _config: ReleasePyConfig,
    unreleased_only: bool,
) -> str:
    """Run git-cliff subprocess.

    Args:
        repo: Git repository
        version: Version for the release
        _config: Configuration (unused, reserved for future use)
        unreleased_only: Only unreleased changes

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
        return result.stdout.strip()
    except subprocess.CalledProcessError as e:
        raise GitCliffError(
            f"git-cliff failed with exit code {e.returncode}",
            stderr=e.stderr,
        ) from e


def generate_fallback_changelog(
    repo: GitRepository,
    version: Version,
    config: ReleasePyConfig,
) -> str:
    """Generate a simple changelog when git-cliff is not available.

    This is a fallback that creates a basic changelog from commits
    without requiring git-cliff.

    Args:
        repo: Git repository
        version: Version being released
        config: Configuration

    Returns:
        Simple changelog content
    """
    from datetime import UTC, datetime

    from release_py.core.commits import group_commits_by_type, parse_commits

    # Get latest tag
    tag_pattern = f"{config.effective_tag_prefix}*"
    latest_tag = repo.get_latest_tag(tag_pattern)

    # Get commits since last tag
    commits = repo.get_commits_since_tag(latest_tag)

    if not commits:
        return ""

    # Parse commits
    parsed = parse_commits(commits, config.commits)
    grouped = group_commits_by_type(parsed)

    # Build changelog
    lines = [
        f"## [{version}] - {datetime.now(UTC).strftime('%Y-%m-%d')}",
        "",
    ]

    # Type labels with emojis
    type_labels = {
        "feat": "### ✨ Features",
        "fix": "### 🐛 Bug Fixes",
        "perf": "### ⚡ Performance",
        "docs": "### 📚 Documentation",
        "refactor": "### ♻️ Refactoring",
        "test": "### 🧪 Tests",
        "build": "### 📦 Build",
        "ci": "### 🔧 CI",
        "style": "### 💄 Style",
        "chore": "### 🔨 Chores",
        "other": "### 📝 Other",
    }

    # Breaking changes first
    breaking = [pc for pc in parsed if pc.is_breaking]
    if breaking:
        lines.append("### ⚠️ Breaking Changes")
        lines.append("")
        for pc in breaking:
            scope = f"**{pc.scope}:** " if pc.scope else ""
            lines.append(f"- {scope}{pc.description}")
        lines.append("")

    # Other changes by type
    for commit_type, label in type_labels.items():
        commits_of_type = grouped.get(commit_type, [])
        # Filter out breaking changes (already listed)
        commits_of_type = [c for c in commits_of_type if not c.is_breaking]

        if commits_of_type:
            lines.append(label)
            lines.append("")
            for pc in commits_of_type:
                scope = f"**{pc.scope}:** " if pc.scope else ""
                lines.append(f"- {scope}{pc.description}")
            lines.append("")

    return "\n".join(lines)

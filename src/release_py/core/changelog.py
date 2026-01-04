"""Changelog generation via git-cliff.

This module wraps git-cliff for generating beautiful, customizable
changelogs from conventional commits.

git-cliff is called as a subprocess and its output is captured
for further processing.

Key features:
- Changelog generation with GitHub integration (PR links, usernames)
- Automatic version bump detection via --bump flag
- Full Conventional Commits support
"""

from __future__ import annotations

import subprocess
from typing import TYPE_CHECKING

from release_py.core.version import BumpType
from release_py.exceptions import ChangelogError, GitCliffError

if TYPE_CHECKING:
    from release_py.config.models import ReleasePyConfig
    from release_py.core.version import Version
    from release_py.vcs.git import GitRepository


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
            "Try reinstalling: pip install --force-reinstall py-release"
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
    config: ReleasePyConfig,  # noqa: ARG001
    *,
    unreleased_only: bool = True,
    github_repo: str | None = None,
) -> str:
    """Generate changelog content using git-cliff.

    Args:
        repo: Git repository instance
        version: Version being released
        config: Release configuration (reserved for future git-cliff config)
        unreleased_only: Only generate for unreleased changes
        github_repo: GitHub repo in "owner/repo" format for enhanced changelog
                    (adds PR links, @usernames, first-time contributor badges)

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
            unreleased_only=unreleased_only,
            github_repo=github_repo,
        )
    except FileNotFoundError as e:
        raise ChangelogError(
            "git-cliff not found. This may indicate a broken installation. "
            "Try reinstalling: pip install --force-reinstall py-release"
        ) from e


def _run_git_cliff(
    repo: GitRepository,
    version: Version,
    unreleased_only: bool,
    github_repo: str | None = None,
) -> str:
    """Run git-cliff subprocess.

    Args:
        repo: Git repository
        version: Version for the release
        unreleased_only: Only unreleased changes
        github_repo: GitHub repo in "owner/repo" format for GitHub integration

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



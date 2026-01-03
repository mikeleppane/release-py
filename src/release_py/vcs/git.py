"""Git repository operations via subprocess.

This module provides a clean interface for git operations without
requiring external git libraries. All operations are performed via
subprocess calls to the git CLI.

Example:
    >>> repo = GitRepository()
    >>> commits = repo.get_commits_since_tag("v1.0.0")
    >>> for commit in commits:
    ...     print(f"{commit.short_sha}: {commit.subject}")
"""

from __future__ import annotations

import re
import subprocess
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path
from typing import TYPE_CHECKING

from release_py.exceptions import (
    DirtyRepositoryError,
    GitError,
    NotARepositoryError,
    TagExistsError,
)

if TYPE_CHECKING:
    from collections.abc import Sequence


# Separator used to split git log fields (unlikely to appear in commit messages)
_FIELD_SEP = "<<<FIELD>>>"
_RECORD_SEP = "<<<RECORD>>>"


@dataclass(frozen=True, slots=True)
class Commit:
    """Represents a git commit.

    Attributes:
        sha: Full commit SHA hash
        message: Complete commit message (subject + body)
        author_name: Name of the commit author
        author_email: Email of the commit author
        date: Commit timestamp
    """

    sha: str
    message: str
    author_name: str
    author_email: str
    date: datetime

    @property
    def short_sha(self) -> str:
        """Return the short (7-character) SHA."""
        return self.sha[:7]

    @property
    def subject(self) -> str:
        """Return the first line of the commit message."""
        return self.message.split("\n", 1)[0]

    @property
    def body(self) -> str | None:
        """Return the commit body (everything after the first line).

        Returns:
            The body text, or None if the commit has no body.
        """
        parts = self.message.split("\n", 1)
        if len(parts) > 1:
            return parts[1].strip()
        return None


class GitRepository:
    """Interface for git repository operations.

    All operations are performed via subprocess calls to the git CLI.
    The repository must be initialized and have at least one commit.

    Args:
        path: Path to the repository root. Defaults to current directory.

    Raises:
        NotARepositoryError: If the path is not a git repository.

    Example:
        >>> repo = GitRepository(Path("/path/to/repo"))
        >>> if repo.is_dirty():
        ...     print("Repository has uncommitted changes")
    """

    def __init__(self, path: Path | None = None) -> None:
        self.path = (path or Path.cwd()).resolve()
        self._validate_repository()

    def _validate_repository(self) -> None:
        """Verify this is a valid git repository.

        Raises:
            NotARepositoryError: If not a git repository.
        """
        try:
            self._run(["rev-parse", "--git-dir"])
        except GitError as e:
            raise NotARepositoryError(f"Not a git repository: {self.path}") from e

    def _run(
        self,
        args: Sequence[str],
        *,
        check: bool = True,
        capture_output: bool = True,
    ) -> subprocess.CompletedProcess[str]:
        """Run a git command.

        Args:
            args: Command arguments (without 'git' prefix)
            check: Whether to raise on non-zero exit code
            capture_output: Whether to capture stdout/stderr

        Returns:
            CompletedProcess with command results

        Raises:
            GitError: If command fails and check=True
        """
        cmd = ["git", "-C", str(self.path), *args]
        try:
            return subprocess.run(
                cmd,
                check=check,
                capture_output=capture_output,
                text=True,
            )
        except subprocess.CalledProcessError as e:
            stderr = e.stderr.strip() if e.stderr else ""
            raise GitError(f"Git command failed: {' '.join(cmd)}\n{stderr}") from e

    # =========================================================================
    # Repository State
    # =========================================================================

    def is_dirty(self) -> bool:
        """Check if the working directory has uncommitted changes.

        Returns:
            True if there are uncommitted changes.
        """
        result = self._run(["status", "--porcelain"])
        return bool(result.stdout.strip())

    def ensure_clean(self) -> None:
        """Ensure the repository has no uncommitted changes.

        Raises:
            DirtyRepositoryError: If there are uncommitted changes.
        """
        if self.is_dirty():
            raise DirtyRepositoryError(
                "Repository has uncommitted changes. Commit or stash them before proceeding."
            )

    def get_current_branch(self) -> str:
        """Get the name of the current branch.

        Returns:
            Current branch name.

        Raises:
            GitError: If in detached HEAD state or other error.
        """
        result = self._run(["rev-parse", "--abbrev-ref", "HEAD"])
        branch = result.stdout.strip()
        if branch == "HEAD":
            raise GitError("Repository is in detached HEAD state")
        return branch

    def get_default_branch(self) -> str:
        """Detect the default branch (main or master).

        Returns:
            The default branch name ('main' or 'master').

        Raises:
            GitError: If neither main nor master exists.
        """
        for branch in ("main", "master"):
            result = self._run(
                ["rev-parse", "--verify", f"refs/heads/{branch}"],
                check=False,
            )
            if result.returncode == 0:
                return branch

        raise GitError("Could not detect default branch. Neither 'main' nor 'master' exists.")

    # =========================================================================
    # Remote Operations
    # =========================================================================

    def get_remote_url(self, remote: str = "origin") -> str:
        """Get the URL of a remote.

        Args:
            remote: Remote name. Defaults to 'origin'.

        Returns:
            The remote URL.

        Raises:
            GitError: If remote doesn't exist.
        """
        result = self._run(["remote", "get-url", remote])
        return result.stdout.strip()

    def parse_github_remote(self, remote: str = "origin") -> tuple[str, str]:
        """Parse owner and repo from a GitHub remote URL.

        Supports both HTTPS and SSH URL formats:
        - https://github.com/owner/repo.git
        - git@github.com:owner/repo.git

        Args:
            remote: Remote name. Defaults to 'origin'.

        Returns:
            Tuple of (owner, repo).

        Raises:
            GitError: If URL cannot be parsed as GitHub URL.
        """
        url = self.get_remote_url(remote)

        # Try HTTPS format
        https_match = re.match(r"https://github\.com/([^/]+)/([^/.]+)(?:\.git)?", url)
        if https_match:
            return https_match.group(1), https_match.group(2)

        # Try SSH format
        ssh_match = re.match(r"git@github\.com:([^/]+)/([^/.]+)(?:\.git)?", url)
        if ssh_match:
            return ssh_match.group(1), ssh_match.group(2)

        raise GitError(f"Could not parse GitHub remote URL: {url}")

    # =========================================================================
    # Commit Operations
    # =========================================================================

    def get_commits_since_tag(self, tag: str | None = None) -> list[Commit]:
        """Get all commits since the given tag.

        Args:
            tag: Tag to get commits since. If None, returns all commits.

        Returns:
            List of commits, newest first.
        """
        # Format: SHA, message, author name, author email, date
        fmt = _FIELD_SEP.join(["%H", "%B", "%an", "%ae", "%aI"]) + _RECORD_SEP

        range_spec = f"{tag}..HEAD" if tag else "HEAD"

        result = self._run(["log", f"--format={fmt}", range_spec])
        output = result.stdout.strip()

        if not output:
            return []

        commits = []
        for record in output.split(_RECORD_SEP):
            record_stripped = record.strip()
            if not record_stripped:
                continue

            parts = record_stripped.split(_FIELD_SEP)
            if len(parts) != 5:
                continue

            sha, message, author_name, author_email, date_str = parts
            commits.append(
                Commit(
                    sha=sha.strip(),
                    message=message.strip(),
                    author_name=author_name.strip(),
                    author_email=author_email.strip(),
                    date=datetime.fromisoformat(date_str.strip()),
                )
            )

        return commits

    def get_commit_count(self) -> int:
        """Get the total number of commits in the repository.

        Returns:
            Number of commits.
        """
        result = self._run(["rev-list", "--count", "HEAD"])
        return int(result.stdout.strip())

    # =========================================================================
    # Tag Operations
    # =========================================================================

    def get_latest_tag(self, pattern: str = "v*") -> str | None:
        """Get the latest tag matching the pattern.

        Tags are sorted by version (using --sort=-v:refname).

        Args:
            pattern: Glob pattern for tag names. Defaults to 'v*'.

        Returns:
            The latest tag name, or None if no tags match.
        """
        result = self._run(
            ["tag", "--list", pattern, "--sort=-v:refname"],
            check=False,
        )
        tags = result.stdout.strip().split("\n")
        return tags[0] if tags and tags[0] else None

    def get_all_tags(self, pattern: str = "v*") -> list[str]:
        """Get all tags matching the pattern.

        Args:
            pattern: Glob pattern for tag names.

        Returns:
            List of tag names, newest first.
        """
        result = self._run(
            ["tag", "--list", pattern, "--sort=-v:refname"],
            check=False,
        )
        tags = result.stdout.strip().split("\n")
        return [t for t in tags if t]

    def tag_exists(self, tag: str) -> bool:
        """Check if a tag exists.

        Args:
            tag: Tag name to check.

        Returns:
            True if the tag exists.
        """
        result = self._run(
            ["tag", "--list", tag],
            check=False,
        )
        return bool(result.stdout.strip())

    def create_tag(
        self,
        tag: str,
        message: str | None = None,
        *,
        force: bool = False,
    ) -> None:
        """Create a new tag.

        Args:
            tag: Tag name.
            message: Tag message (creates annotated tag if provided).
            force: Overwrite existing tag if True.

        Raises:
            TagExistsError: If tag exists and force=False.
        """
        if not force and self.tag_exists(tag):
            raise TagExistsError(tag)

        args = ["tag"]
        if force:
            args.append("--force")
        if message:
            args.extend(["--annotate", "--message", message])
        args.append(tag)

        self._run(args)

    def push_tag(self, tag: str, remote: str = "origin") -> None:
        """Push a tag to remote.

        Args:
            tag: Tag name to push.
            remote: Remote name. Defaults to 'origin'.
        """
        self._run(["push", remote, tag])

    # =========================================================================
    # Branch Operations
    # =========================================================================

    def branch_exists(self, branch: str) -> bool:
        """Check if a branch exists locally.

        Args:
            branch: Branch name.

        Returns:
            True if branch exists.
        """
        result = self._run(
            ["rev-parse", "--verify", f"refs/heads/{branch}"],
            check=False,
        )
        return result.returncode == 0

    def checkout(self, ref: str, *, create: bool = False) -> None:
        """Checkout a branch or ref.

        Args:
            ref: Branch name or ref to checkout.
            create: Create the branch if it doesn't exist.
        """
        args = ["checkout"]
        if create:
            args.append("-B")
        args.append(ref)
        self._run(args)

    def commit(
        self,
        message: str,
        files: Sequence[Path] | None = None,
        *,
        allow_empty: bool = False,
    ) -> str:
        """Create a commit.

        Args:
            message: Commit message.
            files: Specific files to stage and commit. If None, commits
                   all staged changes.
            allow_empty: Allow creating an empty commit.

        Returns:
            The SHA of the new commit.
        """
        if files:
            # Stage specific files
            self._run(["add", *[str(f) for f in files]])

        args = ["commit", "--message", message]
        if allow_empty:
            args.append("--allow-empty")

        self._run(args)

        # Get the commit SHA
        result = self._run(["rev-parse", "HEAD"])
        return result.stdout.strip()

    def push(
        self,
        remote: str = "origin",
        branch: str | None = None,
        *,
        force: bool = False,
        set_upstream: bool = False,
    ) -> None:
        """Push to remote.

        Args:
            remote: Remote name.
            branch: Branch to push. If None, pushes current branch.
            force: Force push.
            set_upstream: Set upstream tracking.
        """
        args = ["push"]
        if force:
            args.append("--force")
        if set_upstream:
            args.append("--set-upstream")
        args.append(remote)
        if branch:
            args.append(branch)
        self._run(args)

    # =========================================================================
    # Contributor Operations
    # =========================================================================

    def get_contributors_since_tag(
        self,
        tag: str | None = None,
        *,
        include_email: bool = False,
    ) -> list[str]:
        """Get unique contributors since the given tag.

        Args:
            tag: Tag to get contributors since. If None, returns all contributors.
            include_email: Include email addresses in the result.

        Returns:
            List of unique contributor names (or "Name <email>" if include_email),
            sorted alphabetically.
        """
        fmt = "%an <%ae>" if include_email else "%an"
        range_spec = f"{tag}..HEAD" if tag else "HEAD"

        result = self._run(
            [
                "log",
                f"--format={fmt}",
                range_spec,
            ]
        )

        contributors = set()
        for line in result.stdout.strip().split("\n"):
            if line.strip():
                contributors.add(line.strip())

        return sorted(contributors, key=str.lower)

    def get_contributor_github_usernames(
        self,
        tag: str | None = None,
    ) -> list[str]:
        """Get GitHub usernames from commit co-authors and trailers.

        Extracts usernames from:
        - Co-authored-by: Name <email@users.noreply.github.com>
        - Commit author emails matching @users.noreply.github.com

        Args:
            tag: Tag to get contributors since.

        Returns:
            List of unique GitHub usernames, sorted alphabetically.
        """
        range_spec = f"{tag}..HEAD" if tag else "HEAD"

        # Get both author emails and full commit messages
        result = self._run(
            [
                "log",
                "--format=%ae%n%b",
                range_spec,
            ]
        )

        usernames = set()
        content = result.stdout

        # Pattern for GitHub noreply emails: username@users.noreply.github.com
        # or 12345678+username@users.noreply.github.com
        noreply_pattern = re.compile(
            r"(?:\d+\+)?([a-zA-Z0-9](?:[a-zA-Z0-9-]*[a-zA-Z0-9])?)@users\.noreply\.github\.com"
        )

        for match in noreply_pattern.finditer(content):
            usernames.add(match.group(1))

        # Pattern for Co-authored-by with GitHub handle
        coauthor_pattern = re.compile(
            r"Co-authored-by:.*?([a-zA-Z0-9](?:[a-zA-Z0-9-]*[a-zA-Z0-9])?)@users\.noreply\.github\.com",
            re.IGNORECASE,
        )

        for match in coauthor_pattern.finditer(content):
            usernames.add(match.group(1))

        return sorted(usernames, key=str.lower)

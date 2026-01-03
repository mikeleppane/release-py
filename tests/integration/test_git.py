"""Integration tests for git operations."""

from __future__ import annotations

import subprocess
from typing import TYPE_CHECKING

import pytest

from release_py.exceptions import (
    DirtyRepositoryError,
    GitError,
    NotARepositoryError,
    TagExistsError,
)
from release_py.vcs.git import GitRepository

if TYPE_CHECKING:
    from pathlib import Path


class TestGitRepository:
    """Integration tests for GitRepository."""

    def test_init_valid_repo(self, temp_git_repo: Path):
        """Initialize with a valid git repository."""
        repo = GitRepository(temp_git_repo)
        assert repo.path == temp_git_repo

    def test_init_invalid_repo_raises(self, tmp_path: Path):
        """Initialize with non-repo raises NotARepositoryError."""
        with pytest.raises(NotARepositoryError):
            GitRepository(tmp_path)

    def test_is_dirty_clean_repo(self, temp_git_repo: Path):
        """Clean repository returns False for is_dirty()."""
        repo = GitRepository(temp_git_repo)
        assert not repo.is_dirty()

    def test_is_dirty_with_changes(self, temp_git_repo: Path):
        """Repository with changes returns True for is_dirty()."""
        repo = GitRepository(temp_git_repo)

        # Make an uncommitted change
        (temp_git_repo / "new_file.txt").write_text("content")

        assert repo.is_dirty()

    def test_ensure_clean_raises_when_dirty(self, temp_git_repo: Path):
        """ensure_clean() raises when repository is dirty."""
        repo = GitRepository(temp_git_repo)
        (temp_git_repo / "new_file.txt").write_text("content")

        with pytest.raises(DirtyRepositoryError):
            repo.ensure_clean()

    def test_get_current_branch(self, temp_git_repo: Path):
        """Get current branch name."""
        repo = GitRepository(temp_git_repo)
        # Default branch in new repos is typically main or master
        branch = repo.get_current_branch()
        assert branch in ("main", "master")


class TestGitCommits:
    """Integration tests for commit operations."""

    def test_get_commits_since_tag_no_tags(self, temp_git_repo_with_commits: Path):
        """Get all commits when no tags exist."""
        repo = GitRepository(temp_git_repo_with_commits)
        commits = repo.get_commits_since_tag(None)

        assert len(commits) > 0
        assert all(c.sha for c in commits)
        assert all(c.message for c in commits)

    def test_get_commits_since_tag(self, temp_git_repo_with_commits: Path):
        """Get commits since a specific tag."""
        repo = GitRepository(temp_git_repo_with_commits)

        # Create a tag
        repo.create_tag("v1.0.0", "Release v1.0.0")

        # Add another commit
        (temp_git_repo_with_commits / "another.txt").write_text("content")
        subprocess.run(
            ["git", "add", "."],
            cwd=temp_git_repo_with_commits,
            check=True,
            capture_output=True,
        )
        subprocess.run(
            ["git", "commit", "-m", "feat: another feature"],
            cwd=temp_git_repo_with_commits,
            check=True,
            capture_output=True,
        )

        commits = repo.get_commits_since_tag("v1.0.0")

        assert len(commits) == 1
        assert "another feature" in commits[0].message

    def test_commit_subject_and_body(self, temp_git_repo: Path):
        """Commit subject and body are parsed correctly."""
        repo = GitRepository(temp_git_repo)

        # Create commit with body
        (temp_git_repo / "test.txt").write_text("content")
        subprocess.run(
            ["git", "add", "."],
            cwd=temp_git_repo,
            check=True,
            capture_output=True,
        )
        subprocess.run(
            ["git", "commit", "-m", "feat: subject\n\nThis is the body."],
            cwd=temp_git_repo,
            check=True,
            capture_output=True,
        )

        commits = repo.get_commits_since_tag(None)
        latest = commits[0]

        assert latest.subject == "feat: subject"
        assert latest.body is not None
        assert "body" in latest.body


class TestGitTags:
    """Integration tests for tag operations."""

    def test_get_latest_tag_none(self, temp_git_repo: Path):
        """get_latest_tag() returns None when no tags exist."""
        repo = GitRepository(temp_git_repo)
        assert repo.get_latest_tag() is None

    def test_create_and_get_tag(self, temp_git_repo: Path):
        """Create and retrieve a tag."""
        repo = GitRepository(temp_git_repo)

        repo.create_tag("v1.0.0", "Release v1.0.0")

        assert repo.tag_exists("v1.0.0")
        assert repo.get_latest_tag() == "v1.0.0"

    def test_get_all_tags(self, temp_git_repo: Path):
        """Get all tags matching pattern."""
        repo = GitRepository(temp_git_repo)

        repo.create_tag("v1.0.0")
        repo.create_tag("v1.1.0")
        repo.create_tag("v2.0.0")

        tags = repo.get_all_tags("v*")

        assert len(tags) == 3
        # Should be sorted by version, newest first
        assert tags[0] == "v2.0.0"

    def test_create_duplicate_tag_raises(self, temp_git_repo: Path):
        """Creating duplicate tag raises TagExistsError."""
        repo = GitRepository(temp_git_repo)

        repo.create_tag("v1.0.0")

        with pytest.raises(TagExistsError):
            repo.create_tag("v1.0.0")

    def test_create_duplicate_tag_with_force(self, temp_git_repo: Path):
        """Creating duplicate tag with force succeeds."""
        repo = GitRepository(temp_git_repo)

        repo.create_tag("v1.0.0")
        repo.create_tag("v1.0.0", force=True)  # Should not raise


class TestGitBranches:
    """Integration tests for branch operations."""

    def test_branch_exists(self, temp_git_repo: Path):
        """Check if branch exists."""
        repo = GitRepository(temp_git_repo)
        current = repo.get_current_branch()

        assert repo.branch_exists(current)
        assert not repo.branch_exists("nonexistent-branch")

    def test_checkout_create_branch(self, temp_git_repo: Path):
        """Create and checkout a new branch."""
        repo = GitRepository(temp_git_repo)

        repo.checkout("feature-branch", create=True)

        assert repo.get_current_branch() == "feature-branch"
        assert repo.branch_exists("feature-branch")


class TestGitRemote:
    """Integration tests for remote operations."""

    def test_parse_github_https_url(self, temp_git_repo: Path):
        """Parse GitHub HTTPS remote URL."""
        repo = GitRepository(temp_git_repo)

        # Add remote
        subprocess.run(
            ["git", "remote", "add", "origin", "https://github.com/owner/repo.git"],
            cwd=temp_git_repo,
            check=True,
            capture_output=True,
        )

        owner, repo_name = repo.parse_github_remote()

        assert owner == "owner"
        assert repo_name == "repo"

    def test_parse_github_ssh_url(self, temp_git_repo: Path):
        """Parse GitHub SSH remote URL."""
        repo = GitRepository(temp_git_repo)

        subprocess.run(
            ["git", "remote", "add", "origin", "git@github.com:owner/repo.git"],
            cwd=temp_git_repo,
            check=True,
            capture_output=True,
        )

        owner, repo_name = repo.parse_github_remote()

        assert owner == "owner"
        assert repo_name == "repo"

    def test_parse_non_github_raises(self, temp_git_repo: Path):
        """Non-GitHub URL raises GitError."""
        repo = GitRepository(temp_git_repo)

        subprocess.run(
            ["git", "remote", "add", "origin", "https://gitlab.com/owner/repo.git"],
            cwd=temp_git_repo,
            check=True,
            capture_output=True,
        )

        with pytest.raises(GitError):
            repo.parse_github_remote()

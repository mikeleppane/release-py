"""Unit tests for changelog generation."""

from __future__ import annotations

import subprocess
from datetime import datetime
from typing import TYPE_CHECKING
from unittest.mock import MagicMock, patch

import pytest

from release_py.config.models import ReleasePyConfig
from release_py.core.changelog import (
    generate_changelog,
    generate_fallback_changelog,
)
from release_py.core.version import Version
from release_py.exceptions import ChangelogError, GitCliffError
from release_py.vcs.git import Commit, GitRepository

if TYPE_CHECKING:
    from pathlib import Path


@pytest.fixture
def mock_repo(tmp_path: Path) -> MagicMock:
    """Create a mock GitRepository."""
    repo = MagicMock(spec=GitRepository)
    repo.path = tmp_path
    return repo


@pytest.fixture
def sample_commits() -> list[Commit]:
    """Sample commits for testing."""
    now = datetime.now()
    return [
        Commit(
            sha="abc1234",
            message="feat: add new feature",
            author_name="Test",
            author_email="test@test.com",
            date=now,
        ),
        Commit(
            sha="def5678",
            message="fix(api): resolve bug",
            author_name="Test",
            author_email="test@test.com",
            date=now,
        ),
        Commit(
            sha="ghi9012",
            message="feat!: breaking change",
            author_name="Test",
            author_email="test@test.com",
            date=now,
        ),
        Commit(
            sha="jkl3456",
            message="docs: update readme",
            author_name="Test",
            author_email="test@test.com",
            date=now,
        ),
    ]


class TestGenerateChangelog:
    """Tests for generate_changelog with git-cliff."""

    def test_generate_changelog_success(self, mock_repo: MagicMock, tmp_path: Path):
        """Generate changelog via git-cliff."""
        version = Version(1, 0, 0)
        config = ReleasePyConfig()

        # Create pyproject.toml
        (tmp_path / "pyproject.toml").write_text("[project]\nname = 'test'\n")

        with patch("subprocess.run") as mock_run:
            mock_run.return_value = MagicMock(
                stdout="## [1.0.0] - 2024-01-01\n\n### Features\n\n- New feature",
                returncode=0,
            )

            result = generate_changelog(
                repo=mock_repo,
                version=version,
                config=config,
            )

            assert "1.0.0" in result
            assert "Features" in result
            mock_run.assert_called_once()

    def test_generate_changelog_git_cliff_not_found(self, mock_repo: MagicMock):
        """Raise ChangelogError when git-cliff not found."""
        version = Version(1, 0, 0)
        config = ReleasePyConfig()

        with patch("subprocess.run") as mock_run:
            mock_run.side_effect = FileNotFoundError("git-cliff not found")

            with pytest.raises(ChangelogError, match="git-cliff not found"):
                generate_changelog(
                    repo=mock_repo,
                    version=version,
                    config=config,
                )

    def test_generate_changelog_git_cliff_failure(self, mock_repo: MagicMock, tmp_path: Path):
        """Raise GitCliffError when git-cliff fails."""
        version = Version(1, 0, 0)
        config = ReleasePyConfig()

        (tmp_path / "pyproject.toml").write_text("[project]\nname = 'test'\n")

        with patch("subprocess.run") as mock_run:
            mock_run.side_effect = subprocess.CalledProcessError(
                1, "git-cliff", stderr="Invalid config"
            )

            with pytest.raises(GitCliffError):
                generate_changelog(
                    repo=mock_repo,
                    version=version,
                    config=config,
                )

    def test_generate_changelog_unreleased_flag(self, mock_repo: MagicMock, tmp_path: Path):
        """Pass --unreleased flag when unreleased_only=True."""
        version = Version(1, 0, 0)
        config = ReleasePyConfig()

        (tmp_path / "pyproject.toml").write_text("[project]\nname = 'test'\n")

        with patch("subprocess.run") as mock_run:
            mock_run.return_value = MagicMock(stdout="changelog", returncode=0)

            generate_changelog(
                repo=mock_repo,
                version=version,
                config=config,
                unreleased_only=True,
            )

            call_args = mock_run.call_args[0][0]
            assert "--unreleased" in call_args


class TestGenerateFallbackChangelog:
    """Tests for fallback changelog generation without git-cliff."""

    def test_fallback_empty_commits(self, mock_repo: MagicMock):
        """Return empty string when no commits."""
        version = Version(1, 0, 0)
        config = ReleasePyConfig()

        mock_repo.get_latest_tag.return_value = None
        mock_repo.get_commits_since_tag.return_value = []

        result = generate_fallback_changelog(
            repo=mock_repo,
            version=version,
            config=config,
        )

        assert result == ""

    def test_fallback_with_features(self, mock_repo: MagicMock, sample_commits: list[Commit]):
        """Generate changelog with features section."""
        version = Version(1, 0, 0)
        config = ReleasePyConfig()

        mock_repo.get_latest_tag.return_value = None
        mock_repo.get_commits_since_tag.return_value = sample_commits

        result = generate_fallback_changelog(
            repo=mock_repo,
            version=version,
            config=config,
        )

        assert "## [1.0.0]" in result
        assert "### ✨ Features" in result
        assert "add new feature" in result

    def test_fallback_with_fixes(self, mock_repo: MagicMock, sample_commits: list[Commit]):
        """Generate changelog with bug fixes section."""
        version = Version(1, 0, 0)
        config = ReleasePyConfig()

        mock_repo.get_latest_tag.return_value = None
        mock_repo.get_commits_since_tag.return_value = sample_commits

        result = generate_fallback_changelog(
            repo=mock_repo,
            version=version,
            config=config,
        )

        assert "### 🐛 Bug Fixes" in result
        assert "**api:** resolve bug" in result

    def test_fallback_with_breaking_changes(
        self, mock_repo: MagicMock, sample_commits: list[Commit]
    ):
        """Generate changelog with breaking changes section."""
        version = Version(1, 0, 0)
        config = ReleasePyConfig()

        mock_repo.get_latest_tag.return_value = None
        mock_repo.get_commits_since_tag.return_value = sample_commits

        result = generate_fallback_changelog(
            repo=mock_repo,
            version=version,
            config=config,
        )

        assert "### ⚠️ Breaking Changes" in result
        assert "breaking change" in result

    def test_fallback_with_docs(self, mock_repo: MagicMock, sample_commits: list[Commit]):
        """Generate changelog with documentation section."""
        version = Version(1, 0, 0)
        config = ReleasePyConfig()

        mock_repo.get_latest_tag.return_value = None
        mock_repo.get_commits_since_tag.return_value = sample_commits

        result = generate_fallback_changelog(
            repo=mock_repo,
            version=version,
            config=config,
        )

        assert "### 📚 Documentation" in result
        assert "update readme" in result

    def test_fallback_date_format(self, mock_repo: MagicMock):
        """Changelog includes date in correct format."""
        version = Version(1, 0, 0)
        config = ReleasePyConfig()
        now = datetime.now()

        mock_repo.get_latest_tag.return_value = None
        mock_repo.get_commits_since_tag.return_value = [
            Commit(
                sha="abc",
                message="feat: test",
                author_name="Test",
                author_email="test@test.com",
                date=now,
            )
        ]

        result = generate_fallback_changelog(
            repo=mock_repo,
            version=version,
            config=config,
        )

        # Check date format is YYYY-MM-DD
        import re

        assert re.search(r"\d{4}-\d{2}-\d{2}", result)

    def test_fallback_uses_tag_prefix(self, mock_repo: MagicMock):
        """Use configured tag prefix for looking up latest tag."""
        version = Version(1, 0, 0)
        config = ReleasePyConfig()

        mock_repo.get_latest_tag.return_value = "v0.9.0"
        mock_repo.get_commits_since_tag.return_value = []

        generate_fallback_changelog(
            repo=mock_repo,
            version=version,
            config=config,
        )

        mock_repo.get_latest_tag.assert_called_once_with("v*")

    def test_fallback_all_commit_types(self, mock_repo: MagicMock):
        """Handle all conventional commit types."""
        version = Version(1, 0, 0)
        config = ReleasePyConfig()
        now = datetime.now()

        all_types = [
            Commit(
                sha="1", message="feat: feature", author_name="T", author_email="t@t.com", date=now
            ),
            Commit(sha="2", message="fix: fix", author_name="T", author_email="t@t.com", date=now),
            Commit(
                sha="3",
                message="perf: performance",
                author_name="T",
                author_email="t@t.com",
                date=now,
            ),
            Commit(
                sha="4",
                message="docs: documentation",
                author_name="T",
                author_email="t@t.com",
                date=now,
            ),
            Commit(
                sha="5",
                message="refactor: refactor",
                author_name="T",
                author_email="t@t.com",
                date=now,
            ),
            Commit(
                sha="6", message="test: test", author_name="T", author_email="t@t.com", date=now
            ),
            Commit(
                sha="7", message="build: build", author_name="T", author_email="t@t.com", date=now
            ),
            Commit(sha="8", message="ci: ci", author_name="T", author_email="t@t.com", date=now),
            Commit(
                sha="9", message="style: style", author_name="T", author_email="t@t.com", date=now
            ),
            Commit(
                sha="10", message="chore: chore", author_name="T", author_email="t@t.com", date=now
            ),
        ]

        mock_repo.get_latest_tag.return_value = None
        mock_repo.get_commits_since_tag.return_value = all_types

        result = generate_fallback_changelog(
            repo=mock_repo,
            version=version,
            config=config,
        )

        # Check all sections are present
        assert "### ✨ Features" in result
        assert "### 🐛 Bug Fixes" in result
        assert "### ⚡ Performance" in result
        assert "### 📚 Documentation" in result
        assert "### ♻️ Refactoring" in result
        assert "### 🧪 Tests" in result
        assert "### 📦 Build" in result
        assert "### 🔧 CI" in result
        assert "### 💄 Style" in result
        assert "### 🔨 Chores" in result

    def test_fallback_breaking_not_duplicated(self, mock_repo: MagicMock):
        """Breaking changes are not duplicated in their type section."""
        version = Version(1, 0, 0)
        config = ReleasePyConfig()
        now = datetime.now()

        commits = [
            Commit(
                sha="abc",
                message="feat!: breaking feature",
                author_name="T",
                author_email="t@t.com",
                date=now,
            ),
        ]

        mock_repo.get_latest_tag.return_value = None
        mock_repo.get_commits_since_tag.return_value = commits

        result = generate_fallback_changelog(
            repo=mock_repo,
            version=version,
            config=config,
        )

        # Should appear in breaking changes
        assert "### ⚠️ Breaking Changes" in result
        # Count occurrences - should only appear once
        assert result.count("breaking feature") == 1

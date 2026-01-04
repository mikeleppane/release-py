"""Unit tests for changelog generation."""

from __future__ import annotations

import subprocess
from typing import TYPE_CHECKING
from unittest.mock import MagicMock, patch

import pytest

from release_py.config.models import ReleasePyConfig
from release_py.core.changelog import (
    generate_changelog,
    get_bump_from_git_cliff,
)
from release_py.core.version import BumpType, Version
from release_py.exceptions import ChangelogError, GitCliffError
from release_py.vcs.git import GitRepository

if TYPE_CHECKING:
    from pathlib import Path


@pytest.fixture
def mock_repo(tmp_path: Path) -> MagicMock:
    """Create a mock GitRepository."""
    repo = MagicMock(spec=GitRepository)
    repo.path = tmp_path
    return repo


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

    def test_generate_changelog_with_github_repo(self, mock_repo: MagicMock, tmp_path: Path):
        """Pass --github-repo flag when github_repo is provided."""
        version = Version(1, 0, 0)
        config = ReleasePyConfig()

        (tmp_path / "pyproject.toml").write_text("[project]\nname = 'test'\n")

        with patch("subprocess.run") as mock_run:
            mock_run.return_value = MagicMock(stdout="changelog with PRs", returncode=0)

            generate_changelog(
                repo=mock_repo,
                version=version,
                config=config,
                github_repo="owner/repo",
            )

            call_args = mock_run.call_args[0][0]
            assert "--github-repo" in call_args
            assert "owner/repo" in call_args

    def test_generate_changelog_without_github_repo(self, mock_repo: MagicMock, tmp_path: Path):
        """Omit --github-repo flag when github_repo is None."""
        version = Version(1, 0, 0)
        config = ReleasePyConfig()

        (tmp_path / "pyproject.toml").write_text("[project]\nname = 'test'\n")

        with patch("subprocess.run") as mock_run:
            mock_run.return_value = MagicMock(stdout="changelog", returncode=0)

            generate_changelog(
                repo=mock_repo,
                version=version,
                config=config,
                github_repo=None,
            )

            call_args = mock_run.call_args[0][0]
            assert "--github-repo" not in call_args


class TestGetBumpFromGitCliff:
    """Tests for get_bump_from_git_cliff."""

    def test_bump_major(self, mock_repo: MagicMock, tmp_path: Path):
        """Detect major bump from git-cliff output."""
        config = ReleasePyConfig()
        (tmp_path / "pyproject.toml").write_text("[project]\nname = 'test'\n")

        with patch("subprocess.run") as mock_run:
            mock_run.return_value = MagicMock(
                stdout="",
                stderr="Bumping major version",
                returncode=0,
            )

            result = get_bump_from_git_cliff(mock_repo, config)
            assert result == BumpType.MAJOR

    def test_bump_minor(self, mock_repo: MagicMock, tmp_path: Path):
        """Detect minor bump from git-cliff output."""
        config = ReleasePyConfig()
        (tmp_path / "pyproject.toml").write_text("[project]\nname = 'test'\n")

        with patch("subprocess.run") as mock_run:
            mock_run.return_value = MagicMock(
                stdout="Detected minor bump",
                stderr="",
                returncode=0,
            )

            result = get_bump_from_git_cliff(mock_repo, config)
            assert result == BumpType.MINOR

    def test_bump_patch(self, mock_repo: MagicMock, tmp_path: Path):
        """Detect patch bump from git-cliff output."""
        config = ReleasePyConfig()
        (tmp_path / "pyproject.toml").write_text("[project]\nname = 'test'\n")

        with patch("subprocess.run") as mock_run:
            mock_run.return_value = MagicMock(
                stdout="patch version",
                stderr="",
                returncode=0,
            )

            result = get_bump_from_git_cliff(mock_repo, config)
            assert result == BumpType.PATCH

    def test_bump_none_no_output(self, mock_repo: MagicMock, tmp_path: Path):
        """Return NONE when no bump info in output."""
        config = ReleasePyConfig()
        (tmp_path / "pyproject.toml").write_text("[project]\nname = 'test'\n")

        with patch("subprocess.run") as mock_run:
            mock_run.return_value = MagicMock(
                stdout="",
                stderr="",
                returncode=0,
            )

            result = get_bump_from_git_cliff(mock_repo, config)
            assert result == BumpType.NONE

    def test_bump_none_no_commits(self, mock_repo: MagicMock, tmp_path: Path):
        """Return NONE when git-cliff reports no commits."""
        config = ReleasePyConfig()
        (tmp_path / "pyproject.toml").write_text("[project]\nname = 'test'\n")

        with patch("subprocess.run") as mock_run:
            mock_run.side_effect = subprocess.CalledProcessError(
                1, "git-cliff", stderr="no commits to process"
            )

            result = get_bump_from_git_cliff(mock_repo, config)
            assert result == BumpType.NONE

    def test_bump_git_cliff_error(self, mock_repo: MagicMock, tmp_path: Path):
        """Raise GitCliffError on other git-cliff failures."""
        config = ReleasePyConfig()
        (tmp_path / "pyproject.toml").write_text("[project]\nname = 'test'\n")

        with patch("subprocess.run") as mock_run:
            mock_run.side_effect = subprocess.CalledProcessError(
                1, "git-cliff", stderr="Invalid configuration"
            )

            with pytest.raises(GitCliffError):
                get_bump_from_git_cliff(mock_repo, config)

    def test_bump_git_cliff_not_found(self, mock_repo: MagicMock):
        """Raise ChangelogError when git-cliff not found."""
        config = ReleasePyConfig()

        with patch("subprocess.run") as mock_run:
            mock_run.side_effect = FileNotFoundError("git-cliff not found")

            with pytest.raises(ChangelogError, match="git-cliff not found"):
                get_bump_from_git_cliff(mock_repo, config)

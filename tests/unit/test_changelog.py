"""Unit tests for changelog generation."""

from __future__ import annotations

import subprocess
from datetime import datetime
from typing import TYPE_CHECKING
from unittest.mock import MagicMock, patch

import pytest

from release_py.config.models import ChangelogConfig, ReleasePyConfig
from release_py.core.changelog import (
    format_commit_entry,
    generate_changelog,
    generate_cliff_config,
    generate_native_changelog,
    get_bump_from_git_cliff,
    is_git_cliff_available,
)
from release_py.core.commits import ParsedCommit
from release_py.core.version import BumpType, Version
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


# =============================================================================
# Native Changelog Tests
# =============================================================================


@pytest.fixture
def sample_commit() -> Commit:
    """Create a sample commit for testing."""
    return Commit(
        sha="abc1234567890",
        message="feat: add new feature",
        author_name="Test Author",
        author_email="test@example.com",
        date=datetime.now(),
    )


@pytest.fixture
def sample_parsed_commit(sample_commit: Commit) -> ParsedCommit:
    """Create a sample parsed commit."""
    return ParsedCommit(
        commit=sample_commit,
        commit_type="feat",
        scope=None,
        description="add new feature",
        is_breaking=False,
        is_conventional=True,
    )


class TestIsGitCliffAvailable:
    """Tests for is_git_cliff_available()."""

    def test_git_cliff_available(self):
        """Return True when git-cliff is found."""
        with patch("shutil.which") as mock_which:
            mock_which.return_value = "/usr/bin/git-cliff"
            assert is_git_cliff_available() is True

    def test_git_cliff_not_available(self):
        """Return False when git-cliff is not found."""
        with patch("shutil.which") as mock_which:
            mock_which.return_value = None
            assert is_git_cliff_available() is False


class TestFormatCommitEntry:
    """Tests for format_commit_entry()."""

    def test_format_simple_commit(self, sample_parsed_commit: ParsedCommit):
        """Format a simple commit without options."""
        config = ChangelogConfig()
        result = format_commit_entry(sample_parsed_commit, config)

        assert result == "add new feature"

    def test_format_with_scope(self, sample_commit: Commit):
        """Format commit with scope."""
        pc = ParsedCommit(
            commit=sample_commit,
            commit_type="fix",
            scope="api",
            description="handle null response",
            is_breaking=False,
            is_conventional=True,
        )
        config = ChangelogConfig()
        result = format_commit_entry(pc, config)

        assert result == "**api:** handle null response"

    def test_format_breaking_change(self, sample_commit: Commit):
        """Format breaking change commit."""
        pc = ParsedCommit(
            commit=sample_commit,
            commit_type="feat",
            scope=None,
            description="redesign API",
            is_breaking=True,
            is_conventional=True,
        )
        config = ChangelogConfig()
        result = format_commit_entry(pc, config)

        assert result == "**BREAKING:** redesign API"

    def test_format_with_author(self, sample_parsed_commit: ParsedCommit):
        """Format commit with author name."""
        config = ChangelogConfig(show_authors=True)
        result = format_commit_entry(sample_parsed_commit, config)

        assert "Test Author" in result
        assert "add new feature" in result

    def test_format_with_hash(self, sample_parsed_commit: ParsedCommit):
        """Format commit with short hash."""
        config = ChangelogConfig(show_commit_hash=True)
        result = format_commit_entry(sample_parsed_commit, config)

        assert "abc1234" in result
        assert "add new feature" in result

    def test_format_with_custom_template(self, sample_parsed_commit: ParsedCommit):
        """Format commit with custom template."""
        config = ChangelogConfig(commit_template="{description} by @{author} ({hash})")
        result = format_commit_entry(sample_parsed_commit, config)

        assert result == "add new feature by @Test Author (abc1234)"

    def test_format_template_with_all_variables(self, sample_commit: Commit):
        """Custom template with all available variables."""
        pc = ParsedCommit(
            commit=sample_commit,
            commit_type="feat",
            scope="core",
            description="new feature",
            is_breaking=False,
            is_conventional=True,
        )
        config = ChangelogConfig(commit_template="[{type}] {scope}: {description} - {author}")
        result = format_commit_entry(pc, config)

        assert result == "[feat] core: new feature - Test Author"

    def test_format_template_empty_scope(self, sample_parsed_commit: ParsedCommit):
        """Template with empty scope renders empty string."""
        config = ChangelogConfig(commit_template="{scope}{description}")
        result = format_commit_entry(sample_parsed_commit, config)

        assert result == "add new feature"


class TestGenerateNativeChangelog:
    """Tests for generate_native_changelog()."""

    def test_generate_empty_commits(self):
        """Return empty string for no commits."""
        config = ChangelogConfig()
        version = Version(1, 0, 0)

        result = generate_native_changelog([], version, config)

        assert result == ""

    def test_generate_single_commit(self, sample_commit: Commit):
        """Generate changelog for single commit."""
        pc = ParsedCommit(
            commit=sample_commit,
            commit_type="feat",
            scope=None,
            description="add new feature",
            is_breaking=False,
            is_conventional=True,
        )
        config = ChangelogConfig()
        version = Version(1, 0, 0)

        result = generate_native_changelog([pc], version, config)

        assert "## [1.0.0]" in result
        assert "### ✨ Features" in result
        assert "- add new feature" in result

    def test_generate_multiple_types(self, sample_commit: Commit):
        """Generate changelog with multiple commit types."""
        commits = [
            ParsedCommit(
                commit=sample_commit,
                commit_type="feat",
                scope=None,
                description="add feature",
                is_breaking=False,
                is_conventional=True,
            ),
            ParsedCommit(
                commit=sample_commit,
                commit_type="fix",
                scope=None,
                description="fix bug",
                is_breaking=False,
                is_conventional=True,
            ),
        ]
        config = ChangelogConfig()
        version = Version(1, 0, 0)

        result = generate_native_changelog(commits, version, config)

        assert "### ✨ Features" in result
        assert "- add feature" in result
        assert "### 🐛 Bug Fixes" in result
        assert "- fix bug" in result

    def test_generate_breaking_changes_first(self, sample_commit: Commit):
        """Breaking changes appear at the top."""
        commits = [
            ParsedCommit(
                commit=sample_commit,
                commit_type="feat",
                scope=None,
                description="add feature",
                is_breaking=False,
                is_conventional=True,
            ),
            ParsedCommit(
                commit=sample_commit,
                commit_type="feat",
                scope=None,
                description="breaking change",
                is_breaking=True,
                is_conventional=True,
            ),
        ]
        config = ChangelogConfig()
        version = Version(2, 0, 0)

        result = generate_native_changelog(commits, version, config)

        # Breaking changes section should come before features
        breaking_pos = result.find("⚠️ Breaking Changes")
        features_pos = result.find("✨ Features")
        assert breaking_pos < features_pos

    def test_generate_with_custom_headers(self, sample_commit: Commit):
        """Use custom section headers."""
        pc = ParsedCommit(
            commit=sample_commit,
            commit_type="feat",
            scope=None,
            description="new feature",
            is_breaking=False,
            is_conventional=True,
        )
        config = ChangelogConfig(section_headers={"feat": "🚀 New Features"})
        version = Version(1, 0, 0)

        result = generate_native_changelog([pc], version, config)

        assert "### 🚀 New Features" in result

    def test_generate_with_custom_changelog_group(self, sample_commit: Commit):
        """Use custom changelog group from parser."""
        pc = ParsedCommit(
            commit=sample_commit,
            commit_type="feat",
            scope=None,
            description="new feature",
            is_breaking=False,
            is_conventional=True,
            changelog_group="✨ Custom Features",
        )
        config = ChangelogConfig()
        version = Version(1, 0, 0)

        result = generate_native_changelog([pc], version, config)

        # Custom group name should be used as header
        assert "### ✨ Custom Features" in result

    def test_generate_version_in_header(self, sample_commit: Commit):
        """Version appears in changelog header."""
        pc = ParsedCommit(
            commit=sample_commit,
            commit_type="feat",
            scope=None,
            description="feature",
            is_breaking=False,
            is_conventional=True,
        )
        config = ChangelogConfig()
        version = Version(2, 1, 3)

        result = generate_native_changelog([pc], version, config)

        assert "## [2.1.3]" in result


class TestGenerateCliffConfig:
    """Tests for generate_cliff_config()."""

    def test_generate_default_config(self):
        """Generate cliff config with defaults."""
        config = ReleasePyConfig()
        result = generate_cliff_config(config)

        assert "[changelog]" in result
        assert "[git]" in result
        assert "conventional_commits = true" in result
        assert "commit_parsers = [" in result

    def test_generate_config_has_standard_sections(self):
        """Generated config includes standard commit type mappings."""
        config = ReleasePyConfig()
        result = generate_cliff_config(config)

        assert "^feat" in result
        assert "^fix" in result
        assert "^perf" in result

    def test_generate_config_uses_section_headers(self):
        """Generated config uses custom section headers."""
        config = ReleasePyConfig(
            changelog=ChangelogConfig(section_headers={"feat": "🚀 New Features"})
        )
        result = generate_cliff_config(config)

        assert "🚀 New Features" in result

    def test_generate_config_includes_custom_parsers(self):
        """Generated config includes custom commit parsers."""
        from release_py.config.models import CommitParser, CommitsConfig

        config = ReleasePyConfig(
            commits=CommitsConfig(
                commit_parsers=[
                    CommitParser(
                        pattern=r"^:sparkles:",
                        type="feat",
                        group="✨ Features",
                    ),
                ]
            )
        )
        result = generate_cliff_config(config)

        assert ":sparkles:" in result
        assert "✨ Features" in result

    def test_generate_config_has_tag_pattern(self):
        """Generated config includes tag pattern."""
        config = ReleasePyConfig()
        result = generate_cliff_config(config)

        assert 'tag_pattern = "v[0-9]*"' in result

    def test_generate_config_custom_tag_prefix(self):
        """Generated config uses custom tag prefix."""
        from release_py.config.models import VersionConfig

        config = ReleasePyConfig(version=VersionConfig(tag_prefix="release-"))
        result = generate_cliff_config(config)

        assert 'tag_pattern = "release-[0-9]*"' in result

    def test_generate_config_has_skip_patterns(self):
        """Generated config skips merge and WIP commits."""
        config = ReleasePyConfig()
        result = generate_cliff_config(config)

        assert "^Merge" in result
        assert "^WIP" in result
        assert "skip = true" in result

    def test_generate_config_custom_body_template(self):
        """Generated config uses custom body template."""
        config = ReleasePyConfig(
            changelog=ChangelogConfig(
                cliff_body_template="{% for commit in commits %}{{ commit.message }}{% endfor %}"
            )
        )
        result = generate_cliff_config(config)

        assert "{% for commit in commits %}" in result

    def test_generate_config_invalid_format_raises(self):
        """Unsupported output format raises ValueError."""
        config = ReleasePyConfig()

        with pytest.raises(ValueError, match="Unsupported output format"):
            generate_cliff_config(config, output_format="yaml")

    def test_generate_config_escapes_special_chars(self):
        """Special characters in patterns are escaped."""
        from release_py.config.models import CommitParser, CommitsConfig

        config = ReleasePyConfig(
            commits=CommitsConfig(
                commit_parsers=[
                    CommitParser(
                        pattern=r'^"test"',
                        type="test",
                        group='Test "Group"',
                    ),
                ]
            )
        )
        result = generate_cliff_config(config)

        # Quotes should be escaped
        assert r"\"" in result

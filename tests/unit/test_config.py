"""Tests for configuration loading and validation."""

from __future__ import annotations

from pathlib import Path

import pytest

from release_py.config.loader import (
    extract_release_py_config,
    find_pyproject_toml,
    get_project_name,
    get_project_version,
    load_config,
    load_pyproject_toml,
)
from release_py.config.models import (
    ChangelogConfig,
    CommitsConfig,
    GitHubConfig,
    HooksConfig,
    PackagesConfig,
    PublishConfig,
    ReleasePyConfig,
    VersionConfig,
)
from release_py.exceptions import ConfigNotFoundError, ConfigValidationError


class TestReleasePyConfig:
    """Tests for ReleasePyConfig model."""

    def test_default_config(self):
        """Default configuration has sensible values."""
        config = ReleasePyConfig()

        assert config.default_branch == "main"
        assert config.allow_dirty is False
        assert config.tag_prefix == "v"
        assert config.changelog_path == Path("CHANGELOG.md")

    def test_nested_defaults(self):
        """Nested configurations have defaults."""
        config = ReleasePyConfig()

        assert config.commits.types_minor == ["feat"]
        assert config.commits.types_patch == ["fix", "perf"]
        assert config.changelog.enabled is True
        assert config.version.initial_version == "0.1.0"
        assert config.github.release_pr_branch == "release-py/release"
        assert config.publish.tool == "uv"

    def test_effective_tag_prefix(self):
        """effective_tag_prefix returns correct value."""
        config = ReleasePyConfig()
        assert config.effective_tag_prefix == "v"

        config = ReleasePyConfig(version=VersionConfig(tag_prefix="release-"))
        assert config.effective_tag_prefix == "release-"

    def test_is_monorepo(self):
        """is_monorepo detects monorepo configuration."""
        config = ReleasePyConfig()
        assert not config.is_monorepo

        config = ReleasePyConfig(packages=PackagesConfig(paths=["packages/core"]))
        assert config.is_monorepo


class TestCommitsConfig:
    """Tests for CommitsConfig model."""

    def test_defaults(self):
        """Default commit type mappings."""
        config = CommitsConfig()

        assert "feat" in config.types_minor
        assert "fix" in config.types_patch
        assert "perf" in config.types_patch

    def test_custom_types(self):
        """Custom commit type mappings."""
        config = CommitsConfig(
            types_major=["breaking"],
            types_minor=["feature", "feat"],
            types_patch=["bugfix", "fix"],
        )

        assert "breaking" in config.types_major
        assert "feature" in config.types_minor


class TestChangelogConfig:
    """Tests for ChangelogConfig model."""

    def test_defaults(self):
        """Default changelog configuration."""
        config = ChangelogConfig()

        assert config.enabled is True
        assert config.path == Path("CHANGELOG.md")


class TestVersionConfig:
    """Tests for VersionConfig model."""

    def test_defaults(self):
        """Default version configuration."""
        config = VersionConfig()

        assert config.initial_version == "0.1.0"
        assert config.tag_prefix == "v"
        assert config.pre_release is None


class TestGitHubConfig:
    """Tests for GitHubConfig model."""

    def test_defaults(self):
        """Default GitHub configuration."""
        config = GitHubConfig()

        assert config.owner is None
        assert config.repo is None
        assert config.release_pr_branch == "release-py/release"
        assert config.release_pr_labels == ["release"]


class TestPublishConfig:
    """Tests for PublishConfig model."""

    def test_defaults(self):
        """Default publish configuration."""
        config = PublishConfig()

        assert config.enabled is True
        assert config.tool == "uv"
        assert config.trusted_publishing is True


class TestPackagesConfig:
    """Tests for PackagesConfig model."""

    def test_defaults(self):
        """Default packages configuration."""
        config = PackagesConfig()

        assert config.paths == []
        assert config.independent is True


class TestHooksConfig:
    """Tests for HooksConfig model."""

    def test_defaults(self):
        """Default hooks configuration (empty lists)."""
        config = HooksConfig()

        assert config.pre_bump == []
        assert config.post_bump == []
        assert config.pre_release == []
        assert config.post_release == []

    def test_custom_hooks(self):
        """Custom hooks can be configured."""
        config = HooksConfig(
            pre_bump=["npm run lint"],
            post_bump=["npm run build"],
            pre_release=["pytest"],
            post_release=["./scripts/notify.sh"],
        )

        assert config.pre_bump == ["npm run lint"]
        assert config.post_bump == ["npm run build"]
        assert config.pre_release == ["pytest"]
        assert config.post_release == ["./scripts/notify.sh"]

    def test_multiple_hooks_per_phase(self):
        """Multiple hooks can be configured per phase."""
        config = HooksConfig(
            pre_release=["pytest", "ruff check", "mypy ."],
        )

        assert len(config.pre_release) == 3


class TestCommitsConfigSkipPatterns:
    """Tests for CommitsConfig skip_release_patterns."""

    def test_default_skip_patterns(self):
        """Default skip release patterns are configured."""
        config = CommitsConfig()

        assert "[skip release]" in config.skip_release_patterns
        assert "[release skip]" in config.skip_release_patterns
        assert "[no release]" in config.skip_release_patterns

    def test_custom_skip_patterns(self):
        """Custom skip patterns can be configured."""
        config = CommitsConfig(
            skip_release_patterns=["[skip ci]", "[wip]"],
        )

        assert config.skip_release_patterns == ["[skip ci]", "[wip]"]


class TestGitHubConfigApiUrl:
    """Tests for GitHubConfig api_url (GitHub Enterprise support)."""

    def test_default_api_url(self):
        """Default API URL is github.com."""
        config = GitHubConfig()

        assert config.api_url == "https://api.github.com"

    def test_github_enterprise_url(self):
        """GitHub Enterprise URL can be configured."""
        config = GitHubConfig(
            api_url="https://github.mycompany.com/api/v3",
        )

        assert config.api_url == "https://github.mycompany.com/api/v3"


class TestLoadPyprojectToml:
    """Tests for load_pyproject_toml()."""

    def test_load_valid_toml(self, temp_git_repo_with_pyproject: Path):
        """Load a valid pyproject.toml."""
        pyproject_path = temp_git_repo_with_pyproject / "pyproject.toml"
        data = load_pyproject_toml(pyproject_path)

        assert "project" in data
        assert data["project"]["name"] == "test-project"

    def test_load_nonexistent_raises(self, tmp_path: Path):
        """Loading nonexistent file raises ConfigNotFoundError."""
        with pytest.raises(ConfigNotFoundError):
            load_pyproject_toml(tmp_path / "nonexistent.toml")


class TestFindPyprojectToml:
    """Tests for find_pyproject_toml()."""

    def test_find_in_current_dir(self, temp_git_repo_with_pyproject: Path):
        """Find pyproject.toml in current directory."""
        found = find_pyproject_toml(temp_git_repo_with_pyproject)
        assert found.name == "pyproject.toml"

    def test_find_in_parent_dir(self, temp_git_repo_with_pyproject: Path):
        """Find pyproject.toml in parent directory."""
        subdir = temp_git_repo_with_pyproject / "src" / "package"
        subdir.mkdir(parents=True)

        found = find_pyproject_toml(subdir)
        assert found.name == "pyproject.toml"

    def test_not_found_raises(self, tmp_path: Path):
        """Raises ConfigNotFoundError when not found."""
        with pytest.raises(ConfigNotFoundError):
            find_pyproject_toml(tmp_path)


class TestExtractReleasePyConfig:
    """Tests for extract_release_py_config()."""

    def test_extract_existing_config(self):
        """Extract existing release-py config."""
        pyproject = {
            "tool": {
                "release-py": {
                    "default_branch": "develop",
                }
            }
        }
        config = extract_release_py_config(pyproject)

        assert config["default_branch"] == "develop"

    def test_extract_missing_config(self):
        """Extract returns empty dict when config missing."""
        pyproject = {"project": {"name": "test"}}
        config = extract_release_py_config(pyproject)

        assert config == {}


class TestLoadConfig:
    """Tests for load_config()."""

    def test_load_with_config(self, temp_git_repo_with_pyproject: Path):
        """Load configuration from pyproject.toml."""
        config = load_config(temp_git_repo_with_pyproject)

        assert isinstance(config, ReleasePyConfig)
        assert config.default_branch == "main"

    def test_load_defaults_when_no_config(self, tmp_path: Path):
        """Load defaults when no [tool.release-py] section."""
        pyproject = tmp_path / "pyproject.toml"
        pyproject.write_text(
            """\
[project]
name = "test"
version = "1.0.0"
"""
        )

        config = load_config(tmp_path)
        assert config.default_branch == "main"


class TestGetProjectInfo:
    """Tests for get_project_name() and get_project_version()."""

    def test_get_project_name(self, temp_git_repo_with_pyproject: Path):
        """Get project name from pyproject.toml."""
        name = get_project_name(temp_git_repo_with_pyproject)
        assert name == "test-project"

    def test_get_project_version(self, temp_git_repo_with_pyproject: Path):
        """Get project version from pyproject.toml."""
        version = get_project_version(temp_git_repo_with_pyproject)
        assert version == "1.0.0"

    def test_missing_name_raises(self, tmp_path: Path):
        """Missing project name raises ConfigValidationError."""
        pyproject = tmp_path / "pyproject.toml"
        pyproject.write_text("[project]\nversion = '1.0.0'\n")

        with pytest.raises(ConfigValidationError):
            get_project_name(tmp_path)

    def test_missing_version_raises(self, tmp_path: Path):
        """Missing project version raises ConfigValidationError."""
        pyproject = tmp_path / "pyproject.toml"
        pyproject.write_text("[project]\nname = 'test'\n")

        with pytest.raises(ConfigValidationError):
            get_project_version(tmp_path)

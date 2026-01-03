"""Integration tests for project detection and manipulation."""

from __future__ import annotations

from typing import TYPE_CHECKING

import pytest

from release_py.exceptions import ProjectNotFoundError, VersionNotFoundError
from release_py.project.detector import detect_project, detect_workspace_packages
from release_py.project.pyproject import (
    get_pyproject_version,
    update_pyproject_version,
    update_version_file,
)

if TYPE_CHECKING:
    from pathlib import Path


class TestDetectProject:
    """Integration tests for project detection."""

    def test_detect_pyproject(self, temp_git_repo_with_pyproject: Path):
        """Detect project with pyproject.toml."""
        info = detect_project(temp_git_repo_with_pyproject)

        assert info.name == "test-project"
        assert info.version == "1.0.0"
        assert info.project_type == "pyproject"
        assert info.build_backend == "hatchling"

    def test_detect_poetry_project(self, tmp_path: Path):
        """Detect Poetry project."""
        pyproject = tmp_path / "pyproject.toml"
        pyproject.write_text(
            """\
[tool.poetry]
name = "poetry-project"
version = "2.0.0"
"""
        )

        info = detect_project(tmp_path)

        assert info.name == "poetry-project"
        assert info.version == "2.0.0"
        assert info.project_type == "poetry"

    def test_detect_no_project_raises(self, tmp_path: Path):
        """Raises ProjectNotFoundError when no project found."""
        with pytest.raises(ProjectNotFoundError):
            detect_project(tmp_path)


class TestDetectWorkspacePackages:
    """Integration tests for workspace/monorepo detection."""

    def test_detect_packages_dir(self, tmp_path: Path):
        """Detect packages in packages/ directory."""
        # Create package structure
        for pkg in ["core", "cli", "utils"]:
            pkg_dir = tmp_path / "packages" / pkg
            pkg_dir.mkdir(parents=True)
            (pkg_dir / "pyproject.toml").write_text(
                f"""\
[project]
name = "my-{pkg}"
version = "1.0.0"
"""
            )

        packages = detect_workspace_packages(tmp_path)

        assert len(packages) == 3
        assert any("core" in str(p) for p in packages)


class TestPyprojectVersion:
    """Integration tests for pyproject.toml version operations."""

    def test_get_version(self, temp_git_repo_with_pyproject: Path):
        """Get version from pyproject.toml."""
        version = get_pyproject_version(temp_git_repo_with_pyproject)
        assert version == "1.0.0"

    def test_update_version(self, temp_git_repo_with_pyproject: Path):
        """Update version in pyproject.toml."""
        update_pyproject_version(temp_git_repo_with_pyproject, "2.0.0")

        # Verify the update
        version = get_pyproject_version(temp_git_repo_with_pyproject)
        assert version == "2.0.0"

    def test_update_preserves_formatting(self, tmp_path: Path):
        """Updating version preserves file formatting."""
        pyproject = tmp_path / "pyproject.toml"
        original = """\
[project]
name = "test"
version = "1.0.0"
description = "A test"

[build-system]
requires = ["hatchling"]
build-backend = "hatchling.build"
"""
        pyproject.write_text(original)

        update_pyproject_version(tmp_path, "2.0.0")

        content = pyproject.read_text()
        assert 'version = "2.0.0"' in content
        assert "[build-system]" in content

    def test_get_version_not_found_raises(self, tmp_path: Path):
        """Raises VersionNotFoundError when version not found."""
        pyproject = tmp_path / "pyproject.toml"
        pyproject.write_text("[project]\nname = 'test'\n")

        with pytest.raises(VersionNotFoundError):
            get_pyproject_version(tmp_path)


class TestVersionFile:
    """Integration tests for version file updates."""

    def test_update_version_file(self, tmp_path: Path):
        """Update __version__ in a Python file."""
        version_file = tmp_path / "__init__.py"
        version_file.write_text('__version__ = "1.0.0"\n')

        update_version_file(version_file, "2.0.0")

        content = version_file.read_text()
        assert '__version__ = "2.0.0"' in content

    def test_update_version_file_preserves_other_content(self, tmp_path: Path):
        """Updating version preserves other file content."""
        version_file = tmp_path / "__init__.py"
        version_file.write_text(
            '''\
"""Package docstring."""

__version__ = "1.0.0"
__author__ = "Test"

def main():
    pass
'''
        )

        update_version_file(version_file, "2.0.0")

        content = version_file.read_text()
        assert '__version__ = "2.0.0"' in content
        assert "__author__" in content
        assert "def main():" in content

    def test_update_nonexistent_raises(self, tmp_path: Path):
        """Updating nonexistent file raises error."""
        from release_py.exceptions import ProjectError

        with pytest.raises(ProjectError):
            update_version_file(tmp_path / "nonexistent.py", "2.0.0")

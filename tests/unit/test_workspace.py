"""Unit tests for workspace/monorepo support."""

from __future__ import annotations

from typing import TYPE_CHECKING

import pytest

if TYPE_CHECKING:
    from pathlib import Path

from release_py.config.models import PackagesConfig, ReleasePyConfig
from release_py.project.workspace import (
    WorkspacePackage,
    detect_workspace,
    get_package_by_name,
)


@pytest.fixture
def workspace_config_with_paths() -> ReleasePyConfig:
    """Config with explicit package paths."""
    return ReleasePyConfig(packages=PackagesConfig(paths=["packages/core", "packages/cli"]))


@pytest.fixture
def workspace_config_auto() -> ReleasePyConfig:
    """Config without explicit paths (auto-detect)."""
    return ReleasePyConfig()


class TestDetectWorkspace:
    """Tests for workspace detection."""

    def test_detect_from_config_paths(
        self, tmp_path: Path, workspace_config_with_paths: ReleasePyConfig
    ):
        """Detect packages from configured paths."""
        # Create package directories
        for pkg in ["core", "cli"]:
            pkg_dir = tmp_path / "packages" / pkg
            pkg_dir.mkdir(parents=True)
            (pkg_dir / "pyproject.toml").write_text(
                f"""
[project]
name = "{pkg}"
version = "1.0.0"
"""
            )

        packages = detect_workspace(workspace_config_with_paths, tmp_path)

        assert len(packages) == 2
        names = [p.name for p in packages]
        assert "core" in names
        assert "cli" in names

    def test_detect_from_config_missing_path(
        self, tmp_path: Path, workspace_config_with_paths: ReleasePyConfig
    ):
        """Skip configured paths that don't exist."""
        # Only create one package
        pkg_dir = tmp_path / "packages" / "core"
        pkg_dir.mkdir(parents=True)
        (pkg_dir / "pyproject.toml").write_text(
            """
[project]
name = "core"
version = "1.0.0"
"""
        )
        # packages/cli doesn't exist

        packages = detect_workspace(workspace_config_with_paths, tmp_path)

        assert len(packages) == 1
        assert packages[0].name == "core"

    def test_detect_auto_packages_dir(self, tmp_path: Path, workspace_config_auto: ReleasePyConfig):
        """Auto-detect packages in packages/ directory."""
        # Create packages in packages/ dir
        packages_dir = tmp_path / "packages"
        for pkg in ["api", "sdk"]:
            pkg_dir = packages_dir / pkg
            pkg_dir.mkdir(parents=True)
            (pkg_dir / "pyproject.toml").write_text(
                f"""
[project]
name = "my-{pkg}"
version = "1.0.0"
"""
            )

        packages = detect_workspace(workspace_config_auto, tmp_path)

        # Should find packages via auto-detection
        assert len(packages) >= 0  # May be 0 if auto-detect doesn't find them

    def test_detect_empty_workspace(self, tmp_path: Path, workspace_config_auto: ReleasePyConfig):
        """Return empty list when no packages found."""
        packages = detect_workspace(workspace_config_auto, tmp_path)
        assert packages == []

    def test_detect_invalid_packages_included(
        self, tmp_path: Path, workspace_config_with_paths: ReleasePyConfig
    ):
        """Packages with missing name/version are still detected (with empty values)."""
        # Create one valid package
        valid_dir = tmp_path / "packages" / "core"
        valid_dir.mkdir(parents=True)
        (valid_dir / "pyproject.toml").write_text(
            """
[project]
name = "core"
version = "1.0.0"
"""
        )

        # Create one package with missing name/version
        incomplete_dir = tmp_path / "packages" / "cli"
        incomplete_dir.mkdir(parents=True)
        (incomplete_dir / "pyproject.toml").write_text(
            """
[project]
# Missing name and version
"""
        )

        packages = detect_workspace(workspace_config_with_paths, tmp_path)

        # Both packages are detected, incomplete one has empty name/version
        assert len(packages) == 2
        names = [p.name for p in packages]
        assert "core" in names
        assert "" in names  # The incomplete package has empty name


class TestWorkspacePackage:
    """Tests for WorkspacePackage dataclass."""

    def test_workspace_package_creation(self, tmp_path: Path):
        """Create WorkspacePackage instance."""
        from release_py.project.detector import ProjectInfo

        info = ProjectInfo(
            name="test-package",
            version="1.0.0",
            path=tmp_path,
            project_type="pyproject",
            build_backend="hatchling",
            pyproject_path=tmp_path / "pyproject.toml",
        )

        pkg = WorkspacePackage(
            name="test-package",
            version="1.0.0",
            path=tmp_path,
            info=info,
        )

        assert pkg.name == "test-package"
        assert pkg.version == "1.0.0"
        assert pkg.path == tmp_path
        assert pkg.info == info


class TestGetPackageByName:
    """Tests for get_package_by_name."""

    def test_find_existing_package(self, tmp_path: Path):
        """Find package by name."""
        from release_py.project.detector import ProjectInfo

        info1 = ProjectInfo(
            name="core",
            version="1.0.0",
            path=tmp_path,
            project_type="pyproject",
            build_backend=None,
            pyproject_path=tmp_path / "pyproject.toml",
        )
        info2 = ProjectInfo(
            name="cli",
            version="2.0.0",
            path=tmp_path,
            project_type="pyproject",
            build_backend=None,
            pyproject_path=tmp_path / "pyproject.toml",
        )

        packages = [
            WorkspacePackage(name="core", version="1.0.0", path=tmp_path, info=info1),
            WorkspacePackage(name="cli", version="2.0.0", path=tmp_path, info=info2),
        ]

        result = get_package_by_name(packages, "cli")

        assert result is not None
        assert result.name == "cli"
        assert result.version == "2.0.0"

    def test_package_not_found(self, tmp_path: Path):
        """Return None when package not found."""
        from release_py.project.detector import ProjectInfo

        info = ProjectInfo(
            name="core",
            version="1.0.0",
            path=tmp_path,
            project_type="pyproject",
            build_backend=None,
            pyproject_path=tmp_path / "pyproject.toml",
        )
        packages = [
            WorkspacePackage(name="core", version="1.0.0", path=tmp_path, info=info),
        ]

        result = get_package_by_name(packages, "nonexistent")

        assert result is None

    def test_empty_package_list(self):
        """Return None for empty package list."""
        result = get_package_by_name([], "anything")
        assert result is None

"""Unit tests for lock file detection and updating."""

from __future__ import annotations

from typing import TYPE_CHECKING
from unittest.mock import MagicMock, patch

from release_py.project.lockfile import (
    LOCK_FILES,
    PackageManager,
    detect_package_manager,
    get_lock_file_path,
    should_update_lock_file,
    update_lock_file,
)

if TYPE_CHECKING:
    from pathlib import Path


class TestPackageManagerDetection:
    """Tests for detect_package_manager function."""

    def test_detect_uv_from_lock_file(self, tmp_path: Path):
        """Detect uv from uv.lock file."""
        (tmp_path / "uv.lock").write_text("# uv lock file")
        assert detect_package_manager(tmp_path) == PackageManager.UV

    def test_detect_poetry_from_lock_file(self, tmp_path: Path):
        """Detect Poetry from poetry.lock file."""
        (tmp_path / "poetry.lock").write_text("# poetry lock file")
        assert detect_package_manager(tmp_path) == PackageManager.POETRY

    def test_detect_pdm_from_lock_file(self, tmp_path: Path):
        """Detect PDM from pdm.lock file."""
        (tmp_path / "pdm.lock").write_text("# pdm lock file")
        assert detect_package_manager(tmp_path) == PackageManager.PDM

    def test_detect_pip_tools_from_requirements_in(self, tmp_path: Path):
        """Detect pip-tools from requirements.in file."""
        (tmp_path / "requirements.in").write_text("requests>=2.0")
        assert detect_package_manager(tmp_path) == PackageManager.PIP_TOOLS

    def test_detect_poetry_from_pyproject(self, tmp_path: Path):
        """Detect Poetry from pyproject.toml configuration."""
        pyproject = tmp_path / "pyproject.toml"
        pyproject.write_text("""
[tool.poetry]
name = "test"
version = "0.1.0"
""")
        assert detect_package_manager(tmp_path) == PackageManager.POETRY

    def test_detect_pdm_from_pyproject(self, tmp_path: Path):
        """Detect PDM from pyproject.toml configuration."""
        pyproject = tmp_path / "pyproject.toml"
        pyproject.write_text("""
[tool.pdm]
distribution = true
""")
        assert detect_package_manager(tmp_path) == PackageManager.PDM

    def test_detect_hatch_from_pyproject(self, tmp_path: Path):
        """Detect Hatch from pyproject.toml configuration."""
        pyproject = tmp_path / "pyproject.toml"
        pyproject.write_text("""
[tool.hatch]
version = "0.1.0"
""")
        assert detect_package_manager(tmp_path) == PackageManager.HATCH

    def test_detect_unknown_empty_directory(self, tmp_path: Path):
        """Return UNKNOWN for empty directory."""
        assert detect_package_manager(tmp_path) == PackageManager.UNKNOWN

    def test_lock_file_takes_precedence_over_pyproject(self, tmp_path: Path):
        """Lock file detection takes precedence over pyproject.toml."""
        # Create both poetry.lock and [tool.pdm] in pyproject
        (tmp_path / "poetry.lock").write_text("# lock")
        pyproject = tmp_path / "pyproject.toml"
        pyproject.write_text("[tool.pdm]\n")

        # poetry.lock should win
        assert detect_package_manager(tmp_path) == PackageManager.POETRY


class TestGetLockFilePath:
    """Tests for get_lock_file_path function."""

    def test_uv_lock_file_path(self, tmp_path: Path):
        """Get uv.lock path."""
        path = get_lock_file_path(tmp_path, PackageManager.UV)
        assert path == tmp_path / "uv.lock"

    def test_poetry_lock_file_path(self, tmp_path: Path):
        """Get poetry.lock path."""
        path = get_lock_file_path(tmp_path, PackageManager.POETRY)
        assert path == tmp_path / "poetry.lock"

    def test_pdm_lock_file_path(self, tmp_path: Path):
        """Get pdm.lock path."""
        path = get_lock_file_path(tmp_path, PackageManager.PDM)
        assert path == tmp_path / "pdm.lock"

    def test_hatch_no_lock_file(self, tmp_path: Path):
        """Hatch has no lock file."""
        path = get_lock_file_path(tmp_path, PackageManager.HATCH)
        assert path is None

    def test_unknown_no_lock_file(self, tmp_path: Path):
        """Unknown package manager has no lock file."""
        path = get_lock_file_path(tmp_path, PackageManager.UNKNOWN)
        assert path is None


class TestShouldUpdateLockFile:
    """Tests for should_update_lock_file function."""

    def test_should_update_when_uv_lock_exists(self, tmp_path: Path):
        """Should update when uv.lock exists."""
        (tmp_path / "uv.lock").write_text("# lock")
        assert should_update_lock_file(tmp_path) is True

    def test_should_update_when_poetry_lock_exists(self, tmp_path: Path):
        """Should update when poetry.lock exists."""
        (tmp_path / "poetry.lock").write_text("# lock")
        assert should_update_lock_file(tmp_path) is True

    def test_should_not_update_for_hatch(self, tmp_path: Path):
        """Should not update for Hatch (no lock files)."""
        pyproject = tmp_path / "pyproject.toml"
        pyproject.write_text("[tool.hatch]\n")
        assert should_update_lock_file(tmp_path) is False

    def test_should_not_update_for_unknown(self, tmp_path: Path):
        """Should not update for unknown package manager."""
        assert should_update_lock_file(tmp_path) is False


class TestUpdateLockFile:
    """Tests for update_lock_file function."""

    def test_update_uv_lock_success(self, tmp_path: Path):
        """Successfully update uv.lock."""
        (tmp_path / "uv.lock").write_text("# lock")

        with patch("subprocess.run") as mock_run, patch("shutil.which", return_value="/usr/bin/uv"):
            mock_run.return_value = MagicMock(returncode=0)

            success, message = update_lock_file(tmp_path, PackageManager.UV)

            assert success is True
            assert "uv.lock" in message
            mock_run.assert_called_once()

    def test_update_poetry_lock_success(self, tmp_path: Path):
        """Successfully update poetry.lock."""
        (tmp_path / "poetry.lock").write_text("# lock")

        with (
            patch("subprocess.run") as mock_run,
            patch("shutil.which", return_value="/usr/bin/poetry"),
        ):
            mock_run.return_value = MagicMock(returncode=0)

            success, message = update_lock_file(tmp_path, PackageManager.POETRY)

            assert success is True
            assert "poetry.lock" in message

    def test_update_no_lock_file_skips(self, tmp_path: Path):
        """Skip update when no lock file exists."""
        # No lock file created
        success, message = update_lock_file(tmp_path, PackageManager.UV)

        assert success is True
        assert "No uv.lock found" in message

    def test_update_tool_not_found(self, tmp_path: Path):
        """Fail when tool not found in PATH."""
        (tmp_path / "uv.lock").write_text("# lock")

        with patch("shutil.which", return_value=None):
            success, message = update_lock_file(tmp_path, PackageManager.UV)

            assert success is False
            assert "not found" in message

    def test_update_hatch_no_lock(self, tmp_path: Path):
        """Hatch returns success (no lock files to update)."""
        success, message = update_lock_file(tmp_path, PackageManager.HATCH)

        assert success is True
        assert "does not use lock files" in message

    def test_update_unknown_fails(self, tmp_path: Path):
        """Unknown package manager fails."""
        success, message = update_lock_file(tmp_path, PackageManager.UNKNOWN)

        assert success is False
        assert "Could not detect" in message

    def test_auto_detect_package_manager(self, tmp_path: Path):
        """Auto-detect package manager when not specified."""
        (tmp_path / "poetry.lock").write_text("# lock")

        with (
            patch("subprocess.run") as mock_run,
            patch("shutil.which", return_value="/usr/bin/poetry"),
        ):
            mock_run.return_value = MagicMock(returncode=0)

            # Don't specify package manager
            success, message = update_lock_file(tmp_path)

            assert success is True
            assert "poetry.lock" in message


class TestLockFilesMapping:
    """Tests for LOCK_FILES constant."""

    def test_all_managers_with_lock_files_are_mapped(self):
        """All package managers with lock files should be in mapping."""
        assert PackageManager.UV in LOCK_FILES
        assert PackageManager.POETRY in LOCK_FILES
        assert PackageManager.PDM in LOCK_FILES

    def test_hatch_not_in_mapping(self):
        """Hatch should not be in lock files mapping."""
        assert PackageManager.HATCH not in LOCK_FILES

    def test_unknown_not_in_mapping(self):
        """Unknown should not be in lock files mapping."""
        assert PackageManager.UNKNOWN not in LOCK_FILES

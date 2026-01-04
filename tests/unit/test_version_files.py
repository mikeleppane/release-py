"""Unit tests for version file detection and updating."""

from __future__ import annotations

from typing import TYPE_CHECKING

import pytest

from release_py.exceptions import ProjectError, VersionNotFoundError
from release_py.project.pyproject import (
    VERSION_PATTERNS,
    detect_version_files,
    get_version_from_file,
    update_version_file,
    update_version_in_plain_file,
)

if TYPE_CHECKING:
    from pathlib import Path


class TestDetectVersionFiles:
    """Tests for detect_version_files function."""

    def test_detect_init_py_in_src_layout(self, tmp_path: Path):
        """Detect __init__.py with version in src/ layout."""
        # Create src/mypackage/__init__.py with version
        pkg_dir = tmp_path / "src" / "mypackage"
        pkg_dir.mkdir(parents=True)
        init_file = pkg_dir / "__init__.py"
        init_file.write_text('__version__ = "1.0.0"\n')

        detected = detect_version_files(tmp_path)

        assert len(detected) == 1
        assert detected[0] == init_file

    def test_detect_version_py_in_src_layout(self, tmp_path: Path):
        """Detect __version__.py in src/ layout."""
        pkg_dir = tmp_path / "src" / "mypackage"
        pkg_dir.mkdir(parents=True)
        (pkg_dir / "__init__.py").write_text("# init")
        version_file = pkg_dir / "__version__.py"
        version_file.write_text('__version__ = "1.0.0"\n')

        detected = detect_version_files(tmp_path)

        assert version_file in detected

    def test_detect_flat_layout(self, tmp_path: Path):
        """Detect version files in flat layout."""
        pkg_dir = tmp_path / "mypackage"
        pkg_dir.mkdir()
        init_file = pkg_dir / "__init__.py"
        init_file.write_text('__version__ = "1.0.0"\n')

        detected = detect_version_files(tmp_path)

        assert len(detected) == 1
        assert detected[0] == init_file

    def test_detect_version_file_in_root(self, tmp_path: Path):
        """Detect VERSION file in project root."""
        version_file = tmp_path / "VERSION"
        version_file.write_text("1.0.0\n")

        detected = detect_version_files(tmp_path)

        assert version_file in detected

    def test_skip_test_directories(self, tmp_path: Path):
        """Skip tests/ directory."""
        # Create tests/conftest.py with version (should be skipped)
        tests_dir = tmp_path / "tests"
        tests_dir.mkdir()
        conftest = tests_dir / "__init__.py"
        conftest.write_text('__version__ = "1.0.0"\n')

        detected = detect_version_files(tmp_path)

        assert len(detected) == 0

    def test_skip_docs_directories(self, tmp_path: Path):
        """Skip docs/ directory."""
        docs_dir = tmp_path / "docs"
        docs_dir.mkdir()
        (docs_dir / "__init__.py").write_text('__version__ = "1.0.0"\n')

        detected = detect_version_files(tmp_path)

        assert len(detected) == 0

    def test_multiple_version_files(self, tmp_path: Path):
        """Detect multiple version files."""
        # Create src layout with both __init__.py and __version__.py
        pkg_dir = tmp_path / "src" / "mypackage"
        pkg_dir.mkdir(parents=True)

        init_file = pkg_dir / "__init__.py"
        init_file.write_text('__version__ = "1.0.0"\n')

        version_file = pkg_dir / "__version__.py"
        version_file.write_text('__version__ = "1.0.0"\n')

        detected = detect_version_files(tmp_path)

        assert len(detected) == 2
        assert init_file in detected
        assert version_file in detected

    def test_ignore_init_without_version(self, tmp_path: Path):
        """Ignore __init__.py without version string."""
        pkg_dir = tmp_path / "mypackage"
        pkg_dir.mkdir()
        init_file = pkg_dir / "__init__.py"
        init_file.write_text("# Just a regular init file\n")

        detected = detect_version_files(tmp_path)

        assert len(detected) == 0

    def test_detect_underscore_version_py(self, tmp_path: Path):
        """Detect _version.py file."""
        pkg_dir = tmp_path / "src" / "mypackage"
        pkg_dir.mkdir(parents=True)
        (pkg_dir / "__init__.py").write_text("# init")
        version_file = pkg_dir / "_version.py"
        version_file.write_text('__version__ = "1.0.0"\n')

        detected = detect_version_files(tmp_path)

        assert version_file in detected


class TestGetVersionFromFile:
    """Tests for get_version_from_file function."""

    def test_get_version_dunder_version(self, tmp_path: Path):
        """Get version from __version__ = '...'."""
        version_file = tmp_path / "__version__.py"
        version_file.write_text('__version__ = "1.2.3"\n')

        version = get_version_from_file(version_file)

        assert version == "1.2.3"

    def test_get_version_single_quotes(self, tmp_path: Path):
        """Get version with single quotes."""
        version_file = tmp_path / "__version__.py"
        version_file.write_text("__version__ = '1.2.3'\n")

        version = get_version_from_file(version_file)

        assert version == "1.2.3"

    def test_get_version_uppercase_version(self, tmp_path: Path):
        """Get version from VERSION = '...'."""
        version_file = tmp_path / "version.py"
        version_file.write_text('VERSION = "2.0.0"\n')

        version = get_version_from_file(version_file)

        assert version == "2.0.0"

    def test_get_version_lowercase_version(self, tmp_path: Path):
        """Get version from version = '...'."""
        version_file = tmp_path / "version.py"
        version_file.write_text('version = "3.0.0"\n')

        version = get_version_from_file(version_file)

        assert version == "3.0.0"

    def test_get_version_custom_pattern(self, tmp_path: Path):
        """Get version with custom pattern."""
        version_file = tmp_path / "custom.py"
        version_file.write_text('MY_VERSION = "4.0.0"\n')

        version = get_version_from_file(
            version_file, pattern=r'^MY_VERSION\s*=\s*["\']([^"\']+)["\']'
        )

        assert version == "4.0.0"

    def test_file_not_found_raises(self, tmp_path: Path):
        """Raise ProjectError when file not found."""
        version_file = tmp_path / "nonexistent.py"

        with pytest.raises(ProjectError, match="not found"):
            get_version_from_file(version_file)

    def test_version_not_found_raises(self, tmp_path: Path):
        """Raise VersionNotFoundError when no version pattern."""
        version_file = tmp_path / "empty.py"
        version_file.write_text("# No version here\n")

        with pytest.raises(VersionNotFoundError):
            get_version_from_file(version_file)


class TestUpdateVersionFile:
    """Tests for update_version_file function."""

    def test_update_dunder_version(self, tmp_path: Path):
        """Update __version__ = '...'."""
        version_file = tmp_path / "__version__.py"
        version_file.write_text('__version__ = "1.0.0"\n')

        update_version_file(version_file, "2.0.0")

        content = version_file.read_text()
        assert '__version__ = "2.0.0"' in content

    def test_update_preserves_other_content(self, tmp_path: Path):
        """Update version preserves other file content."""
        version_file = tmp_path / "__version__.py"
        version_file.write_text('''"""Version module."""
__version__ = "1.0.0"
__author__ = "Test"
''')

        update_version_file(version_file, "2.0.0")

        content = version_file.read_text()
        assert '__version__ = "2.0.0"' in content
        assert "__author__ = " in content
        assert '"""Version module."""' in content

    def test_update_file_not_found_raises(self, tmp_path: Path):
        """Raise ProjectError when file not found."""
        version_file = tmp_path / "nonexistent.py"

        with pytest.raises(ProjectError, match="not found"):
            update_version_file(version_file, "1.0.0")

    def test_update_version_not_found_raises(self, tmp_path: Path):
        """Raise VersionNotFoundError when no version pattern."""
        version_file = tmp_path / "empty.py"
        version_file.write_text("# No version here\n")

        with pytest.raises(VersionNotFoundError):
            update_version_file(version_file, "1.0.0")


class TestUpdateVersionInPlainFile:
    """Tests for update_version_in_plain_file function."""

    def test_update_plain_version_file(self, tmp_path: Path):
        """Update plain VERSION file."""
        version_file = tmp_path / "VERSION"
        version_file.write_text("1.0.0\n")

        update_version_in_plain_file(version_file, "2.0.0")

        content = version_file.read_text()
        assert content == "2.0.0\n"

    def test_file_not_found_raises(self, tmp_path: Path):
        """Raise ProjectError when file not found."""
        version_file = tmp_path / "VERSION"

        with pytest.raises(ProjectError, match="not found"):
            update_version_in_plain_file(version_file, "1.0.0")


class TestVersionPatterns:
    """Tests for VERSION_PATTERNS constant."""

    def test_patterns_match_dunder_version(self):
        """Patterns match __version__ = '...'."""
        import re

        text = '__version__ = "1.0.0"'
        matched = any(re.search(pat, text) for pat in VERSION_PATTERNS)
        assert matched

    def test_patterns_match_uppercase_version(self):
        """Patterns match VERSION = '...'."""
        import re

        text = 'VERSION = "1.0.0"'
        matched = any(re.search(pat, text) for pat in VERSION_PATTERNS)
        assert matched

    def test_patterns_match_lowercase_version(self):
        """Patterns match version = '...'."""
        import re

        text = 'version = "1.0.0"'
        matched = any(re.search(pat, text) for pat in VERSION_PATTERNS)
        assert matched

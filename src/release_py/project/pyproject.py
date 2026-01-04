"""pyproject.toml version manipulation.

This module provides functionality for reading and updating
the version number in pyproject.toml files and other version files.

It preserves formatting and comments by using regex-based
replacement rather than full TOML parsing and rewriting.

Supported version file patterns:
- pyproject.toml (PEP 621 and Poetry formats)
- __init__.py with __version__ = "..."
- __version__.py with __version__ = "..."
- _version.py with __version__ = "..."
- VERSION (plain text file)
"""

from __future__ import annotations

import re
from typing import TYPE_CHECKING

from release_py.config.loader import find_pyproject_toml
from release_py.exceptions import ProjectError, VersionNotFoundError

if TYPE_CHECKING:
    from pathlib import Path


# Common version file patterns to search for
VERSION_FILE_PATTERNS = [
    "__version__.py",
    "_version.py",
    "__init__.py",
    "version.py",
]

# Regex patterns to detect version in Python files
VERSION_PATTERNS = [
    r'^__version__\s*=\s*["\']([^"\']+)["\']',
    r'^VERSION\s*=\s*["\']([^"\']+)["\']',
    r'^version\s*=\s*["\']([^"\']+)["\']',
]


def get_pyproject_version(path: Path | None = None) -> str:
    """Get the version from pyproject.toml.

    Args:
        path: Path to pyproject.toml or directory to search from

    Returns:
        Version string

    Raises:
        VersionNotFoundError: If version cannot be found
    """
    if path is None:
        pyproject_path = find_pyproject_toml()
    elif path.is_dir():
        pyproject_path = find_pyproject_toml(path)
    else:
        pyproject_path = path

    content = pyproject_path.read_text()

    # Try PEP 621 format first: [project] version = "..."
    pep621_match = re.search(
        r'^\[project\].*?^version\s*=\s*["\']([^"\']+)["\']',
        content,
        re.MULTILINE | re.DOTALL,
    )
    if pep621_match:
        return pep621_match.group(1)

    # Try Poetry format: [tool.poetry] version = "..."
    poetry_match = re.search(
        r'^\[tool\.poetry\].*?^version\s*=\s*["\']([^"\']+)["\']',
        content,
        re.MULTILINE | re.DOTALL,
    )
    if poetry_match:
        return poetry_match.group(1)

    raise VersionNotFoundError(
        f"Could not find version in {pyproject_path}. "
        "Expected [project].version or [tool.poetry].version."
    )


def update_pyproject_version(path: Path | None, new_version: str) -> Path:
    """Update the version in pyproject.toml.

    This function preserves formatting and comments by using
    a targeted regex replacement.

    Args:
        path: Path to pyproject.toml or directory containing it
        new_version: New version string to set

    Returns:
        Path to the updated pyproject.toml

    Raises:
        VersionNotFoundError: If version cannot be found
        ProjectError: If update fails
    """
    if path is None:
        pyproject_path = find_pyproject_toml()
    elif path.is_dir():
        pyproject_path = find_pyproject_toml(path)
    else:
        pyproject_path = path

    content = pyproject_path.read_text()
    original_content = content

    # Try to update PEP 621 format
    updated = False

    # Pattern for [project] section version
    # This matches version = "..." within the [project] section
    def replace_pep621(match: re.Match[str]) -> str:
        section = match.group(0)
        # Replace version within the matched section
        return re.sub(
            r'^(version\s*=\s*)["\'][^"\']+["\']',
            rf'\g<1>"{new_version}"',
            section,
            count=1,
            flags=re.MULTILINE,
        )

    # Match the entire [project] section up to the next section or EOF
    pep621_pattern = r"^\[project\].*?(?=^\[|\Z)"
    new_content, count = re.subn(
        pep621_pattern,
        replace_pep621,
        content,
        count=1,
        flags=re.MULTILINE | re.DOTALL,
    )

    if count > 0 and new_content != content:
        content = new_content
        updated = True

    # If not updated, try Poetry format
    if not updated:

        def replace_poetry(match: re.Match[str]) -> str:
            section = match.group(0)
            return re.sub(
                r'^(version\s*=\s*)["\'][^"\']+["\']',
                rf'\g<1>"{new_version}"',
                section,
                count=1,
                flags=re.MULTILINE,
            )

        poetry_pattern = r"^\[tool\.poetry\].*?(?=^\[|\Z)"
        new_content, count = re.subn(
            poetry_pattern,
            replace_poetry,
            content,
            count=1,
            flags=re.MULTILINE | re.DOTALL,
        )

        if count > 0 and new_content != content:
            content = new_content
            updated = True

    if not updated:
        raise VersionNotFoundError(
            f"Could not find version to update in {pyproject_path}. "
            "Expected [project].version or [tool.poetry].version."
        )

    if content == original_content:
        raise ProjectError(
            f"Version in {pyproject_path} was not updated. It may already be {new_version}."
        )

    pyproject_path.write_text(content)
    return pyproject_path


def get_version_from_file(
    file_path: Path,
    pattern: str | None = None,
) -> str:
    """Read version from a Python file (e.g., __version__.py or __init__.py).

    Args:
        file_path: Path to the file to read
        pattern: Custom regex pattern with a capture group for the version.
                 Defaults to matching __version__ = "..."

    Returns:
        Version string

    Raises:
        VersionNotFoundError: If version pattern not found
        ProjectError: If file doesn't exist
    """
    if not file_path.is_file():
        raise ProjectError(f"Version file not found: {file_path}")

    content = file_path.read_text()

    if pattern is None:
        # Match __version__ = "..." or __version__ = '...'
        # Also match VERSION = "..." for common patterns
        patterns = [
            r'^__version__\s*=\s*["\']([^"\']+)["\']',
            r'^VERSION\s*=\s*["\']([^"\']+)["\']',
            r'^version\s*=\s*["\']([^"\']+)["\']',
        ]
    else:
        patterns = [pattern]

    for pat in patterns:
        match = re.search(pat, content, re.MULTILINE)
        if match:
            return match.group(1)

    raise VersionNotFoundError(f"Could not find version pattern in {file_path}")


def update_version_file(
    file_path: Path,
    new_version: str,
    pattern: str | None = None,
) -> None:
    """Update version in a Python file (e.g., __version__.py or __init__.py).

    Args:
        file_path: Path to the file to update
        new_version: New version string
        pattern: Custom regex pattern with a capture group for the version.
                 Defaults to matching __version__ = "..."

    Raises:
        VersionNotFoundError: If version pattern not found
        ProjectError: If file doesn't exist
    """
    if not file_path.is_file():
        raise ProjectError(f"Version file not found: {file_path}")

    content = file_path.read_text()

    if pattern is None:
        # Match __version__ = "..." or __version__ = '...'
        pattern = r'^(__version__\s*=\s*)["\'][^"\']+["\']'

    new_content, count = re.subn(
        pattern,
        rf'\g<1>"{new_version}"',
        content,
        count=1,
        flags=re.MULTILINE,
    )

    if count == 0:
        raise VersionNotFoundError(f"Could not find version pattern in {file_path}")

    file_path.write_text(new_content)


def _file_contains_version(file_path: Path) -> bool:
    """Check if a file contains a version pattern.

    Args:
        file_path: Path to the file to check

    Returns:
        True if file contains a recognizable version pattern
    """
    try:
        content = file_path.read_text()
        return any(re.search(pat, content, re.MULTILINE) for pat in VERSION_PATTERNS)
    except OSError:
        return False


def detect_version_files(project_path: Path) -> list[Path]:
    """Auto-detect files that contain version strings.

    Searches for common version file patterns in the project directory,
    checking both src/ layout and flat layout structures.

    Args:
        project_path: Path to the project root

    Returns:
        List of paths to files containing version patterns

    Example:
        >>> files = detect_version_files(Path("/path/to/project"))
        >>> for f in files:
        ...     print(f)
        /path/to/project/src/mypackage/__init__.py
        /path/to/project/src/mypackage/__version__.py
    """
    from pathlib import Path as PathClass

    found: list[Path] = []
    project_path = PathClass(project_path)

    # Directories to search for version files
    search_dirs: list[Path] = []

    # Directories to skip when looking for packages
    skip_dirs = {"tests", "test", "docs", "doc", "examples", "scripts", "dist", "build"}

    # Check src/ layout (PEP 517/518 recommended)
    src_dir = project_path / "src"
    if src_dir.exists() and src_dir.is_dir():
        search_dirs.extend(
            pkg_dir
            for pkg_dir in src_dir.iterdir()
            if pkg_dir.is_dir() and not pkg_dir.name.startswith((".", "_"))
        )

    # Check flat layout (package directly in project root)
    for item in project_path.iterdir():
        if item.is_dir() and not item.name.startswith((".", "_")):
            # Skip common non-package directories
            if item.name in skip_dirs:
                continue
            # Check if it looks like a Python package
            if (item / "__init__.py").exists():
                search_dirs.append(item)

    # Search for version files in each package directory
    for pkg_dir in search_dirs:
        for pattern in VERSION_FILE_PATTERNS:
            file_path = pkg_dir / pattern
            if file_path.exists() and file_path.is_file() and _file_contains_version(file_path):
                found.append(file_path)

    # Also check for VERSION file in project root (plain text)
    version_file = project_path / "VERSION"
    if version_file.exists() and version_file.is_file():
        found.append(version_file)

    return found


def update_version_in_plain_file(file_path: Path, new_version: str) -> None:
    """Update version in a plain text VERSION file.

    Args:
        file_path: Path to the VERSION file
        new_version: New version string

    Raises:
        ProjectError: If file doesn't exist
    """
    if not file_path.is_file():
        raise ProjectError(f"Version file not found: {file_path}")

    # Plain VERSION files just contain the version string
    file_path.write_text(f"{new_version}\n")

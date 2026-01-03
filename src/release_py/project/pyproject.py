"""pyproject.toml version manipulation.

This module provides functionality for reading and updating
the version number in pyproject.toml files.

It preserves formatting and comments by using regex-based
replacement rather than full TOML parsing and rewriting.
"""

from __future__ import annotations

import re
from typing import TYPE_CHECKING

from release_py.config.loader import find_pyproject_toml
from release_py.exceptions import ProjectError, VersionNotFoundError

if TYPE_CHECKING:
    from pathlib import Path


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

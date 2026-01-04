"""Lock file detection and updating.

This module handles lock file management for various Python package managers:
- uv (uv.lock)
- Poetry (poetry.lock)
- PDM (pdm.lock)
- pip-tools (requirements.txt from requirements.in)

Auto-detection is based on lock file presence and pyproject.toml configuration.
"""

from __future__ import annotations

import shutil
import subprocess
from enum import Enum
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from pathlib import Path


class PackageManager(Enum):
    """Supported package managers."""

    UV = "uv"
    POETRY = "poetry"
    PDM = "pdm"
    PIP_TOOLS = "pip-tools"
    HATCH = "hatch"  # No lock file, but we track it
    UNKNOWN = "unknown"


# Lock file names for each package manager
LOCK_FILES = {
    PackageManager.UV: "uv.lock",
    PackageManager.POETRY: "poetry.lock",
    PackageManager.PDM: "pdm.lock",
}

# Commands to regenerate lock files (without upgrading dependencies)
LOCK_COMMANDS = {
    PackageManager.UV: ["uv", "lock"],
    PackageManager.POETRY: ["poetry", "lock", "--no-update"],
    PackageManager.PDM: ["pdm", "lock", "--no-update"],
    PackageManager.PIP_TOOLS: ["pip-compile", "--no-upgrade"],
}


def detect_package_manager(project_path: Path) -> PackageManager:  # noqa: PLR0911
    """Detect the package manager used by the project.

    Detection order:
    1. Check for existing lock files
    2. Check pyproject.toml for tool-specific configuration
    3. Check for build system configuration
    4. Default to UNKNOWN

    Args:
        project_path: Path to the project root

    Returns:
        Detected PackageManager enum value
    """
    # Check for lock files first (most reliable indicator)
    if (project_path / "uv.lock").exists():
        return PackageManager.UV
    if (project_path / "poetry.lock").exists():
        return PackageManager.POETRY
    if (project_path / "pdm.lock").exists():
        return PackageManager.PDM

    # Check for pip-tools pattern
    if (project_path / "requirements.in").exists():
        return PackageManager.PIP_TOOLS

    # Check pyproject.toml for tool configuration
    pyproject = project_path / "pyproject.toml"
    if pyproject.exists():
        try:
            content = pyproject.read_text()

            # Check for tool-specific sections
            if "[tool.poetry]" in content:
                return PackageManager.POETRY
            if "[tool.pdm]" in content:
                return PackageManager.PDM
            if "[tool.hatch]" in content:
                return PackageManager.HATCH

            # Check build-system for hints
            if "hatchling" in content:
                return PackageManager.HATCH
            if "poetry" in content and "build-backend" in content:
                return PackageManager.POETRY
            if "pdm" in content and "build-backend" in content:
                return PackageManager.PDM

            # If it has [project] section (PEP 621), assume uv for modern projects
            if "[project]" in content and shutil.which("uv") is not None:
                return PackageManager.UV

        except OSError:
            pass

    return PackageManager.UNKNOWN


def get_lock_file_path(project_path: Path, package_manager: PackageManager) -> Path | None:
    """Get the lock file path for the given package manager.

    Args:
        project_path: Path to the project root
        package_manager: The package manager in use

    Returns:
        Path to lock file, or None if the package manager doesn't use lock files
    """
    lock_file_name = LOCK_FILES.get(package_manager)
    if lock_file_name:
        return project_path / lock_file_name
    return None


def update_lock_file(  # noqa: PLR0911
    project_path: Path,
    package_manager: PackageManager | None = None,
) -> tuple[bool, str]:
    """Update the lock file for the project.

    This regenerates the lock file to reflect version changes in pyproject.toml
    without upgrading dependencies to newer versions.

    Args:
        project_path: Path to the project root
        package_manager: Package manager to use (auto-detected if None)

    Returns:
        Tuple of (success, message)
    """
    if package_manager is None:
        package_manager = detect_package_manager(project_path)

    if package_manager == PackageManager.UNKNOWN:
        return False, "Could not detect package manager"

    if package_manager == PackageManager.HATCH:
        # Hatch doesn't use lock files
        return True, "Hatch does not use lock files"

    lock_file = get_lock_file_path(project_path, package_manager)

    # Only update if lock file exists (don't create new ones)
    if lock_file and not lock_file.exists():
        return True, f"No {lock_file.name} found, skipping lock update"

    cmd = LOCK_COMMANDS.get(package_manager)
    if cmd is None:
        return False, f"No lock command for {package_manager.value}"

    # Check if the tool is available
    if shutil.which(cmd[0]) is None:
        return False, f"{cmd[0]} not found in PATH"

    try:
        subprocess.run(
            cmd,
            cwd=project_path,
            capture_output=True,
            text=True,
            check=True,
        )
    except subprocess.CalledProcessError as e:
        return False, f"Lock update failed: {e.stderr}"
    except FileNotFoundError:
        return False, f"{cmd[0]} not found"
    else:
        return True, f"Updated {lock_file.name if lock_file else 'lock file'}"


def should_update_lock_file(project_path: Path) -> bool:
    """Check if the project has a lock file that should be updated.

    Args:
        project_path: Path to the project root

    Returns:
        True if a lock file exists and should be updated
    """
    package_manager = detect_package_manager(project_path)

    if package_manager in (PackageManager.UNKNOWN, PackageManager.HATCH):
        return False

    lock_file = get_lock_file_path(project_path, package_manager)
    return lock_file is not None and lock_file.exists()

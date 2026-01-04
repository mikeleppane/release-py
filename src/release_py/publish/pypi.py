"""PyPI publishing via uv or twine.

This module provides functionality for building and publishing
Python packages to PyPI using either uv or twine.

uv is preferred as it's faster and has better UX, but twine
is supported as a fallback.
"""

from __future__ import annotations

import shutil
import subprocess
from typing import TYPE_CHECKING

from release_py.exceptions import BuildError, PublishError, UploadError

if TYPE_CHECKING:
    from pathlib import Path

    from release_py.config.models import PublishConfig


def build_package(
    project_path: Path,
    *,
    clean: bool = True,
    custom_command: str | None = None,
    version: str | None = None,
) -> list[Path]:
    """Build the package using uv, hatch, or a custom command.

    Args:
        project_path: Path to the project directory
        clean: Whether to clean dist/ before building
        custom_command: Custom build command (supports {version}, {project_path} variables)
        version: Version being built (for template substitution)

    Returns:
        List of paths to built distribution files

    Raises:
        BuildError: If the build fails
    """
    dist_dir = project_path / "dist"

    # Clean dist directory if requested
    if clean and dist_dir.exists():
        shutil.rmtree(dist_dir)

    # Use custom command if provided
    if custom_command:
        # Substitute template variables
        template_vars = {
            "version": version or "",
            "project_path": str(project_path),
        }
        expanded_cmd = custom_command.format(**template_vars)

        try:
            subprocess.run(
                expanded_cmd,
                shell=True,
                cwd=project_path,
                capture_output=True,
                text=True,
                check=True,
            )
        except subprocess.CalledProcessError as e:
            raise BuildError(f"Custom build command failed:\n{e.stderr}") from e
    else:
        # Try uv first, then hatch, then python -m build
        build_commands = [
            (["uv", "build"], "uv"),
            (["hatch", "build"], "hatch"),
            (["python", "-m", "build"], "python-build"),
        ]

        for cmd, tool_name in build_commands:
            if shutil.which(cmd[0]) is not None:
                try:
                    subprocess.run(
                        cmd,
                        cwd=project_path,
                        capture_output=True,
                        text=True,
                        check=True,
                    )
                    break
                except subprocess.CalledProcessError as e:
                    raise BuildError(f"Build with {tool_name} failed:\n{e.stderr}") from e
        else:
            raise BuildError("No build tool found. Install one of: uv, hatch, or build")

    # Find built files
    if not dist_dir.exists():
        raise BuildError("Build completed but dist/ directory not found")

    dist_files = list(dist_dir.glob("*.whl")) + list(dist_dir.glob("*.tar.gz"))

    if not dist_files:
        raise BuildError("Build completed but no distribution files found in dist/")

    return dist_files


def publish_package(
    project_path: Path,
    config: PublishConfig,
    *,
    dist_files: list[Path] | None = None,
) -> None:
    """Publish the package to PyPI.

    Uses the tool specified in config (uv or twine).
    For trusted publishing (OIDC), no token is needed.

    Args:
        project_path: Path to the project directory
        config: Publishing configuration
        dist_files: Specific files to publish. If None, publishes all in dist/

    Raises:
        PublishError: If publishing fails
    """
    if not config.enabled:
        return

    dist_dir = project_path / "dist"

    if dist_files is None:
        dist_files = list(dist_dir.glob("*.whl")) + list(dist_dir.glob("*.tar.gz"))

    if not dist_files:
        raise PublishError("No distribution files to publish")

    # Use configured tool
    if config.tool == "uv":
        _publish_with_uv(dist_files, config)
    else:
        _publish_with_twine(dist_files, config)


def _publish_with_uv(dist_files: list[Path], config: PublishConfig) -> None:
    """Publish using uv publish."""
    if shutil.which("uv") is None:
        raise PublishError("uv not found. Install with: pip install uv")

    cmd = ["uv", "publish"]

    # Add registry if not default PyPI
    if config.registry != "https://upload.pypi.org/legacy/":
        cmd.extend(["--publish-url", config.registry])

    # Add files
    cmd.extend(str(f) for f in dist_files)

    try:
        subprocess.run(
            cmd,
            capture_output=True,
            text=True,
            check=True,
        )
    except subprocess.CalledProcessError as e:
        if "already exists" in e.stderr.lower():
            raise UploadError("This version has already been published to PyPI") from e
        raise UploadError(f"uv publish failed:\n{e.stderr}") from e


def _publish_with_twine(dist_files: list[Path], config: PublishConfig) -> None:
    """Publish using twine."""
    if shutil.which("twine") is None:
        raise PublishError("twine not found. Install with: pip install twine")

    cmd = [
        "twine",
        "upload",
        "--repository-url",
        config.registry,
    ]

    # Add files
    cmd.extend(str(f) for f in dist_files)

    try:
        subprocess.run(
            cmd,
            capture_output=True,
            text=True,
            check=True,
        )
    except subprocess.CalledProcessError as e:
        if "already exists" in e.stderr.lower():
            raise UploadError("This version has already been published to PyPI") from e
        raise UploadError(f"twine upload failed:\n{e.stderr}") from e


def check_pypi_version_exists(
    package_name: str,
    version: str,
) -> bool:
    """Check if a version is already published to PyPI.

    Args:
        package_name: Name of the package
        version: Version to check

    Returns:
        True if the version exists on PyPI
    """
    import httpx

    url = f"https://pypi.org/pypi/{package_name}/{version}/json"

    try:
        response = httpx.get(url, timeout=10)
    except httpx.HTTPError:
        return False
    else:
        return response.status_code == 200

"""Project type detection.

This module detects the type of Python project based on the files
present in the project directory.

Supported project types:
- pyproject.toml (PEP 517/518/621)
- setup.py (legacy setuptools)
- setup.cfg (declarative setuptools)
"""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

from release_py.exceptions import ProjectNotFoundError

# Common locations for version files
_VERSION_FILE_LOCATIONS = [
    ("src", "/__init__.py"),
    ("src", ".py"),
    (".", "/__init__.py"),
    (".", ".py"),
]


@dataclass(frozen=True, slots=True)
class ProjectInfo:
    """Information about a detected Python project.

    Attributes:
        name: Project name
        version: Current version string
        path: Path to the project root
        project_type: Type of project file ('pyproject', 'setup.py', 'setup.cfg')
        build_backend: Build backend if detectable (e.g., 'hatchling', 'setuptools')
        pyproject_path: Path to pyproject.toml if present
    """

    name: str
    version: str
    path: Path
    project_type: str
    build_backend: str | None
    pyproject_path: Path | None


def detect_project(path: Path | None = None) -> ProjectInfo:
    """Detect and analyze a Python project.

    Attempts to detect the project type by checking for:
    1. pyproject.toml with [project] section (PEP 621)
    2. pyproject.toml with [tool.poetry] section (Poetry)
    3. setup.py
    4. setup.cfg with [metadata] section

    Args:
        path: Project directory path. Defaults to current directory.

    Returns:
        ProjectInfo with project details

    Raises:
        ProjectNotFoundError: If no Python project is found
    """
    project_path = (path or Path.cwd()).resolve()

    # Check for pyproject.toml first
    pyproject_path = project_path / "pyproject.toml"
    if pyproject_path.is_file():
        return _detect_pyproject(project_path, pyproject_path)

    # Check for setup.py
    setup_py_path = project_path / "setup.py"
    if setup_py_path.is_file():
        return _detect_setup_py(project_path, setup_py_path)

    # Check for setup.cfg
    setup_cfg_path = project_path / "setup.cfg"
    if setup_cfg_path.is_file():
        return _detect_setup_cfg(project_path, setup_cfg_path)

    raise ProjectNotFoundError(
        f"No Python project found at {project_path}. "
        "Expected pyproject.toml, setup.py, or setup.cfg."
    )


def _resolve_dynamic_version(
    data: dict[str, object],
    project_path: Path,
    build_backend: str | None,
) -> str:
    """Resolve dynamic version from various build backend configurations.

    Supports:
    - Hatchling: [tool.hatch.version] path
    - Setuptools: [tool.setuptools.dynamic] version.attr
    - Flit: [tool.flit.module] name (reads from __init__.py)
    - PDM: [tool.pdm.version] source

    Args:
        data: Parsed pyproject.toml data
        project_path: Path to the project root
        build_backend: Detected build backend name

    Returns:
        Version string or empty string if not found
    """
    tool = data.get("tool", {})
    if not isinstance(tool, dict):
        return ""

    # Try backend-specific resolution
    version = _resolve_backend_version(tool, project_path, build_backend)
    if version:
        return version

    # Fallback: try to find __version__ in common locations
    return _resolve_fallback_version(data, project_path)


def _get_nested_str(data: dict[str, object], *keys: str) -> str | None:
    """Safely get a nested string value from a dict."""
    current: object = data
    for key in keys:
        if not isinstance(current, dict):
            return None
        current = current.get(key)
    return current if isinstance(current, str) else None


def _get_nested_dict(data: dict[str, object], *keys: str) -> dict[str, object]:
    """Safely get a nested dict value, returning empty dict if not found."""
    current: object = data
    for key in keys:
        if not isinstance(current, dict):
            return {}
        current = current.get(key, {})
    return current if isinstance(current, dict) else {}


def _resolve_backend_version(
    tool: dict[str, object],
    project_path: Path,
    build_backend: str | None,
) -> str:
    """Resolve version from build backend configuration."""
    resolvers = {
        "hatchling": _resolve_hatchling_version,
        "setuptools": _resolve_setuptools_version,
        "flit": _resolve_flit_version,
        "pdm": _resolve_pdm_version,
    }

    if build_backend and build_backend in resolvers:
        return resolvers[build_backend](tool, project_path)
    return ""


def _resolve_hatchling_version(tool: dict[str, object], project_path: Path) -> str:
    """Resolve version from hatchling configuration."""
    if path := _get_nested_str(tool, "hatch", "version", "path"):
        return _read_version_from_python_file(project_path / path)
    return ""


def _resolve_setuptools_version(tool: dict[str, object], project_path: Path) -> str:
    """Resolve version from setuptools dynamic configuration."""
    version_config = _get_nested_dict(tool, "setuptools", "dynamic", "version")
    if not version_config:
        return ""

    # attr format: package.__version__
    if (attr := _get_nested_str(version_config, "attr")) and "." in attr:
        module_path = attr.rsplit(".", 1)[0]
        for base, suffix in _VERSION_FILE_LOCATIONS:
            full_path = project_path / base / f"{module_path.replace('.', '/')}{suffix}"
            if full_path.is_file():
                return _read_version_from_python_file(full_path)

    # file format: read from file
    if file_config := _get_nested_str(version_config, "file"):
        version_file = project_path / file_config
        if version_file.is_file():
            return version_file.read_text().strip()

    return ""


def _resolve_flit_version(tool: dict[str, object], project_path: Path) -> str:
    """Resolve version from flit configuration."""
    if name := _get_nested_str(tool, "flit", "module", "name"):
        for base in ["src", "."]:
            init_path = project_path / base / name / "__init__.py"
            if init_path.is_file():
                return _read_version_from_python_file(init_path)
    return ""


def _resolve_pdm_version(tool: dict[str, object], project_path: Path) -> str:
    """Resolve version from pdm configuration."""
    pdm_version = _get_nested_dict(tool, "pdm", "version")
    is_file_source = pdm_version.get("source") == "file"
    if is_file_source and (path := _get_nested_str(pdm_version, "path")):
        return _read_version_from_python_file(project_path / path)
    return ""


def _resolve_fallback_version(data: dict[str, object], project_path: Path) -> str:
    """Try to find version in common locations."""
    name = _get_nested_str(data, "project", "name")
    if not name:
        return ""

    project_name = name.replace("-", "_")
    for base, suffix in _VERSION_FILE_LOCATIONS:
        candidate = project_path / base / f"{project_name}{suffix}"
        if candidate.is_file() and (version := _read_version_from_python_file(candidate)):
            return version

    return ""


def _read_version_from_python_file(file_path: Path) -> str:
    """Read __version__ from a Python file.

    Args:
        file_path: Path to the Python file

    Returns:
        Version string or empty string if not found
    """
    import re

    if not file_path.is_file():
        return ""

    content = file_path.read_text()

    # Match __version__ = "..." or __version__ = '...'
    patterns = [
        r'^__version__\s*=\s*["\']([^"\']+)["\']',
        r'^VERSION\s*=\s*["\']([^"\']+)["\']',
    ]

    for pattern in patterns:
        match = re.search(pattern, content, re.MULTILINE)
        if match:
            return match.group(1)

    return ""


def _detect_pyproject(project_path: Path, pyproject_path: Path) -> ProjectInfo:
    """Detect project from pyproject.toml."""
    import tomllib

    with pyproject_path.open("rb") as f:
        data = tomllib.load(f)

    # Check for PEP 621 [project] section
    if "project" in data:
        project = data["project"]
        name = project.get("name", "")
        version = project.get("version", "")

        # Detect build backend
        build_backend = None
        build_system = data.get("build-system", {})
        if build_backend_str := build_system.get("build-backend"):
            # Extract the main backend name
            if "hatchling" in build_backend_str:
                build_backend = "hatchling"
            elif "setuptools" in build_backend_str:
                build_backend = "setuptools"
            elif "flit" in build_backend_str:
                build_backend = "flit"
            elif "pdm" in build_backend_str:
                build_backend = "pdm"
            elif "maturin" in build_backend_str:
                build_backend = "maturin"
            else:
                build_backend = build_backend_str.split(".")[0]

        # Handle dynamic version
        if not version and "dynamic" in project and "version" in project["dynamic"]:
            version = _resolve_dynamic_version(data, project_path, build_backend)

        return ProjectInfo(
            name=name,
            version=version,
            path=project_path,
            project_type="pyproject",
            build_backend=build_backend,
            pyproject_path=pyproject_path,
        )

    # Check for Poetry
    if "tool" in data and "poetry" in data["tool"]:
        poetry = data["tool"]["poetry"]
        return ProjectInfo(
            name=poetry.get("name", ""),
            version=poetry.get("version", ""),
            path=project_path,
            project_type="poetry",
            build_backend="poetry",
            pyproject_path=pyproject_path,
        )

    raise ProjectNotFoundError(
        "pyproject.toml found but missing [project] or [tool.poetry] section."
    )


def _detect_setup_py(project_path: Path, setup_py_path: Path) -> ProjectInfo:
    """Detect project from setup.py.

    Note: This is a best-effort detection that doesn't execute setup.py.
    It uses regex to find name and version in the file.
    """
    import re

    content = setup_py_path.read_text()

    # Try to find name
    name_match = re.search(r'name\s*=\s*["\']([^"\']+)["\']', content)
    name = name_match.group(1) if name_match else ""

    # Try to find version
    version_match = re.search(r'version\s*=\s*["\']([^"\']+)["\']', content)
    version = version_match.group(1) if version_match else ""

    return ProjectInfo(
        name=name,
        version=version,
        path=project_path,
        project_type="setup.py",
        build_backend="setuptools",
        pyproject_path=None,
    )


def _detect_setup_cfg(project_path: Path, setup_cfg_path: Path) -> ProjectInfo:
    """Detect project from setup.cfg."""
    import configparser

    config = configparser.ConfigParser()
    config.read(setup_cfg_path)

    name = config.get("metadata", "name", fallback="")
    version = config.get("metadata", "version", fallback="")

    return ProjectInfo(
        name=name,
        version=version,
        path=project_path,
        project_type="setup.cfg",
        build_backend="setuptools",
        pyproject_path=None,
    )


def detect_workspace_packages(path: Path | None = None) -> list[Path]:
    """Detect package directories in a monorepo.

    Looks for common monorepo patterns:
    - packages/*/pyproject.toml
    - libs/*/pyproject.toml
    - src/*/pyproject.toml

    Args:
        path: Root directory to search. Defaults to current directory.

    Returns:
        List of paths to detected packages
    """
    root_path = (path or Path.cwd()).resolve()
    packages: list[Path] = []

    # Common monorepo patterns
    patterns = [
        "packages/*/pyproject.toml",
        "libs/*/pyproject.toml",
        "src/*/pyproject.toml",
        "crates/*/pyproject.toml",
        "*/pyproject.toml",  # Direct subdirectories
    ]

    for pattern in patterns:
        for pyproject in root_path.glob(pattern):
            package_dir = pyproject.parent
            # Exclude common non-package directories
            if package_dir.name not in ("tests", "docs", "examples", "scripts"):
                packages.append(package_dir)

    return sorted(set(packages))

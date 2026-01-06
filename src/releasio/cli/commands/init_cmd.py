"""Implementation of the 'init' command.

The init command sets up releasio configuration in a project with an
interactive wizard that supports both quick and comprehensive modes.
"""

from __future__ import annotations

import re
import shutil
import subprocess
import tomllib
from dataclasses import dataclass, field
from enum import Enum
from pathlib import Path
from typing import TYPE_CHECKING

from rich.panel import Panel
from rich.prompt import Confirm, Prompt
from rich.rule import Rule
from rich.syntax import Syntax
from rich.table import Table

if TYPE_CHECKING:
    from rich.console import Console


# =============================================================================
# Enums and Data Classes
# =============================================================================


class WizardMode(Enum):
    """Wizard mode selection."""

    QUICK = "quick"
    COMPREHENSIVE = "comprehensive"


class OutputTarget(Enum):
    """Configuration output target."""

    PYPROJECT = "pyproject.toml"
    DOTFILE = ".releasio.toml"
    VISIBLE = "releasio.toml"


@dataclass
class WizardState:
    """Tracks wizard state and collected configuration."""

    # Wizard metadata
    mode: WizardMode = WizardMode.QUICK
    current_step: int = 1
    total_steps: int = 6
    output_target: OutputTarget = OutputTarget.PYPROJECT

    # Detected values
    detected_branch: str | None = None
    detected_tool: str | None = None
    detected_github_owner: str | None = None
    detected_github_repo: str | None = None
    detected_version: str | None = None
    detected_squash_merge: bool = False
    detected_monorepo: bool = False
    detected_monorepo_paths: list[str] = field(default_factory=list)

    # Core settings
    default_branch: str = "main"
    allow_dirty: bool = False

    # Version settings
    tag_prefix: str = "v"
    initial_version: str = "0.1.0"
    auto_detect_version_files: bool = False

    # Commit settings
    types_minor: list[str] = field(default_factory=lambda: ["feat"])
    types_patch: list[str] = field(default_factory=lambda: ["fix", "perf"])
    enable_gitmoji: bool = False

    # Changelog settings
    changelog_enabled: bool = True
    changelog_path: str = "CHANGELOG.md"
    use_github_prs: bool = False
    show_authors: bool = False
    show_first_time_contributors: bool = False
    use_emoji_headers: bool = True

    # GitHub settings
    github_owner: str | None = None
    github_repo: str | None = None
    github_api_url: str = "https://api.github.com"
    release_pr_branch: str = "releasio/release"
    release_pr_labels: list[str] = field(default_factory=lambda: ["release"])
    draft_releases: bool = False
    release_name_format: str = "{project} {tag}"
    release_assets: list[str] = field(default_factory=list)

    # Release body settings
    release_body_show_authors: bool = True
    release_body_include_contributors: bool = True
    release_body_include_installation: bool = True
    release_body_use_emojis: bool = True

    # Publish settings
    publish_enabled: bool = True
    publish_tool: str = "uv"
    publish_registry: str = "https://upload.pypi.org/legacy/"
    trusted_publishing: bool = True

    # Hooks
    pre_release_hook: str | None = None
    post_release_hook: str | None = None

    # Monorepo
    is_monorepo: bool = False
    monorepo_paths: list[str] = field(default_factory=list)
    monorepo_independent: bool = True

    # Security
    security_enabled: bool = False

    # Branch channels
    branches: dict[str, dict[str, str | bool]] = field(default_factory=dict)

    # Workflow options
    create_workflow: bool = True
    add_pr_check: bool = False


# =============================================================================
# Auto-Detection Functions
# =============================================================================


def _detect_squash_merge(project_path: Path) -> bool:
    """Detect if the project likely uses squash merging.

    Looks at recent commit messages for patterns like "(#123)" which
    indicate squash-merged PRs.
    """
    try:
        result = subprocess.run(
            ["git", "-C", str(project_path), "log", "--oneline", "-20"],
            capture_output=True,
            text=True,
            check=True,
        )
        commits = result.stdout.strip()
        if not commits:
            return False

        # Count commits with "(#123)" pattern (squash merge signature)
        squash_pattern = re.compile(r"\(#\d+\)")
        squash_count = len(squash_pattern.findall(commits))

        # If more than 30% of recent commits have PR numbers, likely squash merge
        total_commits = len(commits.split("\n"))
        if total_commits > 0 and squash_count / total_commits > 0.3:
            return True
    except (subprocess.CalledProcessError, FileNotFoundError):
        pass

    return False


def _detect_build_tool(project_path: Path) -> str | None:
    """Detect the build tool from lock files and pyproject.toml."""
    # Check for lock files (most reliable indicator)
    lock_file_tools = [
        ("uv.lock", "uv"),
        ("poetry.lock", "poetry"),
        ("pdm.lock", "pdm"),
    ]
    for lock_file, tool in lock_file_tools:
        if (project_path / lock_file).exists():
            return tool

    # Check pyproject.toml for build backend hints
    pyproject_path = project_path / "pyproject.toml"
    if pyproject_path.exists():
        try:
            with pyproject_path.open("rb") as f:
                data = tomllib.load(f)

            build_backend = data.get("build-system", {}).get("build-backend", "")
            for backend_name in ("poetry", "pdm"):
                if backend_name in build_backend:
                    return backend_name
        except (tomllib.TOMLDecodeError, OSError):
            pass

    # Default to uv if installed
    return "uv" if shutil.which("uv") else None


def _detect_github_remote(project_path: Path) -> tuple[str | None, str | None]:
    """Detect GitHub owner and repo from git remote."""
    try:
        result = subprocess.run(
            ["git", "-C", str(project_path), "remote", "get-url", "origin"],
            capture_output=True,
            text=True,
            check=True,
        )
        url = result.stdout.strip()

        # HTTPS format: https://github.com/owner/repo.git
        https_match = re.match(r"https://github\.com/([^/]+)/([^/.]+)(?:\.git)?", url)
        if https_match:
            return https_match.group(1), https_match.group(2)

        # SSH format: git@github.com:owner/repo.git
        ssh_match = re.match(r"git@github\.com:([^/]+)/([^/.]+)(?:\.git)?", url)
        if ssh_match:
            return ssh_match.group(1), ssh_match.group(2)
    except (subprocess.CalledProcessError, FileNotFoundError):
        pass

    return None, None


def _detect_default_branch(project_path: Path) -> str | None:
    """Detect the default branch (main or master)."""
    try:
        # First try to get current branch
        result = subprocess.run(
            ["git", "-C", str(project_path), "rev-parse", "--abbrev-ref", "HEAD"],
            capture_output=True,
            text=True,
            check=True,
        )
        current = result.stdout.strip()
        if current in ("main", "master"):
            return current

        # Check if main or master exists
        for branch in ("main", "master"):
            check_result = subprocess.run(
                ["git", "-C", str(project_path), "rev-parse", "--verify", f"refs/heads/{branch}"],
                capture_output=True,
                check=False,
            )
            if check_result.returncode == 0:
                return branch
    except (subprocess.CalledProcessError, FileNotFoundError):
        pass
    return None


def _detect_existing_version(project_path: Path) -> str | None:
    """Detect existing version from pyproject.toml."""
    pyproject_path = project_path / "pyproject.toml"
    if not pyproject_path.exists():
        return None

    try:
        with pyproject_path.open("rb") as f:
            data = tomllib.load(f)

        # PEP 621 format
        if "project" in data and "version" in data["project"]:
            version = data["project"]["version"]
            return str(version) if version else None

        # Poetry format
        if "tool" in data and "poetry" in data["tool"]:
            version = data["tool"]["poetry"].get("version")
            return str(version) if version else None
    except (tomllib.TOMLDecodeError, OSError):
        pass

    return None


def _detect_monorepo(project_path: Path) -> tuple[bool, list[str]]:
    """Detect if this is a monorepo and find package paths."""
    packages_dir = project_path / "packages"
    if packages_dir.is_dir():
        packages = [
            f"packages/{p.name}"
            for p in packages_dir.iterdir()
            if p.is_dir() and (p / "pyproject.toml").exists()
        ]
        if packages:
            return True, packages
    return False, []


def _check_existing_config(project_path: Path) -> str | None:
    """Check if releasio configuration already exists."""
    if (project_path / ".releasio.toml").exists():
        return ".releasio.toml"
    if (project_path / "releasio.toml").exists():
        return "releasio.toml"

    pyproject = project_path / "pyproject.toml"
    if pyproject.exists():
        try:
            with pyproject.open("rb") as f:
                data = tomllib.load(f)
            if data.get("tool", {}).get("releasio"):
                return "pyproject.toml"
        except (tomllib.TOMLDecodeError, OSError):
            pass

    return None


# =============================================================================
# UI Helper Functions
# =============================================================================


def _show_welcome_panel(console: Console) -> None:
    """Display the welcome panel."""
    console.print()
    console.print(
        Panel(
            "[bold]Welcome to releasio![/]\n\n"
            "This wizard will help you set up automated releases for your project.\n\n"
            "[dim]releasio analyzes your commits to automatically determine version bumps,\n"
            "generate changelogs, and publish to PyPI.[/]",
            title="[blue]Setup Wizard[/]",
            border_style="blue",
        )
    )
    console.print()


def _show_section_header(
    console: Console,
    title: str,
    step: int,
    total: int,
    description: str | None = None,
) -> None:
    """Display a section header with progress."""
    console.print()
    console.print(Rule(f"[bold blue]{title}[/] [dim][{step}/{total}][/]"))
    if description:
        console.print(f"[dim]{description}[/]")
    console.print()


def _show_detected_value(
    console: Console,
    name: str,
    value: str,
    source: str | None = None,
) -> None:
    """Show a detected value with its source."""
    source_text = f" [dim](from {source})[/]" if source else " [dim](auto-detected)[/]"
    console.print(f"  [green]Detected:[/] {name} = [cyan]{value}[/]{source_text}")


def _prompt_list(
    prompt_text: str,
    default: list[str] | None = None,
) -> list[str]:
    """Prompt for a comma-separated list."""
    default_str = ", ".join(default) if default else ""
    result = Prompt.ask(prompt_text, default=default_str)
    if not result.strip():
        return []
    return [item.strip() for item in result.split(",") if item.strip()]


def _show_config_preview(
    console: Console,
    config_toml: str,
    output_target: OutputTarget,
) -> None:
    """Display a syntax-highlighted preview of the configuration."""
    console.print()
    console.print(
        Panel(
            Syntax(config_toml, "toml", theme="monokai", line_numbers=False),
            title=f"[bold]Configuration Preview[/] - [cyan]{output_target.value}[/]",
            border_style="blue",
        )
    )
    console.print()


def _show_summary_table(console: Console, state: WizardState) -> None:
    """Show a summary table of selected options."""
    table = Table(title="Configuration Summary", show_header=True, header_style="bold")
    table.add_column("Setting", style="cyan")
    table.add_column("Value", style="green")

    table.add_row("Default Branch", state.default_branch)
    table.add_row("Tag Prefix", state.tag_prefix)
    table.add_row("Build Tool", state.publish_tool)
    table.add_row("PyPI Publishing", "Enabled" if state.publish_enabled else "Disabled")
    table.add_row("Changelog", "Enabled" if state.changelog_enabled else "Disabled")

    if state.github_owner and state.github_repo:
        table.add_row("GitHub Repo", f"{state.github_owner}/{state.github_repo}")

    table.add_row("Output File", state.output_target.value)

    console.print()
    console.print(table)


def _show_success_panel(console: Console, state: WizardState) -> None:
    """Show success message with next steps."""
    config_file = state.output_target.value

    console.print()
    console.print(
        Panel(
            "[bold green]Setup complete![/]\n\n"
            "[bold]Next steps:[/]\n"
            f"  1. Review the configuration in [cyan]{config_file}[/]\n"
            "  2. Make some commits using conventional commit format\n"
            "  3. Run [cyan]releasio check[/] to preview your first release\n"
            "  4. Run [cyan]releasio release-pr[/] to create a release PR\n\n"
            "[bold]Conventional Commit Format:[/]\n"
            "  [cyan]feat:[/] A new feature (minor version bump)\n"
            "  [cyan]fix:[/]  A bug fix (patch version bump)\n"
            "  [cyan]feat!:[/] Breaking change (major version bump)\n\n"
            "[dim]Documentation: https://github.com/mikeleppane/release-py[/]",
            title="[green]Success[/]",
            border_style="green",
        )
    )


# =============================================================================
# Section Functions
# =============================================================================


def _section_mode_selection(console: Console, state: WizardState) -> WizardState:
    """Mode selection section."""
    _show_section_header(
        console,
        "Setup Mode",
        1,
        state.total_steps,
        "Choose how detailed you want the configuration to be",
    )

    console.print("  [cyan]quick[/]         - Sensible defaults, minimal questions (recommended)")
    console.print("  [cyan]comprehensive[/] - Full customization of all options")
    console.print()

    mode = Prompt.ask(
        "Choose setup mode",
        choices=["quick", "comprehensive"],
        default="quick",
    )

    state.mode = WizardMode(mode)
    state.total_steps = 6 if state.mode == WizardMode.QUICK else 9

    return state


def _section_basic_settings(
    console: Console,
    state: WizardState,
) -> WizardState:
    """Basic settings section."""
    _show_section_header(
        console,
        "Basic Settings",
        2,
        state.total_steps,
        "Configure core release settings",
    )

    # Show detected values
    if state.detected_branch:
        _show_detected_value(console, "default_branch", state.detected_branch)
    if state.detected_version:
        _show_detected_value(console, "version", state.detected_version, "pyproject.toml")

    console.print()

    # Default branch
    state.default_branch = Prompt.ask(
        "Default branch for releases",
        default=state.detected_branch or "main",
    )

    # Tag prefix
    state.tag_prefix = Prompt.ask(
        "Git tag prefix (e.g., 'v' for 'v1.0.0')",
        default="v",
    )

    # Additional settings for comprehensive mode
    if state.mode == WizardMode.COMPREHENSIVE:
        state.initial_version = Prompt.ask(
            "Initial version for new projects",
            default="0.1.0",
        )

        state.allow_dirty = Confirm.ask(
            "Allow releases from dirty working directory?",
            default=False,
        )

    return state


def _section_commits(console: Console, state: WizardState) -> WizardState:
    """Commit configuration section (comprehensive mode only)."""
    _show_section_header(
        console,
        "Commit Configuration",
        3,
        state.total_steps,
        "Configure how commits map to version bumps",
    )

    console.print("[dim]Commit types determine version bumps:[/]")
    console.print("  [dim]MINOR: New features (e.g., feat)[/]")
    console.print("  [dim]PATCH: Bug fixes, improvements (e.g., fix, perf)[/]")
    console.print()

    state.types_minor = _prompt_list(
        "Commit types for MINOR bump (comma-separated)",
        default=["feat"],
    )

    state.types_patch = _prompt_list(
        "Commit types for PATCH bump (comma-separated)",
        default=["fix", "perf"],
    )

    state.enable_gitmoji = Confirm.ask(
        "Enable Gitmoji support? (e.g., :sparkles: for feat)",
        default=False,
    )

    return state


def _section_changelog(console: Console, state: WizardState) -> WizardState:
    """Changelog settings section."""
    step = 4 if state.mode == WizardMode.COMPREHENSIVE else 3

    _show_section_header(
        console,
        "Changelog Settings",
        step,
        state.total_steps,
        "Configure changelog generation",
    )

    state.changelog_enabled = Confirm.ask(
        "Enable changelog generation?",
        default=True,
    )

    if not state.changelog_enabled:
        return state

    state.changelog_path = Prompt.ask(
        "Changelog file path",
        default="CHANGELOG.md",
    )

    # Show squash merge detection
    if state.detected_squash_merge:
        console.print()
        console.print("  [yellow]Detected:[/] Your project appears to use squash merging")

    state.use_github_prs = Confirm.ask(
        "Use GitHub PRs for changelog? (recommended for squash merge)",
        default=state.detected_squash_merge,
    )

    if state.mode == WizardMode.COMPREHENSIVE:
        state.show_authors = Confirm.ask(
            "Show commit authors in changelog?",
            default=False,
        )

        state.show_first_time_contributors = Confirm.ask(
            "Highlight first-time contributors?",
            default=False,
        )

        state.use_emoji_headers = Confirm.ask(
            "Use emoji section headers? (e.g., ✨ Features)",
            default=True,
        )

    return state


def _section_github(console: Console, state: WizardState) -> WizardState:
    """GitHub integration section."""
    step = 5 if state.mode == WizardMode.COMPREHENSIVE else 4

    _show_section_header(
        console,
        "GitHub Integration",
        step,
        state.total_steps,
        "Configure GitHub repository settings",
    )

    # Show detected values
    if state.detected_github_owner and state.detected_github_repo:
        _show_detected_value(
            console,
            "repository",
            f"{state.detected_github_owner}/{state.detected_github_repo}",
            "git remote",
        )
        console.print()

        use_detected = Confirm.ask(
            "Use detected GitHub repository?",
            default=True,
        )

        if use_detected:
            state.github_owner = state.detected_github_owner
            state.github_repo = state.detected_github_repo
        else:
            state.github_owner = Prompt.ask("GitHub owner") or None
            state.github_repo = Prompt.ask("GitHub repo") or None
    else:
        console.print("  [dim]No GitHub remote detected[/]")
        console.print()
        state.github_owner = Prompt.ask("GitHub owner (leave empty to skip)", default="") or None
        if state.github_owner:
            state.github_repo = Prompt.ask("GitHub repo") or None

    if state.mode == WizardMode.COMPREHENSIVE and state.github_owner:
        console.print()

        is_enterprise = Confirm.ask(
            "Using GitHub Enterprise?",
            default=False,
        )
        if is_enterprise:
            state.github_api_url = Prompt.ask(
                "GitHub API URL",
                default="https://github.mycompany.com/api/v3",
            )

        state.release_pr_branch = Prompt.ask(
            "Release PR branch name",
            default="releasio/release",
        )

        state.draft_releases = Confirm.ask(
            "Create draft releases?",
            default=False,
        )

        assets_str = Prompt.ask(
            "Release assets (comma-separated glob patterns, or Enter to skip)",
            default="",
        )
        if assets_str.strip():
            state.release_assets = [a.strip() for a in assets_str.split(",") if a.strip()]

    return state


def _section_release_notes(console: Console, state: WizardState) -> WizardState:
    """Release notes customization section (comprehensive mode only)."""
    _show_section_header(
        console,
        "Release Notes",
        6,
        state.total_steps,
        "Customize GitHub release notes appearance",
    )

    state.release_body_show_authors = Confirm.ask(
        "Show author attribution? (e.g., 'by @username')",
        default=True,
    )

    state.release_body_include_contributors = Confirm.ask(
        "Include contributors section?",
        default=True,
    )

    state.release_body_include_installation = Confirm.ask(
        "Include installation instructions?",
        default=True,
    )

    state.release_body_use_emojis = Confirm.ask(
        "Use emojis in section headers?",
        default=True,
    )

    # Release name format
    console.print()
    console.print("[bold]Release Title Format[/]")
    console.print("[dim]How the release appears on GitHub (e.g., 'myapp v1.0.0')[/]")
    console.print()
    console.print("  Variables: {project}, {version}, {tag}")
    console.print("  Examples:")
    console.print("    {project} {tag}    → myapp v1.0.0 (default)")
    console.print("    {version}          → 1.0.0")
    console.print("    {project} {version} → myapp 1.0.0")
    console.print()

    state.release_name_format = Prompt.ask(
        "Release title format",
        default=state.release_name_format,
    )

    return state


def _section_publishing(console: Console, state: WizardState) -> WizardState:
    """Publishing settings section."""
    step = 7 if state.mode == WizardMode.COMPREHENSIVE else 3

    # In quick mode, this comes before changelog
    if state.mode == WizardMode.QUICK:
        step = 3

    _show_section_header(
        console,
        "Publishing Settings",
        step,
        state.total_steps,
        "Configure PyPI publishing",
    )

    # Show detected build tool
    if state.detected_tool:
        _show_detected_value(
            console,
            "build_tool",
            state.detected_tool,
            f"{state.detected_tool}.lock" if state.detected_tool != "uv" else "uv.lock",
        )
        console.print()

    state.publish_enabled = Confirm.ask(
        "Enable PyPI publishing?",
        default=True,
    )

    if not state.publish_enabled:
        return state

    state.publish_tool = Prompt.ask(
        "Build/publish tool",
        choices=["uv", "poetry", "pdm", "twine"],
        default=state.detected_tool or "uv",
    )

    if state.mode == WizardMode.COMPREHENSIVE:
        is_test_pypi = Confirm.ask(
            "Use TestPyPI? (for testing)",
            default=False,
        )
        if is_test_pypi:
            state.publish_registry = "https://test.pypi.org/legacy/"

        state.trusted_publishing = Confirm.ask(
            "Use trusted publishing (OIDC)? (recommended for GitHub Actions)",
            default=True,
        )

    return state


def _section_advanced(console: Console, state: WizardState) -> WizardState:
    """Advanced settings section (comprehensive mode only)."""
    _show_section_header(
        console,
        "Advanced Settings",
        8,
        state.total_steps,
        "Optional: Hooks, monorepo, and release channels",
    )

    configure_advanced = Confirm.ask(
        "Configure advanced settings?",
        default=False,
    )

    if not configure_advanced:
        return state

    # --- Hooks ---
    console.print()
    console.print("[bold]Release Hooks[/]")
    console.print("[dim]Commands to run at specific points in the release process[/]")
    console.print()

    state.pre_release_hook = (
        Prompt.ask(
            "Pre-release command (e.g., 'pytest', or Enter to skip)",
            default="",
        )
        or None
    )

    state.post_release_hook = (
        Prompt.ask(
            "Post-release command (e.g., 'mkdocs gh-deploy', or Enter to skip)",
            default="",
        )
        or None
    )

    # --- Monorepo ---
    console.print()
    console.print("[bold]Monorepo[/]")
    console.print("[dim]For projects with multiple packages[/]")
    console.print()

    if state.detected_monorepo:
        paths_display = ", ".join(state.detected_monorepo_paths)
        console.print(f"  [yellow]Detected:[/] packages at {paths_display}")

    state.is_monorepo = Confirm.ask(
        "Is this a monorepo?",
        default=state.detected_monorepo,
    )

    if state.is_monorepo:
        default_paths = ""
        if state.detected_monorepo_paths:
            default_paths = ", ".join(state.detected_monorepo_paths)
        paths_str = Prompt.ask(
            "Package paths (comma-separated)",
            default=default_paths,
        )
        state.monorepo_paths = [p.strip() for p in paths_str.split(",") if p.strip()]

        state.monorepo_independent = Confirm.ask(
            "Use independent versioning per package?",
            default=True,
        )

    # --- Multi-channel Releases ---
    console.print()
    console.print("[bold]Release Channels[/]")
    console.print("[dim]Configure pre-release branches (alpha, beta)[/]")
    console.print()

    configure_channels = Confirm.ask(
        "Configure release channels?",
        default=False,
    )

    if configure_channels:
        if Confirm.ask("Add beta channel?", default=False):
            beta_branch = Prompt.ask("Beta branch pattern", default="beta")
            state.branches["beta"] = {
                "match": beta_branch,
                "prerelease": True,
                "prerelease_token": "beta",
            }

        if Confirm.ask("Add alpha channel?", default=False):
            alpha_branch = Prompt.ask("Alpha branch pattern", default="alpha")
            state.branches["alpha"] = {
                "match": alpha_branch,
                "prerelease": True,
                "prerelease_token": "alpha",
            }

    return state


def _section_output(
    console: Console,
    state: WizardState,
) -> WizardState:
    """Output configuration and preview section."""
    step = state.total_steps

    _show_section_header(
        console,
        "Output & Preview",
        step,
        state.total_steps,
        "Choose output format and review configuration",
    )

    # Output target selection
    console.print("  [cyan]pyproject[/] - Add to pyproject.toml under [tool.releasio]")
    console.print("  [cyan]dotfile[/]   - Create .releasio.toml (hidden file)")
    console.print("  [cyan]visible[/]   - Create releasio.toml")
    console.print()

    output_choice = Prompt.ask(
        "Configuration file location",
        choices=["pyproject", "dotfile", "visible"],
        default="pyproject",
    )

    state.output_target = {
        "pyproject": OutputTarget.PYPROJECT,
        "dotfile": OutputTarget.DOTFILE,
        "visible": OutputTarget.VISIBLE,
    }[output_choice]

    # GitHub workflows
    console.print()
    state.create_workflow = Confirm.ask(
        "Create GitHub Actions workflow?",
        default=True,
    )

    if state.create_workflow:
        state.add_pr_check = Confirm.ask(
            "Add PR title validation workflow?",
            default=False,
        )

    # Generate and show preview
    config_toml = _generate_toml_config(state)
    _show_config_preview(console, config_toml, state.output_target)

    # Summary table
    _show_summary_table(console, state)

    return state


# =============================================================================
# Configuration Generation
# =============================================================================


def _generate_toml_config(state: WizardState) -> str:
    """Generate TOML configuration from wizard state."""
    lines: list[str] = []

    # Determine if we need the [tool.releasio] wrapper
    use_wrapper = state.output_target == OutputTarget.PYPROJECT
    prefix = "tool.releasio" if use_wrapper else ""

    def section(name: str) -> str:
        return f"[{prefix}.{name}]" if prefix else f"[{name}]"

    def root_section() -> str:
        return f"[{prefix}]" if prefix else ""

    # Root settings
    if use_wrapper:
        lines.append("[tool.releasio]")
    lines.append(f'default_branch = "{state.default_branch}"')
    if state.allow_dirty:
        lines.append("allow_dirty = true")

    # Version settings
    lines.append("")
    lines.append(section("version"))
    lines.append(f'tag_prefix = "{state.tag_prefix}"')
    if state.initial_version != "0.1.0":
        lines.append(f'initial_version = "{state.initial_version}"')
    if state.auto_detect_version_files:
        lines.append("auto_detect_version_files = true")

    # Commits settings
    lines.append("")
    lines.append(section("commits"))
    lines.append(f"types_minor = {_format_list(state.types_minor)}")
    lines.append(f"types_patch = {_format_list(state.types_patch)}")

    # Gitmoji parsers
    if state.enable_gitmoji:
        lines.append("")
        lines.append("# Gitmoji support")
        gitmoji_parsers = [
            ("sparkles", "feat", "Features"),
            ("bug", "fix", "Bug Fixes"),
            ("zap", "perf", "Performance"),
            ("memo", "docs", "Documentation"),
            ("recycle", "refactor", "Refactoring"),
        ]
        for emoji, commit_type, group in gitmoji_parsers:
            parser_key = "commits.commit_parsers"
            parser_section = f"{prefix}.{parser_key}" if prefix else parser_key
            lines.append(f"[[{parser_section}]]")
            lines.append(f'pattern = "^:{emoji}:\\\\s*(?P<description>.+)$"')
            lines.append(f'type = "{commit_type}"')
            lines.append(f'group = "{group}"')

    # Changelog settings
    if state.changelog_enabled:
        lines.append("")
        lines.append(section("changelog"))
        lines.append(f'path = "{state.changelog_path}"')
        if state.use_github_prs:
            lines.append("use_github_prs = true")
        if state.show_authors:
            lines.append("show_authors = true")
        if state.show_first_time_contributors:
            lines.append("show_first_time_contributors = true")

    # GitHub settings
    if state.github_owner or state.github_repo:
        lines.append("")
        lines.append(section("github"))
        if state.github_owner:
            lines.append(f'owner = "{state.github_owner}"')
        if state.github_repo:
            lines.append(f'repo = "{state.github_repo}"')
        if state.github_api_url != "https://api.github.com":
            lines.append(f'api_url = "{state.github_api_url}"')
        lines.append(f'release_pr_branch = "{state.release_pr_branch}"')
        lines.append(f"release_pr_labels = {_format_list(state.release_pr_labels)}")
        if state.draft_releases:
            lines.append("draft_releases = true")
        if state.release_name_format != "{project} {tag}":
            lines.append(f'release_name_format = "{state.release_name_format}"')
        if state.release_assets:
            lines.append(f"release_assets = {_format_list(state.release_assets)}")

        # Release body settings (only if non-default)
        if not state.release_body_show_authors:
            lines.append("release_body_show_authors = false")
        if not state.release_body_include_contributors:
            lines.append("release_body_include_contributors = false")
        if not state.release_body_include_installation:
            lines.append("release_body_include_installation = false")
        if not state.release_body_use_emojis:
            lines.append("release_body_use_emojis = false")

    # Publish settings
    lines.append("")
    lines.append(section("publish"))
    lines.append(f"enabled = {str(state.publish_enabled).lower()}")
    lines.append(f'tool = "{state.publish_tool}"')
    if state.publish_registry != "https://upload.pypi.org/legacy/":
        lines.append(f'registry = "{state.publish_registry}"')
    if not state.trusted_publishing:
        lines.append("trusted_publishing = false")

    # Hooks
    if state.pre_release_hook or state.post_release_hook:
        lines.append("")
        lines.append(section("hooks"))
        if state.pre_release_hook:
            lines.append(f'pre_release = ["{state.pre_release_hook}"]')
        if state.post_release_hook:
            lines.append(f'post_release = ["{state.post_release_hook}"]')

    # Monorepo
    if state.is_monorepo and state.monorepo_paths:
        lines.append("")
        lines.append(section("packages"))
        lines.append(f"paths = {_format_list(state.monorepo_paths)}")
        lines.append(f"independent = {str(state.monorepo_independent).lower()}")

    # Security
    if state.security_enabled:
        lines.append("")
        lines.append(section("security"))
        lines.append("enabled = true")

    # Branches
    for channel_name, channel_config in state.branches.items():
        lines.append("")
        branch_key = f"branches.{channel_name}"
        branch_section = f"{prefix}.{branch_key}" if prefix else branch_key
        lines.append(f"[{branch_section}]")
        lines.append(f'match = "{channel_config["match"]}"')
        lines.append(f"prerelease = {str(channel_config['prerelease']).lower()}")
        lines.append(f'prerelease_token = "{channel_config["prerelease_token"]}"')

    return "\n".join(lines)


def _format_list(items: list[str]) -> str:
    """Format a list for TOML output."""
    return "[" + ", ".join(f'"{item}"' for item in items) + "]"


def _generate_cliff_config() -> str:
    """Generate git-cliff configuration."""
    return '''
[tool.git-cliff.changelog]
header = """
# Changelog

All notable changes to this project will be documented in this file.

"""
body = """
{% if version %}\\
    ## [{{ version | trim_start_matches(pat="v") }}] - {{ timestamp | date(format="%Y-%m-%d") }}
{% else %}\\
    ## [Unreleased]
{% endif %}\\
{% for group, commits in commits | group_by(attribute="group") %}
    ### {{ group | striptags | trim | upper_first }}
    {% for commit in commits %}
        - {% if commit.scope %}*({{ commit.scope }})* {% endif %}\\
            {% if commit.breaking %}[**breaking**] {% endif %}\\
            {{ commit.message | upper_first }}\\
    {% endfor %}
{% endfor %}\\n
"""
trim = true

[tool.git-cliff.git]
conventional_commits = true
filter_unconventional = true
commit_parsers = [
    { message = "^feat", group = "✨ Features" },
    { message = "^fix", group = "🐛 Bug Fixes" },
    { message = "^doc", group = "📚 Documentation" },
    { message = "^perf", group = "⚡ Performance" },
    { message = "^refactor", group = "♻️ Refactoring" },
    { message = "^style", group = "💄 Style" },
    { message = "^test", group = "🧪 Testing" },
    { message = "^build", group = "📦 Build" },
    { message = "^ci", group = "🔧 CI" },
    { message = "^chore\\\\(release\\\\)", skip = true },
    { message = "^chore", group = "🔨 Chores" },
]
tag_pattern = "v[0-9].*"
'''


def _write_config_file(
    project_path: Path,
    state: WizardState,
    config_toml: str,
    console: Console,
    err_console: Console,
) -> None:
    """Write configuration to the appropriate file."""
    cliff_config = _generate_cliff_config()

    if state.output_target == OutputTarget.PYPROJECT:
        # Append to pyproject.toml
        pyproject_path = project_path / "pyproject.toml"
        try:
            with pyproject_path.open("a") as f:
                f.write("\n\n")
                f.write(config_toml)
                f.write("\n")
                f.write(cliff_config.strip())
                f.write("\n")
            console.print(f"  [green]✓[/] Updated [cyan]{pyproject_path}[/]")
        except OSError as e:
            err_console.print(f"[red]Error:[/] Failed to write to {pyproject_path}: {e}")
            raise SystemExit(1) from e
    else:
        # Write to separate config file
        config_file = project_path / state.output_target.value
        try:
            config_file.write_text(config_toml + "\n")
            console.print(f"  [green]✓[/] Created [cyan]{config_file}[/]")
        except OSError as e:
            err_console.print(f"[red]Error:[/] Failed to write to {config_file}: {e}")
            raise SystemExit(1) from e

        # Write cliff config to pyproject.toml (always needed there)
        pyproject_path = project_path / "pyproject.toml"
        try:
            with pyproject_path.open("a") as f:
                f.write("\n")
                f.write(cliff_config.strip())
                f.write("\n")
            console.print(f"  [green]✓[/] Added git-cliff config to [cyan]{pyproject_path}[/]")
        except OSError as e:
            err_console.print(f"[red]Error:[/] Failed to write to {pyproject_path}: {e}")
            raise SystemExit(1) from e


def _create_github_workflows(
    project_path: Path,
    state: WizardState,
    console: Console,
    err_console: Console,
) -> None:
    """Create GitHub Actions workflow files."""
    workflows_dir = project_path / ".github" / "workflows"
    try:
        workflows_dir.mkdir(parents=True, exist_ok=True)
    except OSError as e:
        err_console.print(f"[red]Error:[/] Failed to create {workflows_dir}: {e}")
        raise SystemExit(1) from e

    # Main release workflow
    workflow_path = workflows_dir / "release.yml"
    workflow_content = f"""name: Release

on:
  push:
    branches: [{state.default_branch}]
  pull_request:
    types: [closed]
    branches: [{state.default_branch}]

permissions:
  contents: write
  pull-requests: write
  id-token: write  # For PyPI trusted publishing

jobs:
  # Create/update Release PR on every push to {state.default_branch}
  release-pr:
    if: github.event_name == 'push'
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v4
        with:
          fetch-depth: 0  # Full history for changelog

      - name: Set up Python
        uses: actions/setup-python@v5
        with:
          python-version: "3.11"

      - name: Install uv
        uses: astral-sh/setup-uv@v5

      - name: Install releasio
        run: uv tool install releasio

      - name: Create Release PR
        env:
          GITHUB_TOKEN: ${{{{ secrets.GITHUB_TOKEN }}}}
        run: releasio release-pr

  # Perform release when Release PR is merged
  release:
    if: |
      github.event_name == 'pull_request' &&
      github.event.pull_request.merged == true &&
      contains(github.event.pull_request.labels.*.name, 'release')
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v4
        with:
          fetch-depth: 0

      - name: Set up Python
        uses: actions/setup-python@v5
        with:
          python-version: "3.11"

      - name: Install uv
        uses: astral-sh/setup-uv@v5

      - name: Install releasio
        run: uv tool install releasio

      - name: Perform Release
        env:
          GITHUB_TOKEN: ${{{{ secrets.GITHUB_TOKEN }}}}
        run: releasio release
"""

    try:
        workflow_path.write_text(workflow_content)
        console.print(f"  [green]✓[/] Created [cyan]{workflow_path}[/]")
    except OSError as e:
        err_console.print(f"[red]Error:[/] Failed to write {workflow_path}: {e}")
        raise SystemExit(1) from e

    # PR title check workflow
    if state.add_pr_check:
        pr_check_path = workflows_dir / "pr-title.yml"
        pr_check_content = """name: PR Title Check

on:
  pull_request:
    types: [opened, edited, synchronize, reopened]

jobs:
  check-title:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v4

      - name: Set up Python
        uses: actions/setup-python@v5
        with:
          python-version: "3.11"

      - name: Install uv
        uses: astral-sh/setup-uv@v5

      - name: Install releasio
        run: uv tool install releasio

      - name: Check PR Title
        env:
          GITHUB_PR_TITLE: ${{ github.event.pull_request.title }}
        run: releasio check-pr
"""
        try:
            pr_check_path.write_text(pr_check_content)
            console.print(f"  [green]✓[/] Created [cyan]{pr_check_path}[/]")
        except OSError as e:
            err_console.print(f"[red]Error:[/] Failed to write {pr_check_path}: {e}")
            raise SystemExit(1) from e


# =============================================================================
# Main Entry Point
# =============================================================================


def run_init(
    path: str | None,
    force: bool,
    console: Console,
    err_console: Console,
) -> None:
    """Run the init command with interactive wizard.

    Args:
        path: Optional path to project directory
        force: Whether to overwrite existing configuration
        console: Console for standard output
        err_console: Console for error output
    """
    project_path = Path(path) if path else Path.cwd()
    pyproject_path = project_path / "pyproject.toml"

    # Check if pyproject.toml exists
    if not pyproject_path.exists():
        err_console.print(
            "[red]Error:[/] No pyproject.toml found.\n"
            "Run this command from your project root, or use [cyan]uv init[/] first."
        )
        raise SystemExit(1)

    # Check for existing configuration
    existing_config = _check_existing_config(project_path)
    if existing_config and not force:
        console.print(
            f"[yellow]releasio is already configured in {existing_config}.[/]\n"
            "Use [cyan]--force[/] to overwrite the existing configuration."
        )
        return

    # Initialize wizard state with auto-detection
    state = WizardState()

    # Run auto-detection
    state.detected_branch = _detect_default_branch(project_path)
    state.detected_tool = _detect_build_tool(project_path)
    state.detected_github_owner, state.detected_github_repo = _detect_github_remote(project_path)
    state.detected_version = _detect_existing_version(project_path)
    state.detected_squash_merge = _detect_squash_merge(project_path)
    state.detected_monorepo, state.detected_monorepo_paths = _detect_monorepo(project_path)

    # Run wizard
    _show_welcome_panel(console)

    state = _section_mode_selection(console, state)
    state = _section_basic_settings(console, state)

    if state.mode == WizardMode.COMPREHENSIVE:
        state = _section_commits(console, state)

    # In quick mode, publishing comes before changelog for better flow
    if state.mode == WizardMode.QUICK:
        state = _section_publishing(console, state)
        state = _section_changelog(console, state)
        state = _section_github(console, state)
    else:
        state = _section_changelog(console, state)
        state = _section_github(console, state)
        state = _section_release_notes(console, state)
        state = _section_publishing(console, state)
        state = _section_advanced(console, state)

    state = _section_output(console, state)

    # Confirm and write
    console.print()
    if not Confirm.ask("Write configuration?", default=True):
        console.print("[yellow]Configuration cancelled.[/]")
        return

    console.print()
    console.print("[bold]Writing configuration...[/]")
    console.print()

    # Write configuration
    config_toml = _generate_toml_config(state)
    _write_config_file(project_path, state, config_toml, console, err_console)

    # Create workflows if requested
    if state.create_workflow:
        _create_github_workflows(project_path, state, console, err_console)

    # Show success message
    _show_success_panel(console, state)

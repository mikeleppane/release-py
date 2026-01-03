"""Implementation of the 'update' command.

The update command modifies version and changelog locally.
"""

from __future__ import annotations

from pathlib import Path
from typing import TYPE_CHECKING

from rich.panel import Panel

from release_py.config import load_config
from release_py.core.commits import calculate_bump, filter_skip_release_commits, parse_commits
from release_py.core.version import BumpType, Version
from release_py.vcs import GitRepository

if TYPE_CHECKING:
    from rich.console import Console


def run_update(
    path: str | None,
    execute: bool,
    version_override: str | None,
    prerelease: str | None,
    console: Console,
    err_console: Console,
) -> None:
    """Run the update command.

    Args:
        path: Optional path to project directory
        execute: Whether to actually apply changes
        version_override: Manual version override (e.g., "2.0.0")
        prerelease: Pre-release identifier (e.g., "alpha", "beta", "rc")
        console: Console for standard output
        err_console: Console for error output
    """
    project_path = Path(path) if path else Path.cwd()

    # Load configuration
    try:
        config = load_config(project_path)
    except Exception as e:
        err_console.print(f"[red]Error loading config:[/] {e}")
        raise SystemExit(1) from e

    # Initialize git repository
    try:
        repo = GitRepository(project_path)
    except Exception as e:
        err_console.print(f"[red]Error:[/] {e}")
        raise SystemExit(1) from e

    # Check for dirty working directory
    if not config.allow_dirty and repo.is_dirty():
        err_console.print(
            "[red]Error:[/] Repository has uncommitted changes.\n"
            "Commit or stash them, or use [cyan]allow_dirty = true[/] in config."
        )
        raise SystemExit(1)

    # Get current version
    from release_py.config.loader import get_project_version

    try:
        current_version_str = get_project_version(project_path)
        current_version = Version.parse(current_version_str)
    except Exception as e:
        err_console.print(f"[red]Error getting version:[/] {e}")
        raise SystemExit(1) from e

    # Get latest tag
    tag_pattern = f"{config.effective_tag_prefix}*"
    latest_tag = repo.get_latest_tag(tag_pattern)

    # Detect first release (no existing tags)
    is_first_release = latest_tag is None

    # Get commits since last tag
    commits = repo.get_commits_since_tag(latest_tag)

    if not commits:
        console.print("[yellow]No commits found since last release. Nothing to do.[/]")
        return

    # Filter out commits with skip release markers
    commits = filter_skip_release_commits(commits, config.commits.skip_release_patterns)

    if not commits:
        console.print("[yellow]All commits have skip release markers. Nothing to do.[/]")
        return

    # Parse commits and calculate bump
    parsed = parse_commits(commits, config.commits)
    bump_type = calculate_bump(parsed, config.commits)

    # Handle manual version override
    if version_override:
        try:
            next_version = Version.parse(version_override)
        except Exception as e:
            err_console.print(f"[red]Invalid version format:[/] {e}")
            raise SystemExit(1) from e
    elif is_first_release:
        # Use initial_version for first release
        next_version = Version.parse(config.version.initial_version)
    else:
        # Prevent empty releases (no meaningful changes)
        if bump_type == BumpType.NONE:
            console.print(
                "[yellow]No releasable changes found (only non-release commit types).[/]\n"
                "[dim]Use [cyan]--version[/] to force a specific version.[/]"
            )
            return

        # Calculate next version
        next_version = current_version.bump(bump_type)

    # Apply pre-release identifier if specified
    effective_prerelease = prerelease or config.version.pre_release
    if effective_prerelease:
        next_version = next_version.with_prerelease(effective_prerelease)

    mode_str = "[green]EXECUTING[/]" if execute else "[yellow]DRY-RUN[/]"
    if is_first_release:
        console.print(
            f"\n{mode_str} - 🎉 First release! Setting version to [green]{next_version}[/]\n"
        )
    else:
        console.print(
            f"\n{mode_str} - Updating from [cyan]{current_version}[/] to [green]{next_version}[/]\n"
        )

    if not execute:
        console.print(
            Panel(
                "[bold]Would make the following changes:[/]\n\n"
                f"  • Update version in [cyan]pyproject.toml[/]\n"
                f"  • Generate changelog in [cyan]{config.effective_changelog_path}[/]",
                title="[yellow]Dry Run Preview[/]",
                border_style="yellow",
            )
        )
        console.print("\n[dim]Run with [cyan]--execute[/] to apply these changes.[/]")
        return

    # Run pre-bump hooks
    if config.hooks.pre_bump:
        _run_hooks(
            config.hooks.pre_bump,
            project_path,
            current_version,
            next_version,
            bump_type,
            console,
            err_console,
            "pre-bump",
        )

    # Actually apply changes
    from release_py.project.pyproject import update_pyproject_version, update_version_file

    try:
        update_pyproject_version(project_path, str(next_version))
        console.print("  [green]✓[/] Updated version in pyproject.toml")
    except Exception as e:
        err_console.print(f"[red]Error updating pyproject.toml:[/] {e}")
        raise SystemExit(1) from e

    # Update additional version files
    for version_file in config.version.version_files:
        version_file_path = project_path / version_file
        try:
            update_version_file(version_file_path, str(next_version))
            console.print(f"  [green]✓[/] Updated version in {version_file}")
        except Exception as e:
            err_console.print(f"[red]Error updating {version_file}:[/] {e}")
            raise SystemExit(1) from e

    # Generate changelog
    try:
        from release_py.core.changelog import generate_changelog

        changelog_content = generate_changelog(
            repo=repo,
            version=next_version,
            config=config,
        )

        # Write changelog
        changelog_path = project_path / config.effective_changelog_path
        if changelog_path.exists():
            existing = changelog_path.read_text()
            # Insert new content after header
            # This is a simplified approach; git-cliff handles this better
            new_content = changelog_content + "\n" + existing
        else:
            new_content = changelog_content

        changelog_path.write_text(new_content)
        console.print(f"  [green]✓[/] Updated {config.effective_changelog_path}")
    except Exception as e:
        err_console.print(f"[red]Error generating changelog:[/] {e}")
        raise SystemExit(1) from e

    # Run post-bump hooks
    if config.hooks.post_bump:
        _run_hooks(
            config.hooks.post_bump,
            project_path,
            current_version,
            next_version,
            bump_type,
            console,
            err_console,
            "post-bump",
        )

    console.print(
        Panel(
            f"[green]Successfully updated to version {next_version}![/]\n\n"
            "Next steps:\n"
            "  1. Review the changes\n"
            f"  2. Commit: [cyan]git add . && git commit -m "
            f"'chore(release): prepare {next_version}'[/]\n"
            "  3. Release: [cyan]release-py release[/]",
            title="[green]Update Complete[/]",
            border_style="green",
        )
    )


def _run_hooks(
    hooks: list[str],
    project_path: Path,
    prev_version: Version,
    new_version: Version,
    bump_type: BumpType,
    console: Console,
    err_console: Console,
    hook_name: str,
) -> None:
    """Run hook commands with template variable substitution.

    Args:
        hooks: List of shell commands to run
        project_path: Working directory for commands
        prev_version: Previous version
        new_version: New version
        bump_type: Type of version bump
        console: Console for output
        err_console: Console for error output
        hook_name: Name of the hook phase (for logging)
    """
    import subprocess

    template_vars = {
        "version": str(new_version),
        "prev_version": str(prev_version),
        "bump_type": str(bump_type),
    }

    for cmd in hooks:
        # Substitute template variables
        expanded_cmd = cmd.format(**template_vars)
        console.print(f"  [dim]Running {hook_name} hook:[/] {expanded_cmd}")

        try:
            result = subprocess.run(
                expanded_cmd,
                shell=True,
                cwd=project_path,
                capture_output=True,
                text=True,
                check=True,
            )
            if result.stdout:
                console.print(f"    [dim]{result.stdout.strip()}[/]")
        except subprocess.CalledProcessError as e:
            err_console.print(f"[red]Hook failed:[/] {expanded_cmd}")
            if e.stderr:
                err_console.print(f"[red]{e.stderr}[/]")
            raise SystemExit(1) from e

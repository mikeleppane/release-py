"""Core business logic for release-py.

This module contains the fundamental building blocks:
- Version parsing and manipulation (PEP 440 compliant)
- Conventional commit parsing
- Changelog generation via git-cliff
- Release orchestration
"""

from __future__ import annotations

from release_py.core.changelog import generate_changelog, generate_fallback_changelog
from release_py.core.commits import (
    ParsedCommit,
    calculate_bump,
    format_commit_for_changelog,
    get_breaking_changes,
    group_commits_by_type,
    parse_commits,
)
from release_py.core.version import BumpType, PreRelease, Version, parse_version

__all__ = [
    # Version
    "BumpType",
    # Commits
    "ParsedCommit",
    "PreRelease",
    "Version",
    "calculate_bump",
    "format_commit_for_changelog",
    # Changelog
    "generate_changelog",
    "generate_fallback_changelog",
    "get_breaking_changes",
    "group_commits_by_type",
    "parse_commits",
    "parse_version",
]

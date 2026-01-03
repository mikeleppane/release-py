"""Git forge integrations (GitHub, GitLab, Gitea).

This module provides abstractions for interacting with git forges
(hosting platforms like GitHub, GitLab, and Gitea) for:
- Creating and updating pull/merge requests
- Creating releases
- Managing labels and comments

The Forge protocol defines the interface that all forge implementations
must follow, enabling easy extensibility to new platforms.
"""

from __future__ import annotations

from release_py.forge.base import Forge, MergeRequest, Release
from release_py.forge.github import GitHubClient

__all__ = [
    "Forge",
    "GitHubClient",
    "MergeRequest",
    "Release",
]

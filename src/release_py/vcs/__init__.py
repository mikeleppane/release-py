"""Version control system operations.

This module provides abstractions for interacting with git repositories,
including commit history, tagging, and branch operations.
"""

from __future__ import annotations

from release_py.vcs.git import Commit, GitRepository

__all__ = [
    "Commit",
    "GitRepository",
]

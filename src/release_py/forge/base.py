"""Base protocol and models for git forge integrations.

This module defines the Forge protocol that all forge implementations
(GitHub, GitLab, Gitea) must follow. It also defines the data models
for pull requests and releases.

To add support for a new forge:
1. Create a new module (e.g., gitlab.py)
2. Implement a class that follows the Forge protocol
3. Register it in __init__.py
"""

from __future__ import annotations

from dataclasses import dataclass
from enum import Enum
from typing import Protocol, runtime_checkable


class MergeRequestState(Enum):
    """State of a pull/merge request."""

    OPEN = "open"
    CLOSED = "closed"
    MERGED = "merged"


@dataclass(frozen=True, slots=True)
class MergeRequest:
    """Represents a pull request (GitHub) or merge request (GitLab).

    Uses 'MergeRequest' as the common term following GitLab naming,
    but represents both PR and MR concepts.

    Attributes:
        number: The PR/MR number
        title: Title of the request
        body: Description/body text
        head_branch: Source branch name
        base_branch: Target branch name
        url: Web URL to the request
        state: Current state (open, closed, merged)
        labels: List of label names
    """

    number: int
    title: str
    body: str
    head_branch: str
    base_branch: str
    url: str
    state: MergeRequestState
    labels: list[str]


@dataclass(frozen=True, slots=True)
class Release:
    """Represents a release on a git forge.

    Attributes:
        tag: Git tag for this release
        name: Release name/title
        body: Release notes/description
        url: Web URL to the release
        draft: Whether this is a draft release
        prerelease: Whether this is a pre-release
        assets: List of asset URLs
        id: Release ID from the forge API (used for uploading assets)
    """

    tag: str
    name: str
    body: str
    url: str
    draft: bool
    prerelease: bool
    assets: list[str]
    id: int | None = None


@runtime_checkable
class Forge(Protocol):
    """Protocol defining the interface for git forge integrations.

    All forge implementations (GitHub, GitLab, Gitea) must implement
    this protocol. Methods are async to support efficient API calls.

    Example:
        >>> class MyForge:
        ...     async def find_merge_request(self, head: str, base: str) -> MergeRequest | None:
        ...         ...
        >>> forge: Forge = MyForge()  # Type checks!
    """

    async def find_merge_request(
        self,
        head: str,
        base: str,
    ) -> MergeRequest | None:
        """Find an open merge request for the given branches.

        Args:
            head: Source branch name
            base: Target branch name

        Returns:
            MergeRequest if found, None otherwise
        """
        ...

    async def create_merge_request(
        self,
        title: str,
        body: str,
        head: str,
        base: str,
        labels: list[str] | None = None,
    ) -> MergeRequest:
        """Create a new merge request.

        Args:
            title: MR title
            body: MR description
            head: Source branch
            base: Target branch
            labels: Optional list of labels to apply

        Returns:
            The created MergeRequest
        """
        ...

    async def update_merge_request(
        self,
        number: int,
        title: str | None = None,
        body: str | None = None,
    ) -> MergeRequest:
        """Update an existing merge request.

        Args:
            number: MR number to update
            title: New title (optional)
            body: New description (optional)

        Returns:
            The updated MergeRequest
        """
        ...

    async def create_release(
        self,
        tag: str,
        name: str,
        body: str,
        draft: bool = False,
        prerelease: bool = False,
    ) -> Release:
        """Create a new release.

        Args:
            tag: Git tag for the release
            name: Release name
            body: Release notes
            draft: Create as draft
            prerelease: Mark as pre-release

        Returns:
            The created Release
        """
        ...

    async def get_release_by_tag(self, tag: str) -> Release | None:
        """Get a release by its tag.

        Args:
            tag: Tag to look up

        Returns:
            Release if found, None otherwise
        """
        ...

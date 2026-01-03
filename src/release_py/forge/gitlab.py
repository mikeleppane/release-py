"""GitLab API client implementation (placeholder).

This module provides a placeholder for the GitLab API client.
It implements the Forge protocol but raises NotImplementedError
for all methods until fully implemented.

TODO: Implement GitLab support in a future version.
"""

from __future__ import annotations

from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from release_py.forge.base import MergeRequest, Release


class GitLabClient:
    """Async GitLab API client (placeholder).

    This is a placeholder implementation for GitLab support.
    All methods raise NotImplementedError until fully implemented.

    Args:
        host: GitLab host URL (e.g., 'https://gitlab.com')
        project_id: GitLab project ID or path
        token: GitLab personal access token

    Example:
        >>> client = GitLabClient(
        ...     host="https://gitlab.com",
        ...     project_id="user/project",
        ... )
    """

    def __init__(
        self,
        host: str = "https://gitlab.com",
        project_id: str | int = "",
        token: str | None = None,
    ) -> None:
        self.host = host.rstrip("/")
        self.project_id = project_id
        self._token = token

    async def find_merge_request(
        self,
        head: str,
        base: str,
    ) -> MergeRequest | None:
        """Find an open merge request for the given branches.

        Note:
            GitLab support is not yet implemented.

        Raises:
            NotImplementedError: GitLab support coming soon
        """
        raise NotImplementedError(
            "GitLab support is not yet implemented. "
            "Contributions welcome at https://github.com/mikeleppane/release-py"
        )

    async def create_merge_request(
        self,
        title: str,
        body: str,
        head: str,
        base: str,
        labels: list[str] | None = None,
    ) -> MergeRequest:
        """Create a new merge request.

        Note:
            GitLab support is not yet implemented.

        Raises:
            NotImplementedError: GitLab support coming soon
        """
        raise NotImplementedError(
            "GitLab support is not yet implemented. "
            "Contributions welcome at https://github.com/mikeleppane/release-py"
        )

    async def update_merge_request(
        self,
        number: int,
        title: str | None = None,
        body: str | None = None,
    ) -> MergeRequest:
        """Update an existing merge request.

        Note:
            GitLab support is not yet implemented.

        Raises:
            NotImplementedError: GitLab support coming soon
        """
        raise NotImplementedError(
            "GitLab support is not yet implemented. "
            "Contributions welcome at https://github.com/mikeleppane/release-py"
        )

    async def create_release(
        self,
        tag: str,
        name: str,
        body: str,
        draft: bool = False,
        prerelease: bool = False,
    ) -> Release:
        """Create a new release.

        Note:
            GitLab support is not yet implemented.

        Raises:
            NotImplementedError: GitLab support coming soon
        """
        raise NotImplementedError(
            "GitLab support is not yet implemented. "
            "Contributions welcome at https://github.com/mikeleppane/release-py"
        )

    async def get_release_by_tag(self, tag: str) -> Release | None:
        """Get a release by its tag.

        Note:
            GitLab support is not yet implemented.

        Raises:
            NotImplementedError: GitLab support coming soon
        """
        raise NotImplementedError(
            "GitLab support is not yet implemented. "
            "Contributions welcome at https://github.com/mikeleppane/release-py"
        )

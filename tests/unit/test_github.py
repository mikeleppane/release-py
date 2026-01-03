"""Unit tests for GitHub API client."""

from __future__ import annotations

from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from release_py.exceptions import AuthenticationError, ForgeError, RateLimitError
from release_py.forge.base import MergeRequestState
from release_py.forge.github import GitHubClient


class TestGitHubClientInit:
    """Tests for GitHubClient initialization."""

    def test_init_with_token(self):
        """Initialize with explicit token."""
        client = GitHubClient(owner="owner", repo="repo", token="test-token")
        assert client.owner == "owner"
        assert client.repo == "repo"
        assert client._token == "test-token"
        assert client.base_url == "https://api.github.com"

    def test_init_with_custom_api_url(self):
        """Initialize with custom API URL for GitHub Enterprise."""
        client = GitHubClient(
            owner="owner",
            repo="repo",
            token="test-token",
            api_url="https://github.mycompany.com/api/v3",
        )
        assert client.base_url == "https://github.mycompany.com/api/v3"

    def test_init_strips_trailing_slash_from_api_url(self):
        """Trailing slash is stripped from API URL."""
        client = GitHubClient(
            owner="owner",
            repo="repo",
            token="test-token",
            api_url="https://github.mycompany.com/api/v3/",
        )
        assert client.base_url == "https://github.mycompany.com/api/v3"

    def test_init_from_env_github_token(self, monkeypatch: pytest.MonkeyPatch):
        """Initialize with GITHUB_TOKEN env var."""
        monkeypatch.setenv("GITHUB_TOKEN", "env-token")
        client = GitHubClient(owner="owner", repo="repo")
        assert client._token == "env-token"

    def test_init_from_env_gh_token(self, monkeypatch: pytest.MonkeyPatch):
        """Initialize with GH_TOKEN env var."""
        monkeypatch.delenv("GITHUB_TOKEN", raising=False)
        monkeypatch.setenv("GH_TOKEN", "gh-token")
        client = GitHubClient(owner="owner", repo="repo")
        assert client._token == "gh-token"

    def test_init_from_gh_cli(self, monkeypatch: pytest.MonkeyPatch):
        """Initialize with gh CLI token."""
        monkeypatch.delenv("GITHUB_TOKEN", raising=False)
        monkeypatch.delenv("GH_TOKEN", raising=False)

        with patch("subprocess.run") as mock_run:
            mock_run.return_value = MagicMock(
                stdout="cli-token\n",
                returncode=0,
            )
            client = GitHubClient(owner="owner", repo="repo")
            assert client._token == "cli-token"

    def test_init_no_token_raises(self, monkeypatch: pytest.MonkeyPatch):
        """Raise AuthenticationError when no token available."""
        monkeypatch.delenv("GITHUB_TOKEN", raising=False)
        monkeypatch.delenv("GH_TOKEN", raising=False)

        with patch("subprocess.run") as mock_run:
            mock_run.side_effect = FileNotFoundError("gh not found")
            with pytest.raises(AuthenticationError, match="No GitHub token found"):
                GitHubClient(owner="owner", repo="repo")


class TestGitHubClientHeaders:
    """Tests for request headers."""

    def test_get_headers(self):
        """Headers include auth and API version."""
        client = GitHubClient(owner="owner", repo="repo", token="test-token")
        headers = client._get_headers()

        assert headers["Authorization"] == "Bearer test-token"
        assert headers["Accept"] == "application/vnd.github+json"
        assert "X-GitHub-Api-Version" in headers


class TestGitHubClientRequest:
    """Tests for _request method."""

    @pytest.mark.asyncio
    async def test_request_success(self):
        """Successful API request returns JSON."""
        client = GitHubClient(owner="owner", repo="repo", token="test-token")

        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_response.json.return_value = {"id": 1, "title": "Test"}

        with patch("httpx.AsyncClient") as mock_client:
            mock_client.return_value.__aenter__ = AsyncMock(
                return_value=MagicMock(request=AsyncMock(return_value=mock_response))
            )
            mock_client.return_value.__aexit__ = AsyncMock(return_value=None)

            result = await client._request("GET", "/repos/owner/repo")
            assert result == {"id": 1, "title": "Test"}

    @pytest.mark.asyncio
    async def test_request_401_raises_auth_error(self):
        """401 response raises AuthenticationError."""
        client = GitHubClient(owner="owner", repo="repo", token="bad-token")

        mock_response = MagicMock()
        mock_response.status_code = 401
        mock_response.text = "Bad credentials"

        with patch("httpx.AsyncClient") as mock_client:
            mock_client.return_value.__aenter__ = AsyncMock(
                return_value=MagicMock(request=AsyncMock(return_value=mock_response))
            )
            mock_client.return_value.__aexit__ = AsyncMock(return_value=None)

            with pytest.raises(AuthenticationError, match="authentication failed"):
                await client._request("GET", "/repos/owner/repo")

    @pytest.mark.asyncio
    async def test_request_403_rate_limit_raises(self):
        """403 with rate limit raises RateLimitError."""
        client = GitHubClient(owner="owner", repo="repo", token="test-token")

        mock_response = MagicMock()
        mock_response.status_code = 403
        mock_response.text = "API rate limit exceeded"
        mock_response.headers = {"X-RateLimit-Reset": "1234567890"}

        with patch("httpx.AsyncClient") as mock_client:
            mock_client.return_value.__aenter__ = AsyncMock(
                return_value=MagicMock(request=AsyncMock(return_value=mock_response))
            )
            mock_client.return_value.__aexit__ = AsyncMock(return_value=None)

            with pytest.raises(RateLimitError):
                await client._request("GET", "/repos/owner/repo")

    @pytest.mark.asyncio
    async def test_request_404_returns_empty(self):
        """404 response returns empty dict."""
        client = GitHubClient(owner="owner", repo="repo", token="test-token")

        mock_response = MagicMock()
        mock_response.status_code = 404
        mock_response.text = "Not Found"

        with patch("httpx.AsyncClient") as mock_client:
            mock_client.return_value.__aenter__ = AsyncMock(
                return_value=MagicMock(request=AsyncMock(return_value=mock_response))
            )
            mock_client.return_value.__aexit__ = AsyncMock(return_value=None)

            result = await client._request("GET", "/repos/owner/repo")
            assert result == {}

    @pytest.mark.asyncio
    async def test_request_204_returns_empty(self):
        """204 No Content returns empty dict."""
        client = GitHubClient(owner="owner", repo="repo", token="test-token")

        mock_response = MagicMock()
        mock_response.status_code = 204

        with patch("httpx.AsyncClient") as mock_client:
            mock_client.return_value.__aenter__ = AsyncMock(
                return_value=MagicMock(request=AsyncMock(return_value=mock_response))
            )
            mock_client.return_value.__aexit__ = AsyncMock(return_value=None)

            result = await client._request("POST", "/repos/owner/repo/labels")
            assert result == {}

    @pytest.mark.asyncio
    async def test_request_500_raises_forge_error(self):
        """500 response raises ForgeError."""
        client = GitHubClient(owner="owner", repo="repo", token="test-token")

        mock_response = MagicMock()
        mock_response.status_code = 500
        mock_response.text = "Internal Server Error"

        with patch("httpx.AsyncClient") as mock_client:
            mock_client.return_value.__aenter__ = AsyncMock(
                return_value=MagicMock(request=AsyncMock(return_value=mock_response))
            )
            mock_client.return_value.__aexit__ = AsyncMock(return_value=None)

            with pytest.raises(ForgeError, match="500"):
                await client._request("GET", "/repos/owner/repo")


class TestGitHubClientPullRequests:
    """Tests for pull request operations."""

    @pytest.mark.asyncio
    async def test_find_pull_request_found(self):
        """Find existing PR returns MergeRequest."""
        client = GitHubClient(owner="owner", repo="repo", token="test-token")

        pr_data = [
            {
                "number": 123,
                "title": "Release v1.0.0",
                "body": "Changelog here",
                "state": "open",
                "merged": False,
                "head": {"ref": "release"},
                "base": {"ref": "main"},
                "html_url": "https://github.com/owner/repo/pull/123",
                "labels": [{"name": "release"}],
            }
        ]

        with patch.object(client, "_request", new_callable=AsyncMock) as mock_request:
            mock_request.return_value = pr_data

            result = await client.find_pull_request(head="release", base="main")

            assert result is not None
            assert result.number == 123
            assert result.title == "Release v1.0.0"
            assert result.state == MergeRequestState.OPEN
            assert "release" in result.labels

    @pytest.mark.asyncio
    async def test_find_pull_request_not_found(self):
        """Find non-existent PR returns None."""
        client = GitHubClient(owner="owner", repo="repo", token="test-token")

        with patch.object(client, "_request", new_callable=AsyncMock) as mock_request:
            mock_request.return_value = []

            result = await client.find_pull_request(head="release", base="main")
            assert result is None

    @pytest.mark.asyncio
    async def test_create_pull_request(self):
        """Create PR returns MergeRequest."""
        client = GitHubClient(owner="owner", repo="repo", token="test-token")

        pr_response = {
            "number": 456,
            "title": "New PR",
            "body": "Description",
            "state": "open",
            "merged": False,
            "head": {"ref": "feature"},
            "base": {"ref": "main"},
            "html_url": "https://github.com/owner/repo/pull/456",
            "labels": [],
        }

        with patch.object(client, "_request", new_callable=AsyncMock) as mock_request:
            mock_request.return_value = pr_response

            result = await client.create_pull_request(
                title="New PR",
                body="Description",
                head="feature",
                base="main",
            )

            assert result.number == 456
            assert result.title == "New PR"
            mock_request.assert_called_once()

    @pytest.mark.asyncio
    async def test_create_pull_request_with_labels(self):
        """Create PR with labels adds labels via separate call."""
        client = GitHubClient(owner="owner", repo="repo", token="test-token")

        pr_response = {
            "number": 789,
            "title": "Release PR",
            "body": "Changelog",
            "state": "open",
            "merged": False,
            "head": {"ref": "release"},
            "base": {"ref": "main"},
            "html_url": "https://github.com/owner/repo/pull/789",
            "labels": [],
        }

        with patch.object(client, "_request", new_callable=AsyncMock) as mock_request:
            mock_request.return_value = pr_response

            await client.create_pull_request(
                title="Release PR",
                body="Changelog",
                head="release",
                base="main",
                labels=["release", "automated"],
            )

            # Should have called _request twice: create PR + add labels
            assert mock_request.call_count == 2

    @pytest.mark.asyncio
    async def test_update_pull_request(self):
        """Update existing PR returns updated MergeRequest."""
        client = GitHubClient(owner="owner", repo="repo", token="test-token")

        updated_response = {
            "number": 123,
            "title": "Updated Title",
            "body": "Updated Body",
            "state": "open",
            "merged": False,
            "head": {"ref": "release"},
            "base": {"ref": "main"},
            "html_url": "https://github.com/owner/repo/pull/123",
            "labels": [],
        }

        with patch.object(client, "_request", new_callable=AsyncMock) as mock_request:
            mock_request.return_value = updated_response

            result = await client.update_pull_request(
                number=123,
                title="Updated Title",
                body="Updated Body",
            )

            assert result.title == "Updated Title"
            mock_request.assert_called_once_with(
                "PATCH",
                "/repos/owner/repo/pulls/123",
                json={"title": "Updated Title", "body": "Updated Body"},
            )


class TestGitHubClientReleases:
    """Tests for release operations."""

    @pytest.mark.asyncio
    async def test_create_release(self):
        """Create GitHub release."""
        client = GitHubClient(owner="owner", repo="repo", token="test-token")

        release_response = {
            "tag_name": "v1.0.0",
            "name": "v1.0.0",
            "body": "Release notes",
            "html_url": "https://github.com/owner/repo/releases/tag/v1.0.0",
            "draft": False,
            "prerelease": False,
            "assets": [],
        }

        with patch.object(client, "_request", new_callable=AsyncMock) as mock_request:
            mock_request.return_value = release_response

            result = await client.create_release(
                tag="v1.0.0",
                name="v1.0.0",
                body="Release notes",
            )

            assert result.tag == "v1.0.0"
            assert result.name == "v1.0.0"
            assert not result.draft
            assert not result.prerelease

    @pytest.mark.asyncio
    async def test_create_prerelease(self):
        """Create pre-release."""
        client = GitHubClient(owner="owner", repo="repo", token="test-token")

        release_response = {
            "tag_name": "v1.0.0-rc.1",
            "name": "v1.0.0-rc.1",
            "body": "Pre-release",
            "html_url": "https://github.com/owner/repo/releases/tag/v1.0.0-rc.1",
            "draft": False,
            "prerelease": True,
            "assets": [],
        }

        with patch.object(client, "_request", new_callable=AsyncMock) as mock_request:
            mock_request.return_value = release_response

            result = await client.create_release(
                tag="v1.0.0-rc.1",
                name="v1.0.0-rc.1",
                body="Pre-release",
                prerelease=True,
            )

            assert result.prerelease

    @pytest.mark.asyncio
    async def test_get_release_by_tag_found(self):
        """Get existing release by tag."""
        client = GitHubClient(owner="owner", repo="repo", token="test-token")

        release_response = {
            "tag_name": "v1.0.0",
            "name": "v1.0.0",
            "body": "Notes",
            "html_url": "https://github.com/owner/repo/releases/tag/v1.0.0",
            "draft": False,
            "prerelease": False,
            "assets": [{"browser_download_url": "https://example.com/file.whl"}],
        }

        with patch.object(client, "_request", new_callable=AsyncMock) as mock_request:
            mock_request.return_value = release_response

            result = await client.get_release_by_tag("v1.0.0")

            assert result is not None
            assert result.tag == "v1.0.0"
            assert len(result.assets) == 1

    @pytest.mark.asyncio
    async def test_get_release_by_tag_not_found(self):
        """Get non-existent release returns None."""
        client = GitHubClient(owner="owner", repo="repo", token="test-token")

        with patch.object(client, "_request", new_callable=AsyncMock) as mock_request:
            mock_request.return_value = {}

            result = await client.get_release_by_tag("v99.0.0")
            assert result is None


class TestRateLimitRetry:
    """Tests for rate limit handling and retry logic."""

    @pytest.mark.asyncio
    async def test_retry_on_rate_limit(self):
        """Retry on 403 rate limit with exponential backoff."""
        client = GitHubClient(owner="owner", repo="repo", token="test-token")

        # First call: rate limit, second call: success
        rate_limit_response = MagicMock()
        rate_limit_response.status_code = 403
        rate_limit_response.text = "API rate limit exceeded"
        rate_limit_response.headers = {"X-RateLimit-Reset": "1234567890"}

        success_response = MagicMock()
        success_response.status_code = 200
        success_response.json.return_value = {"id": 1}

        call_count = 0

        async def mock_request(*args, **kwargs):
            nonlocal call_count
            call_count += 1
            if call_count == 1:
                return rate_limit_response
            return success_response

        with (
            patch("httpx.AsyncClient") as mock_client,
            patch("asyncio.sleep", new_callable=AsyncMock) as mock_sleep,
        ):
            mock_client.return_value.__aenter__ = AsyncMock(
                return_value=MagicMock(request=mock_request)
            )
            mock_client.return_value.__aexit__ = AsyncMock(return_value=None)

            result = await client._request("GET", "/test")

            assert result == {"id": 1}
            assert call_count == 2
            mock_sleep.assert_called_once()

    @pytest.mark.asyncio
    async def test_retry_on_abuse_limit(self):
        """Retry on 429 abuse rate limit."""
        client = GitHubClient(owner="owner", repo="repo", token="test-token")

        abuse_response = MagicMock()
        abuse_response.status_code = 429
        abuse_response.text = "Abuse detection mechanism"
        abuse_response.headers = {"Retry-After": "60"}

        success_response = MagicMock()
        success_response.status_code = 200
        success_response.json.return_value = {"ok": True}

        call_count = 0

        async def mock_request(*args, **kwargs):
            nonlocal call_count
            call_count += 1
            if call_count == 1:
                return abuse_response
            return success_response

        with (
            patch("httpx.AsyncClient") as mock_client,
            patch("asyncio.sleep", new_callable=AsyncMock) as mock_sleep,
        ):
            mock_client.return_value.__aenter__ = AsyncMock(
                return_value=MagicMock(request=mock_request)
            )
            mock_client.return_value.__aexit__ = AsyncMock(return_value=None)

            result = await client._request("GET", "/test")

            assert result == {"ok": True}
            assert call_count == 2
            # Should use Retry-After header
            mock_sleep.assert_called_once_with(60.0)

    @pytest.mark.asyncio
    async def test_max_retries_exceeded(self):
        """Raise error after max retries exceeded."""
        client = GitHubClient(owner="owner", repo="repo", token="test-token")

        rate_limit_response = MagicMock()
        rate_limit_response.status_code = 403
        rate_limit_response.text = "API rate limit exceeded"
        rate_limit_response.headers = {}

        with (
            patch("httpx.AsyncClient") as mock_client,
            patch("asyncio.sleep", new_callable=AsyncMock),
        ):
            mock_client.return_value.__aenter__ = AsyncMock(
                return_value=MagicMock(request=AsyncMock(return_value=rate_limit_response))
            )
            mock_client.return_value.__aexit__ = AsyncMock(return_value=None)

            with pytest.raises(RateLimitError):
                await client._request("GET", "/test")


class TestBotFiltering:
    """Tests for bot author filtering."""

    def test_default_bot_authors(self):
        """Default config includes common bots."""
        from release_py.config.models import ChangelogConfig

        config = ChangelogConfig()

        # Check common bots are in the default list
        assert "dependabot[bot]" in config.ignore_authors
        assert "renovate[bot]" in config.ignore_authors
        assert "github-actions[bot]" in config.ignore_authors

    def test_custom_bot_authors(self):
        """Custom bot authors can be configured."""
        from release_py.config.models import ChangelogConfig

        config = ChangelogConfig(ignore_authors=["custom-bot", "another-bot"])

        assert config.ignore_authors == ["custom-bot", "another-bot"]
        assert "dependabot[bot]" not in config.ignore_authors


class TestParallelPRFetching:
    """Tests for parallel PR fetching."""

    @pytest.mark.asyncio
    async def test_parallel_batch_fetching(self):
        """PR details are fetched in parallel batches."""
        client = GitHubClient(owner="owner", repo="repo", token="test-token")

        # Mock compare response with commits
        compare_response = {
            "commits": [
                {"sha": "abc", "commit": {"message": "feat: feature 1 (#1)"}},
                {"sha": "def", "commit": {"message": "fix: bug 1 (#2)"}},
                {"sha": "ghi", "commit": {"message": "feat: feature 2 (#3)"}},
            ]
        }

        # Mock PR details
        pr_details = {
            1: {
                "number": 1,
                "title": "feat: feature 1",
                "user": {"login": "user1"},
                "merged_at": "2024-01-01T00:00:00Z",
                "labels": [],
            },
            2: {
                "number": 2,
                "title": "fix: bug 1",
                "user": {"login": "user2"},
                "merged_at": "2024-01-02T00:00:00Z",
                "labels": [],
            },
            3: {
                "number": 3,
                "title": "feat: feature 2",
                "user": {"login": "user3"},
                "merged_at": "2024-01-03T00:00:00Z",
                "labels": [],
            },
        }

        async def mock_get_pr_details(pr_number):
            return pr_details.get(pr_number)

        with (
            patch.object(client, "_request", new_callable=AsyncMock) as mock_request,
            patch.object(client, "_get_pr_details", side_effect=mock_get_pr_details),
        ):
            mock_request.return_value = compare_response

            prs = await client.get_merged_prs_between_tags(
                base_tag="v0.1.0",
                head_tag="v0.2.0",
                batch_size=2,
            )

            assert len(prs) == 3
            # Should fetch in batches (2 then 1)
            pr_numbers = [pr["number"] for pr in prs]
            assert sorted(pr_numbers) == [1, 2, 3]

    @pytest.mark.asyncio
    async def test_fetch_prs_extracts_pr_numbers_from_messages(self):
        """PR numbers are extracted from various commit message formats."""
        client = GitHubClient(owner="owner", repo="repo", token="test-token")

        compare_response = {
            "commits": [
                # Squash merge format: "Title (#123)"
                {"sha": "abc", "commit": {"message": "feat: add feature (#10)"}},
                # Merge pull request format
                {"sha": "def", "commit": {"message": "Merge pull request #20 from branch"}},
            ]
        }

        pr_details = {
            10: {"number": 10, "title": "Feature", "user": {"login": "user"}},
            20: {"number": 20, "title": "PR", "user": {"login": "user"}},
        }

        async def mock_get_pr_details(pr_number):
            return pr_details.get(pr_number)

        with (
            patch.object(client, "_request", new_callable=AsyncMock) as mock_request,
            patch.object(client, "_get_pr_details", side_effect=mock_get_pr_details),
        ):
            mock_request.return_value = compare_response

            prs = await client.get_merged_prs_between_tags(
                base_tag="v0.1.0",
                head_tag="v0.2.0",
            )

            assert len(prs) == 2
            pr_numbers = sorted(pr["number"] for pr in prs)
            assert pr_numbers == [10, 20]

    @pytest.mark.asyncio
    async def test_fetch_handles_pr_fetch_errors(self):
        """Errors fetching individual PRs don't break the whole operation."""
        client = GitHubClient(owner="owner", repo="repo", token="test-token")

        compare_response = {
            "commits": [
                {"sha": "abc", "commit": {"message": "feat: good (#1)"}},
                {"sha": "def", "commit": {"message": "feat: missing (#2)"}},
            ]
        }

        async def mock_get_pr_details(pr_number):
            if pr_number == 2:
                raise ForgeError("PR not found")
            return {"number": 1, "title": "Good PR", "user": {"login": "user"}}

        with (
            patch.object(client, "_request", new_callable=AsyncMock) as mock_request,
            patch.object(client, "_get_pr_details", side_effect=mock_get_pr_details),
        ):
            mock_request.return_value = compare_response

            prs = await client.get_merged_prs_between_tags(
                base_tag="v0.1.0",
                head_tag="v0.2.0",
            )

            # Should still return the successful PR
            assert len(prs) == 1
            assert prs[0]["number"] == 1


class TestParsePullRequest:
    """Tests for PR response parsing."""

    def test_parse_open_pr(self):
        """Parse open PR."""
        client = GitHubClient(owner="owner", repo="repo", token="test-token")

        data = {
            "number": 1,
            "title": "PR",
            "body": "Body",
            "state": "open",
            "merged": False,
            "head": {"ref": "branch"},
            "base": {"ref": "main"},
            "html_url": "https://github.com/owner/repo/pull/1",
            "labels": [],
        }

        result = client._parse_pull_request(data)
        assert result.state == MergeRequestState.OPEN

    def test_parse_merged_pr(self):
        """Parse merged PR."""
        client = GitHubClient(owner="owner", repo="repo", token="test-token")

        data = {
            "number": 1,
            "title": "PR",
            "body": "Body",
            "state": "closed",
            "merged": True,
            "head": {"ref": "branch"},
            "base": {"ref": "main"},
            "html_url": "https://github.com/owner/repo/pull/1",
            "labels": [],
        }

        result = client._parse_pull_request(data)
        assert result.state == MergeRequestState.MERGED

    def test_parse_closed_pr(self):
        """Parse closed (not merged) PR."""
        client = GitHubClient(owner="owner", repo="repo", token="test-token")

        data = {
            "number": 1,
            "title": "PR",
            "body": None,
            "state": "closed",
            "merged": False,
            "head": {"ref": "branch"},
            "base": {"ref": "main"},
            "html_url": "https://github.com/owner/repo/pull/1",
            "labels": [{"name": "bug"}, {"name": "wontfix"}],
        }

        result = client._parse_pull_request(data)
        assert result.state == MergeRequestState.CLOSED
        assert result.body == ""  # None converted to empty string
        assert result.labels == ["bug", "wontfix"]

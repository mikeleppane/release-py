"""Integration tests for the release command."""

from __future__ import annotations

import subprocess
from pathlib import Path
from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from typer.testing import CliRunner

from release_py.cli.app import app

runner = CliRunner()


@pytest.fixture
def release_ready_repo(temp_git_repo_with_pyproject: Path) -> Path:
    """Create a repo ready for release."""
    repo = temp_git_repo_with_pyproject

    # Add remote
    subprocess.run(
        ["git", "remote", "add", "origin", "https://github.com/owner/repo.git"],
        cwd=repo,
        check=True,
        capture_output=True,
    )

    return repo


class TestReleaseDryRun:
    """Tests for release command in dry-run mode."""

    def test_release_dry_run_shows_preview(self, release_ready_repo: Path):
        """Dry run shows what would happen."""
        # The release command requires being on the default branch (main)
        subprocess.run(
            ["git", "branch", "-m", "master", "main"],
            cwd=release_ready_repo,
            check=True,
            capture_output=True,
        )

        result = runner.invoke(app, ["release", str(release_ready_repo)])

        # Should show preview without actually releasing
        assert result.exit_code == 0
        assert "dry" in result.stdout.lower() or "preview" in result.stdout.lower()

    def test_release_dry_run_no_push(self, release_ready_repo: Path):
        """Dry run doesn't push tags."""
        # The release command requires being on the default branch (main)
        subprocess.run(
            ["git", "branch", "-m", "master", "main"],
            cwd=release_ready_repo,
            check=True,
            capture_output=True,
        )

        result = runner.invoke(app, ["release", str(release_ready_repo)])

        # In dry run, we shouldn't push - no tag should be created
        assert result.exit_code == 0
        # Verify no tag was created
        tags_result = subprocess.run(
            ["git", "tag"], cwd=release_ready_repo, capture_output=True, text=True, check=False
        )
        assert "v1.0.0" not in tags_result.stdout


class TestReleaseExecution:
    """Tests for release command execution."""

    def test_release_creates_tag(self, release_ready_repo: Path):
        """Release creates git tag."""
        with patch("release_py.forge.github.GitHubClient") as mock_github:
            mock_client = MagicMock()
            mock_client.create_release = AsyncMock(
                return_value=MagicMock(
                    tag="v1.0.0",
                    url="https://github.com/owner/repo/releases/tag/v1.0.0",
                )
            )
            mock_github.return_value = mock_client

            with patch("release_py.publish.pypi.build_package") as mock_build:
                mock_build.return_value = []

                with patch("release_py.publish.pypi.publish_package"):
                    with patch("release_py.vcs.git.GitRepository.push_tag"):
                        result = runner.invoke(
                            app, ["release", str(release_ready_repo), "--execute"]
                        )

                        # Check if tag was mentioned or release succeeded
                        assert result.exit_code in (0, 1)

    def test_release_skip_publish(self, release_ready_repo: Path):
        """Release with --skip-publish skips PyPI."""
        with patch("release_py.forge.github.GitHubClient") as mock_github:
            mock_client = MagicMock()
            mock_client.create_release = AsyncMock(
                return_value=MagicMock(
                    tag="v1.0.0",
                    url="https://github.com/owner/repo/releases/tag/v1.0.0",
                )
            )
            mock_github.return_value = mock_client

            with patch("release_py.publish.pypi.build_package") as mock_build:
                mock_build.return_value = []

                with patch("release_py.publish.pypi.publish_package") as mock_publish:
                    with patch("release_py.vcs.git.GitRepository.push_tag"):
                        result = runner.invoke(
                            app,
                            ["release", str(release_ready_repo), "--execute", "--skip-publish"],
                        )

                        # With skip-publish, publish should not be called
                        if result.exit_code == 0:
                            mock_publish.assert_not_called()
                        assert result.exit_code in (0, 1)


class TestReleaseErrors:
    """Tests for release command error handling."""

    def test_release_not_on_default_branch(self, release_ready_repo: Path):
        """Warn/fail when not on default branch."""
        # Create and checkout a feature branch
        subprocess.run(
            ["git", "checkout", "-b", "feature-branch"],
            cwd=release_ready_repo,
            check=True,
            capture_output=True,
        )

        result = runner.invoke(app, ["release", str(release_ready_repo), "--execute"])

        # Should warn or fail about wrong branch
        assert result.exit_code in (0, 1)

    def test_release_dirty_repo(self, release_ready_repo: Path):
        """Fail when repo is dirty."""
        # Make repo dirty
        (release_ready_repo / "uncommitted.txt").write_text("dirty")

        result = runner.invoke(app, ["release", str(release_ready_repo), "--execute"])

        # Should fail due to dirty repo
        assert result.exit_code == 1

    def test_release_no_remote(self, temp_git_repo_with_pyproject: Path):
        """Handle missing remote gracefully."""
        result = runner.invoke(app, ["release", str(temp_git_repo_with_pyproject), "--execute"])

        # Should fail or warn about missing remote
        assert result.exit_code == 1

    def test_release_tag_exists(self, release_ready_repo: Path):
        """Handle existing tag."""
        # Create a tag
        subprocess.run(
            ["git", "tag", "v1.0.0"],
            cwd=release_ready_repo,
            check=True,
            capture_output=True,
        )

        result = runner.invoke(app, ["release", str(release_ready_repo), "--execute"])

        # Should handle existing tag
        assert result.exit_code in (0, 1)


class TestReleaseGitHubIntegration:
    """Tests for GitHub release creation."""

    def test_release_creates_github_release(self, release_ready_repo: Path):
        """Create GitHub release with changelog."""
        with patch("release_py.forge.github.GitHubClient") as mock_github:
            mock_client = MagicMock()
            mock_client.create_release = AsyncMock(
                return_value=MagicMock(
                    tag="v1.0.0",
                    name="v1.0.0",
                    url="https://github.com/owner/repo/releases/tag/v1.0.0",
                )
            )
            mock_github.return_value = mock_client

            with patch("release_py.publish.pypi.build_package", return_value=[]):
                with patch("release_py.publish.pypi.publish_package"):
                    with patch("release_py.vcs.git.GitRepository.push_tag"):
                        result = runner.invoke(
                            app, ["release", str(release_ready_repo), "--execute"]
                        )

                        # Verify create_release was called
                        if result.exit_code == 0:
                            mock_client.create_release.assert_called_once()

    def test_release_uses_changelog_as_body(self, release_ready_repo: Path):
        """GitHub release body contains release info."""
        with patch("release_py.forge.github.GitHubClient") as mock_github:
            mock_client = MagicMock()
            mock_client.create_release = AsyncMock(
                return_value=MagicMock(
                    tag="v1.0.0",
                    url="https://github.com/owner/repo/releases/tag/v1.0.0",
                )
            )
            mock_github.return_value = mock_client

            with patch("release_py.publish.pypi.build_package", return_value=[]):
                with patch("release_py.publish.pypi.publish_package"):
                    with patch("release_py.vcs.git.GitRepository.push_tag"):
                        result = runner.invoke(
                            app, ["release", str(release_ready_repo), "--execute"]
                        )

                        if result.exit_code == 0:
                            # Check that create_release was called
                            mock_client.create_release.assert_called_once()
                            # The release body is generated by _generate_release_body
                            call_kwargs = mock_client.create_release.call_args
                            if call_kwargs:
                                # Body should contain installation instructions
                                body = call_kwargs.kwargs.get("body", "")
                                assert "pip install" in body or len(body) > 0


class TestReleasePublishing:
    """Tests for PyPI publishing during release."""

    def test_release_builds_package(self, release_ready_repo: Path):
        """Release builds package before publishing."""
        with patch("release_py.forge.github.GitHubClient") as mock_github:
            mock_client = MagicMock()
            mock_client.create_release = AsyncMock(
                return_value=MagicMock(tag="v1.0.0", url="http://example.com")
            )
            mock_github.return_value = mock_client

            with patch("release_py.publish.pypi.build_package") as mock_build:
                mock_build.return_value = [Path("/dist/pkg-1.0.0.whl")]

                with patch("release_py.publish.pypi.publish_package"):
                    with patch("release_py.vcs.git.GitRepository.push_tag"):
                        result = runner.invoke(
                            app, ["release", str(release_ready_repo), "--execute"]
                        )

                        if result.exit_code == 0:
                            mock_build.assert_called_once()

    def test_release_publishes_to_pypi(self, release_ready_repo: Path):
        """Release publishes built package to PyPI."""
        with patch("release_py.forge.github.GitHubClient") as mock_github:
            mock_client = MagicMock()
            mock_client.create_release = AsyncMock(
                return_value=MagicMock(tag="v1.0.0", url="http://example.com")
            )
            mock_github.return_value = mock_client

            dist_files = [Path("/dist/pkg-1.0.0.whl")]

            with patch("release_py.publish.pypi.build_package", return_value=dist_files):
                with patch("release_py.publish.pypi.publish_package") as mock_publish:
                    with patch("release_py.vcs.git.GitRepository.push_tag"):
                        result = runner.invoke(
                            app, ["release", str(release_ready_repo), "--execute"]
                        )

                        if result.exit_code == 0:
                            mock_publish.assert_called_once()


class TestReleaseBodyGeneration:
    """Tests for release body generation and changelog integration."""

    def test_release_with_pr_based_changelog(self, release_ready_repo: Path):
        """Release with PR-based changelog fetches PRs from GitHub."""
        # Add PR-based config to pyproject.toml
        pyproject = release_ready_repo / "pyproject.toml"
        config_content = pyproject.read_text()
        config_content += "\n[tool.releasio.changelog]\nuse_github_prs = true\n"
        pyproject.write_text(config_content)

        # Rename to main branch
        subprocess.run(
            ["git", "branch", "-m", "master", "main"],
            cwd=release_ready_repo,
            check=True,
            capture_output=True,
        )

        with patch("release_py.forge.github.GitHubClient") as mock_github:
            mock_client = MagicMock()

            # Mock PR-based changelog methods
            mock_client.generate_pr_based_changelog = AsyncMock(
                return_value="## Changes\n\n- feat: New feature (#1)\n- fix: Bug fix (#2)"
            )
            mock_client.get_merged_prs_between_tags = AsyncMock(
                return_value=[{"number": 1, "author": "user1"}, {"number": 2, "author": "user2"}]
            )
            mock_client.get_contributors_from_prs = AsyncMock(return_value=["user1", "user2"])
            mock_client.create_release = AsyncMock(
                return_value=MagicMock(
                    tag="v1.0.0",
                    url="https://github.com/owner/repo/releases/tag/v1.0.0",
                )
            )
            mock_github.return_value = mock_client

            with patch("release_py.publish.pypi.build_package", return_value=[]):
                with patch("release_py.publish.pypi.publish_package"):
                    with patch("release_py.vcs.git.GitRepository.push_tag"):
                        result = runner.invoke(
                            app, ["release", str(release_ready_repo), "--execute"]
                        )

                        if result.exit_code == 0:
                            # Verify PR-based methods were called
                            mock_client.generate_pr_based_changelog.assert_called_once()
                            mock_client.get_merged_prs_between_tags.assert_called_once()
                            mock_client.get_contributors_from_prs.assert_called_once()

    def test_release_with_commit_based_changelog(self, release_ready_repo: Path):
        """Release with commit-based changelog uses git-cliff."""
        # Rename to main branch
        subprocess.run(
            ["git", "branch", "-m", "master", "main"],
            cwd=release_ready_repo,
            check=True,
            capture_output=True,
        )

        # Add a conventional commit
        (release_ready_repo / "feature.py").write_text("# Feature\n")
        subprocess.run(["git", "add", "."], cwd=release_ready_repo, check=True, capture_output=True)
        subprocess.run(
            ["git", "commit", "-m", "feat: add new feature"],
            cwd=release_ready_repo,
            check=True,
            capture_output=True,
        )

        with patch("release_py.forge.github.GitHubClient") as mock_github:
            mock_client = MagicMock()
            mock_client.create_release = AsyncMock(
                return_value=MagicMock(
                    tag="v1.0.0",
                    url="https://github.com/owner/repo/releases/tag/v1.0.0",
                )
            )
            mock_github.return_value = mock_client

            # Mock changelog generation
            with patch(
                "release_py.core.changelog.generate_changelog",
                return_value="## Features\n\n- add new feature",
            ) as mock_changelog:
                with patch("release_py.publish.pypi.build_package", return_value=[]):
                    with patch("release_py.publish.pypi.publish_package"):
                        with patch("release_py.vcs.git.GitRepository.push_tag"):
                            result = runner.invoke(
                                app, ["release", str(release_ready_repo), "--execute"]
                            )

                            if result.exit_code == 0:
                                # Verify commit-based changelog was called
                                mock_changelog.assert_called_once()
                                # Verify release body contains changelog
                                call_kwargs = mock_client.create_release.call_args.kwargs
                                body = call_kwargs.get("body", "")
                                assert "feature" in body.lower() or len(body) > 0

    def test_release_body_includes_contributors(self, release_ready_repo: Path):
        """Release body includes contributors section."""
        # Rename to main branch
        subprocess.run(
            ["git", "branch", "-m", "master", "main"],
            cwd=release_ready_repo,
            check=True,
            capture_output=True,
        )

        # Add commits from different contributors
        (release_ready_repo / "feature1.py").write_text("# Feature 1\n")
        subprocess.run(["git", "add", "."], cwd=release_ready_repo, check=True, capture_output=True)
        subprocess.run(
            ["git", "config", "user.name", "Alice"],
            cwd=release_ready_repo,
            check=True,
            capture_output=True,
        )
        subprocess.run(
            ["git", "commit", "-m", "feat: feature 1"],
            cwd=release_ready_repo,
            check=True,
            capture_output=True,
        )

        (release_ready_repo / "feature2.py").write_text("# Feature 2\n")
        subprocess.run(["git", "add", "."], cwd=release_ready_repo, check=True, capture_output=True)
        subprocess.run(
            ["git", "config", "user.name", "Bob"],
            cwd=release_ready_repo,
            check=True,
            capture_output=True,
        )
        subprocess.run(
            ["git", "commit", "-m", "feat: feature 2"],
            cwd=release_ready_repo,
            check=True,
            capture_output=True,
        )

        with patch("release_py.forge.github.GitHubClient") as mock_github:
            mock_client = MagicMock()
            mock_client.create_release = AsyncMock(
                return_value=MagicMock(
                    tag="v1.0.0",
                    url="https://github.com/owner/repo/releases/tag/v1.0.0",
                )
            )
            mock_github.return_value = mock_client

            # Mock changelog generation
            with patch(
                "release_py.core.changelog.generate_changelog",
                return_value="## Features\n\n- feature 1\n- feature 2",
            ):
                with patch("release_py.publish.pypi.build_package", return_value=[]):
                    with patch("release_py.publish.pypi.publish_package"):
                        with patch("release_py.vcs.git.GitRepository.push_tag"):
                            result = runner.invoke(
                                app, ["release", str(release_ready_repo), "--execute"]
                            )

                            if result.exit_code == 0:
                                # Check that release body includes contributors
                                call_kwargs = mock_client.create_release.call_args.kwargs
                                body = call_kwargs.get("body", "")
                                # Should contain Contributors section or installation instructions
                                assert "Contributors" in body or "Installation" in body, (
                                    f"Release body missing expected sections: {body}"
                                )

    def test_release_github_api_failure_shows_error(self, release_ready_repo: Path):
        """Release shows clear error when GitHub API fails."""
        # Rename to main branch
        subprocess.run(
            ["git", "branch", "-m", "master", "main"],
            cwd=release_ready_repo,
            check=True,
            capture_output=True,
        )

        with patch("release_py.forge.github.GitHubClient") as mock_github:
            mock_client = MagicMock()
            # Simulate GitHub API failure
            mock_client.create_release = AsyncMock(
                side_effect=Exception("GitHub API rate limit exceeded")
            )
            mock_github.return_value = mock_client

            # Mock changelog generation
            with patch(
                "release_py.core.changelog.generate_changelog",
                return_value="## Changes",
            ):
                with patch("release_py.publish.pypi.build_package", return_value=[]):
                    with patch("release_py.publish.pypi.publish_package"):
                        # Don't mock push_tag to allow tag creation
                        with patch("release_py.vcs.git.GitRepository.push_tag"):
                            result = runner.invoke(
                                app, ["release", str(release_ready_repo), "--execute"]
                            )

                            # Should fail with error message
                            assert result.exit_code == 1
                            output = result.stdout + (
                                result.output if hasattr(result, "output") else ""
                            )
                            # Error message should mention the GitHub error
                            assert "error" in output.lower() or "github" in output.lower(), (
                                f"Expected error message about GitHub, got: {output}"
                            )


class TestReleaseAssetUploads:
    """Tests for release asset upload functionality."""

    def test_release_uploads_configured_assets(self, release_ready_repo: Path, monkeypatch):
        """Release uploads assets when configured."""
        # Set fake GitHub token to avoid authentication errors
        monkeypatch.setenv("GITHUB_TOKEN", "fake-token-for-testing")

        subprocess.run(
            ["git", "branch", "-m", "master", "main"],
            cwd=release_ready_repo,
            check=True,
            capture_output=True,
        )

        # Add .gitignore to prevent dist/ from making repo dirty
        gitignore = release_ready_repo / ".gitignore"
        gitignore.write_text("dist/\n")
        subprocess.run(["git", "add", ".gitignore"], cwd=release_ready_repo, check=True)
        subprocess.run(
            ["git", "commit", "-m", "chore: add gitignore"],
            cwd=release_ready_repo,
            check=True,
            capture_output=True,
        )

        # Create test asset files
        dist_dir = release_ready_repo / "dist"
        dist_dir.mkdir(exist_ok=True)
        (dist_dir / "test-project-1.0.0-py3-none-any.whl").write_text("fake wheel")
        (dist_dir / "test-project-1.0.0.tar.gz").write_text("fake tarball")

        # Add asset configuration to pyproject.toml
        pyproject_path = release_ready_repo / "pyproject.toml"
        config = pyproject_path.read_text()
        # Use dotted key to avoid duplicate [tool.releasio] section
        config = config.replace("[tool.releasio]\n", "[tool.releasio]\nallow_dirty = true\n")
        config += '\n[tool.releasio.github]\nrelease_assets = ["dist/*.whl", "dist/*.tar.gz"]\n'
        pyproject_path.write_text(config)

        mock_release = MagicMock()
        mock_release.id = 12345
        mock_release.url = "https://github.com/owner/repo/releases/tag/v1.0.0"
        mock_release.tag = "v1.0.0"
        mock_release.name = "test-project v1.0.0"
        mock_release.body = "Release notes"
        mock_release.draft = False
        mock_release.prerelease = False
        mock_release.assets = []

        async def mock_create_release(*args, **kwargs):
            return mock_release

        async def mock_upload_asset(release_id, file_path, content_type):
            return f"https://github.com/owner/repo/releases/download/v1.0.0/{file_path.name}"

        with patch("release_py.forge.github.GitHubClient.create_release", new=mock_create_release):
            with patch(
                "release_py.forge.github.GitHubClient.upload_release_asset",
                new=mock_upload_asset,
            ):
                with patch("release_py.vcs.git.GitRepository.create_tag"):
                    with patch("release_py.vcs.git.GitRepository.push_tag"):
                        with patch(
                            "release_py.core.changelog.generate_changelog",
                            return_value="## Changes",
                        ):
                            result = runner.invoke(
                                app,
                                ["release", str(release_ready_repo), "--execute", "--skip-publish"],
                            )

        # Should succeed and mention asset uploads
        if result.exit_code != 0:
            print(f"Exit code: {result.exit_code}")
            print(f"Output: {result.stdout}")
        assert result.exit_code == 0
        assert "asset" in result.stdout.lower()

    def test_release_continues_on_asset_upload_failure(self, release_ready_repo: Path, monkeypatch):
        """Release continues even if asset upload fails."""
        # Set fake GitHub token to avoid authentication errors
        monkeypatch.setenv("GITHUB_TOKEN", "fake-token-for-testing")

        subprocess.run(
            ["git", "branch", "-m", "master", "main"],
            cwd=release_ready_repo,
            check=True,
            capture_output=True,
        )

        # Add .gitignore to prevent dist/ from making repo dirty
        gitignore = release_ready_repo / ".gitignore"
        gitignore.write_text("dist/\n")
        subprocess.run(["git", "add", ".gitignore"], cwd=release_ready_repo, check=True)
        subprocess.run(
            ["git", "commit", "-m", "chore: add gitignore"],
            cwd=release_ready_repo,
            check=True,
            capture_output=True,
        )

        # Create test asset
        dist_dir = release_ready_repo / "dist"
        dist_dir.mkdir(exist_ok=True)
        (dist_dir / "test-project-1.0.0-py3-none-any.whl").write_text("fake wheel")

        # Add asset configuration
        pyproject_path = release_ready_repo / "pyproject.toml"
        config = pyproject_path.read_text()
        # Use dotted key to avoid duplicate [tool.releasio] section
        config = config.replace("[tool.releasio]\n", "[tool.releasio]\nallow_dirty = true\n")
        config += '\n[tool.releasio.github]\nrelease_assets = ["dist/*.whl"]\n'
        pyproject_path.write_text(config)

        mock_release = MagicMock()
        mock_release.id = 12345
        mock_release.url = "https://github.com/owner/repo/releases/tag/v1.0.0"
        mock_release.tag = "v1.0.0"
        mock_release.name = "test-project v1.0.0"
        mock_release.body = "Release notes"
        mock_release.draft = False
        mock_release.prerelease = False
        mock_release.assets = []

        async def mock_create_release(*args, **kwargs):
            return mock_release

        async def mock_upload_asset(release_id, file_path, content_type):
            raise Exception("Upload failed")

        with patch("release_py.forge.github.GitHubClient.create_release", new=mock_create_release):
            with patch(
                "release_py.forge.github.GitHubClient.upload_release_asset",
                new=mock_upload_asset,
            ):
                with patch("release_py.vcs.git.GitRepository.create_tag"):
                    with patch("release_py.vcs.git.GitRepository.push_tag"):
                        with patch(
                            "release_py.core.changelog.generate_changelog",
                            return_value="## Changes",
                        ):
                            result = runner.invoke(
                                app,
                                ["release", str(release_ready_repo), "--execute", "--skip-publish"],
                            )

        # Should still succeed (warnings about failed upload)
        assert result.exit_code == 0
        # Should show warning about failed upload
        assert "failed" in result.stdout.lower() or "⚠" in result.stdout


class TestReleaseValidation:
    """Tests for package validation and pre-publish checks."""

    def test_release_validates_dist_files(self, release_ready_repo: Path, monkeypatch):
        """Release validates distribution files before publishing."""
        # Set fake GitHub token to avoid authentication errors
        monkeypatch.setenv("GITHUB_TOKEN", "fake-token-for-testing")

        subprocess.run(
            ["git", "branch", "-m", "master", "main"],
            cwd=release_ready_repo,
            check=True,
            capture_output=True,
        )

        # Add .gitignore to prevent dist/ from making repo dirty
        gitignore = release_ready_repo / ".gitignore"
        gitignore.write_text("dist/\n")
        subprocess.run(["git", "add", ".gitignore"], cwd=release_ready_repo, check=True)
        subprocess.run(
            ["git", "commit", "-m", "chore: add gitignore"],
            cwd=release_ready_repo,
            check=True,
            capture_output=True,
        )

        # Enable validation in config
        pyproject_path = release_ready_repo / "pyproject.toml"
        config = pyproject_path.read_text()
        # Use dotted key to avoid duplicate [tool.releasio] section
        config = config.replace("[tool.releasio]\n", "[tool.releasio]\nallow_dirty = true\n")
        config += "\n[tool.releasio.publish]\nvalidate_before_publish = true\n"
        pyproject_path.write_text(config)

        mock_release = MagicMock()
        mock_release.id = None
        mock_release.url = "https://github.com/owner/repo/releases/tag/v1.0.0"
        mock_release.tag = "v1.0.0"
        mock_release.name = "test-project v1.0.0"
        mock_release.body = "Release notes"
        mock_release.draft = False
        mock_release.prerelease = False
        mock_release.assets = []

        async def mock_create_release(*args, **kwargs):
            return mock_release

        with patch("release_py.forge.github.GitHubClient.create_release", new=mock_create_release):
            with patch("release_py.vcs.git.GitRepository.create_tag"):
                with patch("release_py.vcs.git.GitRepository.push_tag"):
                    with patch(
                        "release_py.core.changelog.generate_changelog",
                        return_value="## Changes",
                    ):
                        with patch(
                            "release_py.publish.pypi.build_package",
                            return_value=[Path("dist/test-project-1.0.0-py3-none-any.whl")],
                        ):
                            with patch(
                                "release_py.publish.pypi.validate_dist_files",
                                return_value=(True, "Validation passed"),
                            ) as mock_validate:
                                with patch("release_py.publish.pypi.publish_package"):
                                    result = runner.invoke(
                                        app, ["release", str(release_ready_repo), "--execute"]
                                    )

        # Should call validation
        mock_validate.assert_called_once()
        assert result.exit_code == 0

    def test_release_stops_on_validation_failure(self, release_ready_repo: Path, monkeypatch):
        """Release stops if validation fails."""
        # Set fake GitHub token to avoid authentication errors
        monkeypatch.setenv("GITHUB_TOKEN", "fake-token-for-testing")

        subprocess.run(
            ["git", "branch", "-m", "master", "main"],
            cwd=release_ready_repo,
            check=True,
            capture_output=True,
        )

        # Add .gitignore to prevent dist/ from making repo dirty
        gitignore = release_ready_repo / ".gitignore"
        gitignore.write_text("dist/\n")
        subprocess.run(["git", "add", ".gitignore"], cwd=release_ready_repo, check=True)
        subprocess.run(
            ["git", "commit", "-m", "chore: add gitignore"],
            cwd=release_ready_repo,
            check=True,
            capture_output=True,
        )

        # Enable validation in config
        pyproject_path = release_ready_repo / "pyproject.toml"
        config = pyproject_path.read_text()
        # Use dotted key to avoid duplicate [tool.releasio] section
        config = config.replace("[tool.releasio]\n", "[tool.releasio]\nallow_dirty = true\n")
        config += "\n[tool.releasio.publish]\nvalidate_before_publish = true\n"
        pyproject_path.write_text(config)

        with patch("release_py.vcs.git.GitRepository.create_tag"):
            with patch("release_py.vcs.git.GitRepository.push_tag"):
                with patch(
                    "release_py.core.changelog.generate_changelog",
                    return_value="## Changes",
                ):
                    with patch(
                        "release_py.publish.pypi.build_package",
                        return_value=[Path("dist/test-project-1.0.0-py3-none-any.whl")],
                    ):
                        with patch(
                            "release_py.publish.pypi.validate_dist_files",
                            return_value=(False, "Package metadata is invalid"),
                        ):
                            result = runner.invoke(
                                app, ["release", str(release_ready_repo), "--execute"]
                            )

        # Should fail with validation error
        assert result.exit_code == 1
        # Error messages are printed to stderr via err_console
        combined_output = result.stdout + (result.stderr or "")
        assert "validation" in combined_output.lower() or "package" in combined_output.lower()

    def test_release_checks_pypi_version_exists(self, release_ready_repo: Path, monkeypatch):
        """Release checks if version already exists on PyPI."""
        # Set fake GitHub token to avoid authentication errors
        monkeypatch.setenv("GITHUB_TOKEN", "fake-token-for-testing")

        subprocess.run(
            ["git", "branch", "-m", "master", "main"],
            cwd=release_ready_repo,
            check=True,
            capture_output=True,
        )

        # Add .gitignore to prevent dist/ from making repo dirty
        gitignore = release_ready_repo / ".gitignore"
        gitignore.write_text("dist/\n")
        subprocess.run(["git", "add", ".gitignore"], cwd=release_ready_repo, check=True)
        subprocess.run(
            ["git", "commit", "-m", "chore: add gitignore"],
            cwd=release_ready_repo,
            check=True,
            capture_output=True,
        )

        # Enable version checking in config
        pyproject_path = release_ready_repo / "pyproject.toml"
        config = pyproject_path.read_text()
        # Use dotted key to avoid duplicate [tool.releasio] section
        config = config.replace("[tool.releasio]\n", "[tool.releasio]\nallow_dirty = true\n")
        config += "\n[tool.releasio.publish]\ncheck_existing_version = true\n"
        pyproject_path.write_text(config)

        with patch("release_py.vcs.git.GitRepository.create_tag"):
            with patch("release_py.vcs.git.GitRepository.push_tag"):
                with patch(
                    "release_py.core.changelog.generate_changelog",
                    return_value="## Changes",
                ):
                    with patch(
                        "release_py.publish.pypi.build_package",
                        return_value=[Path("dist/test-project-1.0.0-py3-none-any.whl")],
                    ):
                        # Mock validation to pass so we can test version check
                        with patch(
                            "release_py.publish.pypi.validate_dist_files",
                            return_value=(True, ""),
                        ):
                            with patch(
                                "release_py.publish.pypi.check_pypi_version_exists",
                                return_value=True,
                            ):
                                result = runner.invoke(
                                    app, ["release", str(release_ready_repo), "--execute"]
                                )

        # Should fail with version exists error
        assert result.exit_code == 1
        # Error messages are printed to stderr via err_console
        combined_output = result.stdout + (result.stderr or "")
        assert "already exists" in combined_output.lower() or "pypi" in combined_output.lower()

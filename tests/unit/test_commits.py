"""Tests for conventional commit parsing."""

from __future__ import annotations

from datetime import datetime

from release_py.config.models import CommitsConfig
from release_py.core.commits import (
    DEFAULT_ALLOWED_TYPES,
    ParsedCommit,
    calculate_bump,
    filter_skip_release_commits,
    format_commit_for_changelog,
    get_breaking_changes,
    group_commits_by_type,
    parse_commits,
    validate_pr_title,
    validate_pr_titles_batch,
)
from release_py.core.version import BumpType
from release_py.vcs.git import Commit


class TestParsedCommit:
    """Tests for ParsedCommit.from_commit()."""

    def test_parse_simple_feat(self):
        """Parse a simple feat commit."""
        commit = Commit(
            sha="abc123",
            message="feat: add new feature",
            author_name="Test",
            author_email="test@test.com",
            date=datetime.now(),
        )
        pc = ParsedCommit.from_commit(commit, r"BREAKING[ -]CHANGE:")

        assert pc.is_conventional
        assert pc.commit_type == "feat"
        assert pc.scope is None
        assert pc.description == "add new feature"
        assert not pc.is_breaking

    def test_parse_with_scope(self):
        """Parse commit with scope."""
        commit = Commit(
            sha="abc123",
            message="fix(api): handle null response",
            author_name="Test",
            author_email="test@test.com",
            date=datetime.now(),
        )
        pc = ParsedCommit.from_commit(commit, r"BREAKING[ -]CHANGE:")

        assert pc.commit_type == "fix"
        assert pc.scope == "api"
        assert pc.description == "handle null response"

    def test_parse_breaking_with_exclamation(self):
        """Parse breaking change with ! indicator."""
        commit = Commit(
            sha="abc123",
            message="feat!: redesign API",
            author_name="Test",
            author_email="test@test.com",
            date=datetime.now(),
        )
        pc = ParsedCommit.from_commit(commit, r"BREAKING[ -]CHANGE:")

        assert pc.is_breaking
        assert pc.commit_type == "feat"

    def test_parse_breaking_with_scope_and_exclamation(self):
        """Parse breaking change with scope and ! indicator."""
        commit = Commit(
            sha="abc123",
            message="feat(core)!: change config format",
            author_name="Test",
            author_email="test@test.com",
            date=datetime.now(),
        )
        pc = ParsedCommit.from_commit(commit, r"BREAKING[ -]CHANGE:")

        assert pc.is_breaking
        assert pc.commit_type == "feat"
        assert pc.scope == "core"

    def test_parse_breaking_in_body(self):
        """Parse breaking change in commit body."""
        commit = Commit(
            sha="abc123",
            message="feat: new feature\n\nBREAKING CHANGE: old API removed",
            author_name="Test",
            author_email="test@test.com",
            date=datetime.now(),
        )
        pc = ParsedCommit.from_commit(commit, r"BREAKING[ -]CHANGE:")

        assert pc.is_breaking

    def test_parse_non_conventional(self):
        """Parse non-conventional commit."""
        commit = Commit(
            sha="abc123",
            message="Updated the readme file",
            author_name="Test",
            author_email="test@test.com",
            date=datetime.now(),
        )
        pc = ParsedCommit.from_commit(commit, r"BREAKING[ -]CHANGE:")

        assert not pc.is_conventional
        assert pc.commit_type is None
        assert pc.description == "Updated the readme file"


class TestParseCommits:
    """Tests for parse_commits()."""

    def test_parse_multiple_commits(self, sample_commits: list[Commit]):
        """Parse multiple commits."""
        config = CommitsConfig()
        parsed = parse_commits(sample_commits, config)

        assert len(parsed) == len(sample_commits)
        assert all(isinstance(pc, ParsedCommit) for pc in parsed)

    def test_filter_by_scope(self):
        """Filter commits by scope regex."""
        commits = [
            Commit("a", "feat(api): feature 1", "T", "t@t.com", datetime.now()),
            Commit("b", "fix(core): fix 1", "T", "t@t.com", datetime.now()),
            Commit("c", "feat(api): feature 2", "T", "t@t.com", datetime.now()),
        ]
        config = CommitsConfig(scope_regex=r"^api$")
        parsed = parse_commits(commits, config)

        assert len(parsed) == 2
        assert all(pc.scope == "api" for pc in parsed)


class TestCalculateBump:
    """Tests for calculate_bump()."""

    def test_empty_commits_returns_none(self):
        """Empty commit list returns NONE bump."""
        config = CommitsConfig()
        assert calculate_bump([], config) == BumpType.NONE

    def test_feat_returns_minor(self, feat_commit: Commit):
        """feat commit triggers MINOR bump."""
        config = CommitsConfig()
        parsed = [ParsedCommit.from_commit(feat_commit, config.breaking_pattern)]
        assert calculate_bump(parsed, config) == BumpType.MINOR

    def test_fix_returns_patch(self, fix_commit: Commit):
        """fix commit triggers PATCH bump."""
        config = CommitsConfig()
        parsed = [ParsedCommit.from_commit(fix_commit, config.breaking_pattern)]
        assert calculate_bump(parsed, config) == BumpType.PATCH

    def test_breaking_returns_major(self, breaking_commit: Commit):
        """Breaking change triggers MAJOR bump."""
        config = CommitsConfig()
        parsed = [ParsedCommit.from_commit(breaking_commit, config.breaking_pattern)]
        assert calculate_bump(parsed, config) == BumpType.MAJOR

    def test_breaking_takes_precedence(self, feat_commit: Commit, breaking_commit: Commit):
        """Breaking change takes precedence over other types."""
        config = CommitsConfig()
        parsed = [
            ParsedCommit.from_commit(feat_commit, config.breaking_pattern),
            ParsedCommit.from_commit(breaking_commit, config.breaking_pattern),
        ]
        assert calculate_bump(parsed, config) == BumpType.MAJOR

    def test_feat_takes_precedence_over_fix(self, feat_commit: Commit, fix_commit: Commit):
        """feat takes precedence over fix."""
        config = CommitsConfig()
        parsed = [
            ParsedCommit.from_commit(fix_commit, config.breaking_pattern),
            ParsedCommit.from_commit(feat_commit, config.breaking_pattern),
        ]
        assert calculate_bump(parsed, config) == BumpType.MINOR

    def test_custom_types_major(self):
        """Custom commit types can trigger MAJOR bump."""
        config = CommitsConfig(types_major=["remove"])
        commit = Commit("a", "remove: delete deprecated API", "T", "t@t.com", datetime.now())
        parsed = [ParsedCommit.from_commit(commit, config.breaking_pattern)]
        assert calculate_bump(parsed, config) == BumpType.MAJOR


class TestGroupCommitsByType:
    """Tests for group_commits_by_type()."""

    def test_group_by_type(self, sample_commits: list[Commit]):
        """Group commits by their type."""
        config = CommitsConfig()
        parsed = parse_commits(sample_commits, config)
        grouped = group_commits_by_type(parsed)

        assert "feat" in grouped
        assert "fix" in grouped
        assert "docs" in grouped
        assert "chore" in grouped


class TestGetBreakingChanges:
    """Tests for get_breaking_changes()."""

    def test_get_breaking_changes(self, sample_commits: list[Commit]):
        """Get only breaking change commits."""
        config = CommitsConfig()
        parsed = parse_commits(sample_commits, config)
        breaking = get_breaking_changes(parsed)

        assert len(breaking) == 1
        assert breaking[0].is_breaking


class TestFormatCommitForChangelog:
    """Tests for format_commit_for_changelog()."""

    def test_format_simple(self, feat_commit: Commit):
        """Format simple commit."""
        config = CommitsConfig()
        pc = ParsedCommit.from_commit(feat_commit, config.breaking_pattern)
        formatted = format_commit_for_changelog(pc)

        assert "add user authentication" in formatted

    def test_format_with_scope(self, fix_commit: Commit):
        """Format commit with scope."""
        config = CommitsConfig()
        pc = ParsedCommit.from_commit(fix_commit, config.breaking_pattern)
        formatted = format_commit_for_changelog(pc, include_scope=True)

        assert "**core:**" in formatted

    def test_format_breaking(self, breaking_commit: Commit):
        """Format breaking change commit."""
        config = CommitsConfig()
        pc = ParsedCommit.from_commit(breaking_commit, config.breaking_pattern)
        formatted = format_commit_for_changelog(pc)

        assert "[BREAKING]" in formatted

    def test_format_with_sha(self, feat_commit: Commit):
        """Format commit with SHA."""
        config = CommitsConfig()
        pc = ParsedCommit.from_commit(feat_commit, config.breaking_pattern)
        formatted = format_commit_for_changelog(pc, include_sha=True)

        assert "feat123" in formatted


# =============================================================================
# Skip Release Marker Tests
# =============================================================================


class TestFilterSkipReleaseCommits:
    """Tests for filter_skip_release_commits()."""

    def test_filter_with_skip_release_marker(self):
        """Commits with [skip release] are filtered out."""
        commits = [
            Commit("a", "feat: add feature", "T", "t@t.com", datetime.now()),
            Commit("b", "fix: bug fix [skip release]", "T", "t@t.com", datetime.now()),
            Commit("c", "docs: update readme", "T", "t@t.com", datetime.now()),
        ]
        filtered = filter_skip_release_commits(commits, ["[skip release]"])

        assert len(filtered) == 2
        assert filtered[0].sha == "a"
        assert filtered[1].sha == "c"

    def test_filter_with_release_skip_marker(self):
        """Commits with [release skip] are filtered out."""
        commits = [
            Commit("a", "feat: add feature [release skip]", "T", "t@t.com", datetime.now()),
            Commit("b", "fix: bug fix", "T", "t@t.com", datetime.now()),
        ]
        filtered = filter_skip_release_commits(commits, ["[release skip]"])

        assert len(filtered) == 1
        assert filtered[0].sha == "b"

    def test_filter_case_insensitive(self):
        """Skip markers are matched case-insensitively."""
        commits = [
            Commit("a", "feat: add feature [SKIP RELEASE]", "T", "t@t.com", datetime.now()),
            Commit("b", "fix: bug fix [Skip Release]", "T", "t@t.com", datetime.now()),
            Commit("c", "docs: update readme", "T", "t@t.com", datetime.now()),
        ]
        filtered = filter_skip_release_commits(commits, ["[skip release]"])

        assert len(filtered) == 1
        assert filtered[0].sha == "c"

    def test_filter_multiple_patterns(self):
        """Multiple skip patterns are all respected."""
        commits = [
            Commit("a", "feat: add feature [skip release]", "T", "t@t.com", datetime.now()),
            Commit("b", "fix: bug fix [no release]", "T", "t@t.com", datetime.now()),
            Commit("c", "docs: update readme [release skip]", "T", "t@t.com", datetime.now()),
            Commit("d", "chore: cleanup", "T", "t@t.com", datetime.now()),
        ]
        patterns = ["[skip release]", "[no release]", "[release skip]"]
        filtered = filter_skip_release_commits(commits, patterns)

        assert len(filtered) == 1
        assert filtered[0].sha == "d"

    def test_filter_empty_patterns_returns_all(self):
        """Empty patterns list returns all commits."""
        commits = [
            Commit("a", "feat: add feature [skip release]", "T", "t@t.com", datetime.now()),
            Commit("b", "fix: bug fix", "T", "t@t.com", datetime.now()),
        ]
        filtered = filter_skip_release_commits(commits, [])

        assert len(filtered) == 2

    def test_filter_marker_in_body(self):
        """Skip markers in commit body are also detected."""
        commits = [
            Commit(
                "a",
                "feat: add feature\n\nSome details [skip release]",
                "T",
                "t@t.com",
                datetime.now(),
            ),
            Commit("b", "fix: bug fix", "T", "t@t.com", datetime.now()),
        ]
        filtered = filter_skip_release_commits(commits, ["[skip release]"])

        assert len(filtered) == 1
        assert filtered[0].sha == "b"

    def test_filter_all_commits_skipped(self):
        """All commits with skip markers returns empty list."""
        commits = [
            Commit("a", "feat: add feature [skip release]", "T", "t@t.com", datetime.now()),
            Commit("b", "fix: bug fix [skip release]", "T", "t@t.com", datetime.now()),
        ]
        filtered = filter_skip_release_commits(commits, ["[skip release]"])

        assert len(filtered) == 0


# =============================================================================
# PR Title Validation Tests
# =============================================================================


class TestValidatePrTitle:
    """Tests for validate_pr_title()."""

    def test_valid_feat_title(self):
        """Valid feat: title passes validation."""
        result = validate_pr_title("feat: add user authentication")
        assert result.is_valid
        assert result.error is None
        assert result.commit_type == "feat"
        assert result.description == "add user authentication"
        assert not result.is_breaking

    def test_valid_fix_with_scope(self):
        """Valid fix(scope): title passes validation."""
        result = validate_pr_title("fix(api): handle null responses")
        assert result.is_valid
        assert result.commit_type == "fix"
        assert result.scope == "api"
        assert result.description == "handle null responses"

    def test_valid_breaking_change(self):
        """Breaking change with ! is detected."""
        result = validate_pr_title("feat!: redesign config format")
        assert result.is_valid
        assert result.is_breaking
        assert result.commit_type == "feat"

    def test_valid_breaking_with_scope(self):
        """Breaking change with scope and ! is detected."""
        result = validate_pr_title("feat(core)!: change API structure")
        assert result.is_valid
        assert result.is_breaking
        assert result.scope == "core"

    def test_invalid_empty_title(self):
        """Empty title fails validation."""
        result = validate_pr_title("")
        assert not result.is_valid
        assert result.error == "PR title cannot be empty"

    def test_invalid_whitespace_title(self):
        """Whitespace-only title fails validation."""
        result = validate_pr_title("   ")
        assert not result.is_valid
        assert result.error == "PR title cannot be empty"

    def test_invalid_non_conventional(self):
        """Non-conventional title fails validation."""
        result = validate_pr_title("Added a new feature")
        assert not result.is_valid
        assert "conventional commit format" in result.error.lower()

    def test_invalid_commit_type(self):
        """Unknown commit type fails validation."""
        result = validate_pr_title("unknown: some change")
        assert not result.is_valid
        assert "Invalid commit type" in result.error
        assert "unknown" in result.error

    def test_title_exceeds_max_length(self):
        """Title exceeding max length fails validation."""
        long_title = "feat: " + "a" * 100
        result = validate_pr_title(long_title, max_length=50)
        assert not result.is_valid
        assert "exceeds 50 characters" in result.error

    def test_require_scope_without_scope(self):
        """Title without scope fails when scope is required."""
        result = validate_pr_title("feat: add feature", require_scope=True)
        assert not result.is_valid
        assert "must include a scope" in result.error

    def test_require_scope_with_scope(self):
        """Title with scope passes when scope is required."""
        result = validate_pr_title("feat(api): add feature", require_scope=True)
        assert result.is_valid

    def test_empty_description(self):
        """Title with empty description fails validation."""
        result = validate_pr_title("feat:    ")
        assert not result.is_valid
        # Empty description doesn't match regex, so it fails format validation
        assert "conventional commit format" in result.error.lower()

    def test_custom_allowed_types(self):
        """Custom allowed types are respected."""
        custom_types = frozenset(["add", "remove", "change"])
        result = validate_pr_title("add: new feature", allowed_types=custom_types)
        assert result.is_valid
        assert result.commit_type == "add"

    def test_custom_allowed_types_rejects_standard(self):
        """Standard types rejected when custom types specified."""
        custom_types = frozenset(["add", "remove"])
        result = validate_pr_title("feat: new feature", allowed_types=custom_types)
        assert not result.is_valid
        assert "Invalid commit type" in result.error

    def test_all_default_types_valid(self):
        """All default commit types are valid."""
        for commit_type in DEFAULT_ALLOWED_TYPES:
            result = validate_pr_title(f"{commit_type}: some change")
            assert result.is_valid, f"Type '{commit_type}' should be valid"

    def test_case_insensitive_type(self):
        """Commit types are case-insensitive."""
        result = validate_pr_title("FEAT: uppercase type")
        assert result.is_valid
        assert result.commit_type == "feat"  # Normalized to lowercase


class TestValidatePrTitlesBatch:
    """Tests for validate_pr_titles_batch()."""

    def test_batch_validation(self):
        """Batch validation returns results for all titles."""
        titles = [
            "feat: add feature",
            "invalid title",
            "fix(api): handle error",
        ]
        results = validate_pr_titles_batch(titles)

        assert len(results) == 3
        assert results[0].is_valid
        assert not results[1].is_valid
        assert results[2].is_valid

    def test_batch_with_options(self):
        """Batch validation respects options."""
        titles = [
            "feat: no scope",
            "feat(api): with scope",
        ]
        results = validate_pr_titles_batch(titles, require_scope=True)

        assert not results[0].is_valid  # No scope
        assert results[1].is_valid  # Has scope

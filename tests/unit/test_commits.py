"""Tests for conventional commit parsing."""

from __future__ import annotations

from datetime import datetime

from releasio.config.models import CommitParser, CommitsConfig
from releasio.core.commits import (
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
from releasio.core.version import BumpType
from releasio.vcs.git import Commit


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
        assert result.error is not None
        assert "conventional commit format" in result.error.lower()

    def test_invalid_commit_type(self):
        """Unknown commit type fails validation."""
        result = validate_pr_title("unknown: some change")
        assert not result.is_valid
        assert result.error is not None
        assert "Invalid commit type" in result.error
        assert "unknown" in result.error

    def test_title_exceeds_max_length(self):
        """Title exceeding max length fails validation."""
        long_title = "feat: " + "a" * 100
        result = validate_pr_title(long_title, max_length=50)
        assert not result.is_valid
        assert result.error is not None
        assert "exceeds 50 characters" in result.error

    def test_require_scope_without_scope(self):
        """Title without scope fails when scope is required."""
        result = validate_pr_title("feat: add feature", require_scope=True)
        assert not result.is_valid
        assert result.error is not None
        assert "must include a scope" in result.error

    def test_require_scope_with_scope(self):
        """Title with scope passes when scope is required."""
        result = validate_pr_title("feat(api): add feature", require_scope=True)
        assert result.is_valid

    def test_empty_description(self):
        """Title with empty description fails validation."""
        result = validate_pr_title("feat:    ")
        assert not result.is_valid
        assert result.error is not None
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
        assert result.error is not None
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


# =============================================================================
# Custom Parser Tests
# =============================================================================


class TestCustomParsers:
    """Tests for custom commit parser support."""

    def test_gitmoji_sparkles_feat(self):
        """Parse Gitmoji :sparkles: as feat."""
        parser = CommitParser(
            pattern=r"^:sparkles:\s*(?P<description>.+)$",
            type="feat",
            group="✨ Features",
        )
        commit = Commit(
            sha="abc123",
            message=":sparkles: add new feature",
            author_name="Test",
            author_email="test@test.com",
            date=datetime.now(),
        )
        pc = ParsedCommit.from_commit(
            commit,
            breaking_pattern=r"BREAKING[ -]CHANGE:",
            custom_parsers=[parser],
        )

        assert pc.is_conventional
        assert pc.commit_type == "feat"
        assert pc.description == "add new feature"
        assert pc.changelog_group == "✨ Features"
        assert not pc.is_breaking

    def test_gitmoji_bug_fix(self):
        """Parse Gitmoji :bug: as fix."""
        parser = CommitParser(
            pattern=r"^:bug:\s*(?P<description>.+)$",
            type="fix",
            group="🐛 Bug Fixes",
        )
        commit = Commit(
            sha="abc123",
            message=":bug: fix authentication issue",
            author_name="Test",
            author_email="test@test.com",
            date=datetime.now(),
        )
        pc = ParsedCommit.from_commit(
            commit,
            breaking_pattern=r"BREAKING[ -]CHANGE:",
            custom_parsers=[parser],
        )

        assert pc.commit_type == "fix"
        assert pc.description == "fix authentication issue"
        assert pc.changelog_group == "🐛 Bug Fixes"

    def test_gitmoji_boom_breaking(self):
        """Parse Gitmoji :boom: as breaking change."""
        parser = CommitParser(
            pattern=r"^:boom:\s*(?P<description>.+)$",
            type="breaking",
            group="💥 Breaking Changes",
            breaking_indicator=":boom:",
        )
        commit = Commit(
            sha="abc123",
            message=":boom: redesign API",
            author_name="Test",
            author_email="test@test.com",
            date=datetime.now(),
        )
        pc = ParsedCommit.from_commit(
            commit,
            breaking_pattern=r"BREAKING[ -]CHANGE:",
            custom_parsers=[parser],
        )

        assert pc.commit_type == "breaking"
        assert pc.is_breaking
        assert pc.changelog_group == "💥 Breaking Changes"

    def test_custom_parser_with_scope(self):
        """Parse commit with custom scope extraction."""
        parser = CommitParser(
            pattern=r"^\[(?P<scope>\w+)\]\s*(?P<description>.+)$",
            type="change",
            group="Changes",
            scope_group="scope",
        )
        commit = Commit(
            sha="abc123",
            message="[api] update authentication",
            author_name="Test",
            author_email="test@test.com",
            date=datetime.now(),
        )
        pc = ParsedCommit.from_commit(
            commit,
            breaking_pattern=r"BREAKING[ -]CHANGE:",
            custom_parsers=[parser],
        )

        assert pc.commit_type == "change"
        assert pc.scope == "api"
        assert pc.description == "update authentication"

    def test_parser_order_matters(self):
        """First matching parser wins."""
        parsers = [
            CommitParser(
                pattern=r"^:sparkles:\s*(?P<description>.+)$",
                type="feat",
                group="Features",
            ),
            CommitParser(
                pattern=r"^:.*:\s*(?P<description>.+)$",  # Catch-all for emoji
                type="other",
                group="Other",
            ),
        ]
        commit = Commit(
            sha="abc123",
            message=":sparkles: add feature",
            author_name="Test",
            author_email="test@test.com",
            date=datetime.now(),
        )
        pc = ParsedCommit.from_commit(
            commit,
            breaking_pattern=r"BREAKING[ -]CHANGE:",
            custom_parsers=parsers,
        )

        # First parser should match
        assert pc.commit_type == "feat"
        assert pc.changelog_group == "Features"

    def test_fallback_to_conventional(self):
        """Fall back to conventional commits when no custom parser matches."""
        parser = CommitParser(
            pattern=r"^:sparkles:\s*(?P<description>.+)$",
            type="feat",
            group="Features",
        )
        commit = Commit(
            sha="abc123",
            message="fix(api): handle error",  # Conventional format
            author_name="Test",
            author_email="test@test.com",
            date=datetime.now(),
        )
        pc = ParsedCommit.from_commit(
            commit,
            breaking_pattern=r"BREAKING[ -]CHANGE:",
            custom_parsers=[parser],
            use_conventional_fallback=True,
        )

        # Should fall back to conventional parsing
        assert pc.commit_type == "fix"
        assert pc.scope == "api"
        assert pc.changelog_group is None  # No custom group from conventional

    def test_no_fallback_unmatched(self):
        """Without fallback, unmatched commits are non-conventional."""
        parser = CommitParser(
            pattern=r"^:sparkles:\s*(?P<description>.+)$",
            type="feat",
            group="Features",
        )
        commit = Commit(
            sha="abc123",
            message="fix(api): handle error",  # Conventional format
            author_name="Test",
            author_email="test@test.com",
            date=datetime.now(),
        )
        pc = ParsedCommit.from_commit(
            commit,
            breaking_pattern=r"BREAKING[ -]CHANGE:",
            custom_parsers=[parser],
            use_conventional_fallback=False,
        )

        # Should not match and not be conventional
        assert not pc.is_conventional
        assert pc.commit_type is None

    def test_parse_commits_with_custom_parsers(self):
        """parse_commits() uses custom parsers from config."""
        config = CommitsConfig(
            commit_parsers=[
                CommitParser(
                    pattern=r"^:sparkles:\s*(?P<description>.+)$",
                    type="feat",
                    group="Features",
                ),
                CommitParser(
                    pattern=r"^:bug:\s*(?P<description>.+)$",
                    type="fix",
                    group="Bug Fixes",
                ),
            ],
        )
        commits = [
            Commit(
                sha="abc123",
                message=":sparkles: add feature",
                author_name="Test",
                author_email="test@test.com",
                date=datetime.now(),
            ),
            Commit(
                sha="def456",
                message=":bug: fix bug",
                author_name="Test",
                author_email="test@test.com",
                date=datetime.now(),
            ),
            Commit(
                sha="ghi789",
                message="fix: conventional fix",  # Should fall back
                author_name="Test",
                author_email="test@test.com",
                date=datetime.now(),
            ),
        ]
        parsed = parse_commits(commits, config)

        assert len(parsed) == 3
        assert parsed[0].commit_type == "feat"
        assert parsed[0].changelog_group == "Features"
        assert parsed[1].commit_type == "fix"
        assert parsed[1].changelog_group == "Bug Fixes"
        assert parsed[2].commit_type == "fix"
        assert parsed[2].changelog_group is None  # Conventional fallback

    def test_invalid_regex_pattern_skipped(self):
        """Invalid regex patterns are gracefully skipped."""
        parser = CommitParser(
            pattern=r"^[invalid(regex$",  # Invalid regex
            type="feat",
            group="Features",
        )
        commit = Commit(
            sha="abc123",
            message="feat: add feature",
            author_name="Test",
            author_email="test@test.com",
            date=datetime.now(),
        )
        # Should not crash, just skip the invalid parser and fall back
        pc = ParsedCommit.from_commit(
            commit,
            breaking_pattern=r"BREAKING[ -]CHANGE:",
            custom_parsers=[parser],
        )

        # Falls back to conventional
        assert pc.commit_type == "feat"
        assert pc.is_conventional

    def test_breaking_in_body_with_custom_parser(self):
        """Breaking change in body detected with custom parser."""
        parser = CommitParser(
            pattern=r"^:sparkles:\s*(?P<description>.+)$",
            type="feat",
            group="Features",
        )
        commit = Commit(
            sha="abc123",
            message=":sparkles: add feature\n\nBREAKING CHANGE: API changed",
            author_name="Test",
            author_email="test@test.com",
            date=datetime.now(),
        )
        pc = ParsedCommit.from_commit(
            commit,
            breaking_pattern=r"BREAKING[ -]CHANGE:",
            custom_parsers=[parser],
        )

        assert pc.commit_type == "feat"
        assert pc.is_breaking  # Detected from body

    def test_invalid_regex_in_custom_parser_is_skipped(self):
        """Custom parser with invalid regex is gracefully skipped."""
        # Invalid regex (unclosed bracket)
        invalid_parser = CommitParser(
            pattern=r"^[unclosed",
            type="feat",
            group="Features",
        )
        valid_parser = CommitParser(
            pattern=r"^:sparkles:\s*(?P<description>.+)$",
            type="feat",
            group="Features",
        )
        commit = Commit(
            sha="abc123",
            message=":sparkles: add new feature",
            author_name="Test",
            author_email="test@test.com",
            date=datetime.now(),
        )
        # Should not raise, invalid parser is skipped and valid one matches
        pc = ParsedCommit.from_commit(
            commit,
            breaking_pattern=r"BREAKING[ -]CHANGE:",
            custom_parsers=[invalid_parser, valid_parser],
        )

        assert pc.is_conventional
        assert pc.commit_type == "feat"
        assert pc.description == "add new feature"

    def test_only_invalid_regex_falls_back_to_conventional(self):
        """When only invalid regex parser provided, falls back to conventional."""
        invalid_parser = CommitParser(
            pattern=r"^[unclosed",
            type="feat",
            group="Features",
        )
        commit = Commit(
            sha="abc123",
            message="feat: add new feature",
            author_name="Test",
            author_email="test@test.com",
            date=datetime.now(),
        )
        # Invalid parser is skipped, falls back to conventional commit parsing
        pc = ParsedCommit.from_commit(
            commit,
            breaking_pattern=r"BREAKING[ -]CHANGE:",
            custom_parsers=[invalid_parser],
        )

        assert pc.is_conventional
        assert pc.commit_type == "feat"
        assert pc.description == "add new feature"

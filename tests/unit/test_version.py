"""Tests for version parsing and manipulation."""

from __future__ import annotations

import pytest
from hypothesis import given
from hypothesis import strategies as st

from release_py.core.version import BumpType, PreRelease, Version, parse_version
from release_py.exceptions import InvalidVersionError


class TestVersionParsing:
    """Tests for Version.parse()."""

    def test_parse_simple_version(self):
        """Parse a simple version string."""
        v = Version.parse("1.2.3")
        assert v.major == 1
        assert v.minor == 2
        assert v.patch == 3
        assert v.pre is None
        assert v.local is None

    def test_parse_version_with_v_prefix(self):
        """Parse version with 'v' prefix."""
        v = Version.parse("v1.2.3")
        assert v.major == 1
        assert v.minor == 2
        assert v.patch == 3

    def test_parse_version_with_prerelease_alpha(self):
        """Parse version with alpha pre-release."""
        v = Version.parse("1.0.0a1")
        assert v.major == 1
        assert v.minor == 0
        assert v.patch == 0
        assert v.pre is not None
        assert v.pre.phase == "alpha"
        assert v.pre.number == 1

    def test_parse_version_with_prerelease_beta(self):
        """Parse version with beta pre-release."""
        v = Version.parse("2.0.0-beta.2")
        assert v.pre is not None
        assert v.pre.phase == "beta"
        assert v.pre.number == 2

    def test_parse_version_with_prerelease_rc(self):
        """Parse version with rc pre-release."""
        v = Version.parse("3.0.0rc1")
        assert v.pre is not None
        assert v.pre.phase == "rc"
        assert v.pre.number == 1

    def test_parse_version_with_local(self):
        """Parse version with local identifier."""
        v = Version.parse("1.0.0+local.build.123")
        assert v.local == "local.build.123"

    def test_parse_invalid_version_raises(self):
        """Invalid version strings raise InvalidVersionError."""
        with pytest.raises(InvalidVersionError):
            Version.parse("not-a-version")

    def test_parse_empty_string_raises(self):
        """Empty string raises InvalidVersionError."""
        with pytest.raises(InvalidVersionError):
            Version.parse("")

    def test_parse_negative_version_raises(self):
        """Negative version numbers raise InvalidVersionError."""
        with pytest.raises(InvalidVersionError):
            Version.parse("-1.0.0")


class TestVersionStr:
    """Tests for Version.__str__()."""

    def test_str_simple_version(self):
        """String representation of simple version."""
        v = Version(major=1, minor=2, patch=3)
        assert str(v) == "1.2.3"

    def test_str_with_prerelease(self):
        """String representation with pre-release."""
        v = Version(major=1, minor=0, patch=0, pre=PreRelease("alpha", 1))
        assert str(v) == "1.0.0a1"

    def test_str_with_local(self):
        """String representation with local identifier."""
        v = Version(major=1, minor=0, patch=0, local="dev")
        assert str(v) == "1.0.0+dev"


class TestVersionComparison:
    """Tests for version comparison."""

    def test_equal_versions(self):
        """Equal versions compare as equal."""
        v1 = Version.parse("1.2.3")
        v2 = Version.parse("1.2.3")
        assert v1 == v2

    def test_different_versions(self):
        """Different versions compare as not equal."""
        v1 = Version.parse("1.2.3")
        v2 = Version.parse("1.2.4")
        assert v1 != v2

    def test_version_ordering(self):
        """Versions are ordered correctly."""
        v1 = Version.parse("1.0.0")
        v2 = Version.parse("1.0.1")
        v3 = Version.parse("1.1.0")
        v4 = Version.parse("2.0.0")

        assert v1 < v2 < v3 < v4

    def test_prerelease_less_than_release(self):
        """Pre-release versions are less than release."""
        pre = Version.parse("1.0.0a1")
        release = Version.parse("1.0.0")
        assert pre < release

    def test_prerelease_ordering(self):
        """Pre-release versions are ordered correctly."""
        alpha = Version.parse("1.0.0a1")
        beta = Version.parse("1.0.0b1")
        rc = Version.parse("1.0.0rc1")
        release = Version.parse("1.0.0")

        assert alpha < beta < rc < release


class TestVersionBump:
    """Tests for version bumping."""

    def test_bump_patch(self):
        """Bump patch version."""
        v = Version.parse("1.2.3")
        bumped = v.bump(BumpType.PATCH)
        assert str(bumped) == "1.2.4"

    def test_bump_minor(self):
        """Bump minor version resets patch."""
        v = Version.parse("1.2.3")
        bumped = v.bump(BumpType.MINOR)
        assert str(bumped) == "1.3.0"

    def test_bump_major(self):
        """Bump major version resets minor and patch."""
        v = Version.parse("1.2.3")
        bumped = v.bump(BumpType.MAJOR)
        assert str(bumped) == "2.0.0"

    def test_bump_none(self):
        """Bump none returns base version."""
        v = Version.parse("1.2.3")
        bumped = v.bump(BumpType.NONE)
        assert str(bumped) == "1.2.3"

    def test_initial_development_major_bump(self):
        """In 0.x.y, major bump becomes minor bump."""
        v = Version.parse("0.5.3")
        bumped = v.bump(BumpType.MAJOR)
        assert str(bumped) == "0.6.0"

    def test_bump_removes_prerelease(self):
        """Bumping removes pre-release identifier."""
        v = Version.parse("1.0.0a1")
        bumped = v.bump(BumpType.PATCH)
        assert v.is_prerelease
        assert not bumped.is_prerelease


class TestVersionProperties:
    """Tests for version properties."""

    def test_is_prerelease(self):
        """is_prerelease property works correctly."""
        assert Version.parse("1.0.0a1").is_prerelease
        assert Version.parse("1.0.0b2").is_prerelease
        assert Version.parse("1.0.0rc1").is_prerelease
        assert not Version.parse("1.0.0").is_prerelease

    def test_is_initial_development(self):
        """is_initial_development property works correctly."""
        assert Version.parse("0.1.0").is_initial_development
        assert Version.parse("0.99.99").is_initial_development
        assert not Version.parse("1.0.0").is_initial_development

    def test_short_sha(self):
        """short_sha returns first 7 characters."""
        from datetime import datetime

        from release_py.vcs.git import Commit

        c = Commit("abc1234567890", "msg", "author", "email", datetime.now())
        assert c.short_sha == "abc1234"

    def test_with_tag_prefix(self):
        """with_tag_prefix adds prefix correctly."""
        v = Version.parse("1.2.3")
        assert v.with_tag_prefix() == "v1.2.3"
        assert v.with_tag_prefix("release-") == "release-1.2.3"


class TestPreRelease:
    """Tests for PreRelease class."""

    def test_parse_alpha(self):
        """Parse alpha pre-release."""
        pr = PreRelease.parse("alpha.1")
        assert pr.phase == "alpha"
        assert pr.number == 1

    def test_parse_short_form(self):
        """Parse short form pre-release."""
        pr = PreRelease.parse("a1")
        assert pr.phase == "alpha"
        assert pr.number == 1

    def test_str_output(self):
        """String representation is PEP 440 compatible."""
        assert str(PreRelease("alpha", 1)) == "a1"
        assert str(PreRelease("beta", 2)) == "b2"
        assert str(PreRelease("rc", 3)) == "rc3"

    def test_next(self):
        """next() increments the number."""
        pr = PreRelease("alpha", 1)
        assert pr.next() == PreRelease("alpha", 2)


class TestParseVersionFunction:
    """Tests for the parse_version convenience function."""

    def test_parse_version_function(self):
        """parse_version function works like Version.parse."""
        v = parse_version("1.2.3")
        assert isinstance(v, Version)
        assert str(v) == "1.2.3"


# =============================================================================
# Pre-1.0.0 Semver Handling Tests
# =============================================================================


class TestPre100SemverHandling:
    """Comprehensive tests for Pre-1.0.0 semver handling.

    According to semantic versioning specification:
    - Major version zero (0.y.z) is for initial development
    - Anything MAY change at any time
    - The public API SHOULD NOT be considered stable
    - Breaking changes in 0.x.y should bump MINOR, not MAJOR

    This is critical for projects in early development where breaking
    changes are expected and should not prematurely bump to 1.0.0.
    """

    def test_0x_major_bump_becomes_minor_bump(self):
        """Breaking changes in 0.x.y versions should bump minor, not major.

        This prevents accidental jumps to 1.0.0 during early development.
        """
        v = Version.parse("0.5.3")
        bumped = v.bump(BumpType.MAJOR)

        # Should NOT be 1.0.0
        assert bumped.major == 0
        # Should bump minor
        assert bumped.minor == 6
        # Should reset patch
        assert bumped.patch == 0
        assert str(bumped) == "0.6.0"

    def test_0x_minor_bump_works_normally(self):
        """Minor bumps in 0.x.y work as expected."""
        v = Version.parse("0.3.5")
        bumped = v.bump(BumpType.MINOR)

        assert bumped.major == 0
        assert bumped.minor == 4
        assert bumped.patch == 0
        assert str(bumped) == "0.4.0"

    def test_0x_patch_bump_works_normally(self):
        """Patch bumps in 0.x.y work as expected."""
        v = Version.parse("0.3.5")
        bumped = v.bump(BumpType.PATCH)

        assert bumped.major == 0
        assert bumped.minor == 3
        assert bumped.patch == 6
        assert str(bumped) == "0.3.6"

    def test_0_0_x_edge_case(self):
        """0.0.x versions also handle major bump correctly."""
        v = Version.parse("0.0.1")
        bumped = v.bump(BumpType.MAJOR)

        assert str(bumped) == "0.1.0"

    def test_0_99_99_edge_case(self):
        """High 0.x.y versions don't overflow to 1.0.0."""
        v = Version.parse("0.99.99")
        bumped = v.bump(BumpType.MAJOR)

        assert str(bumped) == "0.100.0"

    def test_1x_major_bump_works_normally(self):
        """Post-1.0.0 versions bump major normally."""
        v = Version.parse("1.2.3")
        bumped = v.bump(BumpType.MAJOR)

        assert str(bumped) == "2.0.0"

    def test_transition_to_1_0_0_is_explicit(self):
        """Users must explicitly set 1.0.0 - it's not automatic."""
        # A project at 0.99.0 with a breaking change
        v = Version.parse("0.99.0")
        bumped = v.bump(BumpType.MAJOR)

        # Still stays at 0.x.y
        assert bumped.major == 0
        assert str(bumped) == "0.100.0"

        # To reach 1.0.0, user must use version override
        v1 = Version.parse("1.0.0")
        assert str(v1) == "1.0.0"

    def test_is_initial_development_property(self):
        """is_initial_development correctly identifies 0.x.y versions."""
        assert Version.parse("0.0.1").is_initial_development
        assert Version.parse("0.1.0").is_initial_development
        assert Version.parse("0.99.99").is_initial_development
        assert Version.parse("0.0.0").is_initial_development

        assert not Version.parse("1.0.0").is_initial_development
        assert not Version.parse("1.0.0a1").is_initial_development
        assert not Version.parse("2.5.3").is_initial_development

    def test_0x_with_prerelease_major_bump(self):
        """0.x.y with pre-release handles major bump correctly."""
        v = Version.parse("0.5.0a1")
        bumped = v.bump(BumpType.MAJOR)

        # Should bump minor, remove prerelease
        assert str(bumped) == "0.6.0"
        assert not bumped.is_prerelease

    def test_sequential_0x_major_bumps(self):
        """Multiple sequential major bumps in 0.x.y stay in 0.x.y."""
        v = Version.parse("0.1.0")

        # Simulate multiple breaking changes over time
        v = v.bump(BumpType.MAJOR)
        assert str(v) == "0.2.0"

        v = v.bump(BumpType.MAJOR)
        assert str(v) == "0.3.0"

        v = v.bump(BumpType.MAJOR)
        assert str(v) == "0.4.0"

        # Still in initial development
        assert v.is_initial_development

    def test_comparison_across_0x_1x_boundary(self):
        """Version comparison works across 0.x.y to 1.x.y boundary."""
        v0 = Version.parse("0.99.99")
        v1 = Version.parse("1.0.0")

        assert v0 < v1
        assert v1 > v0

    def test_all_bump_types_on_0x(self):
        """All bump types work correctly on 0.x.y versions."""
        v = Version.parse("0.5.5")

        assert str(v.bump(BumpType.NONE)) == "0.5.5"
        assert str(v.bump(BumpType.PATCH)) == "0.5.6"
        assert str(v.bump(BumpType.MINOR)) == "0.6.0"
        assert str(v.bump(BumpType.MAJOR)) == "0.6.0"  # Same as MINOR for 0.x.y


# =============================================================================
# Property-based tests
# =============================================================================


class TestVersionHypothesis:
    """Property-based tests for Version."""

    @given(
        major=st.integers(min_value=0, max_value=100),
        minor=st.integers(min_value=0, max_value=100),
        patch=st.integers(min_value=0, max_value=100),
    )
    def test_parse_roundtrip(self, major: int, minor: int, patch: int):
        """Version.parse(str(v)) == v for all valid versions."""
        v = Version(major=major, minor=minor, patch=patch)
        parsed = Version.parse(str(v))
        assert parsed == v

    @given(
        major=st.integers(min_value=0, max_value=100),
        minor=st.integers(min_value=0, max_value=100),
        patch=st.integers(min_value=0, max_value=100),
    )
    def test_bump_increases_version(self, major: int, minor: int, patch: int):
        """Bumping always increases the version (except NONE)."""
        v = Version(major=major, minor=minor, patch=patch)

        assert v.bump(BumpType.PATCH) > v
        assert v.bump(BumpType.MINOR) > v

        # MAJOR bump is special for 0.x.y versions
        if major > 0:
            assert v.bump(BumpType.MAJOR) > v

    @given(
        major=st.integers(min_value=0, max_value=100),
        minor=st.integers(min_value=0, max_value=100),
        patch=st.integers(min_value=0, max_value=100),
    )
    def test_version_hash_consistent(self, major: int, minor: int, patch: int):
        """Equal versions have equal hashes."""
        v1 = Version(major=major, minor=minor, patch=patch)
        v2 = Version(major=major, minor=minor, patch=patch)
        assert hash(v1) == hash(v2)

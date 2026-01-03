"""Semantic version parsing and manipulation.

This module provides a PEP 440 compliant version class with support for:
- Parsing version strings
- Comparing versions
- Bumping major/minor/patch versions
- Pre-release versions (alpha, beta, rc)

Example:
    >>> v = Version.parse("1.2.3")
    >>> v.bump(BumpType.MINOR)
    Version(major=1, minor=3, patch=0, pre=None)

    >>> v = Version.parse("0.9.0")
    >>> v.bump(BumpType.MAJOR)  # 0.x.y: major bump → minor bump
    Version(major=0, minor=10, patch=0, pre=None)
"""

from __future__ import annotations

import re
from dataclasses import dataclass
from enum import Enum
from functools import total_ordering
from typing import Self

from release_py.exceptions import InvalidVersionError


class BumpType(Enum):
    """Types of version bumps following semantic versioning."""

    MAJOR = "major"
    MINOR = "minor"
    PATCH = "patch"
    NONE = "none"  # No version change needed

    def __str__(self) -> str:
        return self.value


@dataclass(frozen=True, slots=True)
class PreRelease:
    """Pre-release version component (e.g., alpha.1, beta.2, rc.1).

    Follows PEP 440 pre-release naming:
    - 'a' or 'alpha' → alpha
    - 'b' or 'beta' → beta
    - 'rc' → release candidate
    """

    phase: str  # "alpha", "beta", or "rc"
    number: int

    @classmethod
    def parse(cls, pre_str: str) -> Self:
        """Parse a pre-release string.

        Args:
            pre_str: Pre-release string (e.g., "alpha.1", "a1", "rc.3")

        Returns:
            PreRelease instance

        Raises:
            InvalidVersionError: If the string is not a valid pre-release
        """
        # Normalize phase names
        normalized = pre_str.lower()
        normalized = normalized.replace("alpha", "a").replace("beta", "b")

        # Match patterns like: a1, a.1, alpha1, alpha.1, rc1, rc.1
        match = re.match(r"^(a|b|rc)\.?(\d+)$", normalized)
        if not match:
            raise InvalidVersionError(
                pre_str,
                reason="Pre-release must be alpha/beta/rc followed by a number",
            )

        phase_short = match.group(1)
        number = int(match.group(2))

        # Expand to full phase name
        phase_map = {"a": "alpha", "b": "beta", "rc": "rc"}
        phase = phase_map[phase_short]

        return cls(phase=phase, number=number)

    def __str__(self) -> str:
        """Return PEP 440 compatible string (e.g., 'a1', 'b2', 'rc1')."""
        short = {"alpha": "a", "beta": "b", "rc": "rc"}[self.phase]
        return f"{short}{self.number}"

    def __lt__(self, other: object) -> bool:
        if not isinstance(other, PreRelease):
            return NotImplemented
        # Phase ordering: alpha < beta < rc
        phase_order = {"alpha": 0, "beta": 1, "rc": 2}
        self_order = phase_order.get(self.phase, 99)
        other_order = phase_order.get(other.phase, 99)
        if self_order != other_order:
            return self_order < other_order
        return self.number < other.number

    def next(self) -> PreRelease:
        """Return the next pre-release in the same phase."""
        return PreRelease(phase=self.phase, number=self.number + 1)


# Regex for parsing PEP 440 version strings
_VERSION_PATTERN = re.compile(
    r"""
    ^
    (?P<major>0|[1-9]\d*)
    \.
    (?P<minor>0|[1-9]\d*)
    \.
    (?P<patch>0|[1-9]\d*)
    (?:
        (?P<pre_sep>[-.])?
        (?P<pre>(?:a|alpha|b|beta|rc)\.?\d+)
    )?
    (?:
        \+
        (?P<local>[a-zA-Z0-9]+(?:[._-][a-zA-Z0-9]+)*)
    )?
    $
    """,
    re.VERBOSE | re.IGNORECASE,
)


@total_ordering
@dataclass(frozen=True, slots=True)
class Version:
    """A semantic version following PEP 440.

    Supports:
    - Standard versions: 1.2.3
    - Pre-release versions: 1.2.3a1, 1.2.3-beta.2, 1.2.3-rc.1
    - Local versions: 1.2.3+local.build

    Attributes:
        major: Major version number
        minor: Minor version number
        patch: Patch version number
        pre: Pre-release component (alpha, beta, rc)
        local: Local version label

    Example:
        >>> v = Version(major=1, minor=2, patch=3)
        >>> str(v)
        '1.2.3'

        >>> v = Version(major=1, minor=0, patch=0, pre=PreRelease("alpha", 1))
        >>> str(v)
        '1.0.0a1'
    """

    major: int
    minor: int
    patch: int
    pre: PreRelease | None = None
    local: str | None = None

    def __post_init__(self) -> None:
        """Validate version components."""
        if self.major < 0:
            raise InvalidVersionError(str(self), "Major version cannot be negative")
        if self.minor < 0:
            raise InvalidVersionError(str(self), "Minor version cannot be negative")
        if self.patch < 0:
            raise InvalidVersionError(str(self), "Patch version cannot be negative")

    @classmethod
    def parse(cls, version_str: str) -> Self:
        """Parse a version string into a Version object.

        Args:
            version_str: Version string (e.g., "1.2.3", "1.0.0a1")

        Returns:
            Version instance

        Raises:
            InvalidVersionError: If the string is not a valid version

        Example:
            >>> Version.parse("1.2.3")
            Version(major=1, minor=2, patch=3, pre=None, local=None)

            >>> Version.parse("2.0.0-rc.1")
            Version(major=2, minor=0, patch=0, pre=PreRelease('rc', 1), local=None)
        """
        # Strip leading 'v' if present
        version_str = version_str.lstrip("v")

        match = _VERSION_PATTERN.match(version_str)
        if not match:
            raise InvalidVersionError(
                version_str,
                reason="Version must be in format MAJOR.MINOR.PATCH[-PRERELEASE][+LOCAL]",
            )

        groups = match.groupdict()

        pre = None
        if groups["pre"]:
            pre = PreRelease.parse(groups["pre"])

        return cls(
            major=int(groups["major"]),
            minor=int(groups["minor"]),
            patch=int(groups["patch"]),
            pre=pre,
            local=groups.get("local"),
        )

    def __str__(self) -> str:
        """Return the version as a PEP 440 compliant string."""
        version = f"{self.major}.{self.minor}.{self.patch}"
        if self.pre:
            version = f"{version}{self.pre}"
        if self.local:
            version = f"{version}+{self.local}"
        return version

    def __lt__(self, other: object) -> bool:
        """Compare versions for ordering.

        Pre-release versions are less than the release version:
        1.0.0a1 < 1.0.0b1 < 1.0.0rc1 < 1.0.0
        """
        if not isinstance(other, Version):
            return NotImplemented

        # Compare major.minor.patch first
        self_tuple = (self.major, self.minor, self.patch)
        other_tuple = (other.major, other.minor, other.patch)

        if self_tuple != other_tuple:
            return self_tuple < other_tuple

        # Same base version - compare pre-release
        # A version without pre-release is greater than one with
        if self.pre is None and other.pre is None:
            return False
        if self.pre is None:
            return False  # self is release, other is pre-release
        if other.pre is None:
            return True  # self is pre-release, other is release

        return self.pre < other.pre

    def __eq__(self, other: object) -> bool:
        if not isinstance(other, Version):
            return NotImplemented
        return (
            self.major == other.major
            and self.minor == other.minor
            and self.patch == other.patch
            and self.pre == other.pre
            # Note: local versions are ignored for equality per PEP 440
        )

    def __hash__(self) -> int:
        return hash((self.major, self.minor, self.patch, self.pre))

    @property
    def is_prerelease(self) -> bool:
        """Check if this is a pre-release version."""
        return self.pre is not None

    @property
    def is_initial_development(self) -> bool:
        """Check if this is an initial development version (0.x.y).

        During initial development, the public API is unstable and
        breaking changes may occur in minor version bumps.
        """
        return self.major == 0

    @property
    def base_version(self) -> Version:
        """Return the base version without pre-release or local."""
        return Version(major=self.major, minor=self.minor, patch=self.patch)

    def with_tag_prefix(self, prefix: str = "v") -> str:
        """Return the version with a tag prefix.

        Args:
            prefix: Prefix to add (default: 'v')

        Returns:
            Version string with prefix (e.g., 'v1.2.3')
        """
        return f"{prefix}{self}"

    def bump(self, bump_type: BumpType) -> Version:
        """Create a new version with the specified bump applied.

        For 0.x.y versions (initial development), major bumps are
        treated as minor bumps since the API is still unstable.

        Args:
            bump_type: Type of version bump to apply

        Returns:
            New Version instance with the bump applied

        Example:
            >>> Version(1, 2, 3).bump(BumpType.MINOR)
            Version(major=1, minor=3, patch=0, pre=None, local=None)

            >>> Version(0, 9, 5).bump(BumpType.MAJOR)
            Version(major=0, minor=10, patch=0, pre=None, local=None)
        """
        match bump_type:
            case BumpType.NONE:
                return self.base_version

            case BumpType.PATCH:
                return Version(
                    major=self.major,
                    minor=self.minor,
                    patch=self.patch + 1,
                )

            case BumpType.MINOR:
                return Version(
                    major=self.major,
                    minor=self.minor + 1,
                    patch=0,
                )

            case BumpType.MAJOR:
                if self.is_initial_development:
                    # 0.x.y: major changes only bump minor
                    return Version(
                        major=0,
                        minor=self.minor + 1,
                        patch=0,
                    )
                return Version(
                    major=self.major + 1,
                    minor=0,
                    patch=0,
                )

    def with_prerelease(self, phase: str, number: int = 1) -> Version:
        """Create a pre-release version.

        Args:
            phase: Pre-release phase ('alpha', 'beta', or 'rc')
            number: Pre-release number (default: 1)

        Returns:
            New Version with pre-release

        Example:
            >>> Version(1, 0, 0).with_prerelease("alpha")
            Version(major=1, minor=0, patch=0, pre=PreRelease('alpha', 1), local=None)
        """
        return Version(
            major=self.major,
            minor=self.minor,
            patch=self.patch,
            pre=PreRelease(phase=phase, number=number),
        )

    def next_prerelease(self) -> Version:
        """Bump to next pre-release version.

        If already a pre-release, increments the number.
        If a release version, creates alpha.1 of the next patch.

        Returns:
            Next pre-release version

        Example:
            >>> Version.parse("1.0.0a1").next_prerelease()
            Version(major=1, minor=0, patch=0, pre=PreRelease('alpha', 2), local=None)
        """
        if self.pre:
            return Version(
                major=self.major,
                minor=self.minor,
                patch=self.patch,
                pre=self.pre.next(),
            )
        # Create first pre-release of next patch
        return Version(
            major=self.major,
            minor=self.minor,
            patch=self.patch + 1,
            pre=PreRelease(phase="alpha", number=1),
        )


def parse_version(version_str: str) -> Version:
    """Convenience function to parse a version string.

    Args:
        version_str: Version string to parse

    Returns:
        Parsed Version object

    Raises:
        InvalidVersionError: If the string is not a valid version
    """
    return Version.parse(version_str)

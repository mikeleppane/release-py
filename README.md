# release-py

[![PyPI version](https://img.shields.io/pypi/v/release-py.svg)](https://pypi.org/project/release-py/)
[![Python versions](https://img.shields.io/pypi/pyversions/release-py.svg)](https://pypi.org/project/release-py/)
[![License](https://img.shields.io/github/license/mikeleppane/release-py.svg)](https://github.com/mikeleppane/release-py/blob/main/LICENSE)
[![CI](https://github.com/mikeleppane/release-py/actions/workflows/ci.yml/badge.svg)](https://github.com/mikeleppane/release-py/actions/workflows/ci.yml)
[![codecov](https://codecov.io/gh/mikeleppane/release-py/branch/main/graph/badge.svg)](https://codecov.io/gh/mikeleppane/release-py)
[![Ruff](https://img.shields.io/endpoint?url=https://raw.githubusercontent.com/astral-sh/ruff/main/assets/badge/v2.json)](https://github.com/astral-sh/ruff)
[![Checked with mypy](https://www.mypy-lang.org/static/mypy_badge.svg)](https://mypy-lang.org/)
[![uv](https://img.shields.io/endpoint?url=https://raw.githubusercontent.com/astral-sh/uv/main/assets/badge/v0.json)](https://github.com/astral-sh/uv)

**Best-in-class Python release automation**, inspired by [release-plz](https://github.com/MarcoIeni/release-plz).

release-py automates version bumping, changelog generation, and publishing for Python projects. It uses [Conventional Commits](https://www.conventionalcommits.org/) to determine version bumps and generates beautiful changelogs.

## Features

- **Release PR Workflow** - Automatically creates and maintains a release PR with version bump and changelog
- **Conventional Commits** - Automatic version bumping based on commit types (`feat:`, `fix:`, etc.)
- **Beautiful Changelogs** - Professional changelog generation with PR links and author attribution
- **Zero Config** - Works out of the box with sensible defaults
- **GitHub Actions** - First-class GitHub Actions support with outputs
- **Pre-1.0.0 Semver** - Proper handling of 0.x.y versions (breaking changes bump minor, not major)
- **Pre-release Versions** - Support for alpha, beta, and rc versions
- **Monorepo Ready** - Independent versioning per package (coming soon)
- **Typed** - Full type annotations with `py.typed` marker

## Installation

```bash
# Using uv (recommended)
uv tool install release-py

# Using pip
pip install release-py

# Using pipx
pipx install release-py
```

## Quick Start

### 1. Check what would happen

```bash
release-py check
```

This shows you what version bump would occur based on commits since the last tag.

### 2. Update version and changelog locally

```bash
# Preview changes (dry-run)
release-py update

# Apply changes
release-py update --execute
```

### 3. Create a Release PR (recommended workflow)

```bash
# Preview the PR
release-py release-pr --dry-run

# Create/update the PR
release-py release-pr
```

### 4. Perform the release

After merging the release PR:

```bash
release-py release
```

This creates a git tag, publishes to PyPI, and creates a GitHub release.

## CLI Commands

### `release-py check`

Preview what would happen during a release without making changes.

```bash
release-py check [PATH] [--verbose]
```

### `release-py update`

Update version and changelog locally.

```bash
release-py update [PATH] [OPTIONS]

Options:
  --execute, -x          Apply changes (default is dry-run)
  --version, -v TEXT     Override calculated version
  --prerelease TEXT      Create pre-release (alpha, beta, rc)
```

**Examples:**

```bash
release-py update                      # Preview changes
release-py update --execute            # Apply changes
release-py update --version 2.0.0 -x   # Force specific version
release-py update --prerelease alpha   # Create 1.2.0a1
```

### `release-py release-pr`

Create or update a release pull request.

```bash
release-py release-pr [PATH] [--dry-run]
```

The PR includes:

- Version bump in `pyproject.toml`
- Updated changelog
- Professional PR body with all changes listed

### `release-py release`

Perform a release: tag, publish, and create GitHub release.

```bash
release-py release [PATH] [OPTIONS]

Options:
  --dry-run              Preview without making changes
  --skip-publish         Skip PyPI publishing
```

### `release-py check-pr`

Validate that a PR title follows Conventional Commits format.

```bash
release-py check-pr [--require-scope]
```

## Configuration

Configuration is read from `pyproject.toml` under `[tool.release-py]`.

### Full Configuration Reference

```toml
[tool.release-py]
# Core settings
default_branch = "main"          # Branch for releases
allow_dirty = false              # Allow releases from dirty working directory
tag_prefix = "v"                 # Git tag prefix (v1.0.0)
changelog_path = "CHANGELOG.md"  # Path to changelog file

[tool.release-py.version]
initial_version = "0.1.0"        # Version for first release
tag_prefix = "v"                 # Can override top-level tag_prefix
version_files = []               # Additional files to update version in

[tool.release-py.commits]
types_minor = ["feat"]           # Commit types triggering minor bump
types_patch = ["fix", "perf"]    # Commit types triggering patch bump
breaking_pattern = "BREAKING[ -]CHANGE:"  # Pattern for breaking changes
skip_release_patterns = [        # Commits to exclude from releases
    "[skip release]",
    "[release skip]",
    "[no release]"
]

[tool.release-py.changelog]
enabled = true                   # Whether to generate changelog
path = "CHANGELOG.md"            # Changelog file path
use_github_prs = false           # Use PR-based changelog (for squash merges)

[tool.release-py.github]
owner = ""                       # GitHub owner (auto-detected)
repo = ""                        # GitHub repo (auto-detected)
api_url = "https://api.github.com"  # API URL (for GitHub Enterprise)
release_pr_branch = "release-py/release"  # Branch for release PRs
release_pr_labels = ["release"]  # Labels for release PRs
draft_releases = false           # Create releases as drafts

[tool.release-py.publish]
enabled = true                   # Whether to publish to PyPI
registry = "https://upload.pypi.org/legacy/"
tool = "uv"                      # Publishing tool: "uv" or "twine"
trusted_publishing = true        # Use OIDC trusted publishing

[tool.release-py.hooks]
pre_bump = []                    # Commands before version bump
post_bump = []                   # Commands after version bump
pre_release = []                 # Commands before release
post_release = []                # Commands after release
```

### Minimal Configuration

For most projects, you don't need any configuration! release-py works with sensible defaults.

If you want to customize, a minimal config might look like:

```toml
[tool.release-py]
default_branch = "main"

[tool.release-py.commits]
types_patch = ["fix", "perf", "docs"]  # Include docs in patch releases
```

## GitHub Actions

release-py provides a GitHub Action for seamless CI/CD integration.

### Recommended Workflow

Create `.github/workflows/release.yml`:

```yaml
name: Release

on:
  push:
    branches: [main]
  pull_request:
    types: [closed]
    branches: [main]

permissions:
  contents: write
  pull-requests: write
  id-token: write  # For PyPI trusted publishing

jobs:
  # Validate PR titles follow conventional commits
  check-pr:
    if: github.event_name == 'pull_request' && !github.event.pull_request.merged
    runs-on: ubuntu-latest
    steps:
      - uses: mikeleppane/release-py@v1
        with:
          command: check-pr

  # Create/update release PR on every push to main
  release-pr:
    if: github.event_name == 'push'
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v4
        with:
          fetch-depth: 0  # Full history for changelog

      - uses: mikeleppane/release-py@v1
        with:
          command: release-pr
        id: release-pr

      - name: Output PR URL
        if: steps.release-pr.outputs.pr-url
        run: echo "Release PR: ${{ steps.release-pr.outputs.pr-url }}"

  # Perform release when release PR is merged
  release:
    if: |
      github.event_name == 'pull_request' &&
      github.event.pull_request.merged == true &&
      contains(github.event.pull_request.labels.*.name, 'release')
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v4
        with:
          fetch-depth: 0

      - uses: mikeleppane/release-py@v1
        with:
          command: release
        # PyPI trusted publishing - no token needed!
```

### Action Inputs

| Input | Description | Required | Default |
|-------|-------------|----------|---------|
| `command` | Command to run: `release-pr`, `release`, `check`, `check-pr` | Yes | - |
| `github-token` | GitHub token for API access | No | `${{ github.token }}` |
| `pypi-token` | PyPI token (uses trusted publishing if not set) | No | - |
| `working-directory` | Working directory | No | `.` |
| `python-version` | Python version | No | `3.11` |
| `dry-run` | Run without making changes | No | `false` |
| `skip-publish` | Skip PyPI publishing | No | `false` |
| `require-scope` | Require scope in PR title | No | `false` |

### Action Outputs

| Output | Description | Commands |
|--------|-------------|----------|
| `version` | The version released/to be released | All |
| `pr-number` | Created/updated PR number | `release-pr` |
| `pr-url` | Created/updated PR URL | `release-pr` |
| `release-url` | GitHub release URL | `release` |
| `tag` | Git tag created | `release` |
| `valid` | Whether PR title is valid | `check-pr` |

## How It Works

### Workflow Overview

```text
┌─────────────────┐     ┌─────────────────┐     ┌─────────────────┐
│   Push to main  │────▶│  release-pr     │────▶│  Release PR     │
│   (commits)     │     │  (automated)    │     │  Created/Updated│
└─────────────────┘     └─────────────────┘     └────────┬────────┘
                                                         │
                                                         │ Merge PR
                                                         ▼
┌─────────────────┐     ┌─────────────────┐     ┌─────────────────┐
│  GitHub Release │◀────│    release      │◀────│   PR Merged     │
│  + PyPI Publish │     │   (automated)   │     │   (manual)      │
└─────────────────┘     └─────────────────┘     └─────────────────┘
```

### Version Bumping Rules

| Commit Type | Version Bump | Example |
|-------------|--------------|---------|
| `feat:` | Minor (0.1.0 → 0.2.0) | `feat: add user authentication` |
| `fix:` | Patch (0.1.0 → 0.1.1) | `fix: handle null response` |
| `perf:` | Patch | `perf: optimize database queries` |
| `feat!:` or `BREAKING CHANGE:` | Major (0.1.0 → 1.0.0)* | `feat!: redesign API` |

*For 0.x.y versions, breaking changes bump minor instead of major to avoid premature 1.0.0 releases.

### Pre-1.0.0 Semver Handling

release-py follows semantic versioning strictly for 0.x.y versions:

- Breaking changes in 0.x.y bump **minor** (0.1.0 → 0.2.0), not major
- This prevents accidental jumps to 1.0.0 during early development
- To release 1.0.0, explicitly use `--version 1.0.0`

### Changelog Format

release-py generates changelogs in FastAPI-style format with PR links and author attribution:

```markdown
### Features

- add user authentication. PR [#123](https://github.com/org/repo/pull/123) by @johndoe.
- **api:** implement rate limiting. PR [#124](https://github.com/org/repo/pull/124) by @janedoe.

### Bug Fixes

- handle null response from server. PR [#125](https://github.com/org/repo/pull/125) by @contributor.
```

## Comparison with Alternatives

| Feature | release-py | python-semantic-release | bump2version |
|---------|------------|------------------------|--------------|
| Release PR workflow | ✅ | ❌ | ❌ |
| Conventional commits | ✅ | ✅ | ❌ |
| Changelog generation | ✅ | ✅ | ❌ |
| PR/commit links | ✅ | ❌ | ❌ |
| GitHub Actions | ✅ | ✅ | ❌ |
| Zero config | ✅ | ❌ | ❌ |
| Pre-1.0.0 semver | ✅ | ✅ | ❌ |
| Typed | ✅ | ✅ | ❌ |

## Requirements

- Python 3.11+
- Git repository with conventional commits
- `pyproject.toml` with `[project]` section

## Contributing

Contributions are welcome! Please read our [Contributing Guide](CONTRIBUTING.md)
for details on the development process, code style, and how to submit pull requests.

```bash
# Clone the repository
git clone https://github.com/mikeleppane/release-py.git
cd release-py

# Install dependencies
uv sync --all-extras

# Run tests
uv run pytest

# Run linting
uv run ruff check
uv run mypy src
```

## License

MIT License - see [LICENSE](LICENSE) for details.

---

<p align="center">
  Made with ❤️ for the Python community
</p>

<h1 align="center">release-py</h1>

<p align="center">
  <strong>Automated releases for Python projects</strong><br>
  <em>Version bumping, changelog generation, and PyPI publishing powered by conventional commits</em>
</p>

<p align="center">
  <a href="https://pypi.org/project/release-py/"><img src="https://img.shields.io/pypi/v/release-py.svg" alt="PyPI version"></a>
  <a href="https://pypi.org/project/release-py/"><img src="https://img.shields.io/pypi/pyversions/release-py.svg" alt="Python versions"></a>
  <a href="https://github.com/mikeleppane/release-py/blob/main/LICENSE"><img src="https://img.shields.io/github/license/mikeleppane/release-py.svg" alt="License"></a>
  <a href="https://github.com/mikeleppane/release-py/actions/workflows/ci.yml"><img src="https://github.com/mikeleppane/release-py/actions/workflows/ci.yml/badge.svg" alt="CI"></a>
  <a href="https://codecov.io/gh/mikeleppane/release-py"><img src="https://codecov.io/gh/mikeleppane/release-py/branch/main/graph/badge.svg" alt="codecov"></a>
</p>

<p align="center">
  <a href="https://github.com/astral-sh/ruff"><img src="https://img.shields.io/endpoint?url=https://raw.githubusercontent.com/astral-sh/ruff/main/assets/badge/v2.json" alt="Ruff"></a>
  <a href="https://mypy-lang.org/"><img src="https://www.mypy-lang.org/static/mypy_badge.svg" alt="Checked with mypy"></a>
  <a href="https://github.com/astral-sh/uv"><img src="https://img.shields.io/endpoint?url=https://raw.githubusercontent.com/astral-sh/uv/main/assets/badge/v0.json" alt="uv"></a>
</p>

---

Inspired by [release-plz](https://github.com/MarcoIeni/release-plz), release-py brings the same powerful release automation to the Python ecosystem. It analyzes your [Conventional Commits](https://www.conventionalcommits.org/) to automatically determine version bumps, generate beautiful changelogs, and publish to PyPI.

## Features

- **Release PR Workflow** - Automatically creates and maintains a release PR with version bump and changelog
- **Conventional Commits** - Automatic version bumping based on commit types (`feat:`, `fix:`, etc.)
- **Beautiful Changelogs** - Professional changelog generation with PR links and author attribution
- **Zero Config** - Works out of the box with sensible defaults
- **GitHub Actions** - First-class GitHub Actions support with outputs
- **PyPI Trusted Publishing** - Native OIDC support, no tokens required
- **Pre-1.0.0 Semver** - Proper handling of 0.x.y versions (breaking changes bump minor, not major)
- **Pre-release Versions** - Support for alpha, beta, and rc versions
- **Fully Typed** - Complete type annotations with `py.typed` marker

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

```bash
# 1. Check what would happen
release-py check

# 2. Create a release PR (recommended workflow)
release-py release-pr

# 3. After merging the PR, perform the release
release-py release
```

That's it! release-py handles version bumping, changelog generation, git tagging, PyPI publishing, and GitHub release creation.

## CLI Commands

| Command | Description |
|---------|-------------|
| `release-py check` | Preview what would happen during a release |
| `release-py update` | Update version and changelog locally |
| `release-py release-pr` | Create or update a release pull request |
| `release-py release` | Tag, publish to PyPI, and create GitHub release |
| `release-py check-pr` | Validate PR title follows conventional commits |
| `release-py init` | Initialize release-py configuration |

### Common Options

```bash
release-py update --execute              # Apply changes (default is dry-run)
release-py update --version 2.0.0        # Force specific version
release-py update --prerelease alpha     # Create pre-release (1.2.0a1)
release-py release --skip-publish        # Skip PyPI publishing
release-py check-pr --require-scope      # Require scope in PR title
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
  # Create/update release PR on every push to main
  release-pr:
    if: github.event_name == 'push'
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v4
        with:
          fetch-depth: 0

      - uses: mikeleppane/release-py@v1
        with:
          command: release-pr

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

| Input | Description | Default |
|-------|-------------|---------|
| `command` | Command: `release-pr`, `release`, `check`, `check-pr` | *required* |
| `github-token` | GitHub token for API access | `github.token` |
| `python-version` | Python version to use | `3.11` |
| `dry-run` | Run without making changes | `false` |
| `skip-publish` | Skip PyPI publishing | `false` |

### Action Outputs

| Output | Description |
|--------|-------------|
| `version` | The version released/to be released |
| `pr-number` | Created/updated PR number |
| `pr-url` | Created/updated PR URL |
| `release-url` | GitHub release URL |
| `tag` | Git tag created |

## How It Works

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
| `feat!:` or `BREAKING CHANGE:` | Major* | `feat!: redesign API` |

*For 0.x.y versions, breaking changes bump minor instead of major to prevent accidental 1.0.0 releases.

## Configuration

Configuration is optional. release-py works out of the box with sensible defaults.

Add to `pyproject.toml` if you need to customize:

```toml
[tool.release-py]
default_branch = "main"
tag_prefix = "v"

[tool.release-py.commits]
types_minor = ["feat"]
types_patch = ["fix", "perf", "docs"]

[tool.release-py.changelog]
use_github_prs = false  # Set to true for squash merge workflows

[tool.release-py.github]
release_pr_labels = ["release"]
draft_releases = false

[tool.release-py.publish]
tool = "uv"  # or "twine"
trusted_publishing = true
```

<details>
<summary><strong>Full Configuration Reference</strong></summary>

```toml
[tool.release-py]
default_branch = "main"          # Branch for releases
allow_dirty = false              # Allow releases from dirty working directory
tag_prefix = "v"                 # Git tag prefix (v1.0.0)
changelog_path = "CHANGELOG.md"  # Path to changelog file

[tool.release-py.version]
initial_version = "0.1.0"        # Version for first release
version_files = []               # Additional files to update version in

[tool.release-py.commits]
types_minor = ["feat"]           # Commit types triggering minor bump
types_patch = ["fix", "perf"]    # Commit types triggering patch bump
breaking_pattern = "BREAKING[ -]CHANGE:"
skip_release_patterns = ["[skip release]", "[release skip]"]

[tool.release-py.changelog]
enabled = true
path = "CHANGELOG.md"
use_github_prs = false           # Use PR-based changelog (for squash merges)

[tool.release-py.github]
owner = ""                       # Auto-detected from git remote
repo = ""                        # Auto-detected from git remote
api_url = "https://api.github.com"
release_pr_branch = "release-py/release"
release_pr_labels = ["release"]
draft_releases = false

[tool.release-py.publish]
enabled = true
registry = "https://upload.pypi.org/legacy/"
tool = "uv"
trusted_publishing = true

[tool.release-py.hooks]
pre_bump = []                    # Commands before version bump
post_bump = []                   # Commands after version bump
pre_release = []                 # Commands before release
post_release = []                # Commands after release
```

</details>

## Requirements

- Python 3.11+
- Git repository with conventional commits
- `pyproject.toml` with `[project]` section

## Contributing

Contributions are welcome! Please read our [Contributing Guide](CONTRIBUTING.md) for details.

```bash
git clone https://github.com/mikeleppane/release-py.git
cd release-py
uv sync --all-extras
uv run pytest
```

## License

MIT License - see [LICENSE](LICENSE) for details.

---

<p align="center">
  <sub>Built with <a href="https://github.com/astral-sh/uv">uv</a> and <a href="https://github.com/astral-sh/ruff">ruff</a></sub>
</p>

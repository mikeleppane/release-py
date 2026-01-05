# Development Setup

:material-cog: Set up your local development environment.

---

## Prerequisites

- Python 3.11 or higher
- Git
- [uv](https://docs.astral.sh/uv/) (recommended) or pip

---

## Quick Start

```bash
# Clone the repository
git clone https://github.com/mikeleppane/releasio.git
cd releasio

# Install dependencies with uv
uv sync --all-extras

# Run tests to verify setup
uv run pytest
```

---

## Development Commands

### Running Tests

```bash
# Run all tests
uv run pytest

# Run with coverage
uv run pytest --cov=src/releasio --cov-report=term-missing

# Run specific test file
uv run pytest tests/unit/test_version.py

# Run tests matching pattern
uv run pytest -k "test_parse"
```

### Linting and Formatting

```bash
# Check linting
uv run ruff check src/ tests/

# Fix auto-fixable issues
uv run ruff check --fix src/ tests/

# Format code
uv run ruff format src/ tests/

# Check formatting only
uv run ruff format --check src/ tests/
```

### Type Checking

```bash
# Run mypy
uv run mypy src/
```

### Running the CLI

```bash
# Run locally
uv run releasio --help
uv run releasio check
```

---

## Project Structure

```
releasio/
├── src/releasio/          # Source code
│   ├── cli/               # CLI commands
│   ├── core/              # Business logic
│   ├── config/            # Configuration
│   ├── vcs/               # Git operations
│   ├── forge/             # GitHub integration
│   └── publish/           # PyPI publishing
├── tests/                 # Test suite
│   ├── unit/              # Unit tests
│   └── integration/       # Integration tests
├── docs/                  # Documentation
└── pyproject.toml         # Project config
```

---

## Writing Tests

### Test Structure

```python
class TestVersionParsing:
    """Tests for version parsing."""

    def test_parse_simple_version(self):
        """Parse a simple semantic version."""
        version = Version.parse("1.2.3")
        assert version.major == 1
        assert version.minor == 2
        assert version.patch == 3

    def test_parse_with_prerelease(self):
        """Parse version with pre-release."""
        version = Version.parse("1.0.0-beta.1")
        assert version.pre_release == "beta"
        assert version.pre_release_num == 1

    @pytest.mark.parametrize("version_str,expected", [
        ("1.0.0", Version(1, 0, 0)),
        ("2.1.0", Version(2, 1, 0)),
    ])
    def test_parse_various(self, version_str: str, expected: Version):
        """Parse various version strings."""
        assert Version.parse(version_str) == expected
```

### Using Fixtures

```python
@pytest.fixture
def git_repo(tmp_path: Path) -> GitRepository:
    """Create a temporary Git repository."""
    subprocess.run(["git", "init"], cwd=tmp_path, check=True)
    subprocess.run(
        ["git", "config", "user.email", "test@example.com"],
        cwd=tmp_path,
    )
    subprocess.run(
        ["git", "config", "user.name", "Test User"],
        cwd=tmp_path,
    )
    return GitRepository(tmp_path)


def test_get_commits(git_repo: GitRepository):
    """Test getting commits from repository."""
    # Create a commit
    (git_repo.path / "file.txt").write_text("content")
    subprocess.run(["git", "add", "."], cwd=git_repo.path)
    subprocess.run(
        ["git", "commit", "-m", "feat: initial commit"],
        cwd=git_repo.path,
    )

    commits = git_repo.get_commits_since_tag(None)
    assert len(commits) == 1
```

---

## Commit Messages

Use [Conventional Commits](https://www.conventionalcommits.org/):

```bash
# Features
git commit -m "feat: add custom parser support"
git commit -m "feat(cli): add verbose flag"

# Bug fixes
git commit -m "fix: handle empty commit list"
git commit -m "fix(changelog): escape special characters"

# Documentation
git commit -m "docs: add configuration examples"

# Refactoring
git commit -m "refactor: simplify version parsing"

# Tests
git commit -m "test: add Gitmoji parser tests"

# Chores
git commit -m "chore: update dependencies"
```

---

## Pull Request Process

1. **Fork** the repository
2. **Create** a feature branch: `git checkout -b feat/my-feature`
3. **Make** your changes
4. **Test** thoroughly: `uv run pytest`
5. **Lint** your code: `uv run ruff check src/ tests/`
6. **Commit** with conventional commits
7. **Push** your branch
8. **Open** a pull request

### PR Checklist

- [ ] Tests pass (`uv run pytest`)
- [ ] Linting passes (`uv run ruff check`)
- [ ] Type checking passes (`uv run mypy src/`)
- [ ] Documentation updated (if needed)
- [ ] Commit messages follow convention

---

## Documentation

### Building Docs Locally

```bash
# Install docs dependencies
uv sync --extra docs

# Serve docs locally
uv run mkdocs serve

# Build docs
uv run mkdocs build
```

### Documentation Structure

```
docs/
├── index.md                 # Landing page
├── getting-started/         # Getting started guides
├── user-guide/              # User documentation
│   ├── cli/                 # CLI commands
│   ├── configuration/       # Config reference
│   ├── versioning/          # Version management
│   ├── changelog/           # Changelog generation
│   └── commits/             # Commit parsing
├── github/                  # GitHub integration
├── publishing/              # PyPI publishing
├── advanced/                # Advanced features
├── architecture/            # System design
└── contributing/            # This section
```

---

## Code Style

### Python Style

```python
# Use type annotations everywhere
def calculate_bump(
    commits: list[ParsedCommit],
    config: CommitsConfig,
) -> BumpType:
    ...

# Use dataclasses for data structures
@dataclass(frozen=True, slots=True)
class ParsedCommit:
    commit: Commit
    commit_type: str | None
    description: str
    is_breaking: bool

# Use Path objects for file paths
config_path: Path = repo_path / "pyproject.toml"

# Prefer early returns
def get_version(path: Path) -> Version | None:
    if not path.exists():
        return None
    content = path.read_text()
    if not content.strip():
        return None
    return parse_version(content)
```

### Error Handling

```python
# Use custom exceptions
class ChangelogError(ReleaseError):
    """Raised when changelog generation fails."""

# Provide context in exceptions
raise ChangelogError(
    f"Failed to generate changelog for {version}: {e}",
) from e

# Handle expected errors gracefully
try:
    result = subprocess.run(args, check=True, capture_output=True)
except subprocess.CalledProcessError as e:
    if "no commits" in e.stderr.lower():
        return BumpType.NONE
    raise GitError(f"Command failed: {e}") from e
```

---

## Release Process

Releases are automated via GitHub Actions:

1. Merge PR to `main`
2. GitHub Action creates release PR
3. Review and merge release PR
4. GitHub Action creates tag and publishes

---

## Getting Help

- Open an [issue](https://github.com/mikeleppane/releasio/issues)
- Check existing issues and discussions
- Read the [Architecture](../architecture/index.md) docs

---

## See Also

- [Architecture Overview](../architecture/overview.md) - System design
- [API Reference](../reference/index.md) - Code documentation

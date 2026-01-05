# System Overview

:material-view-dashboard: High-level architecture of releasio.

---

## Component Architecture

```mermaid
%%{init: {'theme': 'neutral'}}%%
graph TB
    subgraph User["User Interface"]
        CLI[CLI Commands]
        GHA[GitHub Action]
    end

    subgraph Core["Core Engine"]
        VP[Version Parser]
        VC[Version Calculator]
        CP[Commit Parser]
        CG[Changelog Generator]
    end

    subgraph VCS["Version Control"]
        GIT[Git Repository]
        TAG[Tag Manager]
    end

    subgraph Remote["Remote Services"]
        GH[GitHub API]
        PYPI[PyPI Registry]
    end

    subgraph Config["Configuration"]
        CL[Config Loader]
        PM[Pydantic Models]
    end

    CLI --> CL
    GHA --> CL
    CL --> PM

    CLI --> VP
    CLI --> VC
    CLI --> CP
    CLI --> CG

    VP --> GIT
    VC --> CP
    CP --> GIT
    CG --> GIT
    CG --> TAG

    CLI --> GH
    CLI --> PYPI
    GH --> TAG
```

---

## Directory Structure

```
src/releasio/
├── cli/                  # Command-line interface
│   ├── app.py           # Typer app setup
│   ├── check.py         # check command
│   ├── update.py        # update command
│   ├── release.py       # release command
│   ├── release_pr.py    # release-pr command
│   └── do_release.py    # do-release command
│
├── core/                 # Business logic
│   ├── version.py       # Version parsing and bumping
│   ├── commits.py       # Commit parsing
│   ├── changelog.py     # Changelog generation
│   └── version_files.py # Version file management
│
├── config/               # Configuration handling
│   ├── loader.py        # Config file discovery
│   └── models.py        # Pydantic config models
│
├── vcs/                  # Version control
│   └── git.py           # Git operations
│
├── forge/                # Forge integrations
│   └── github.py        # GitHub API client
│
├── publish/              # Publishing
│   └── pypi.py          # PyPI publishing
│
└── exceptions.py         # Custom exceptions
```

---

## Core Components

### CLI Layer (`cli/`)

The CLI layer handles user interaction:

```mermaid
%%{init: {'theme': 'neutral'}}%%
graph LR
    A[User] --> B[Typer App]
    B --> C[check]
    B --> D[update]
    B --> E[release]
    B --> F[release-pr]
    B --> G[do-release]
```

**Responsibilities:**

- Parse command-line arguments
- Validate inputs
- Display formatted output (Rich)
- Orchestrate core operations

### Core Layer (`core/`)

The core layer contains all business logic:

```mermaid
%%{init: {'theme': 'neutral'}}%%
graph TB
    subgraph Version["version.py"]
        V1[Version class]
        V2[BumpType enum]
        V3[parse_version]
        V4[calculate_bump]
    end

    subgraph Commits["commits.py"]
        C1[ParsedCommit]
        C2[ConventionalParser]
        C3[parse_commits]
    end

    subgraph Changelog["changelog.py"]
        CL1[generate_changelog]
        CL2[format_entries]
    end

    Commits --> Version
    Version --> Changelog
```

**Responsibilities:**

- Parse commit messages
- Calculate version bumps
- Generate changelogs
- Manage version files

### Config Layer (`config/`)

Configuration loading and validation:

```mermaid
%%{init: {'theme': 'neutral'}}%%
graph LR
    A[.releasio.toml] --> B[Config Loader]
    C[releasio.toml] --> B
    D[pyproject.toml] --> B
    B --> E[Pydantic Models]
    E --> F[Validated Config]
```

**Priority order:**

1. `.releasio.toml` (highest)
2. `releasio.toml`
3. `pyproject.toml` under `[tool.releasio]`

### VCS Layer (`vcs/`)

Git operations abstraction:

```python
class GitRepository:
    def get_commits_since_tag(self, tag: str) -> list[Commit]
    def get_latest_tag(self) -> str | None
    def create_tag(self, tag: str, message: str) -> None
    def push(self, ref: str) -> None
```

### Forge Layer (`forge/`)

GitHub integration:

```python
class GitHubClient:
    def create_release(self, tag: str, body: str) -> Release
    def create_pull_request(self, title: str, body: str) -> PullRequest
    def upload_assets(self, release_id: int, files: list[Path]) -> None
```

### Publish Layer (`publish/`)

PyPI publishing:

```python
class PyPIPublisher:
    def build(self) -> None
    def publish(self, trusted: bool = True) -> None
    def validate(self) -> bool
```

---

## Key Classes

### Version

```python
@dataclass(frozen=True)
class Version:
    major: int
    minor: int
    patch: int
    pre_release: str | None = None
    pre_release_num: int | None = None

    def bump(self, bump_type: BumpType) -> Version:
        ...

    def __str__(self) -> str:
        ...
```

### ParsedCommit

```python
@dataclass(frozen=True, slots=True)
class ParsedCommit:
    commit: Commit
    commit_type: str | None
    scope: str | None
    description: str
    body: str | None
    is_breaking: bool
    is_conventional: bool
```

### ReleasePyConfig

```python
class ReleasePyConfig(BaseModel):
    default_branch: str = "main"
    version: VersionConfig = VersionConfig()
    changelog: ChangelogConfig = ChangelogConfig()
    commits: CommitsConfig = CommitsConfig()
    github: GitHubConfig = GitHubConfig()
    publish: PublishConfig = PublishConfig()
    hooks: HooksConfig = HooksConfig()
```

---

## Design Patterns

### Strategy Pattern

Different changelog generators:

```python
class ChangelogGenerator(Protocol):
    def generate(self, commits: list[ParsedCommit]) -> str:
        ...

class NativeGenerator:
    def generate(self, commits: list[ParsedCommit]) -> str:
        ...

class GitCliffGenerator:
    def generate(self, commits: list[ParsedCommit]) -> str:
        ...
```

### Factory Pattern

Build tool selection:

```python
def get_publisher(tool: str) -> Publisher:
    match tool:
        case "uv":
            return UvPublisher()
        case "poetry":
            return PoetryPublisher()
        case "pdm":
            return PdmPublisher()
```

### Repository Pattern

Git operations:

```python
class GitRepository:
    def __init__(self, path: Path):
        self.path = path

    def get_commits(self) -> list[Commit]:
        ...

    def get_tags(self) -> list[str]:
        ...
```

---

## Error Handling

Custom exception hierarchy:

```python
class ReleaseError(Exception):
    """Base exception for releasio."""

class ConfigError(ReleaseError):
    """Configuration-related errors."""

class GitError(ReleaseError):
    """Git operation errors."""

class PublishError(ReleaseError):
    """Publishing errors."""

class GitHubError(ReleaseError):
    """GitHub API errors."""
```

---

## Testing Strategy

```
tests/
├── unit/              # Fast, isolated tests
│   ├── test_version.py
│   ├── test_commits.py
│   └── test_changelog.py
├── integration/       # Tests with real Git
│   ├── test_cli.py
│   └── test_workflow.py
└── conftest.py        # Shared fixtures
```

### Test Fixtures

```python
@pytest.fixture
def git_repo(tmp_path: Path) -> GitRepository:
    """Create a temporary Git repository."""
    subprocess.run(["git", "init"], cwd=tmp_path)
    return GitRepository(tmp_path)

@pytest.fixture
def sample_config() -> ReleasePyConfig:
    """Create a sample configuration."""
    return ReleasePyConfig()
```

---

## See Also

- [Data Flow](data-flow.md) - How data moves through the system
- [Contributing](../contributing/index.md) - Development guide
- [API Reference](../reference/index.md) - Code documentation

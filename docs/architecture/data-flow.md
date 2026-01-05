# Data Flow

:material-transit-connection-variant: How data moves through releasio.

---

## Release Workflow

The complete release flow:

```mermaid
%%{init: {'theme': 'neutral'}}%%
sequenceDiagram
    participant U as User
    participant CLI as CLI
    participant Git as Git Repository
    participant Core as Core Engine
    participant GH as GitHub
    participant PyPI as PyPI

    U->>CLI: releasio release
    CLI->>Git: Get commits since last tag
    Git-->>CLI: Commit list
    CLI->>Core: Parse commits
    Core-->>CLI: Parsed commits
    CLI->>Core: Calculate version bump
    Core-->>CLI: New version
    CLI->>Core: Generate changelog
    Core-->>CLI: Changelog content
    CLI->>Git: Create tag
    CLI->>GH: Create release
    GH-->>CLI: Release URL
    CLI->>PyPI: Publish package
    PyPI-->>CLI: Success
    CLI->>U: Release complete
```

---

## Command Data Flows

### check Command

Preview release without changes:

```mermaid
%%{init: {'theme': 'neutral'}}%%
graph LR
    A[Config] --> B[Load Config]
    B --> C[Git Repo]
    C --> D[Get Commits]
    D --> E[Parse Commits]
    E --> F[Calculate Bump]
    F --> G[Display Preview]
```

**Data transformations:**

1. **Config** → Validated `ReleasePyConfig`
2. **Git log** → List of `Commit` objects
3. **Commits** → List of `ParsedCommit` objects
4. **Parsed commits** → `BumpType` (major/minor/patch)
5. **Current version + bump** → New `Version`

### update Command

Update version and changelog locally:

```mermaid
%%{init: {'theme': 'neutral'}}%%
graph LR
    A[check flow] --> B[Calculate New Version]
    B --> C[Update pyproject.toml]
    C --> D[Update Version Files]
    D --> E[Generate Changelog]
    E --> F[Write CHANGELOG.md]
    F --> G[Commit Changes]
```

**File modifications:**

```
pyproject.toml    → version = "1.2.0"
__init__.py       → __version__ = "1.2.0"
CHANGELOG.md      → ## [1.2.0] - 2024-01-15
```

### release-pr Command

Create a pull request:

```mermaid
%%{init: {'theme': 'neutral'}}%%
graph TB
    A[update flow] --> B[Create Branch]
    B --> C[Commit Changes]
    C --> D[Push Branch]
    D --> E[Create PR via API]
    E --> F[Return PR URL]
```

**API calls:**

1. `POST /repos/{owner}/{repo}/pulls` - Create PR

### release Command

Tag and publish:

```mermaid
%%{init: {'theme': 'neutral'}}%%
graph TB
    A[Validate State] --> B[Create Git Tag]
    B --> C[Push Tag]
    C --> D[Create GitHub Release]
    D --> E[Upload Assets]
    E --> F[Build Package]
    F --> G[Publish to PyPI]
    G --> H[Complete]
```

**API calls:**

1. `POST /repos/{owner}/{repo}/releases` - Create release
2. `POST /releases/{id}/assets` - Upload each asset
3. PyPI upload via build tool

---

## Commit Parsing Pipeline

```mermaid
%%{init: {'theme': 'neutral'}}%%
graph TD
    A[Raw Commit] --> B[Extract Subject]
    B --> C{Matches Convention?}
    C -->|Yes| D[Parse Type/Scope]
    C -->|No| E[Try Custom Parsers]
    D --> F[Check Breaking]
    E --> F
    F --> G[ParsedCommit]
```

### Parsing Rules

```python
# Input: "feat(api)!: add user endpoint"

# Step 1: Match pattern
pattern = r"^(?P<type>\w+)(\((?P<scope>[^)]+)\))?(?P<breaking>!)?:\s*(?P<desc>.+)$"

# Step 2: Extract groups
type = "feat"
scope = "api"
breaking = True  # from "!"
description = "add user endpoint"

# Step 3: Create ParsedCommit
ParsedCommit(
    commit=commit,
    commit_type="feat",
    scope="api",
    description="add user endpoint",
    is_breaking=True,
    is_conventional=True,
)
```

---

## Version Calculation

```mermaid
%%{init: {'theme': 'neutral'}}%%
graph TD
    A[ParsedCommits] --> B{Any Breaking?}
    B -->|Yes| C[Major Bump]
    B -->|No| D{Any feat?}
    D -->|Yes| E[Minor Bump]
    D -->|No| F{Any fix/docs/perf?}
    F -->|Yes| G[Patch Bump]
    F -->|No| H[No Bump]

    C --> I[New Version]
    E --> I
    G --> I
    H --> I
```

### Bump Priority

```python
def calculate_bump(commits: list[ParsedCommit]) -> BumpType:
    if any(c.is_breaking for c in commits):
        return BumpType.MAJOR
    if any(c.commit_type == "feat" for c in commits):
        return BumpType.MINOR
    if any(c.commit_type in PATCH_TYPES for c in commits):
        return BumpType.PATCH
    return BumpType.NONE
```

---

## Changelog Generation

```mermaid
%%{init: {'theme': 'neutral'}}%%
graph TD
    A[ParsedCommits] --> B[Group by Type]
    B --> C[Sort Groups]
    C --> D[Format Entries]
    D --> E[Apply Template]
    E --> F[Prepend to File]
```

### Grouping

```python
# Input commits
commits = [
    ParsedCommit(type="feat", desc="add dashboard"),
    ParsedCommit(type="fix", desc="resolve bug"),
    ParsedCommit(type="feat", desc="add settings"),
]

# Grouped
groups = {
    "feat": [
        ParsedCommit(desc="add dashboard"),
        ParsedCommit(desc="add settings"),
    ],
    "fix": [
        ParsedCommit(desc="resolve bug"),
    ],
}
```

### Template Application

```markdown
## [1.2.0] - 2024-01-15

### Features
- Add dashboard
- Add settings

### Bug Fixes
- Resolve bug
```

---

## Configuration Loading

```mermaid
%%{init: {'theme': 'neutral'}}%%
graph TD
    A[Start] --> B{.releasio.toml exists?}
    B -->|Yes| C[Load .releasio.toml]
    B -->|No| D{releasio.toml exists?}
    D -->|Yes| E[Load releasio.toml]
    D -->|No| F{pyproject.toml has tool.releasio?}
    F -->|Yes| G[Load from pyproject.toml]
    F -->|No| H[Use Defaults]

    C --> I[Validate with Pydantic]
    E --> I
    G --> I
    H --> I

    I --> J[ReleasePyConfig]
```

### Merge Strategy

```python
# Defaults < pyproject.toml < releasio.toml < .releasio.toml
config = ReleasePyConfig()  # Defaults
config = merge(config, pyproject_config)
config = merge(config, releasio_config)
config = merge(config, dotreleasio_config)
```

---

## Publishing Pipeline

```mermaid
%%{init: {'theme': 'neutral'}}%%
graph TD
    A[Start] --> B[Run Hooks: pre_release]
    B --> C{Hooks Passed?}
    C -->|No| X[Abort]
    C -->|Yes| D[Build Package]
    D --> E[Validate Package]
    E --> F{Valid?}
    F -->|No| X
    F -->|Yes| G{Trusted Publishing?}
    G -->|Yes| H[Request OIDC Token]
    G -->|No| I[Use API Token]
    H --> J[Upload to PyPI]
    I --> J
    J --> K{Success?}
    K -->|No| X
    K -->|Yes| L[Run Hooks: post_release]
    L --> M[Complete]
```

### Build Commands

| Tool | Build | Publish |
|------|-------|---------|
| uv | `uv build` | `uv publish` |
| poetry | `poetry build` | `poetry publish` |
| pdm | `pdm build` | `pdm publish` |

---

## GitHub Release Creation

```mermaid
%%{init: {'theme': 'neutral'}}%%
sequenceDiagram
    participant R as releasio
    participant G as GitHub API

    R->>G: POST /repos/{owner}/{repo}/releases
    Note right of R: body: tag_name, name, body, prerelease
    G-->>R: 201 Created (release_id)

    loop For each asset
        R->>G: POST /releases/{id}/assets
        Note right of R: file content
        G-->>R: 201 Created
    end

    R->>R: Complete
```

### Request Payload

```json
{
  "tag_name": "v1.2.0",
  "name": "v1.2.0",
  "body": "## What's Changed\n\n- Added dashboard\n- Fixed bug",
  "draft": false,
  "prerelease": false
}
```

---

## Error Propagation

```mermaid
%%{init: {'theme': 'neutral'}}%%
graph TD
    A[Operation] --> B{Success?}
    B -->|No| C[Raise Exception]
    C --> D{Recoverable?}
    D -->|Yes| E[Log Warning]
    D -->|No| F[Log Error]
    F --> G[Exit with Code 1]
    E --> H[Continue]
    B -->|Yes| H
```

### Exception Hierarchy

```
ReleaseError
├── ConfigError
├── GitError
│   ├── TagExistsError
│   └── PushError
├── GitHubError
│   ├── AuthenticationError
│   └── RateLimitError
└── PublishError
    ├── BuildError
    └── UploadError
```

---

## See Also

- [System Overview](overview.md) - Component architecture
- [Configuration](../user-guide/configuration/reference.md) - Config options
- [API Reference](../reference/index.md) - Code documentation

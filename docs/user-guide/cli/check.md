# releasio check

:material-eye: Preview what a release would look like without making any changes.

---

## Usage

```bash
releasio check [PATH] [OPTIONS]
```

## Description

The `check` command analyzes your commits since the last release and shows:

- **Current version** from `pyproject.toml`
- **Next version** calculated from commits
- **Bump type** (major, minor, patch)
- **Commits** that would be included
- **Changelog preview**

!!! success "Always Safe"
    This command **never** modifies any files. Use it freely to preview releases.

---

## Arguments

| Argument | Type | Default | Description |
|----------|------|---------|-------------|
| `PATH` | Path | `.` | Project directory path |

---

## Options

| Option | Short | Description |
|--------|-------|-------------|
| `--verbose` | `-v` | Show detailed output including all commits |
| `--help` | | Show help message |

---

## Examples

### Basic Check

```bash
releasio check
```

??? example "Example Output"

    ```
    ╭─ Release Preview ────────────────────────────────────────╮
    │                                                          │
    │  📦 Project: my-project                                  │
    │  📌 Current: v1.2.3                                      │
    │  🚀 Next:    v1.3.0 (minor)                              │
    │                                                          │
    │  📝 Changes:                                             │
    │    ✨ feat: add user authentication                      │
    │    🐛 fix: resolve connection timeout                    │
    │    📚 docs: update API reference                         │
    │                                                          │
    ╰──────────────────────────────────────────────────────────╯
    ```

### Verbose Output

```bash
releasio check --verbose
```

Shows additional details:

- Full commit messages with bodies
- Commit hashes
- Authors and dates
- Detailed changelog preview

### Different Directory

```bash
releasio check /path/to/project
```

---

## How It Works

```mermaid
%%{init: {'theme': 'neutral'}}%%
flowchart TD
    A[releasio check] --> B[Load pyproject.toml]
    B --> C[Find latest git tag]
    C --> D[Get commits since tag]
    D --> E[Parse conventional commits]
    E --> F{Any breaking<br/>changes?}
    F -->|Yes| G[Major bump]
    F -->|No| H{Any feat:<br/>commits?}
    H -->|Yes| I[Minor bump]
    H -->|No| J{Any fix/perf/<br/>docs commits?}
    J -->|Yes| K[Patch bump]
    J -->|No| L[No bump needed]
    G --> M[Display preview]
    I --> M
    K --> M
    L --> M
```

---

## When to Use

- **Before creating a release PR** - Verify the version bump is correct
- **After making commits** - See how they affect the next version
- **Debugging** - Understand why a version bump is happening
- **CI/CD** - Validate release conditions

---

## What Determines the Version Bump?

releasio analyzes commits using [conventional commits](../commits/format.md):

| Commit Type | Bump |
|-------------|------|
| `feat:` | Minor |
| `fix:`, `perf:`, `docs:` | Patch |
| `feat!:` or `BREAKING CHANGE:` | Major |

!!! note "Pre-1.0.0 Behavior"
    Before version 1.0.0, breaking changes bump **minor** instead of major.

---

## See Also

- [update](update.md) - Update version locally
- [release-pr](release-pr.md) - Create a release PR
- [Conventional Commits](../commits/format.md) - Commit format reference

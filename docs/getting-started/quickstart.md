# Quick Start

Get releasio running in 5 minutes.

## Prerequisites

- Python project with `pyproject.toml`
- Git repository with commit history
- *(Optional)* [git-cliff](installation.md#optional-install-git-cliff-recommended) for advanced changelog customization

## Step 1: Install releasio

```bash
pip install releasio
```

## Step 2: Preview Your Release

Run `check` to see what would happen:

```bash
releasio check
```

Example output:

```
┌─ Release Preview ─────────────────────────────────────────┐
│                                                           │
│  Project: my-awesome-project                              │
│  Current: v1.2.0                                          │
│  Next:    v1.3.0 (minor bump)                             │
│                                                           │
│  Commits (5):                                             │
│    feat: add new authentication module                    │
│    fix: resolve database connection issue                 │
│    docs: update API documentation                         │
│    fix: handle edge case in parser                        │
│    chore: update dependencies                             │
│                                                           │
└───────────────────────────────────────────────────────────┘
```

!!! tip "Safe to Run"
    The `check` command never modifies any files. Run it anytime to preview
    what a release would look like.

## Step 3: Create a Release PR

Create a pull request with your release:

```bash
releasio release-pr --execute
```

This will:

1. Create a branch (default: `releasio/release`)
2. Update version in `pyproject.toml`
3. Generate/update `CHANGELOG.md`
4. Create a pull request

## Step 4: Merge and Release

After merging the PR, create the release:

```bash
releasio release --execute
```

This will:

1. Create a git tag
2. Push the tag
3. Create a GitHub release
4. Publish to PyPI (if configured)

## One-Command Release

For a complete release in one command:

```bash
releasio do-release --execute
```

This combines update, commit, tag, and publish into a single workflow.

## Using Conventional Commits

releasio uses [conventional commits](../user-guide/commits/format.md) to determine version bumps:

```bash
# Minor version bump (feat)
git commit -m "feat: add user authentication"

# Patch version bump (fix)
git commit -m "fix: resolve login issue"

# Major version bump (breaking change)
git commit -m "feat!: redesign API endpoints"
```

## Next Steps

- [First Release](first-release.md) - Complete walkthrough with GitHub Actions
- [Configuration](../user-guide/configuration/index.md) - Customize releasio
- [GitHub Actions](../github/actions/index.md) - Automate releases

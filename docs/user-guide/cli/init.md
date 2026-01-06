# releasio init

:material-cog: Interactive configuration wizard for setting up releasio.

---

## Usage

```bash
releasio init [PATH] [OPTIONS]
```

## Description

The `init` command launches a beautiful, interactive configuration wizard that guides you through setting up releasio for your project. It auto-detects your project settings and creates the optimal configuration.

---

## Interactive Wizard

The wizard offers two setup modes:

### Quick Mode (Recommended)

6 steps with sensible defaults for most projects:

1. **Setup Mode** - Choose quick or comprehensive
2. **Basic Settings** - Branch, tag prefix
3. **Publishing** - Build tool, PyPI settings
4. **Changelog** - Enable/disable, path, PR-based
5. **GitHub** - Owner/repo detection, workflow creation
6. **Output** - File location, preview, confirm

### Comprehensive Mode

9 sections for full customization:

1. **Setup Mode** - Choose mode
2. **Basic Settings** - Branch, tag prefix, initial version
3. **Commits** - Types for major/minor/patch, Gitmoji support
4. **Changelog** - Detailed options, authors, first-time contributors
5. **GitHub** - Full GitHub integration settings
6. **Release Notes** - Author attribution, contributors, installation, emojis, title format
7. **Publishing** - Tool, registry, trusted publishing
8. **Advanced** - Hooks, monorepo, security, release channels
9. **Output** - File choice, preview, workflows

---

## Smart Auto-Detection

The wizard automatically detects:

| Setting | Detection Method |
|---------|------------------|
| **Build tool** | Lock files (`uv.lock`, `poetry.lock`, `pdm.lock`) |
| **GitHub remote** | Git remote URL |
| **Default branch** | Current branch or main/master existence |
| **Version** | `pyproject.toml` project version |
| **Squash merge** | Commit message patterns |
| **Monorepo** | `packages/` directory structure |

---

## Arguments

| Argument | Type | Default | Description |
|----------|------|---------|-------------|
| `PATH` | Path | `.` | Project directory |

---

## Options

| Option | Description |
|--------|-------------|
| `--force` | Overwrite existing configuration |
| `--help` | Show help message |

---

## Example Session

```
╭────────────────────── Setup Wizard ──────────────────────╮
│ Welcome to releasio!                                     │
│                                                          │
│ This wizard will help you set up automated releases      │
│ for your project.                                        │
╰──────────────────────────────────────────────────────────╯

─────────────────── Setup Mode [1/6] ───────────────────────
Choose how detailed you want the configuration to be

  quick         - Sensible defaults, minimal questions (recommended)
  comprehensive - Full customization of all options

Choose setup mode [quick/comprehensive] (quick):
```

---

## Output Options

The wizard can create configuration in three locations:

| Output | File | Notes |
|--------|------|-------|
| `pyproject` | `pyproject.toml` | Under `[tool.releasio]` section |
| `dotfile` | `.releasio.toml` | Hidden file (highest priority) |
| `visible` | `releasio.toml` | Visible config file |

---

## Generated Configuration

Example output for quick mode:

```toml title="pyproject.toml"
[tool.releasio]
default_branch = "main"

[tool.releasio.version]
tag_prefix = "v"

[tool.releasio.commits]
types_minor = ["feat"]
types_patch = ["fix", "perf"]

[tool.releasio.changelog]
path = "CHANGELOG.md"

[tool.releasio.github]
owner = "myorg"
repo = "myproject"
release_pr_branch = "releasio/release"
release_pr_labels = ["release"]

[tool.releasio.publish]
enabled = true
tool = "uv"
```

---

## GitHub Workflows

The wizard can generate GitHub Actions workflows:

### Release Workflow

Creates `.github/workflows/release.yml`:

```yaml
name: Release
on:
  push:
    branches: [main]

permissions:
  contents: write
  pull-requests: write
  id-token: write

jobs:
  release-pr:
    if: "!startsWith(github.event.head_commit.message, 'chore(release):')"
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v4
        with:
          fetch-depth: 0
      - uses: astral-sh/setup-uv@v4
      - run: uv sync --all-extras
      - run: uv run releasio release-pr --execute
        env:
          GITHUB_TOKEN: ${{ secrets.GITHUB_TOKEN }}

  release:
    if: startsWith(github.event.head_commit.message, 'chore(release):')
    runs-on: ubuntu-latest
    environment: release
    steps:
      - uses: actions/checkout@v4
        with:
          fetch-depth: 0
      - uses: astral-sh/setup-uv@v4
      - run: uv sync --all-extras
      - run: uv run releasio release --execute
        env:
          GITHUB_TOKEN: ${{ secrets.GITHUB_TOKEN }}
```

### PR Title Validation Workflow

Optionally creates `.github/workflows/pr-title.yml` for conventional commit enforcement.

---

## When to Use

Use `init` when you want to:

- **Set up releasio** for a new project
- **Customize** version bumping rules
- **Change** changelog settings
- **Configure** GitHub release options
- **Generate** GitHub Actions workflows

!!! note "Zero Config"
    releasio works without any configuration. Only run `init` if you need
    to customize the defaults or want guided setup.

---

## See Also

- [Configuration Overview](../configuration/index.md)
- [Full Reference](../configuration/reference.md)
- [Examples](../configuration/examples.md)
- [GitHub Actions Guide](../../github/actions/index.md)

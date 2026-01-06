# Frequently Asked Questions

## General

### What is releasio?

releasio is an automated release tool for Python projects, inspired by [release-plz](https://github.com/MarcoIeni/release-plz). It analyzes conventional commits to automatically determine version bumps, generate changelogs, and publish to PyPI.

### How does releasio differ from similar tools?

| Feature | releasio | semantic-release | python-semantic-release |
|---------|----------|------------------|-------------------------|
| Language | Python | Node.js | Python |
| Config format | TOML | JSON/YAML | TOML |
| Changelog tool | git-cliff + native | Built-in | Built-in |
| Monorepo support | Yes | Plugin-based | Limited |
| Dry-run mode | Yes | Yes | Yes |
| GitHub Actions | Native | Native | Native |

### Do I need to use conventional commits?

Yes, releasio relies on [Conventional Commits](https://www.conventionalcommits.org/) to determine version bumps:

- `feat:` triggers a **minor** version bump
- `fix:` triggers a **patch** version bump
- `feat!:` or `BREAKING CHANGE:` triggers a **major** version bump

You can customize which commit types trigger which bump in your configuration.

---

## Configuration

### Where should I put my configuration?

releasio supports multiple configuration locations (in order of precedence):

1. `.releasio.toml` - Dedicated dotfile (highest priority)
2. `releasio.toml` - Dedicated visible file
3. `pyproject.toml` under `[tool.releasio]` - Standard location

For most projects, using `pyproject.toml` is recommended to keep configuration centralized.

### What's the minimum configuration needed?

Zero configuration! releasio works out of the box with sensible defaults. Just ensure your `pyproject.toml` has:

```toml
[project]
name = "your-package"
version = "1.0.0"
```

### How do I customize commit types?

```toml
[tool.releasio.commits]
# These trigger minor bumps
types_minor = ["feat"]

# These trigger patch bumps
types_patch = ["fix", "perf", "docs", "refactor", "style", "test", "build", "ci"]
```

### Can I use a custom version file?

Yes, configure additional version file locations:

```toml
[tool.releasio.version]
files = ["src/mypackage/__version__.py", "src/mypackage/__init__.py"]
```

releasio will update `__version__ = "x.y.z"` patterns in these files.

---

## Commands

### What's the difference between `check` and `update`?

- **`releasio check`**: Analyzes commits and shows what would change (read-only)
- **`releasio update`**: Actually modifies version files and changelog

Always run `check` first to preview changes before using `update --execute`.

### What does `--execute` do?

Commands like `update`, `release`, and `release-pr` require `--execute` to make actual changes. Without it, they run in dry-run mode showing what would happen.

```bash
# Preview changes (safe)
releasio update

# Apply changes
releasio update --execute
```

### How do I create a release PR?

```bash
# Create a PR with version bump and changelog
releasio release-pr --execute

# The PR will be created on GitHub with:
# - Updated version in pyproject.toml
# - Updated CHANGELOG.md
# - "release" label applied
```

### How do I publish to PyPI?

```bash
# Full release: create tag, GitHub release, and publish
releasio release --execute
```

For CI/CD, use the `do-release` command which is designed for automation:

```bash
releasio do-release --execute
```

---

## GitHub Integration

### What GitHub token permissions do I need?

For most operations, you need:

- `contents: write` - To create commits and tags
- `pull-requests: write` - To create release PRs

```yaml
permissions:
  contents: write
  pull-requests: write
```

### How do I set up Trusted Publishing for PyPI?

1. Go to PyPI → Your project → Settings → Publishing
2. Add a new publisher with:
   - Owner: Your GitHub username/org
   - Repository: Your repo name
   - Workflow: `release.yml` (or your workflow filename)
   - Environment: `release` (optional but recommended)

3. Configure your workflow:

```yaml
jobs:
  release:
    runs-on: ubuntu-latest
    environment: release  # Optional
    permissions:
      id-token: write
      contents: write
    steps:
      - uses: actions/checkout@v4
      - uses: astral-sh/setup-uv@v4
      - run: uv sync
      - run: uv run releasio do-release --execute
```

### Can I use releasio without GitHub?

The core functionality (version bumping, changelog generation) works locally without GitHub. However, features like `release-pr` and GitHub Releases require GitHub integration.

---

## Changelog

### Do I need git-cliff installed?

No, releasio has a native changelog generator that works without external dependencies. However, git-cliff provides more customization options and is recommended for advanced use cases.

### How do I customize the changelog format?

With git-cliff, create a `cliff.toml` in your project root. releasio will use it automatically.

For native changelog, configure groups and headers:

```toml
[tool.releasio.changelog]
path = "CHANGELOG.md"
```

### Why is my changelog empty?

Common causes:

1. **No conventional commits**: Ensure commits follow the format `type: description`
2. **Wrong commit types**: Check your `types_minor` and `types_patch` configuration
3. **No commits since last tag**: Run `git log $(git describe --tags --abbrev=0)..HEAD` to verify

---

## Versioning

### How does releasio determine the next version?

1. Finds the latest git tag (e.g., `v1.2.3`)
2. Analyzes commits since that tag
3. Determines bump type based on commit messages:
   - Any `feat!:` or `BREAKING CHANGE:` → Major bump
   - Any `feat:` → Minor bump
   - Any `fix:`, `perf:`, etc. → Patch bump
4. Applies the highest bump found

### Can I force a specific version?

Yes, use the `--version` flag:

```bash
releasio update --execute --version 2.0.0
```

### How do I create pre-releases?

```bash
# Create alpha release
releasio update --execute --pre-release a1

# Create beta release
releasio update --execute --pre-release b1

# Create release candidate
releasio update --execute --pre-release rc1
```

### What tag format does releasio use?

By default, tags are prefixed with `v`:

```
v1.0.0
v1.1.0
v2.0.0-rc1
```

Customize with:

```toml
[tool.releasio.version]
tag_prefix = ""  # No prefix: 1.0.0
```

---

## Monorepo Support

### Does releasio support monorepos?

Yes! releasio can manage multiple packages in a single repository.

```toml
# .releasio.toml at repo root
[packages.core]
path = "packages/core"

[packages.cli]
path = "packages/cli"
```

### How do I release individual packages?

```bash
# Release specific package
releasio release --package core --execute

# Release all packages
releasio release --all --execute
```

---

## Troubleshooting

### Why isn't releasio detecting my commits?

1. **Check commit format**: Must be `type: description` or `type(scope): description`
2. **Check git history**: `git log --oneline` to see recent commits
3. **Check tag**: `git describe --tags` to see the latest tag
4. **Run check**: `releasio check` for detailed analysis

### releasio says "no changes to release"

This means no conventional commits were found since the last release. Either:

1. Add conventional commits and try again
2. Force a version bump: `releasio update --execute --bump patch`

### My pre-commit hooks are blocking commits

If releasio's changes fail pre-commit hooks:

1. **Review the hook output** for specific errors
2. **Run formatters**: `ruff format . && ruff check --fix .`
3. **Configure hooks** to ignore auto-generated files if needed

For more detailed troubleshooting, see the [Troubleshooting Guide](troubleshooting/index.md).

# Configuration Reference

Complete reference for all releasio configuration options.

---

## Quick Reference

| Section | Option | Default | Description |
|---------|--------|---------|-------------|
| *General* | `default_branch` | `"main"` | Default branch for releases |
| | `allow_dirty` | `false` | Allow dirty working directory |
| `[version]` | `tag_prefix` | `"v"` | Git tag prefix |
| | `initial_version` | `"0.1.0"` | First release version |
| | `version_files` | `[]` | Additional version files |
| | `auto_detect_version_files` | `false` | Auto-detect version files |
| | `update_lock_file` | `true` | Update lock file after bump |
| `[changelog]` | `enabled` | `true` | Enable changelog generation |
| | `path` | `"CHANGELOG.md"` | Changelog file path |
| | `use_github_prs` | `false` | Use PR-based changelog |
| | `show_authors` | `false` | Show commit authors |
| | `native_fallback` | `true` | Use native if git-cliff missing |
| `[commits]` | `types_minor` | `["feat"]` | Types triggering minor bump |
| | `types_patch` | `["fix", "perf"]` | Types triggering patch bump |
| | `breaking_pattern` | `"BREAKING[ -]CHANGE:"` | Breaking change pattern |
| `[github]` | `release_pr_branch` | `"releasio/release"` | Release PR branch name |
| | `release_pr_labels` | `["release"]` | PR labels |
| | `draft_releases` | `false` | Create draft releases |
| `[publish]` | `enabled` | `true` | Enable PyPI publishing |
| | `registry` | PyPI URL | Package registry |
| | `tool` | `"uv"` | Build/publish tool |
| | `trusted_publishing` | `true` | Use OIDC publishing |
| `[hooks]` | `pre_bump` | `[]` | Commands before bump |
| | `post_bump` | `[]` | Commands after bump |
| | `pre_release` | `[]` | Commands before release |
| | `post_release` | `[]` | Commands after release |

---

## General Settings

Top-level settings that apply to the entire release process.

### `default_branch`

:octicons-tag-24: Type: `string` · Default: `"main"`

The default branch for releases.

```toml
default_branch = "main"
```

### `allow_dirty`

:octicons-tag-24: Type: `boolean` · Default: `false`

Allow releases from a dirty working directory.

```toml
allow_dirty = false
```

!!! warning
    Not recommended for production releases.

---

## `[version]` {#version}

Version management settings.

### `tag_prefix`

:octicons-tag-24: Type: `string` · Default: `"v"`

Prefix for git tags.

```toml
[version]
tag_prefix = "v"  # Creates tags like v1.0.0
```

### `initial_version`

:octicons-tag-24: Type: `string` · Default: `"0.1.0"`

Version to use for the first release (when no tags exist).

```toml
[version]
initial_version = "0.1.0"
```

### `pre_release`

:octicons-tag-24: Type: `string | null` · Default: `null`

Global pre-release identifier. Use for always creating pre-releases.

```toml
[version]
pre_release = "alpha"  # All releases are alpha
```

### `version_files`

:octicons-tag-24: Type: `list[path]` · Default: `[]`

Additional files to update with the version.

```toml
[version]
version_files = [
    "src/myproject/__init__.py",
    "docs/conf.py",
]
```

### `auto_detect_version_files`

:octicons-tag-24: Type: `boolean` · Default: `false`

Automatically detect and update version files.

```toml
[version]
auto_detect_version_files = true
```

Searches for:

- `__init__.py` with `__version__`
- `__version__.py`
- `_version.py`

### `update_lock_file`

:octicons-tag-24: Type: `boolean` · Default: `true`

Update lock file after version bump.

```toml
[version]
update_lock_file = true
```

Supports: `uv.lock`, `poetry.lock`, `pdm.lock`

---

## `[changelog]` {#changelog}

Changelog generation settings.

### `enabled`

:octicons-tag-24: Type: `boolean` · Default: `true`

Enable changelog generation.

```toml
[changelog]
enabled = true
```

### `path`

:octicons-tag-24: Type: `path` · Default: `"CHANGELOG.md"`

Path to the changelog file.

```toml
[changelog]
path = "CHANGELOG.md"
```

### `template`

:octicons-tag-24: Type: `string | null` · Default: `null`

Custom git-cliff template (path or inline).

```toml
[changelog]
template = "cliff-template.toml"
```

### `header`

:octicons-tag-24: Type: `string | null` · Default: `null`

Custom header for the changelog.

```toml
[changelog]
header = "# Release Notes\n\nAll notable changes to this project.\n"
```

### `use_github_prs`

:octicons-tag-24: Type: `boolean` · Default: `false`

Use GitHub PR-based changelog (recommended for squash merge).

```toml
[changelog]
use_github_prs = true
```

### `ignore_authors`

:octicons-tag-24: Type: `list[string]` · Default: `[list of bots]`

Authors to exclude from changelog.

```toml
[changelog]
ignore_authors = [
    "dependabot[bot]",
    "renovate[bot]",
]
```

### `section_headers`

:octicons-tag-24: Type: `dict[string, string]` · Default: `{...}`

Custom section headers for each commit type.

```toml
[changelog.section_headers]
feat = "✨ New Features"
fix = "🐛 Bug Fixes"
perf = "⚡ Performance"
docs = "📚 Documentation"
breaking = "⚠️ Breaking Changes"
```

### `show_authors`

:octicons-tag-24: Type: `boolean` · Default: `false`

Include author names in changelog entries.

```toml
[changelog]
show_authors = true
```

### `show_commit_hash`

:octicons-tag-24: Type: `boolean` · Default: `false`

Include short commit hash in changelog entries.

```toml
[changelog]
show_commit_hash = true
```

### `commit_template`

:octicons-tag-24: Type: `string | null` · Default: `null`

Custom template for each commit entry.

```toml
[changelog]
commit_template = "- {description} ({hash}) by @{author}"
```

Available variables: `{scope}`, `{description}`, `{author}`, `{hash}`, `{body}`, `{type}`

### `show_first_time_contributors`

:octicons-tag-24: Type: `boolean` · Default: `false`

Highlight first-time contributors.

```toml
[changelog]
show_first_time_contributors = true
first_contributor_badge = "🎉 First contribution!"
```

### `include_dependency_updates`

:octicons-tag-24: Type: `boolean` · Default: `false`

Include dependency updates section.

```toml
[changelog]
include_dependency_updates = true
```

### `native_fallback`

:octicons-tag-24: Type: `boolean` · Default: `true`

Generate changelog natively if git-cliff unavailable.

```toml
[changelog]
native_fallback = true
```

---

## `[commits]` {#commits}

Commit parsing and version bump rules.

### `types_minor`

:octicons-tag-24: Type: `list[string]` · Default: `["feat"]`

Commit types that trigger a **minor** version bump.

```toml
[commits]
types_minor = ["feat"]
```

### `types_patch`

:octicons-tag-24: Type: `list[string]` · Default: `["fix", "perf"]`

Commit types that trigger a **patch** version bump.

```toml
[commits]
types_patch = ["fix", "perf", "docs", "refactor"]
```

### `types_major`

:octicons-tag-24: Type: `list[string]` · Default: `[]`

Commit types that trigger a **major** version bump.

```toml
[commits]
types_major = []  # Usually empty; use breaking_pattern instead
```

### `breaking_pattern`

:octicons-tag-24: Type: `string` · Default: `"BREAKING[ -]CHANGE:"`

Regex pattern to detect breaking changes in commit body.

```toml
[commits]
breaking_pattern = "BREAKING[ -]CHANGE:"
```

### `scope_regex`

:octicons-tag-24: Type: `string | null` · Default: `null`

Only process commits matching this scope (for monorepos).

```toml
[commits]
scope_regex = "^(api|core)$"
```

### `skip_release_patterns`

:octicons-tag-24: Type: `list[string]` · Default: `["[skip release]", ...]`

Patterns in commit messages that skip release.

```toml
[commits]
skip_release_patterns = [
    "[skip release]",
    "[release skip]",
    "[no release]",
]
```

### `commit_parsers`

:octicons-tag-24: Type: `list[CommitParser]` · Default: `[]`

Custom commit parsers for non-conventional formats.

```toml
[[commits.commit_parsers]]
pattern = "^:sparkles:\\s*(?P<description>.+)$"
type = "feat"
group = "Features"

[[commits.commit_parsers]]
pattern = "^:bug:\\s*(?P<description>.+)$"
type = "fix"
group = "Bug Fixes"
```

### `use_conventional_fallback`

:octicons-tag-24: Type: `boolean` · Default: `true`

Fall back to conventional commit parsing if no custom parser matches.

```toml
[commits]
use_conventional_fallback = true
```

---

## `[github]` {#github}

GitHub integration settings.

### `owner` / `repo`

:octicons-tag-24: Type: `string | null` · Default: `null` (auto-detected)

Repository owner and name.

```toml
[github]
owner = "myorg"
repo = "myproject"
```

### `api_url`

:octicons-tag-24: Type: `string` · Default: `"https://api.github.com"`

GitHub API URL (for GitHub Enterprise).

```toml
[github]
api_url = "https://github.mycompany.com/api/v3"
```

### `release_pr_branch`

:octicons-tag-24: Type: `string` · Default: `"releasio/release"`

Branch name for release PRs.

```toml
[github]
release_pr_branch = "releasio/release"
```

### `release_pr_labels`

:octicons-tag-24: Type: `list[string]` · Default: `["release"]`

Labels to apply to release PRs.

```toml
[github]
release_pr_labels = ["release", "automated"]
```

### `draft_releases`

:octicons-tag-24: Type: `boolean` · Default: `false`

Create releases as drafts.

```toml
[github]
draft_releases = true
```

### `release_assets`

:octicons-tag-24: Type: `list[string]` · Default: `[]`

Files to upload as release assets (supports glob).

```toml
[github]
release_assets = [
    "dist/*.whl",
    "dist/*.tar.gz",
]
```

---

## `[publish]` {#publish}

PyPI publishing settings.

### `enabled`

:octicons-tag-24: Type: `boolean` · Default: `true`

Enable PyPI publishing.

```toml
[publish]
enabled = true
```

### `registry`

:octicons-tag-24: Type: `string` · Default: `"https://upload.pypi.org/legacy/"`

PyPI registry URL.

```toml
[publish]
registry = "https://test.pypi.org/legacy/"  # TestPyPI
```

### `tool`

:octicons-tag-24: Type: `"uv" | "poetry" | "pdm" | "twine"` · Default: `"uv"`

Tool to use for building and publishing.

```toml
[publish]
tool = "uv"
```

### `trusted_publishing`

:octicons-tag-24: Type: `boolean` · Default: `true`

Use OIDC trusted publishing when available.

```toml
[publish]
trusted_publishing = true
```

### `validate_before_publish`

:octicons-tag-24: Type: `boolean` · Default: `true`

Run validation (twine check) before publishing.

```toml
[publish]
validate_before_publish = true
```

### `check_existing_version`

:octicons-tag-24: Type: `boolean` · Default: `true`

Check if version already exists on PyPI.

```toml
[publish]
check_existing_version = true
```

---

## `[hooks]` {#hooks}

Release lifecycle hooks.

### `pre_bump`

:octicons-tag-24: Type: `list[string]` · Default: `[]`

Commands to run before version bump.

```toml
[hooks]
pre_bump = ["npm run lint", "pytest"]
```

### `post_bump`

:octicons-tag-24: Type: `list[string]` · Default: `[]`

Commands to run after version bump.

```toml
[hooks]
post_bump = ["npm run build"]
```

### `pre_release`

:octicons-tag-24: Type: `list[string]` · Default: `[]`

Commands to run before release.

```toml
[hooks]
pre_release = ["./scripts/pre-release.sh"]
```

### `post_release`

:octicons-tag-24: Type: `list[string]` · Default: `[]`

Commands to run after release.

```toml
[hooks]
post_release = ["./scripts/notify-slack.sh {version}"]
```

### `build`

:octicons-tag-24: Type: `string | null` · Default: `null`

Custom build command.

```toml
[hooks]
build = "make build VERSION={version}"
```

Available variables: `{version}`, `{project_path}`

---

## `[security]` {#security}

Security advisory settings.

### `enabled`

:octicons-tag-24: Type: `boolean` · Default: `false`

Enable security advisory integration.

```toml
[security]
enabled = true
```

### `auto_create_advisory`

:octicons-tag-24: Type: `boolean` · Default: `true`

Automatically create GitHub Security Advisories.

```toml
[security]
auto_create_advisory = true
```

### `security_patterns`

:octicons-tag-24: Type: `list[string]` · Default: `[...]`

Regex patterns to detect security commits.

```toml
[security]
security_patterns = [
    "fix\\(security\\):",
    "security:",
    "CVE-\\d{4}-\\d+",
]
```

---

## `[branches]` {#branches}

Multi-channel release configuration.

```toml
[branches.main]
match = "main"
prerelease = false

[branches.beta]
match = "beta"
prerelease = true
prerelease_token = "beta"

[branches.alpha]
match = "alpha/*"
prerelease = true
prerelease_token = "alpha"
```

### `match`

Branch name or glob pattern.

### `prerelease`

Whether releases are pre-releases.

### `prerelease_token`

Pre-release identifier (e.g., `"alpha"`, `"beta"`, `"rc"`).

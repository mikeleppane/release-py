# git-cliff Integration

:material-cliff: Advanced changelog generation with git-cliff.

---

## Overview

[git-cliff](https://git-cliff.org/) is a powerful changelog generator that offers:

- Custom templates (Tera/Jinja2 syntax)
- Advanced commit parsing
- Multiple output formats
- Extensive configuration

releasio integrates seamlessly with git-cliff for users who need more control.

---

## Setup

### Install git-cliff

```bash
# With cargo
cargo install git-cliff

# With homebrew
brew install git-cliff

# With pipx
pipx install git-cliff
```

### Enable in releasio

```toml title=".releasio.toml"
[changelog]
engine = "git-cliff"
```

---

## Configuration

### Basic cliff.toml

Create a `cliff.toml` in your project root:

```toml title="cliff.toml"
[changelog]
header = """
# Changelog

All notable changes to this project will be documented in this file.
"""
body = """
{% if version %}\
    ## [{{ version | trim_start_matches(pat="v") }}] - {{ timestamp | date(format="%Y-%m-%d") }}
{% else %}\
    ## [Unreleased]
{% endif %}\
{% for group, commits in commits | group_by(attribute="group") %}
    ### {{ group | upper_first }}
    {% for commit in commits %}
        - {{ commit.message | upper_first }}\
    {% endfor %}
{% endfor %}
"""
footer = ""
trim = true

[git]
conventional_commits = true
filter_unconventional = true
commit_parsers = [
    { message = "^feat", group = "Features" },
    { message = "^fix", group = "Bug Fixes" },
    { message = "^doc", group = "Documentation" },
    { message = "^perf", group = "Performance" },
    { message = "^refactor", group = "Refactoring" },
    { message = "^style", group = "Styling" },
    { message = "^test", group = "Testing" },
]
```

### releasio Integration

```toml title=".releasio.toml"
[changelog]
engine = "git-cliff"
cliff_config = "cliff.toml"  # Path to git-cliff config
path = "CHANGELOG.md"
```

---

## Templates

### Tera Syntax

git-cliff uses [Tera](https://tera.netlify.app/) templates:

```jinja2
{% for group, commits in commits | group_by(attribute="group") %}
### {{ group | upper_first }}
{% for commit in commits %}
- {{ commit.message }}{% if commit.scope %} ({{ commit.scope }}){% endif %}
{% endfor %}
{% endfor %}
```

### Available Variables

| Variable | Description |
|----------|-------------|
| `version` | Current version |
| `timestamp` | Release timestamp |
| `commits` | List of commits |
| `commit.id` | Full commit hash |
| `commit.message` | Commit message |
| `commit.group` | Parsed group |
| `commit.scope` | Commit scope |
| `commit.author.name` | Author name |
| `commit.author.email` | Author email |

### Filters

```jinja2
{{ version | trim_start_matches(pat="v") }}
{{ timestamp | date(format="%Y-%m-%d") }}
{{ message | upper_first }}
{{ commits | length }}
```

---

## Advanced Patterns

### With Authors

```toml title="cliff.toml"
[changelog]
body = """
{% for group, commits in commits | group_by(attribute="group") %}
### {{ group | upper_first }}
{% for commit in commits %}
- {{ commit.message | upper_first }} by @{{ commit.author.name }}
{% endfor %}
{% endfor %}
"""
```

### With Breaking Changes

```toml title="cliff.toml"
[git]
commit_parsers = [
    { message = "^.*!:", group = "Breaking Changes" },
    { body = ".*BREAKING CHANGE.*", group = "Breaking Changes" },
    { message = "^feat", group = "Features" },
    { message = "^fix", group = "Bug Fixes" },
]
```

### With Scope Grouping

```toml title="cliff.toml"
[changelog]
body = """
{% for group, commits in commits | group_by(attribute="group") %}
### {{ group | upper_first }}
{% for scope, scope_commits in commits | group_by(attribute="scope") %}
{% if scope %}**{{ scope }}**{% endif %}
{% for commit in scope_commits %}
- {{ commit.message | upper_first }}
{% endfor %}
{% endfor %}
{% endfor %}
"""
```

---

## Commit Parsers

### Pattern Matching

```toml title="cliff.toml"
[git]
commit_parsers = [
    # Breaking changes first
    { message = "^.*!", group = "⚠️ Breaking Changes" },
    { body = "BREAKING CHANGE", group = "⚠️ Breaking Changes" },

    # Standard types
    { message = "^feat", group = "✨ Features" },
    { message = "^fix", group = "🐛 Bug Fixes" },
    { message = "^doc", group = "📚 Documentation" },
    { message = "^perf", group = "⚡ Performance" },
    { message = "^refactor", group = "♻️ Refactoring" },

    # Skip certain commits
    { message = "^chore", skip = true },
    { message = "^ci", skip = true },

    # Catch-all
    { message = ".*", group = "Other" },
]
```

### Gitmoji Support

```toml title="cliff.toml"
[git]
commit_parsers = [
    { message = "^:boom:", group = "💥 Breaking Changes" },
    { message = "^:sparkles:", group = "✨ Features" },
    { message = "^:bug:", group = "🐛 Bug Fixes" },
    { message = "^:memo:", group = "📝 Documentation" },
    { message = "^:zap:", group = "⚡ Performance" },
    { message = "^:recycle:", group = "♻️ Refactoring" },
]
```

---

## Output Formats

### Markdown (Default)

```toml title="cliff.toml"
[changelog]
body = """
## [{{ version }}] - {{ timestamp | date(format="%Y-%m-%d") }}
...
"""
```

### JSON

```bash
git cliff --output CHANGELOG.json --output-format json
```

### Keep a Changelog

```toml title="cliff.toml"
[changelog]
header = """
# Changelog

All notable changes to this project will be documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.0.0/),
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).
"""
```

---

## Example Configurations

### Full-Featured

```toml title="cliff.toml"
[changelog]
header = """
# Changelog
"""
body = """
{% if version %}\
    ## [{{ version | trim_start_matches(pat="v") }}] - {{ timestamp | date(format="%Y-%m-%d") }}
{% else %}\
    ## [Unreleased]
{% endif %}\
{% for group, commits in commits | group_by(attribute="group") %}
    ### {{ group | upper_first }}
    {% for commit in commits %}
        - {% if commit.scope %}**{{ commit.scope }}:** {% endif %}\
          {{ commit.message | upper_first }}\
          {% if commit.github.pr_number %} (#{{ commit.github.pr_number }}){% endif %}\
          {% if commit.github.username %} by @{{ commit.github.username }}{% endif %}
    {% endfor %}
{% endfor %}
"""
footer = """
---
*Generated by [git-cliff](https://git-cliff.org)*
"""
trim = true

[git]
conventional_commits = true
filter_unconventional = true
split_commits = false
commit_preprocessors = [
    { pattern = '\((\w+\s)?#([0-9]+)\)', replace = "([#${2}](https://github.com/user/repo/issues/${2}))" },
]
commit_parsers = [
    { message = "^feat", group = "Features" },
    { message = "^fix", group = "Bug Fixes" },
    { message = "^doc", group = "Documentation" },
    { message = "^perf", group = "Performance" },
    { message = "^refactor", group = "Refactoring" },
    { message = "^style", group = "Styling" },
    { message = "^test", group = "Testing" },
    { message = "^chore\\(release\\)", skip = true },
    { message = "^chore", group = "Miscellaneous" },
]
filter_commits = false
tag_pattern = "v[0-9]*"
```

### Minimal

```toml title="cliff.toml"
[changelog]
body = """
{% for group, commits in commits | group_by(attribute="group") %}
### {{ group }}
{% for commit in commits %}
- {{ commit.message }}
{% endfor %}
{% endfor %}
"""

[git]
conventional_commits = true
commit_parsers = [
    { message = "^feat", group = "Added" },
    { message = "^fix", group = "Fixed" },
]
```

---

## Fallback Behavior

If git-cliff is unavailable, releasio automatically falls back to native generation (enabled by default):

```toml title=".releasio.toml"
[changelog]
# Native fallback is enabled by default (true)
# Set to false to require git-cliff and fail if not available
native_fallback = true
```

!!! info "git-cliff is Optional"
    releasio works without git-cliff installed. The native changelog generator
    handles most use cases. Only install git-cliff if you need advanced Tera
    templates or custom commit parsing.

---

## Troubleshooting

### "git-cliff not found"

```
Warning: git-cliff not available, using native generator
```

**This is normal behavior.** releasio automatically uses its native changelog
generator when git-cliff is not installed. If you want to require git-cliff,
set `native_fallback = false` in your config.

### Template Errors

```
Error: Failed to parse template
```

**Solution**: Validate your Tera template:

```bash
git cliff --dry-run
```

### Missing Commits

```
Warning: No commits found for changelog
```

**Checklist**:

- [ ] Commits follow conventional format
- [ ] `filter_unconventional = false` if using custom formats
- [ ] Tag pattern matches your tags

---

## See Also

- [git-cliff Documentation](https://git-cliff.org/docs/)
- [Tera Templates](https://tera.netlify.app/docs/)
- [Changelog Templates](templates.md) - Native template options
- [Conventional Commits](../commits/index.md) - Commit format

# Troubleshooting

This guide covers common issues you might encounter when using releasio and how to resolve them.

## Configuration Errors

### Configuration file not found

**Error:** `ConfigNotFoundError: Could not find pyproject.toml`

**Cause:** releasio requires a `pyproject.toml` file with project metadata.

**Solution:**

1. Ensure you're running releasio from your project root directory
2. Verify `pyproject.toml` exists and contains a `[project]` section:

```toml
[project]
name = "your-package"
version = "1.0.0"
```

### Invalid configuration values

**Error:** `ConfigValidationError: Invalid configuration`

**Cause:** Configuration values don't match expected types or constraints.

**Solution:**

1. Check for typos in configuration keys (releasio uses `extra = "forbid"` to catch these)
2. Verify all paths are valid
3. Ensure version patterns follow semantic versioning

```toml
# Correct
[tool.releasio.version]
tag_prefix = "v"

# Wrong - 'prefix' instead of 'tag_prefix'
[tool.releasio.version]
prefix = "v"  # This will error
```

---

## Git Errors

### Not a git repository

**Error:** `NotARepositoryError: Not a git repository`

**Cause:** The current directory is not initialized as a git repository.

**Solution:**

```bash
# Initialize git repository
git init

# Or navigate to the correct directory
cd /path/to/your/project
```

### Dirty repository

**Error:** `DirtyRepositoryError: Repository has uncommitted changes`

**Cause:** You have uncommitted changes and `allow_dirty = false` in configuration.

**Solution:**

=== "Commit your changes"

    ```bash
    git add .
    git commit -m "chore: save work in progress"
    ```

=== "Allow dirty working tree"

    ```toml
    [tool.releasio]
    allow_dirty = true
    ```

### Tag already exists

**Error:** `TagExistsError: Tag 'v1.0.0' already exists`

**Cause:** You're trying to create a release with a version that's already tagged.

**Solution:**

1. **Check existing tags:**
   ```bash
   git tag -l
   ```

2. **If the tag was created by mistake, delete it:**
   ```bash
   git tag -d v1.0.0
   git push origin :refs/tags/v1.0.0  # Remove from remote
   ```

3. **Or bump the version manually:**
   ```bash
   releasio update --execute --bump minor
   ```

---

## Version Errors

### Invalid version format

**Error:** `InvalidVersionError: Invalid version: '1.0' (must follow PEP 440)`

**Cause:** The version string doesn't follow [PEP 440](https://peps.python.org/pep-0440/) format.

**Solution:**

Use a valid semantic version format:

```toml
# Valid versions
version = "1.0.0"
version = "2.1.0a1"      # Alpha pre-release
version = "2.1.0b2"      # Beta pre-release
version = "2.1.0rc1"     # Release candidate
version = "1.0.0.post1"  # Post-release

# Invalid versions
version = "1.0"          # Missing patch
version = "v1.0.0"       # No 'v' prefix in version string
version = "1.0.0-beta"   # Use PEP 440 format: 1.0.0b1
```

### Version not found

**Error:** `VersionNotFoundError: Could not find version in project files`

**Cause:** releasio couldn't locate the version in your project.

**Solution:**

Ensure version is defined in `pyproject.toml`:

```toml
[project]
name = "your-package"
version = "1.0.0"  # Required
```

Or configure custom version file locations:

```toml
[tool.releasio.version]
files = ["src/mypackage/__init__.py"]
```

---

## GitHub Errors

### Authentication failed

**Error:** `AuthenticationError: GitHub authentication failed`

**Cause:** Invalid or missing GitHub token.

**Solution:**

=== "GitHub Actions"

    Ensure you're passing the token to the action:

    ```yaml
    - uses: mikeleppane/releasio-action@v1
      with:
        github-token: ${{ secrets.GITHUB_TOKEN }}
    ```

=== "Local CLI"

    Set the `GITHUB_TOKEN` environment variable:

    ```bash
    export GITHUB_TOKEN=ghp_your_token_here
    releasio release-pr --execute
    ```

### Rate limit exceeded

**Error:** `RateLimitError: API rate limit exceeded. Resets at 2024-01-15T10:30:00Z`

**Cause:** Too many GitHub API requests.

**Solution:**

1. **Wait for the rate limit to reset** (shown in error message)
2. **Use a token with higher limits:**
   - Unauthenticated: 60 requests/hour
   - Authenticated: 5,000 requests/hour
3. **Reduce API calls** by running releasio less frequently

---

## Publishing Errors

### Build failed

**Error:** `BuildError: Failed to build package`

**Cause:** The package build process failed.

**Solution:**

1. **Test the build locally:**
   ```bash
   # With uv
   uv build

   # With pip
   pip install build
   python -m build
   ```

2. **Check for missing files** in your `pyproject.toml`:
   ```toml
   [build-system]
   requires = ["hatchling"]
   build-backend = "hatchling.build"

   [tool.hatch.build.targets.wheel]
   packages = ["src/your_package"]
   ```

3. **Verify MANIFEST.in** includes all necessary files

### Already published

**Error:** `AlreadyPublishedError: mypackage 1.0.0 is already published`

**Cause:** This version already exists on PyPI.

**Solution:**

PyPI doesn't allow overwriting published versions. You must:

1. **Bump the version:**
   ```bash
   releasio update --execute --bump patch
   ```

2. **Or use a pre-release suffix:**
   ```bash
   releasio update --execute --pre-release rc1
   ```

### Upload failed

**Error:** `UploadError: Failed to upload to PyPI`

**Cause:** Various issues with PyPI upload.

**Solution:**

1. **Check your credentials:**
   - For Trusted Publishing, ensure your GitHub workflow is configured correctly
   - For token auth, verify your `PYPI_TOKEN` is valid

2. **Verify package name availability:**
   - Search [PyPI](https://pypi.org) to ensure the name isn't taken

3. **Check network connectivity:**
   ```bash
   curl -I https://upload.pypi.org/legacy/
   ```

---

## Changelog Errors

### git-cliff not found

**Error:** `ChangelogError: git-cliff not found, using native fallback`

**Cause:** git-cliff is not installed (this is a warning, not an error).

**Solution:**

=== "Install git-cliff (recommended)"

    ```bash
    # macOS
    brew install git-cliff

    # Linux
    cargo install git-cliff

    # Or use pre-built binaries from GitHub releases
    ```

=== "Use native changelog"

    releasio automatically falls back to native changelog generation. No action needed.

### Empty changelog

**Cause:** No conventional commits found since the last release.

**Solution:**

1. **Ensure you're using conventional commits:**
   ```bash
   git log --oneline -10  # Check recent commits
   ```

2. **Valid conventional commit formats:**
   ```
   feat: add new feature
   fix: resolve bug
   docs: update readme
   chore: update dependencies
   ```

3. **Check your commit type configuration:**
   ```toml
   [tool.releasio.commits]
   types_minor = ["feat"]
   types_patch = ["fix", "perf", "docs", "refactor"]
   ```

---

## Common Issues

### No version bump detected

**Cause:** Commits since last tag don't match any configured bump types.

**Solution:**

1. **Check commits since last tag:**
   ```bash
   releasio check
   ```

2. **Ensure commits follow conventional format:**
   ```
   feat: ...   # Minor bump
   fix: ...    # Patch bump
   feat!: ...  # Major bump (breaking change)
   ```

3. **Verify configuration:**
   ```toml
   [tool.releasio.commits]
   types_minor = ["feat"]
   types_patch = ["fix", "perf", "docs", "refactor", "style", "test", "build", "ci"]
   ```

### Pre-commit hooks fail

**Cause:** Code style or type errors before commit.

**Solution:**

1. **Run formatters:**
   ```bash
   ruff format .
   ruff check --fix .
   ```

2. **Fix type errors:**
   ```bash
   mypy src/
   ```

3. **Skip hooks temporarily (not recommended):**
   ```bash
   git commit --no-verify -m "feat: emergency fix"
   ```

---

## Getting Help

If you can't resolve your issue:

1. **Check existing issues:** [GitHub Issues](https://github.com/mikeleppane/release-py/issues)
2. **Search discussions:** [GitHub Discussions](https://github.com/mikeleppane/release-py/discussions)
3. **Open a new issue** with:
   - releasio version (`releasio --version`)
   - Python version (`python --version`)
   - Full error message and stack trace
   - Your `pyproject.toml` configuration (remove sensitive data)
   - Steps to reproduce

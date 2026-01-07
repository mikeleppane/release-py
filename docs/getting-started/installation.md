# Installation

## Install releasio

=== "pip"

    ```bash
    pip install releasio
    ```

=== "uv"

    ```bash
    uv add releasio --dev
    ```

=== "pipx (global)"

    ```bash
    pipx install releasio
    ```

## Optional: Install git-cliff (Recommended)

releasio works out of the box with its built-in native changelog generator. For more advanced changelog customization, you can optionally install [git-cliff](https://git-cliff.org/):

=== "Homebrew (macOS/Linux)"

    ```bash
    brew install git-cliff
    ```

=== "Cargo (Rust)"

    ```bash
    cargo install git-cliff
    ```

=== "npm"

    ```bash
    npm install -g git-cliff
    ```

=== "Scoop (Windows)"

    ```bash
    scoop install git-cliff
    ```

!!! success "No External Dependencies Required"
    **git-cliff is optional.** releasio includes a native changelog generator that's
    enabled by default (`native_fallback = true`). Install git-cliff only if you
    need advanced features like custom Tera templates or complex commit parsing.

## Verify Installation

Check that releasio is installed correctly:

```bash
# Check releasio
releasio --version

# Optional: Check git-cliff (if installed)
git-cliff --version
```

## GitHub Actions

When using releasio in GitHub Actions, git-cliff is installed automatically
by the action. No additional setup required.

```yaml
- uses: mikeleppane/releasio@v2
  with:
    command: release-pr
    github-token: ${{ secrets.GITHUB_TOKEN }}
```

## Next Steps

- [Quick Start](quickstart.md) - Get up and running in 5 minutes
- [First Release](first-release.md) - Complete walkthrough

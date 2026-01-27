# Shared Linter Configurations

This directory contains the **canonical linter configurations** used by both:
1. **Central-linter repository** (for self-linting)
2. **Client repositories** (as bundled defaults when they don't provide their own configs)

## Files

- `yamllint.yaml` - Shared yamllint configuration
- `ruff.toml` - Shared Ruff configuration

## How It Works

### For Central-Linter Repository (Self-Linting)

The central-linter repo uses these configs via symlinks:
```
.yamllint -> config/yamllint.yaml
.ruff.toml -> config/ruff.toml
```

When CI runs `make linter-central` in the central-linter repo, it uses these files.

### For Client Repositories (Bundled in Container Image)

These files are copied into the container image during build:
```dockerfile
COPY config/yamllint.yaml /home/linter/.config/yamllint.yaml
COPY config/ruff.toml /home/linter/.config/ruff.toml
```

When a client repo without its own configs runs `make linter-central`, the Makefile falls back to `$HOME/.config/`.

## Design Philosophy

**One source of truth**: These configs define the AIPCC team's recommended linting standards. They are:
- Lenient enough for general use (line-length warnings, not errors)
- Strict enough to catch common issues (basic Python and YAML checks)
- Easily overridable by client repos that need stricter/different rules

## Modifying These Configs

When you change these files:
1. **Central-linter repo** immediately uses the changes (via symlinks)
2. **Client repos** get the changes after:
   - CI builds a new container image
   - Client repos pull the new image

This ensures consistency across all AIPCC projects using the central-linter.

# Central Linter

A centralized linter container image for AIPCC CI/CD workflows, providing consistent linting across all projects.

## Features

This image includes the following linters:

- **ruff** - Fast Python linter and code formatter
- **yamllint** - YAML file linter
- **renovate-config-validator** - Validates Renovate configuration files
- **mr-commit-linter** - Validates GitLab merge requests and commit messages against AIPCC guidelines

## Image Location

`quay.io/aipcc-cicd/central-linter`

**Supported Architectures:** `amd64` (x86_64), `arm64` (aarch64)

The image is built as a multi-architecture manifest, automatically selecting the correct architecture when pulled.

**OpenShift Compatible:** The image supports running with arbitrary UIDs (OpenShift Security Context Constraints) by using GID 0 (root group) ownership with group write permissions.

## Usage

### Running Linters Locally

```bash
# Run all linters
make linter-central

# Or run individual linters
make linter-ruff-check
make linter-yamllint
make linter-renovate
```

The `linter-central` target executes:
- `ruff check .`
- `yamllint .`
- `renovate-config-validator` (auto-discovers configs, passes if none found)
- `mr-commit-linter` (validates commit messages and MR titles/descriptions)

### Using the Container Image

```bash
# Pull the image
podman pull quay.io/aipcc-cicd/central-linter:latest

# Run ruff check
podman run --rm -v $(pwd):/workspace:z quay.io/aipcc-cicd/central-linter:latest ruff check /workspace

# Run yamllint
podman run --rm -v $(pwd):/workspace:z quay.io/aipcc-cicd/central-linter:latest yamllint /workspace

# Validate Renovate config (auto-discovery)
podman run --rm -v $(pwd):/workspace:z -w /workspace \
  quay.io/aipcc-cicd/central-linter:latest \
  renovate-config-validator

# Validate specific Renovate config file
podman run --rm -v $(pwd):/workspace:z quay.io/aipcc-cicd/central-linter:latest \
  renovate-config-validator /workspace/renovate.json
```

### In GitLab CI/CD

See `examples/gitlab-ci-integration.yml` for complete examples. Basic usage:

```yaml
# Shared template
.lint-template:
  stage: lint
  # IMPORTANT: Pin to specific version for stability
  # Use :latest ONLY for central-linter repo self-linting
  image: quay.io/aipcc-cicd/central-linter:v0.1.0
  rules:
    - if: '$CI_PIPELINE_SOURCE == "merge_request_event"'
    - if: '$CI_COMMIT_BRANCH == $CI_DEFAULT_BRANCH'

# Option 1: Run all linters together
lint-all:
  extends: .lint-template
  script:
    - make linter-central

# Option 2: Run linters individually
ruff:
  extends: .lint-template
  script:
    - ruff check .
```

**Version Pinning Best Practices:**

| Usage | Recommended Tag | Reason |
|-------|----------------|---------|
| **Client repos (production)** | `:v0.1.0` or `:abc1234` | Stability, predictable behavior |
| **Central-linter self-lint** | `:latest` | Test latest changes |
| **Development/testing** | `:latest` or `:main` | Latest features |

**Available tags:**
- `:latest` - Latest stable release from main branch
- `:v0.1.0` - Specific version (recommended for production)
- `:abc1234` - Specific commit SHA (maximum reproducibility)

**To update your pinned version:**
```yaml
# Check available versions at: https://quay.io/repository/aipcc-cicd/central-linter?tab=tags
image: quay.io/aipcc-cicd/central-linter:v0.2.0  # Update to new version
```

## Local Development Integration

This section shows how to integrate central-linter into client repositories for local development. Use these patterns to ensure developers can run the same linters locally that run in CI/CD.

**Complete example**: See [`examples/Makefile.local-integration`](./examples/Makefile.local-integration) for a comprehensive Makefile example covering all use cases that you can copy to your project.

### Option 1: Direct Container Usage (Simplest)

Run linters directly with podman/docker without any integration:

```bash
# Pull the image once (use :latest for local dev, or pin version for stability)
podman pull quay.io/aipcc-cicd/central-linter:latest

# Run all linters via Makefile
podman run --rm -v $(pwd):/workspace:z -w /workspace \
  quay.io/aipcc-cicd/central-linter:latest \
  make linter-central

# Or run individual linters
podman run --rm -v $(pwd):/workspace:z -w /workspace \
  quay.io/aipcc-cicd/central-linter:latest \
  ruff check .

podman run --rm -v $(pwd):/workspace:z -w /workspace \
  quay.io/aipcc-cicd/central-linter:latest \
  yamllint .
```

**Note:** For local development, using `:latest` is acceptable. For CI/CD and production, always pin to a specific version (e.g., `:v0.1.0`).

**Use when:** Quick one-off linting, no permanent integration needed

---

### Option 2: Makefile Integration (Recommended)

Add central-linter targets to your project's Makefile:

```makefile
# Central-linter configuration
# For CI/CD: Pin to specific version (e.g., v0.1.0)
# For local dev: :latest is acceptable
LINTER_IMAGE := quay.io/aipcc-cicd/central-linter:latest
LINTER_MOUNT := -v $(CURDIR):/workspace:z -w /workspace
LINTER_RUN := podman run --rm $(LINTER_MOUNT) $(LINTER_IMAGE)

# Run central-linter (all linters)
# IMPORTANT: Pass variables through for Use Case 3 (custom config locations)
.PHONY: linter-central
linter-central:
	$(LINTER_RUN) make linter-central \
		RUFF_CONFIG="$(RUFF_CONFIG)" \
		YAMLLINT_CONFIG="$(YAMLLINT_CONFIG)" \
		RENOVATE_CONFIG="$(RENOVATE_CONFIG)"

# Run individual linters
.PHONY: linter-ruff-check
linter-ruff-check:
	$(LINTER_RUN) make linter-ruff-check

.PHONY: linter-yamllint
linter-yamllint:
	$(LINTER_RUN) make linter-yamllint

.PHONY: linter-renovate
linter-renovate:
	$(LINTER_RUN) make linter-renovate

# Auto-fix with ruff
.PHONY: linter-fix
linter-fix:
	$(LINTER_RUN) ruff check --fix .
	$(LINTER_RUN) ruff format .
```

**Integration with existing linters:**

If your project already has a `linter` target, integrate central-linter as a dependency:

```makefile
.PHONY: linter
linter: linter-central linter-custom-checks
	@echo "All linters passed"

# Your existing custom linters
.PHONY: linter-custom-checks
linter-custom-checks:
	./custom_linter.sh
```

**Example from wheels/builder:**

```makefile
# Add to existing Makefile
LINTER_IMAGE := quay.io/aipcc-cicd/central-linter:latest
LINTER_MOUNT := -v $(CURDIR):/workspace:z -w /workspace
LINTER_RUN := podman run --rm $(LINTER_MOUNT) $(LINTER_IMAGE)

.PHONY: linter-central
linter-central:
	$(LINTER_RUN) make linter-central \
		RUFF_CONFIG="$(RUFF_CONFIG)" \
		YAMLLINT_CONFIG="$(YAMLLINT_CONFIG)" \
		RENOVATE_CONFIG="$(RENOVATE_CONFIG)"

# Integrate with existing linter target
.PHONY: linter
linter: linter-tools linter-core linter-changelog linter-build-arg linter-jira linter-central
```

**Usage examples**:
```bash
# Use Case 1 & 2: No config or standard locations (auto-discovery)
make linter-central

# Use Case 3: Custom config locations
make linter-central \
  RUFF_CONFIG="--config .ci/ruff.toml" \
  YAMLLINT_CONFIG="-c .ci/yamllint.yaml"
```

**Use when:** Permanent integration, standard workflow for all developers

---

### Option 3: Tox Integration (Python Projects)

Add central-linter as a tox environment:

```ini
# tox.ini
[testenv:linter-central]
skip_install = true
allowlist_externals = podman
commands =
    podman run --rm \
        -v {toxinidir}:/workspace:z \
        -w /workspace \
        quay.io/aipcc-cicd/central-linter:latest \
        make linter-central
```

**Run with:**
```bash
tox -e linter-central
```

**Integration with existing tox linters:**

```ini
[tox]
envlist = linter,linter-central,py3,mypy

[testenv:linter]
# Your existing linter environment
deps = ruff
commands =
    ruff check package_plugins test

[testenv:linter-central]
skip_install = true
allowlist_externals = podman
commands =
    podman run --rm \
        -v {toxinidir}:/workspace:z \
        -w /workspace \
        quay.io/aipcc-cicd/central-linter:latest \
        ruff check .
    podman run --rm \
        -v {toxinidir}:/workspace:z \
        -w /workspace \
        quay.io/aipcc-cicd/central-linter:latest \
        yamllint .
```

**Run all linters in parallel:**
```bash
tox run-parallel -e linter,linter-central
```

**Use when:** Python project with tox, want parallel linter execution

---

### Option 4: Shell Alias (Developer Convenience)

Add to `~/.bashrc` or `~/.zshrc`:

```bash
# Central-linter aliases
alias linter-central='podman run --rm -v $(pwd):/workspace:z -w /workspace quay.io/aipcc-cicd/central-linter:latest make linter-central'
alias linter-ruff='podman run --rm -v $(pwd):/workspace:z -w /workspace quay.io/aipcc-cicd/central-linter:latest ruff check .'
alias linter-yamllint='podman run --rm -v $(pwd):/workspace:z -w /workspace quay.io/aipcc-cicd/central-linter:latest yamllint .'
alias linter-fix='podman run --rm -v $(pwd):/workspace:z -w /workspace quay.io/aipcc-cicd/central-linter:latest ruff check --fix . && podman run --rm -v $(pwd):/workspace:z -w /workspace quay.io/aipcc-cicd/central-linter:latest ruff format .'
```

**Use anywhere:**
```bash
cd /path/to/project
linter-central
linter-fix
```

**Use when:** Personal workflow, working across multiple repositories

---

### Option 5: Pre-Commit Hooks (Optional)

Add `.pre-commit-config.yaml`:

```yaml
repos:
  - repo: local
    hooks:
      - id: central-linter-ruff
        name: Central Linter - Ruff
        entry: podman run --rm -v $(pwd):/workspace:z -w /workspace quay.io/aipcc-cicd/central-linter:latest ruff check .
        language: system
        pass_filenames: false
        types: [python]

      - id: central-linter-yamllint
        name: Central Linter - YAML Lint
        entry: podman run --rm -v $(pwd):/workspace:z -w /workspace quay.io/aipcc-cicd/central-linter:latest yamllint .
        language: system
        pass_filenames: false
        types: [yaml]
```

**Install:**
```bash
pip install pre-commit
pre-commit install
```

**Run manually:**
```bash
pre-commit run --all-files
```

**Use when:** Want automatic linting before commits, enforce code quality

---

### Custom Configuration in Client Repos

When using custom linter configurations (stored in `.ci/` or `config/`), pass them via environment variables:

**Makefile example:**
```makefile
.PHONY: linter-central
linter-central:
	podman run --rm -v $(CURDIR):/workspace:z -w /workspace \
		$(LINTER_IMAGE) \
		make linter-central \
		RUFF_CONFIG="--config .ci/ruff.toml" \
		YAMLLINT_CONFIG="-c .ci/yamllint.yaml" \
		RENOVATE_CONFIG="config/renovate.json"
```

**Direct command example:**
```bash
podman run --rm -v $(pwd):/workspace:z -w /workspace \
  quay.io/aipcc-cicd/central-linter:latest \
  ruff check --config .ci/ruff.toml .
```

---

### Docker vs Podman

All examples use `podman`. To use `docker` instead:

```bash
# Replace podman with docker in commands
docker run --rm -v $(pwd):/workspace -w /workspace \
  quay.io/aipcc-cicd/central-linter:latest \
  make linter-central
```

**Note:** Docker uses `-v $(pwd):/workspace` while Podman uses `-v $(pwd):/workspace:z` (SELinux relabeling).

---

### Quick Reference

| **Integration** | **Complexity** | **Best For** |
|-----------------|----------------|--------------|
| Direct Container | Low | Quick checks, no permanent setup |
| Makefile | Medium | Standard workflow, all developers |
| Tox | Medium | Python projects, parallel execution |
| Shell Alias | Low | Personal workflow, multi-repo |
| Pre-commit | High | Enforce quality, automatic checks |

## Building the Image

```bash
# Build for your native architecture
make build

# Test the image
make test

# Push to quay.io (optional, for testing)
make push

# Build and push with specific tag
make build IMAGE_TAG=v0.1.0
make push IMAGE_TAG=v0.1.0
```

**Note:** Pushing requires authentication to quay.io:
```bash
podman login quay.io
```

**Local builds** create single-architecture images for your native platform (amd64 or arm64).

**Multi-architecture images** are automatically built and published by the GitLab CI/CD pipeline.

### Available Make Targets

Run `make help` to see all available targets:

```
linter-central     - Run all linters (ruff, yamllint, renovate-config-validator)
linter-ruff-check  - Run only ruff check
linter-yamllint    - Run only yamllint
linter-renovate    - Run only renovate-config-validator
build              - Build image for native architecture
test               - Test the linters in the container
push               - Push image to quay.io
clean              - Remove local images
```

### Running Unit Tests

Unit tests for the `mr_commit_linter` are located in `tests/` and run automatically in CI.

```bash
# Run tests locally (requires pytest)
pip install pytest pytest-mock
pytest tests/ -v

# With coverage
pip install pytest-cov
pytest tests/ --cov=scripts.mr_commit_linter --cov-report=html
```

Tests run in the CI pipeline during the `test` stage. The `test-unit` job ensures:
- All validation functions work correctly
- Pattern matching is accurate
- Error handling behaves as expected

See `scripts/README.md` for more details on the test suite.

### Multi-Arch Image Structure

After the CI/CD pipeline completes, the registry contains:

```
quay.io/aipcc-cicd/central-linter:latest          # Multi-arch manifest
quay.io/aipcc-cicd/central-linter:abc1234         # Multi-arch manifest (commit SHA)
quay.io/aipcc-cicd/central-linter:abc1234-amd64   # x86_64 specific image
quay.io/aipcc-cicd/central-linter:abc1234-arm64   # ARM64 specific image
quay.io/aipcc-cicd/central-linter:v0.1.0          # Multi-arch manifest (git tag)
```

When you `podman pull` or `docker pull` the `:latest` tag, the container runtime automatically selects the correct architecture-specific image for your platform.

**Note:** Local builds using `make build` create single-architecture images only. Multi-architecture manifests are created exclusively by the CI/CD pipeline.

## Setup

### Prerequisites

- Access to `redhat/rhel-ai/ci-cd/central-linter` GitLab project
- Quay.io robot account for `aipcc-cicd` organization

### Required GitLab CI/CD Variables

Configure in Settings → CI/CD → Variables:

| Variable | Type | Protected | Masked |
|----------|------|-----------|--------|
| `QUAY_USERNAME` | Variable | Yes | No |
| `QUAY_PASSWORD` | Variable | Yes | Yes |

### CI/CD Pipeline

The pipeline automatically:

1. **Build** - Builds container images for both architectures in parallel on native runners:
   - Builds amd64 image on x86_64 runner
   - Builds arm64 image on aarch64 runner
   - Saves each image as an OCI archive tarball artifact
2. **Lint & Test** - After build completes, lint and test jobs run in parallel:
   - **Lint** (stage: lint) - Loads newly built amd64 image and runs `make linter-central`
   - **Test amd64** (stage: test) - Loads amd64 image and validates all linters work
   - **Test arm64** (stage: test) - Loads arm64 image and validates all linters work
3. **Push** - Pushes images and creates multi-arch manifests:
   - Loads images from tarballs and tags them
   - Pushes architecture-specific images (`:commit-sha-amd64`, `:commit-sha-arm64`)
   - Creates and pushes multi-arch manifests:
     - Main branch → `:latest` and `:commit-sha`
     - Git tags → `:v0.1.0` (version tag) and `:commit-sha`

All manifests support both `amd64` and `arm64` architectures.

**Pipeline stages:** The pipeline uses 4 stages (build → lint → test → push) for organizational clarity, but lint and test jobs run in parallel after their build dependencies complete, improving efficiency.

**Note:** The lint job uses the newly built image (not `:latest`), which allows linter configuration changes to be validated within the same merge request.

**Note:** The `:latest` tag is only updated on main branch commits, not on every tag. This ensures backports or hotfix tags don't accidentally become "latest".

#### Runner Requirements

The CI/CD pipeline requires GitLab runners with both architectures:
- **amd64 runner** - Tagged with `aipcc-small-x86_64` (for x86_64 builds)
- **arm64 runner** - Tagged with `aipcc-small-aarch64` (for ARM64 builds)

Both builds run **natively** on their respective runners for maximum performance and reliability (no emulation).

**Note:** This follows the AIPCC standard runner naming convention used across all projects.

### Creating a Release

```bash
# Create annotated tag with commit history
git tag -a v0.1.0 -m "$(git log $(git describe --tags --abbrev=0 2>/dev/null || git rev-list --max-parents=0 HEAD)..HEAD --oneline --no-decorate)"

# Push tag (triggers CI/CD to build and push image)
git push origin v0.1.0
```

## Automated Dependency Updates

Renovate automatically creates merge requests when new versions are available:

- **ruff**: Monitors GitHub releases from `astral-sh/ruff`
- **yamllint**: Monitors PyPI package
- **renovate**: Monitors npm package

Linter versions are defined in `Containerfile`:

```
ARG RUFF_VERSION=0.14.2
ARG YAMLLINT_VERSION=1.37.1
ARG RENOVATE_VERSION=42.21.3
ARG NODE_MAJOR=20
```

Version detection and grouping is configured in `renovate.json` using regex managers.

**Note:** Node.js 20 LTS is installed from NodeSource to support Renovate's ESM modules.

## Configuration

All linters support three configuration approaches:

### Use Case 1: No Configuration (Use Shared Configs)

Simply run the linters without any configuration files. The image includes **shared configurations** that are:
- The same configs used by the central-linter repository itself
- Maintained in a central location: `config/` folder
- More lenient than linter built-in defaults

**Shared config settings:**
- **yamllint**: Line length up to 120 chars (**warning**, not error), no document-start required
- **ruff**: Line length 120 chars, basic Python checks (E, F, I), E501 ignored

```bash
# Locally
make linter-central

# In GitLab CI
lint:
  image: quay.io/aipcc-cicd/central-linter:latest
  script:
    - make linter-central
```

**What happens:**
1. Makefile checks if your repo has `.yamllint`, `.ruff.toml`, or `pyproject.toml`
2. If **not found** → Uses shared configs from `~/.config/linter/` (same as central-linter uses)
3. If **found** → Uses your config (auto-discovery)

**Shared configs location:**
- **Source**: `config/yamllint.yaml` and `config/ruff.toml` in this repo
- **In container image**: `~/.config/linter/yamllint.yaml` and `~/.config/linter/ruff.toml` (in linter user's home)
- **Central-linter self-linting**: Via symlinks `.yamllint` → `config/yamllint.yaml`

**View/Copy shared configs:**
```bash
# View from container
podman run --rm quay.io/aipcc-cicd/central-linter:latest cat ~/.config/linter/yamllint.yaml

# Copy to your repo (optional - creates a local override)
podman run --rm quay.io/aipcc-cicd/central-linter:latest \
  cat ~/.config/linter/yamllint.yaml > .yamllint
```

**Works for:** Quick setup, simple projects, consistent AIPCC team standards without strict line-length errors

---

### Use Case 2: Configuration in Standard Locations (Auto-Discovery)

Place configuration files in your project root. Linters automatically discover and use them.

**File structure:**
```
my-project/
├── .ruff.toml              # Ruff auto-discovers this
├── .yamllint               # yamllint auto-discovers this
├── renovate.json           # renovate-config-validator checks this by default
└── src/
```

**Usage:**
```bash
# Locally - configs are auto-discovered
make linter-central

# In GitLab CI - same
lint:
  image: quay.io/aipcc-cicd/central-linter:latest
  script:
    - make linter-central
```

**How auto-discovery works:**

When `make linter-central` runs, the Makefile checks if you provided explicit config paths. If not, **the linters themselves search for config files** in these locations:

| Linter | Search Order (first match wins) | Behavior |
|--------|--------------------------------|----------|
| **Ruff** | 1. `pyproject.toml` (in current dir)<br>2. `ruff.toml`<br>3. `.ruff.toml`<br>4. Check parent directories recursively<br>5. If none found → Use `$HOME/.config/linter/ruff.toml` (shared config) | Stops at first match |
| **yamllint** | 1. `.yamllint` (in current dir)<br>2. `.yamllint.yaml`<br>3. `.yamllint.yml`<br>4. `$XDG_CONFIG_HOME/yamllint/config`<br>5. `~/.config/yamllint/config`<br>6. If none found → Use `$HOME/.config/linter/yamllint.yaml` (shared config) | Stops at first match |
| **Renovate** | 1. Auto-discovers: `renovate.json`, `.renovaterc`, `.renovaterc.json`, etc.<br>2. Or specify via `RENOVATE_CONFIG=path` | Auto-discovery by default, passes if none found |

**Example:** If your repo has both `pyproject.toml` with `[tool.ruff]` section AND `.ruff.toml`, Ruff will use `pyproject.toml` (first in search order).

**Example configs:** See [config/ruff.toml](./config/ruff.toml) and [config/yamllint.yaml](./config/yamllint.yaml) for the shared configs.

---

### Use Case 3: Configuration in Custom Locations

Store configs in subdirectories (e.g., `.ci/`, `config/`) for better organization.

**File structure:**
```
my-project/
├── .ci/
│   ├── ruff.toml
│   └── yamllint.yaml
├── config/
│   └── renovate.json
└── src/
```

**Option A: Pass config paths via Makefile variables**

```bash
# Locally
make linter-central \
  RUFF_CONFIG="--config .ci/ruff.toml" \
  YAMLLINT_CONFIG="-c .ci/yamllint.yaml" \
  RENOVATE_CONFIG="config/renovate.json"
```

**In .gitlab-ci.yml:**

```yaml
# Method 1: Use Makefile with custom config paths
lint-with-custom-configs:
  stage: lint
  image: quay.io/aipcc-cicd/central-linter:latest
  variables:
    RUFF_CONFIG: "--config .ci/ruff.toml"
    YAMLLINT_CONFIG: "-c .ci/yamllint.yaml"
    RENOVATE_CONFIG: "config/renovate.json"
  script:
    - make linter-central

# Method 2: Pass inline to make
lint-with-inline-vars:
  stage: lint
  image: quay.io/aipcc-cicd/central-linter:latest
  script:
    - make linter-central
        RUFF_CONFIG="--config .ci/ruff.toml"
        YAMLLINT_CONFIG="-c .ci/yamllint.yaml"
        RENOVATE_CONFIG="config/renovate.json"
```

**Option B: Run linters directly (no Makefile)**

```yaml
lint-direct:
  stage: lint
  image: quay.io/aipcc-cicd/central-linter:latest
  script:
    - ruff check --config .ci/ruff.toml .
    - yamllint -c .ci/yamllint.yaml .
    - renovate-config-validator --strict config/renovate.json
```

**Option C: Create symlinks to standard locations**

```bash
# One-time setup
ln -s .ci/ruff.toml .ruff.toml
ln -s .ci/yamllint.yaml .yamllint

# Now auto-discovery works
make linter-central
```

---

### Makefile Variables Reference

Run `make help` to see all available configuration options:

| Variable | Purpose | Example |
|----------|---------|---------|
| `RUFF_CONFIG` | Custom ruff config path | `--config .ci/ruff.toml` |
| `YAMLLINT_CONFIG` | Custom yamllint config path | `-c .ci/yamllint.yaml` |
| `RENOVATE_CONFIG` | Custom renovate file path (default: auto-discovery) | `config/renovate.json` |
| `RUFF_ARGS` | Additional ruff arguments | `check --fix .` |
| `YAMLLINT_ARGS` | Additional yamllint arguments | `-s .` |

---

### Quick Reference

| Scenario | Setup | Command |
|----------|-------|---------|
| No config files | _(none)_ | `make linter-central` |
| Configs in project root | `.ruff.toml`<br>`.yamllint`<br>`renovate.json` | `make linter-central` |
| Configs in `.ci/` dir | Move configs to `.ci/` | `make linter-central RUFF_CONFIG="--config .ci/ruff.toml" ...` |

## Container Security and OpenShift Compatibility

The central-linter container image is **fully compatible with OpenShift Container Platform (OCP)** and supports running with **arbitrary UIDs**.

**OpenShift Security Context Constraints (SCC):**
- OpenShift runs containers with a random UID from the namespace-allocated range (e.g., `1000570000`)
- All UIDs are placed in GID 0 (root group) for compatibility

**Implementation:**
```dockerfile
# Set ownership to root group (GID 0) with group permissions
chown -R 1001:0 /workspace /home/linter
chmod -R g=u /workspace /home/linter
```

This allows the container to run as UID 1001 (regular Docker/Podman) or as random UID in GID 0 (OpenShift).

**Testing OpenShift compatibility locally:**
```bash
# Simulate OpenShift arbitrary UID
podman run --rm --user 1000570000:0 \
  -v $(pwd):/workspace:z -w /workspace \
  quay.io/aipcc-cicd/central-linter:latest \
  make linter-central
```

**Security features:**
- Non-root user (UID 1001, never root)
- Minimal base image (Red Hat UBI9)
- No privileged operations required
- Compatible with OpenShift `restricted` SCC (default, most secure)

## MR/Commit Linter

The MR/commit linter validates merge requests and commit messages against AIPCC commit guidelines.

### What It Checks

**For each commit:**
1. Title must begin with a valid JIRA ticket ID (RHELAI, RHOAIENG, AIPCC, INFERENG, RHAIENG) or INTERNAL
2. Body must contain a `Signed-off-by:` tag
3. Body must be at least 3 lines (description + empty line + Signed-off-by)

**For merge requests (CI only):**
1. MR title must begin with a valid JIRA ticket ID or INTERNAL
2. MR description must contain a `Signed-off-by:` tag

**INTERNAL commits:**
- Can only modify files listed in `config/linterignore`
- Cannot modify `config/linterignore` itself (requires JIRA ticket)

**Bot exemptions:**
- Commits/MRs created by `platform-engineering-bot` or `aipcc-cicd-bot` are automatically skipped

### Usage

```bash
# Run all linters including MR/commit linter
make linter-central

# Run MR/commit linter only
make linter-mr-commit
```

### Local vs CI Behavior

**Local development:**
- MR title/description checks are skipped (no CI environment variables)
- Commit message checks still run against your branch commits
- Compares your branch against `main` branch (or `CI_MERGE_REQUEST_DIFF_BASE_SHA` if set)

**In GitLab CI:**
- Checks all commits in the merge request
- Validates MR title and description
- Uses `CI_MERGE_REQUEST_DIFF_BASE_SHA` to determine commit range

### INTERNAL File Allowlist

The `config/linterignore` file defines which files can be modified with INTERNAL commits:

```
# config/linterignore
README.md
.gitignore
.gitlab-ci.yml
Makefile
renovate.json
```

**To customize for your repository:**

1. Create `.linterignore` in your repo root (overrides bundled config)
2. List files that can be modified without JIRA tickets
3. Supports exact paths and directory wildcards (`directory/*`)

Example:
```
# .linterignore
README.md
docs/*
test/fixtures/*
```

### Error Messages

Common validation failures:

```
ERROR: Commit abc1234: title must begin with a valid Jira ticket (RHELAI,RHOAIENG, AIPCC, INFERENG, RHAIENG or INTERNAL).
```
Fix: Add JIRA ticket or INTERNAL to commit title

```
ERROR: Commit abc1234: commit does not contain a Signed-off-by: tag.
```
Fix: Add `Signed-off-by: Your Name <your.email@example.com>` to commit message

```
ERROR: Commit abc1234: description must be at least three lines in length
```
Fix: Add a meaningful commit description before the Signed-off-by line

```
ERROR: path/to/file.txt is not in /home/linter/.config/linterignore
```
Fix: Either use a JIRA ticket instead of INTERNAL, or add the file to linterignore

For more details, see [AIPCC Commit and Merge Request Guidelines](https://docs.google.com/document/d/1TAicyqGKKELzaYL4o-Plz2s7tFUhOctZFzHErMQSc8c).

## Troubleshooting

## License

Internal CI/CD tooling for Red Hat AIPCC projects.

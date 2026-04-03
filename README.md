# Central Linter

A centralized linter container image for AIPCC CI/CD workflows, providing consistent linting across all projects.

## Features

This image includes the following linters:

- **ruff** - Fast Python linter and code formatter
- **yamllint** - YAML file linter
- **renovate-config-validator** - Validates Renovate configuration files
- **mr-commit-linter** - Validates GitLab merge requests and commit messages against AIPCC guidelines
- **shellcheck** - Static analysis for shell scripts
- **markdownlint** - Markdown style and syntax linter

## Image Location

`quay.io/aipcc-cicd/central-linter`

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
make linter-shellcheck
make linter-markdownlint
```

The `linter-central` target executes:
- `ruff check .`
- `yamllint .`
- `renovate-config-validator` (auto-discovers configs, passes if none found)
- `mr-commit-linter` (validates commit messages and MR titles/descriptions)
- `shellcheck` (checks all `*.sh` files, skips if none found)
- `markdownlint` (checks all `*.md` files)

### Using the Container Image

```bash
# Pull the image
podman pull quay.io/aipcc-cicd/central-linter:latest

# Run all linters using container's Makefile (recommended)
podman run --rm -v $(pwd):/workspace:z -w /workspace \
  quay.io/aipcc-cicd/central-linter:latest \
  make -f /home/linter/Makefile linter-central

# Or run individual linters directly
# Run ruff check
podman run --rm -v $(pwd):/workspace:z -w /workspace \
  quay.io/aipcc-cicd/central-linter:latest ruff check .

# Run yamllint
podman run --rm -v $(pwd):/workspace:z -w /workspace \
  quay.io/aipcc-cicd/central-linter:latest yamllint .

# Validate Renovate config (auto-discovery)
podman run --rm -v $(pwd):/workspace:z -w /workspace \
  quay.io/aipcc-cicd/central-linter:latest \
  renovate-config-validator

# Validate specific Renovate config file
podman run --rm -v $(pwd):/workspace:z -w /workspace \
  quay.io/aipcc-cicd/central-linter:latest \
  renovate-config-validator renovate.json
```

### In GitLab CI/CD

**Recommended: Use the includable CI template** with a pinned `ref:`. This gives you version pinning, Renovate-managed updates, and a centralized job definition:

```yaml
# In your .gitlab-ci.yml
include:
  - project: 'redhat/rhel-ai/ci-cd/central-linter'
    file: '/templates/linter-central.yml'
    ref: v0.1.0
```

The template defines a `linter-central` job in the `lint` stage. To customize the stage:

```yaml
include:
  - project: 'redhat/rhel-ai/ci-cd/central-linter'
    file: '/templates/linter-central.yml'
    ref: v0.1.0
    inputs:
      JOB_STAGE: checks
```

**Renovate setup for automatic version updates:**

Add to your `renovate.json` to get MRs when new central-linter versions are released:

```json
{
  "customType": "regex",
  "managerFilePatterns": [".gitlab-ci.yml"],
  "matchStrings": [
    "project:\\s*'redhat/rhel-ai/ci-cd/central-linter'\\s+file:\\s*'[^']*'\\s+ref:\\s*(?<currentValue>v[^\\s]+)"
  ],
  "datasourceTemplate": "gitlab-releases",
  "depNameTemplate": "redhat/rhel-ai/ci-cd/central-linter"
}
```

**Alternative: Direct image reference** (see `examples/gitlab-ci-integration.yml` for more examples):

```yaml
lint:
  stage: lint
  image: quay.io/aipcc-cicd/central-linter:v0.1.0
  rules:
    - if: $CI_COMMIT_MESSAGE =~ /^Draft:/
      when: never
    - if: '$CI_PIPELINE_SOURCE == "merge_request_event"'
  script:
    - make -f $HOME/Makefile linter-central
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
# Uses Makefile from container image for config auto-discovery
.PHONY: linter-central
linter-central:
	$(LINTER_RUN) make -f /home/linter/Makefile linter-central

# Run individual linters
.PHONY: linter-ruff-check
linter-ruff-check:
	$(LINTER_RUN) make -f /home/linter/Makefile linter-ruff-check

.PHONY: linter-yamllint
linter-yamllint:
	$(LINTER_RUN) make -f /home/linter/Makefile linter-yamllint

.PHONY: linter-renovate
linter-renovate:
	$(LINTER_RUN) make -f /home/linter/Makefile linter-renovate

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
	$(LINTER_RUN) make -f /home/linter/Makefile linter-central

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
alias linter-central='podman run --rm -v $(pwd):/workspace:z -w /workspace quay.io/aipcc-cicd/central-linter:latest make -f /home/linter/Makefile linter-central'
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

**Local builds** create images for your native platform.

### Available Make Targets

Run `make help` to see all available targets:

```
linter-central       - Run all linters (ruff, yamllint, renovate, mr-commit, shellcheck, markdownlint)
linter-ruff-check    - Run only ruff check
linter-yamllint      - Run only yamllint
linter-renovate      - Run only renovate-config-validator
linter-mr-commit     - Run only MR/commit linter
linter-shellcheck    - Run only shellcheck
linter-markdownlint  - Run only markdownlint
build                - Build image for native architecture
test                 - Test the linters in the container
push                 - Push image to quay.io
clean                - Remove local images
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

Tests run in the CI pipeline during the `test` stage. The `test` job ensures:
- All validation functions work correctly
- Pattern matching is accurate
- Error handling behaves as expected

See `scripts/README.md` for more details on the test suite.

### Image Tags

After the CI/CD pipeline completes, the registry contains:

```
quay.io/aipcc-cicd/central-linter:latest    # Latest main-branch image
quay.io/aipcc-cicd/central-linter:abc1234   # Commit SHA tag
quay.io/aipcc-cicd/central-linter:v0.1.0   # Git tag (version release)
```

**Note:** The `:latest` tag is only updated on main branch commits, not on every tag. This ensures backports or hotfix tags don't accidentally become "latest".

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

1. **Build** - Builds a single container image and pushes it to the GitLab registry with the commit SHA tag.
2. **Lint & Test** - After build completes, lint and test jobs run in parallel:
   - **Lint** (stage: lint) - Runs `make linter-central` inside the newly built image
   - **Test** (stage: test) - Runs directly inside the built image, validating all linters and running unit tests
3. **Push** - Pulls the built image from the GitLab registry and pushes it to quay.io:
   - Always pushes `:commit-sha`
   - Main branch → also pushes `:latest`
   - Git tags → also pushes `:v0.1.0` (version tag)

**Pipeline stages:** The pipeline uses 4 stages (build → lint → test → push). Lint and test run in parallel after build completes.

**Note:** The lint and test jobs use the newly built image (not `:latest`), which allows linter configuration changes to be validated within the same merge request.

#### Runner Requirements

The CI/CD pipeline uses the following runners:
- **Default runner** - Tagged with `aipcc-k8s-cicd` (most jobs)
- **Build and push jobs** - Tagged with `aipcc-small-x86_64`

### Creating a Release

Use `release.sh` to bump the image version in the CI template, commit, and tag in one step:

```bash
# Bump version, commit, and tag
./release.sh v0.2.0

# Push commit and tag (triggers CI/CD to build and push image)
git push && git push --tags
```

The script updates the image version in `templates/linter-central.yml` to match the tag, ensuring the template and image are always in sync. Consuming repos using `include: project:` with a pinned `ref:` will get the matching image version automatically.

## Automated Dependency Updates

Renovate automatically creates merge requests when new versions are available:

- **ruff**: Monitors GitHub releases from `astral-sh/ruff`
- **yamllint**: Monitors PyPI package
- **renovate**: Monitors npm package
- **shellcheck-py**: Monitors PyPI package (wraps the shellcheck binary)
- **markdownlint-cli**: Monitors npm package

Linter versions are defined in `Containerfile`:

```
ARG RUFF_VERSION=0.14.2
ARG YAMLLINT_VERSION=1.38.0
ARG RENOVATE_VERSION=43.55.6
ARG SHELLCHECK_VERSION=0.10.0.1
ARG MARKDOWNLINT_VERSION=0.44.0
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
- **markdownlint**: Stylistic rules disabled (line length, inline HTML, blank lines around fences/lists, tabs in code blocks, emphasis-as-heading, duplicate headings, code block language, first-line heading); structural and correctness rules remain active

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
1. Makefile checks if your repo has `.yamllint`, `.ruff.toml`, `pyproject.toml`, or `.markdownlint.yaml`
2. If **not found** → Uses shared configs from `~/.config/linter/` (same as central-linter uses)
3. If **found** → Uses your config (auto-discovery)

Note: shellcheck natively auto-discovers `.shellcheckrc` in the project root — no Makefile logic needed.

**Shared configs location:**
- **Source**: `config/yamllint.yaml`, `config/ruff.toml`, and `config/markdownlint.yaml` in this repo
- **In container image**: `~/.config/linter/` (in linter user's home)
- **Central-linter self-linting**: Via symlinks `.yamllint` → `config/yamllint.yaml`

**View/Copy shared configs:**
```bash
# View from container
podman run --rm quay.io/aipcc-cicd/central-linter:latest cat ~/.config/linter/yamllint.yaml
podman run --rm quay.io/aipcc-cicd/central-linter:latest cat ~/.config/linter/markdownlint.yaml

# Copy to your repo (optional - creates a local override)
podman run --rm quay.io/aipcc-cicd/central-linter:latest \
  cat ~/.config/linter/markdownlint.yaml > .markdownlint.yaml
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
├── .markdownlint.yaml      # markdownlint auto-discovers this
├── .shellcheckrc           # shellcheck auto-discovers this
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
| **shellcheck** | 1. `.shellcheckrc` (in current dir, then parent dirs)<br>2. `~/.shellcheckrc`<br>3. If none found → Uses built-in defaults | Native auto-discovery, override flags via `SHELLCHECK_ARGS` |
| **markdownlint** | 1. `.markdownlint.yaml` (in current dir)<br>2. `.markdownlint.yml`<br>3. `.markdownlint.json`<br>4. If none found → Use `$HOME/.config/linter/markdownlint.yaml` (shared config) | Stops at first match |

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
| `SHELLCHECK_ARGS` | shellcheck flags (default: `--severity=warning`) | `--severity=error -e SC2086` |
| `MARKDOWNLINT_CONFIG` | Custom markdownlint config path | `.ci/markdownlint.yaml` |
| `RUFF_ARGS` | Additional ruff arguments | `check --fix .` |
| `YAMLLINT_ARGS` | Additional yamllint arguments | `-s .` |
| `MARKDOWNLINT_ARGS` | Additional markdownlint arguments (default: `.`) | `docs/` |

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

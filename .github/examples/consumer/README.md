# Protected Paths Guard - Consumer Integration

This directory contains example workflows for integrating central-linter's protected-paths guard into consumer repositories.

## Overview

The protected-paths guard is a deterministic (no-AI) supply-chain visibility layer that posts an informational comment when a PR touches sensitive configuration files. It does NOT enforce approval by itself — CODEOWNERS + branch protection remain the actual approval gate.

## Fork Safety

The guard uses a two-stage workflow pattern for fork safety:

1. **Detect stage** (`protected-paths-detect.yml`): Runs unprivileged on `pull_request`. It reads the base repo's config and changed file paths via the GitHub API, then produces a sanitized JSON artifact.
2. **Comment stage** (`protected-paths-comment.yml`): Runs privileged on `workflow_run`. It consumes only the sanitized artifact and posts an informational comment.

This separation ensures that fork PRs cannot access secrets or write to the repository, even if they modify CI/CD configuration.

## Installation

### 1. Add the two caller workflows

Add these two small files to your consumer repo (contents shown in this directory).
They are the **entire** per-repo footprint — no scripts, no logic to maintain:

- `.github/workflows/protected-paths-detect.yml`  (calls the reusable detect workflow on `pull_request`)
- `.github/workflows/protected-paths-comment.yml` (calls the reusable comment workflow on `workflow_run`)

All detection/comment logic lives in `opendatahub-io/central-linter` and is versioned via the `@v1` ref
(Renovate can keep it current).

### 2. Create your protected-paths config (REQUIRED)

The guard reads its protected-path list from a config file **in your repo** at the path
given by the `config` input (default `.github/protected-paths.yml`). **If that file does not
exist, nothing is protected** — the detect stage emits an empty result and no comment is posted.
There is no implicit default list applied to consumer repos. Create the file:

```yaml
paths:
  # AI assistant configuration (primary breach vector)
  - ".claude/"
  - ".cursor/"
  - "AGENTS.md"
  - "CLAUDE.md"
  # CI / supply-chain configuration
  - ".github/workflows/"
  - ".github/actions/"
  - ".gitlab-ci.yml"
  - ".tekton/"
  # Access control — self-protection so the gate can't be silently removed
  - "CODEOWNERS"
  - ".github/CODEOWNERS"
  - ".github/protected-paths.yml"
  # Add any other sensitive paths specific to your repo
```

A good starting point is to copy central-linter's own
[`.github/protected-paths.yml`](../../protected-paths.yml) and tailor it to your repo.

### 3. Optional: customize the detect caller

Edit `.github/workflows/protected-paths-detect.yml` to:
- Point `central-ref` to a specific version (default: `v1`)
- Change the `config` path if your protected-paths config is elsewhere

### 4. Optional: verify with a test PR

Create a PR that modifies a protected path (e.g., edit `.github/workflows/some-workflow.yml`). The detect stage should run and the comment stage should post a guard comment on the PR.

## How it Works

### Detect Stage

```yaml
uses: opendatahub-io/central-linter/.github/workflows/protected-paths-detect.yml@v1
with:
  config: .github/protected-paths.yml
```

**Inputs:**
- `config` (default: `.github/protected-paths.yml`) — Path to your protected-paths config file
- `central-ref` (default: `v1`) — Git ref of central-linter to fetch scripts from

**Output:** Creates an artifact `protected-paths-result` containing a sanitized JSON file with:
- `pr_number` — The PR number
- `head_sha` — The PR's head commit SHA
- `matches` — Array of protected paths that were modified

### Comment Stage

```yaml
permissions:
  contents: read
  actions: read        # required to download the detect run's artifact via run-id
  pull-requests: write
jobs:
  comment:
    uses: opendatahub-io/central-linter/.github/workflows/protected-paths-comment.yml@v1
    with:
      run-id: ${{ github.event.workflow_run.id }}
    secrets: inherit
```

> **`actions: read` is required.** The comment stage downloads the detect run's artifact from a
> different run (via `run-id`), which is an Actions API read. If your repo/org sets the default
> `GITHUB_TOKEN` permissions to restricted, omitting this scope makes the download fail and the
> comment is never posted.

**Inputs:**
- `run-id` (required) — The `workflow_run` id containing the sanitized artifact
- `central-ref` (default: `v1`) — Git ref of central-linter to fetch scripts from

**Secrets:**
- `token` (optional) — GitHub token; if not provided, uses inherited `github.token`

**Behavior:**
- Idempotent: if a comment already exists, it updates it instead of creating duplicates
- Stale removal: if no protected paths changed, deletes any existing guard comment
- Non-blocking: comment is informational only

## Important Notes

### Workflow Names

The comment caller's `workflows` array **MUST** match the detect caller's `name` field. By default:

```yaml
# In protected-paths-detect.yml:
name: Protected Paths (detect)

# In protected-paths-comment.yml:
on:
  workflow_run:
    workflows: ["Protected Paths (detect)"]
```

If you customize the detect caller's name, update the comment caller's `workflows` array to match.

### Versioning

Both callers reference `opendatahub-io/central-linter/.github/workflows/..@v1`. Update the `@v1` tag to pin a specific version, or use `@main` for the latest (not recommended for production).

### Config File Location

The detect stage reads your protected-paths config from the **base repo** (not the PR head). This ensures that PRs cannot hide themselves by modifying the config.

## Troubleshooting

### Comment not appearing

1. Check that the detect stage completed successfully in the PR's "Checks" tab
2. Verify that your protected-paths config exists at the path specified in the detect caller
3. Confirm that at least one file in your PR matches a pattern in the config
4. Check the comment stage's logs for errors

### Workflow is skipped

The comment stage will be skipped if:
- The detect stage failed
- The detect stage did not produce an artifact
- The `workflow_run` event was not triggered by a `pull_request`

### Token issues

If you see "authentication failed" errors:
- Ensure `secrets: inherit` is present in the comment caller
- Verify that the repo's GitHub Actions settings allow workflows to write to pull requests

### Comment step fails on artifact download / comment not posted despite a match

Ensure the comment caller grants `actions: read` in its `permissions:` block. The download of the
detect run's artifact (via `run-id`) needs it. Repos with permissive default token permissions may
work without it, but restricted-default repos will deny the download.

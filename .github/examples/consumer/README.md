# Protected Paths Guard - Consumer Integration

This directory contains example workflows for integrating central-linter's protected-paths guard into consumer repositories.

## Overview

The protected-paths guard is a deterministic (no-AI) supply-chain visibility layer that posts an informational comment when a PR touches sensitive configuration files. It does NOT enforce approval by itself — CODEOWNERS + branch protection remain the actual approval gate.

## Fork Safety

The guard uses a two-stage workflow pattern for fork safety:

1. **Detect stage** (`protected-paths-detect.yml`): Runs unprivileged on `pull_request`. It reads the base repo's config and changed file paths via the GitHub API, then produces a limited JSON result artifact.
2. **Comment stage** (`protected-paths-comment.yml`): Runs privileged on
   `workflow_run`. It validates the artifact's PR/run identity, then recomputes
   matches from the trusted base-commit config before posting an informational
   comment.

The privileged stage treats the artifact as untrusted input: it verifies the
originating workflow path, run ID, PR number, head SHA, and base SHA when
available, then reruns the detector from the trusted central-linter ref. If
GitHub omits associated PR metadata for a fork run, it resolves the PR using the
run's head repository, branch, and SHA. It never uses artifact-provided matches
to construct a comment, and never executes PR-provided code.

Central-linter's self-guard uses `pull_request_target` so GitHub loads the
caller workflow from the trusted base branch. Its detector still only reads the
base config and changed-path API; it does not check out or execute PR code.

## Installation

### 1. Add the two caller workflows

Add these two small files to your consumer repo (contents shown in this directory).
They are the **entire** per-repo footprint — no scripts, no logic to maintain:

- `.github/workflows/protected-paths-detect.yml`  (calls the reusable detect workflow on `pull_request`)
- `.github/workflows/protected-paths-comment.yml` (calls the reusable comment workflow on `workflow_run`)

All detection/comment logic lives in `opendatahub-io/central-linter`. Pin both
reusable workflow calls and the `central-ref` script checkout to the same
reviewed full commit SHA.
The examples are pinned to the reviewed implementation commit; update both
references together when selecting a newer version.

### 2. Create your protected-paths config (REQUIRED)

The guard reads its protected-path list from a config file **in your repo** at
the path given by the `config` input (default `.github/protected-paths.yml`).
There is no implicit default list applied to consumer repos. The config is
required: if it is absent, detection emits no matches and the privileged stage
fails closed without modifying an existing comment. Create the file:

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
- Set `central-ref` to the same reviewed full commit SHA used by `uses`
- Change the `config` path if your protected-paths config is elsewhere

### 4. Optional: verify with a test PR

Create a PR that modifies a protected path (e.g., edit `.github/workflows/some-workflow.yml`). The detect stage should run and the comment stage should post a guard comment on the PR.

## How it Works

### Detect Stage

```yaml
uses: opendatahub-io/central-linter/.github/workflows/protected-paths-detect.yml@eb29144f0e8de39a5c1062710f9aba0c80ea0e7c
with:
  config: .github/protected-paths.yml
  central-ref: eb29144f0e8de39a5c1062710f9aba0c80ea0e7c
```

**Inputs:**
- `config` (default: `.github/protected-paths.yml`) — Path to your protected-paths config file
- `central-ref` (required) — Full commit SHA of central-linter to fetch scripts from

**Output:** Creates an artifact `protected-paths-result` containing a sanitized JSON file with:
- `pr_number` — The PR number
- `head_sha` — The PR's head commit SHA
- `matches` — Array of protected paths that were modified

### Comment Stage

```yaml
jobs:
  comment:
    if: ${{ github.event.workflow_run.event == 'pull_request' && github.event.workflow_run.conclusion == 'success' }}
    uses: opendatahub-io/central-linter/.github/workflows/protected-paths-comment.yml@eb29144f0e8de39a5c1062710f9aba0c80ea0e7c
    permissions:
      contents: read
      actions: read        # required to download the detect run's artifact via run-id
      pull-requests: write
    with:
      run-id: ${{ github.event.workflow_run.id }}
      config: .github/protected-paths.yml
      detect-workflow-path: .github/workflows/protected-paths-detect.yml
      central-ref: eb29144f0e8de39a5c1062710f9aba0c80ea0e7c
```

> **`actions: read` is required.** The comment stage downloads the detect run's artifact from a
> different run (via `run-id`), which is an Actions API read. If your repo/org sets the default
> `GITHUB_TOKEN` permissions to restricted, omitting this scope makes the download fail and the
> comment is never posted.

**Inputs:**
- `run-id` (required) — The `workflow_run` id containing the sanitized artifact
- `config` (default: `.github/protected-paths.yml`) — Config path, read from the
  PR's base commit
- `detect-workflow-path` (required) — Exact path of the detect caller workflow;
  used to validate artifact provenance
- `central-ref` (required) — Full commit SHA of central-linter to fetch scripts from

**Secrets:**
- `token` (optional) — GitHub token; if not provided, uses `github.token`

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

Use the same reviewed full commit SHA for each reusable workflow reference and
its `central-ref` input. Do not use mutable tags or branch names for privileged
workflow execution or script checkout.

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
- Ensure the comment job grants `actions: read` and `pull-requests: write`
- Verify that the repo's GitHub Actions settings allow workflows to write to pull requests

### Comment step fails on artifact download / comment not posted despite a match

Ensure the comment caller grants `actions: read` in its `permissions:` block. The download of the
detect run's artifact (via `run-id`) needs it. Repos with permissive default token permissions may
work without it, but restricted-default repos will deny the download.

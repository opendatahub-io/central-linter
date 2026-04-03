---
name: central-linter-release
description: Release a new version of central-linter. Handles the full two-phase workflow: opening a version bump MR, then publishing the GitLab Release after merge so Renovate updates client repos.
user-invocable: true
tools: [Bash, Read, AskUserQuestion]
---

# Central-Linter Release

## Overview

Releases central-linter in two phases:

- **Phase 1 (`./release.sh <version>`)** — bumps the image reference in `templates/linter-central.yml`, opens an MR titled `INTERNAL: Release vX.Y.Z`, and exits.
- **Phase 2 (`./release.sh --publish <version>`)** — after the MR is merged, pulls main, creates the GitLab Release (tag + release notes), which triggers CI to build and push the versioned image and causes Renovate to open update MRs on client repos.

Run from the root of the central-linter repository.

## Workflow

### Step 1 — Determine version

If a version was passed as a skill argument (e.g. `/central-linter-release v0.2.0`), use it directly.

Otherwise, check the latest tags and ask:

```bash
git tag --sort=-version:refname | head -5
```

Ask the user: "What version do you want to release? (latest tags shown above)"

Validate it matches `vX.Y.Z` or `vX.Y`.

### Step 2 — Run Phase 1 (open MR)

From the repo root, run:

```bash
./release.sh <version>
```

This will:
1. Check clean working tree and correct branch
2. Create branch `release/<version>`
3. Bump image reference in `templates/linter-central.yml`
4. Commit and push the branch
5. Open MR titled `INTERNAL: Release <version>`

Capture the MR URL from the output and show it to the user.

### Step 3 — Wait for MR merge

Tell the user:

> "MR is open. Please review and merge it, then come back and I'll publish the release."
> MR URL: `<url>`

Ask: "Has the MR been merged? (yes/no)"

Do not proceed until the user confirms.

### Step 4 — Run Phase 2 (publish)

After user confirms merge, run:

```bash
git checkout main && ./release.sh --publish <version>
```

This will:
1. Pull latest main
2. Verify the version bump is in main
3. Generate release notes from commits since the last tag (no-merge commits)
4. Run `glab release create <version>` — creates the git tag and GitLab Release in one shot

### Step 5 — Confirm and summarise

Show the user:
- The GitLab Release URL (parse from `glab release create` output or construct as `https://gitlab.com/redhat/rhel-ai/ci-cd/central-linter/-/releases/<version>`)
- What happens next: CI builds `quay.io/aipcc-cicd/central-linter:<version>`, then Renovate opens update MRs on client repos

## Error Handling

- **Uncommitted changes**: tell user to commit or stash first
- **Not on main**: tell user to `git checkout main`
- **Tag already exists**: check if Phase 1 was already done and skip straight to Phase 2
- **Version not in template after merge**: MR may not have been merged yet — ask user to check
- **`glab` not authenticated**: tell user to run `glab auth login`

## Notes

- Release notes are generated automatically from `git log <last-tag>..HEAD --no-merges`
- The MR title must start with `INTERNAL:` — this is enforced by the script
- The GitLab Release (not just a git tag) is required for Renovate's `gitlab-releases` datasource to detect the new version
- Do not push tags manually — `glab release create --ref main` handles both tag and release creation atomically

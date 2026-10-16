#!/usr/bin/env bash
#
# protected-paths-comment.sh
#
# Runs in the PRIVILEGED workflow_run context (base repo, has write token).
# Uses the untrusted JSON artifact only to identify its PR and head commit,
# validates those against the workflow_run and live PR, and recomputes matches
# from the trusted base config. It never executes PR-provided code.
#
# Posts (or updates) a single idempotent PR comment listing the protected
# paths a pull request touches. It does NOT set a failing status -- CODEOWNERS
# + branch protection remain the enforcement gate. This is a visibility layer.
#
# Required env:
#   GH_TOKEN      - token with pull-requests: write (base repo)
#   REPO          - owner/name
#   RESULT_FILE   - path to the sanitized JSON artifact
#   EVENT_FILE    - workflow_run event payload
#   RUN_ID        - workflow_run id for the artifact
#   EXPECTED_DETECT_WORKFLOW_PATH - trusted path of the detect caller workflow
#   CONFIG_FILE   - config checked out from the PR's base SHA
#   CENTRAL_LINTER_PATH - checkout containing the trusted detector script

set -euo pipefail

: "${GH_TOKEN:?}"
: "${REPO:?}"
: "${RESULT_FILE:?}"
: "${EVENT_FILE:?}"
: "${RUN_ID:?}"
: "${EXPECTED_DETECT_WORKFLOW_PATH:?}"
: "${CONFIG_FILE:?}"
: "${CENTRAL_LINTER_PATH:?}"

MARKER="<!-- protected-paths-guard -->"

if [[ ! -f "$RESULT_FILE" ]]; then
  echo "No result artifact found at $RESULT_FILE; nothing to do."
  exit 0
fi

if ! jq -e '(.pr_number | type == "number" and . > 0 and floor == .) and (.head_sha | type == "string" and test("^[0-9a-f]{40,64}$")) and (.matches | type == "array")' "$RESULT_FILE" >/dev/null; then
  echo "Artifact has an invalid result format; aborting."
  exit 1
fi

PR_NUMBER=$(jq -r '.pr_number' "$RESULT_FILE")
ARTIFACT_HEAD_SHA=$(jq -r '.head_sha' "$RESULT_FILE")

# Verify this is the expected successful pull_request run and that the artifact
# identifies the same PR and commit as the event that requested the comment.
RUN_EVENT=$(jq -r '.workflow_run.event // empty' "$EVENT_FILE")
RUN_CONCLUSION=$(jq -r '.workflow_run.conclusion // empty' "$EVENT_FILE")
EVENT_RUN_ID=$(jq -r '.workflow_run.id // empty' "$EVENT_FILE")
RUN_PATH=$(jq -r '.workflow_run.path // empty' "$EVENT_FILE")
RUN_HEAD_SHA=$(jq -r '.workflow_run.head_sha // empty' "$EVENT_FILE")
RUN_REPOSITORY=$(jq -r '.workflow_run.repository.full_name // empty' "$EVENT_FILE")
EVENT_PR_NUMBER=$(jq -r '.workflow_run.pull_requests[0].number // empty' "$EVENT_FILE")
RUN_BASE_SHA=$(jq -r '.workflow_run.pull_requests[0].base.sha // empty' "$EVENT_FILE")
RUN_HEAD_REPOSITORY=$(jq -r '.workflow_run.head_repository.full_name // empty' "$EVENT_FILE")

if [[ "$RUN_EVENT" != "pull_request" || "$RUN_CONCLUSION" != "success" || \
      "$EVENT_RUN_ID" != "$RUN_ID" || "$RUN_PATH" != "$EXPECTED_DETECT_WORKFLOW_PATH" || \
      "$RUN_REPOSITORY" != "$REPO" || "$EVENT_PR_NUMBER" != "$PR_NUMBER" || \
      "$RUN_HEAD_SHA" != "$ARTIFACT_HEAD_SHA" ]]; then
  echo "Artifact provenance does not match the expected workflow run and PR; aborting."
  exit 1
fi

# Recheck the live PR to reject stale runs and ensure it still targets this repo.
PR_JSON=$(gh api "repos/${REPO}/pulls/${PR_NUMBER}")
PR_STATE=$(jq -r '.state' <<<"$PR_JSON")
PR_HEAD_SHA=$(jq -r '.head.sha' <<<"$PR_JSON")
PR_HEAD_REPOSITORY=$(jq -r '.head.repo.full_name // empty' <<<"$PR_JSON")
PR_BASE_SHA=$(jq -r '.base.sha' <<<"$PR_JSON")
PR_BASE_REPOSITORY=$(jq -r '.base.repo.full_name' <<<"$PR_JSON")

if [[ "$PR_STATE" != "open" || "$PR_HEAD_SHA" != "$RUN_HEAD_SHA" || \
      "$PR_BASE_SHA" != "$RUN_BASE_SHA" || "$PR_HEAD_REPOSITORY" != "$RUN_HEAD_REPOSITORY" || \
      "$PR_BASE_REPOSITORY" != "$REPO" ]]; then
  echo "The originating PR is closed, stale, or targets a different repository; skipping."
  exit 0
fi

# Never trust the artifact's matched paths. Re-run the detector from the trusted
# central-linter checkout against the trusted base-commit config and GitHub API.
VERIFIED_RESULT=$(mktemp)
trap 'rm -f "${VERIFIED_RESULT:-}" "${BODY_FILE:-}"' EXIT
GH_TOKEN="$GH_TOKEN" \
REPO="$REPO" \
PR_NUMBER="$PR_NUMBER" \
HEAD_SHA="$RUN_HEAD_SHA" \
CONFIG_FILE="$CONFIG_FILE" \
OUTPUT_FILE="$VERIFIED_RESULT" \
  "${CENTRAL_LINTER_PATH}/.github/scripts/protected-paths-detect.sh"
RESULT_FILE="$VERIFIED_RESULT"
MATCH_COUNT=$(jq -r '.matches | length' "$RESULT_FILE")

# Locate any existing guard comment (idempotent upsert across re-runs).
EXISTING_ID=$(
  gh api "repos/${REPO}/issues/${PR_NUMBER}/comments" --paginate \
    --jq "map(select(.body | contains(\"${MARKER}\"))) | .[0].id // empty"
)

if [[ "$MATCH_COUNT" -eq 0 ]]; then
  # No protected paths touched. Remove a stale comment if one exists so the
  # PR doesn't keep a false warning after the offending files are reverted.
  if [[ -n "$EXISTING_ID" ]]; then
    echo "No protected paths changed; deleting stale guard comment ${EXISTING_ID}."
    gh api -X DELETE "repos/${REPO}/issues/comments/${EXISTING_ID}"
  else
    echo "No protected paths changed; no comment needed."
  fi
  exit 0
fi

# Build the comment body from the recomputed trusted matches.
BODY_FILE=$(mktemp)
{
  echo "$MARKER"
  echo ""
  echo "### :shield: Protected paths modified"
  echo ""
  echo "This PR changes files that are protected because they affect CI/CD, security, or supply-chain configuration. **Reviewers: please confirm these changes are intended before approving.**"
  echo ""
  echo "| Protected file |"
  echo "|----------------|"
  jq -r '.matches[] | "| `" + . + "` |"' "$RESULT_FILE"
  echo ""
  echo "> Approval is enforced by \`CODEOWNERS\`. This comment is an informational safeguard so a sensitive change is never approved unnoticed."
} > "$BODY_FILE"

if [[ -n "$EXISTING_ID" ]]; then
  echo "Updating existing guard comment ${EXISTING_ID}."
  gh api -X PATCH "repos/${REPO}/issues/comments/${EXISTING_ID}" \
    -F body=@"$BODY_FILE" >/dev/null
else
  echo "Creating new guard comment on PR ${PR_NUMBER}."
  gh api -X POST "repos/${REPO}/issues/${PR_NUMBER}/comments" \
    -F body=@"$BODY_FILE" >/dev/null
fi

echo "Done."

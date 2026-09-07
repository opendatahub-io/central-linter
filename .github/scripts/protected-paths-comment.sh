#!/usr/bin/env bash
#
# protected-paths-comment.sh
#
# Runs in the PRIVILEGED workflow_run context (base repo, has write token).
# Consumes ONLY the sanitized JSON artifact produced by the unprivileged
# detect job. It never checks out or executes any PR-provided code.
#
# Posts (or updates) a single idempotent PR comment listing the protected
# paths a pull request touches. It does NOT set a failing status -- CODEOWNERS
# + branch protection remain the enforcement gate. This is a visibility layer.
#
# Required env:
#   GH_TOKEN      - token with pull-requests: write (base repo)
#   REPO          - owner/name
#   RESULT_FILE   - path to the sanitized JSON artifact

set -euo pipefail

: "${GH_TOKEN:?}"
: "${REPO:?}"
: "${RESULT_FILE:?}"

MARKER="<!-- protected-paths-guard -->"

if [[ ! -f "$RESULT_FILE" ]]; then
  echo "No result artifact found at $RESULT_FILE; nothing to do."
  exit 0
fi

PR_NUMBER=$(jq -r '.pr_number' "$RESULT_FILE")
MATCH_COUNT=$(jq -r '.matches | length' "$RESULT_FILE")

if [[ -z "$PR_NUMBER" || "$PR_NUMBER" == "null" ]]; then
  echo "Artifact missing pr_number; aborting."
  exit 0
fi

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

# Build the comment body from sanitized matches.
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

rm -f "$BODY_FILE"
echo "Done."

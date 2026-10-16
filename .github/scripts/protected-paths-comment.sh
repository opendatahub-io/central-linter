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
#   RESULT_FILE   - path to the untrusted detector JSON artifact
#   EVENT_FILE    - workflow_run event payload
#   RUN_ID        - workflow_run id for the artifact
#   EXPECTED_DETECT_WORKFLOW_PATH - trusted path of the detect caller workflow
#   CONFIG_PATH   - path to the config file in the consumer repository
#   CONFIG_FILE   - temporary path where the trusted base config is written
#   RUNNER_TEMP   - directory for temporary files
#   CENTRAL_LINTER_PATH - checkout containing the trusted detector script

set -euo pipefail

: "${GH_TOKEN:?}"
: "${REPO:?}"
: "${RESULT_FILE:?}"
: "${EVENT_FILE:?}"
: "${RUN_ID:?}"
: "${EXPECTED_DETECT_WORKFLOW_PATH:?}"
: "${CONFIG_PATH:?}"
: "${CONFIG_FILE:?}"
: "${RUNNER_TEMP:?}"
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
EVENT_PR_NUMBERS=$(jq -r '[.workflow_run.pull_requests[]?.number] | unique | .[]' "$EVENT_FILE")
RUN_BASE_SHAS=$(jq -r '[.workflow_run.pull_requests[]?.base.sha] | unique | .[]' "$EVENT_FILE")
RUN_HEAD_REPOSITORY=$(jq -r '.workflow_run.head_repository.full_name // empty' "$EVENT_FILE")
RUN_HEAD_BRANCH=$(jq -r '.workflow_run.head_branch // empty' "$EVENT_FILE")

# workflow_run.path is normally a path; accept a pull_request merge-ref suffix
# when GitHub includes one, but never accept a suffix for another ref or PR.
RUN_WORKFLOW_PATH=${RUN_PATH%%@*}
RUN_WORKFLOW_REF=""
if [[ "$RUN_PATH" == *@* ]]; then
  RUN_WORKFLOW_REF=${RUN_PATH#*@}
fi

if [[ "$RUN_EVENT" != "pull_request" || "$RUN_CONCLUSION" != "success" || \
      "$EVENT_RUN_ID" != "$RUN_ID" || "$RUN_WORKFLOW_PATH" != "$EXPECTED_DETECT_WORKFLOW_PATH" || \
      ( -n "$RUN_WORKFLOW_REF" && "$RUN_WORKFLOW_REF" != "refs/pull/${PR_NUMBER}/merge" ) || \
      "$RUN_REPOSITORY" != "$REPO" || \
      "$RUN_HEAD_SHA" != "$ARTIFACT_HEAD_SHA" ]]; then
  echo "Artifact provenance does not match the expected workflow run and PR; aborting."
  exit 1
fi

if [[ -n "$EVENT_PR_NUMBERS" && "$EVENT_PR_NUMBERS" != "$PR_NUMBER" ]]; then
  echo "Artifact PR number does not match the workflow_run pull request; aborting."
  exit 1
fi
if [[ -n "$RUN_BASE_SHAS" && $(printf '%s\n' "$RUN_BASE_SHAS" | wc -l | tr -d ' ') != 1 ]]; then
  echo "workflow_run contains ambiguous pull request base commits; aborting."
  exit 1
fi
RUN_BASE_SHA=${RUN_BASE_SHAS:-}

# Recheck the live PR to reject stale runs and ensure it still targets this repo.
PR_JSON=$(gh api "repos/${REPO}/pulls/${PR_NUMBER}")
PR_STATE=$(jq -r '.state' <<<"$PR_JSON")
PR_HEAD_SHA=$(jq -r '.head.sha' <<<"$PR_JSON")
PR_HEAD_REPOSITORY=$(jq -r '.head.repo.full_name // empty' <<<"$PR_JSON")
PR_HEAD_BRANCH=$(jq -r '.head.ref' <<<"$PR_JSON")
PR_BASE_SHA=$(jq -r '.base.sha' <<<"$PR_JSON")
PR_BASE_REPOSITORY=$(jq -r '.base.repo.full_name' <<<"$PR_JSON")

if [[ "$PR_STATE" != "open" || "$PR_HEAD_SHA" != "$RUN_HEAD_SHA" || \
      ( -n "$RUN_BASE_SHA" && "$PR_BASE_SHA" != "$RUN_BASE_SHA" ) || \
      ( -n "$RUN_HEAD_REPOSITORY" && "$PR_HEAD_REPOSITORY" != "$RUN_HEAD_REPOSITORY" ) || \
      ( -n "$RUN_HEAD_BRANCH" && "$PR_HEAD_BRANCH" != "$RUN_HEAD_BRANCH" ) || \
      "$PR_BASE_REPOSITORY" != "$REPO" ]]; then
  echo "The originating PR is closed, stale, or targets a different repository; skipping."
  exit 0
fi

# When GitHub omits pull_requests from workflow_run (seen for some fork runs),
# confirm this artifact's PR is associated with the run's head commit.
if [[ -z "$EVENT_PR_NUMBERS" ]]; then
  if [[ -z "$RUN_HEAD_REPOSITORY" || -z "$RUN_HEAD_BRANCH" ]]; then
    echo "Fork workflow_run omitted PR metadata and head repository details; aborting."
    exit 1
  fi
  CANDIDATE_PRS=$(gh api --method GET "repos/${REPO}/pulls" \
    -f state=all -f head="${RUN_HEAD_REPOSITORY}:${RUN_HEAD_BRANCH}")
  ASSOCIATED_PR_COUNT=$(jq --arg sha "$RUN_HEAD_SHA" --arg repo "$REPO" \
    --arg head_repo "$RUN_HEAD_REPOSITORY" \
    '[.[] | select(.head.sha == $sha and .head.repo.full_name == $head_repo and .base.repo.full_name == $repo)] | length' \
    <<<"$CANDIDATE_PRS")
  ASSOCIATED_PR_NUMBER=$(jq -r --arg sha "$RUN_HEAD_SHA" --arg repo "$REPO" \
    --arg head_repo "$RUN_HEAD_REPOSITORY" \
    '[.[] | select(.head.sha == $sha and .head.repo.full_name == $head_repo and .base.repo.full_name == $repo)][0].number // empty' \
    <<<"$CANDIDATE_PRS")
  if [[ "$ASSOCIATED_PR_COUNT" != "1" || "$ASSOCIATED_PR_NUMBER" != "$PR_NUMBER" ]]; then
    echo "Artifact PR is not uniquely associated with the originating workflow run; aborting."
    exit 1
  fi
fi

# Fetch the configuration at the live base SHA (the caller never checks out an
# event-provided PR array, which may be empty for fork runs).
CONFIG_JSON=$(gh api "repos/${REPO}/contents/${CONFIG_PATH}?ref=${PR_BASE_SHA}")
if [[ $(jq -r '.encoding // empty' <<<"$CONFIG_JSON") != "base64" ]]; then
  echo "Protected-path config response was not base64 encoded; aborting."
  exit 1
fi
printf '%s' "$(jq -r '.content' <<<"$CONFIG_JSON" | tr -d '\n')" | base64 --decode > "$CONFIG_FILE"

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
EXISTING_IDS=$(gh api "repos/${REPO}/issues/${PR_NUMBER}/comments" --paginate \
  --jq '.[] | select(.user.login == "github-actions[bot]" and (.body | contains("<!-- protected-paths-guard -->"))) | .id')
EXISTING_ID=${EXISTING_IDS%%$'\n'*}

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
  jq -r '
    def table_escape:
      gsub("&"; "&amp;")
      | gsub("<"; "&lt;")
      | gsub(">"; "&gt;")
      | gsub("\\|"; "&#124;")
      | gsub("`"; "&#96;")
      | gsub("\r"; "&#13;")
      | gsub("\n"; "&#10;");
    .matches[] | "| <code>" + table_escape + "</code> |"
  ' "$RESULT_FILE"
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

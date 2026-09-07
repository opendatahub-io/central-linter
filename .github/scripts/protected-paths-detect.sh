#!/usr/bin/env bash
#
# protected-paths-detect.sh
#
# Deterministic (no AI) detection of protected-path changes in a pull request.
# Runs in the UNPRIVILEGED pull_request context: it must NOT rely on secrets,
# must NOT check out or execute PR-provided code, and only reads the list of
# changed file paths via the GitHub API.
#
# Output: writes a sanitized JSON artifact to $OUTPUT_FILE containing only the
# PR number, head SHA, and the list of matched protected paths. The privileged
# workflow_run job consumes ONLY this sanitized data.
#
# Required env:
#   GH_TOKEN     - read-only token (github.token on pull_request is sufficient)
#   REPO         - owner/name
#   PR_NUMBER    - pull request number
#   HEAD_SHA     - pull request head sha
#   CONFIG_FILE  - path to protected-paths.yml (checked out from BASE repo)
#   OUTPUT_FILE  - where to write the sanitized JSON result

set -euo pipefail

: "${GH_TOKEN:?}"
: "${REPO:?}"
: "${PR_NUMBER:?}"
: "${HEAD_SHA:?}"
: "${CONFIG_FILE:?}"
: "${OUTPUT_FILE:?}"

# --- Load protected patterns from the BASE-repo config (trusted) ------------
# We read the config that was checked out from the base repo, NOT from the PR,
# so a fork cannot alter which paths are considered protected.
if [[ ! -f "$CONFIG_FILE" ]]; then
  echo "No config file at $CONFIG_FILE; nothing to protect."
  printf '{"pr_number":%s,"head_sha":"%s","matches":[]}\n' "$PR_NUMBER" "$HEAD_SHA" > "$OUTPUT_FILE"
  exit 0
fi

# Minimal YAML list extraction (patterns under `paths:`). Deterministic, no deps
# beyond coreutils. Lines like:  - ".claude/"
mapfile -t PATTERNS < <(
  sed -n 's/^[[:space:]]*-[[:space:]]*["'\'']\{0,1\}\([^"'\'']*\)["'\'']\{0,1\}[[:space:]]*$/\1/p' "$CONFIG_FILE"
)

if [[ ${#PATTERNS[@]} -eq 0 ]]; then
  echo "Config contains no patterns; skipping."
  printf '{"pr_number":%s,"head_sha":"%s","matches":[]}\n' "$PR_NUMBER" "$HEAD_SHA" > "$OUTPUT_FILE"
  exit 0
fi

echo "Loaded ${#PATTERNS[@]} protected pattern(s)."

# --- Fetch changed files via API (no checkout of PR code) --------------------
# --paginate handles PRs with >30 files. previous_filename catches renames OUT
# of a protected path.
mapfile -t CHANGED < <(
  gh api "repos/${REPO}/pulls/${PR_NUMBER}/files" \
    --paginate --jq '.[] | .filename, (.previous_filename // empty)'
)

echo "PR changes ${#CHANGED[@]} file path entry(ies)."

# --- Match ------------------------------------------------------------------
declare -a MATCHED=()
for pat in "${PATTERNS[@]}"; do
  [[ -z "$pat" ]] && continue
  for f in "${CHANGED[@]}"; do
    [[ -z "$f" ]] && continue
    if [[ "$pat" == */ ]]; then
      # Directory prefix match
      if [[ "$f" == "$pat"* ]]; then
        MATCHED+=("$f")
      fi
    else
      # Exact or shell-glob match (glob does not cross '/')
      # shellcheck disable=SC2053
      if [[ "$f" == "$pat" || "$f" == $pat ]]; then
        MATCHED+=("$f")
      fi
    fi
  done
done

# De-duplicate
if [[ ${#MATCHED[@]} -gt 0 ]]; then
  mapfile -t MATCHED < <(printf '%s\n' "${MATCHED[@]}" | sort -u)
fi

echo "Matched ${#MATCHED[@]} protected file(s)."

# --- Emit sanitized JSON ----------------------------------------------------
# Only PR number, head sha, and matched paths cross the trust boundary.
if [[ ${#MATCHED[@]} -eq 0 ]]; then
  matches_json="[]"
else
  matches_json=$(printf '%s\n' "${MATCHED[@]}" | jq -R . | jq -s .)
fi

jq -n \
  --argjson pr "$PR_NUMBER" \
  --arg sha "$HEAD_SHA" \
  --argjson matches "$matches_json" \
  '{pr_number: $pr, head_sha: $sha, matches: $matches}' > "$OUTPUT_FILE"

echo "Wrote sanitized result to $OUTPUT_FILE:"
cat "$OUTPUT_FILE"

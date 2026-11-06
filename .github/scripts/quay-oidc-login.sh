#!/usr/bin/env bash
# Reference: https://github.com/ktdreyer/quay-oidc-demo/blob/main/quay-oidc.md
set -euo pipefail

: "${QUAY_ROBOT_USER:?QUAY_ROBOT_USER is required}"
: "${ACTIONS_ID_TOKEN_REQUEST_TOKEN:?Must run inside GitHub Actions with id-token: write}"
: "${ACTIONS_ID_TOKEN_REQUEST_URL:?Must run inside GitHub Actions with id-token: write}"

OIDC_TOKEN=$(curl -sSf \
  -H "Authorization: bearer ${ACTIONS_ID_TOKEN_REQUEST_TOKEN}" \
  "${ACTIONS_ID_TOKEN_REQUEST_URL}" | jq -r .value)
echo "::add-mask::${OIDC_TOKEN}"

QUAY_RESPONSE=$(curl -sS \
  "https://quay.io/oauth2/federation/robot/token" \
  -u "${QUAY_ROBOT_USER}:${OIDC_TOKEN}")
QUAY_TOKEN=$(echo "${QUAY_RESPONSE}" | jq -r '.token // empty' 2>/dev/null || true)
if [[ -z "${QUAY_TOKEN}" ]]; then
  echo "ERROR: Quay federation token exchange failed. Response:"
  echo "${QUAY_RESPONSE}" | sed 's/"token": *"[^"]*"/"token": "***"/'
  exit 1
fi
echo "::add-mask::${QUAY_TOKEN}"

buildah login -u "${QUAY_ROBOT_USER}" --password-stdin quay.io <<< "${QUAY_TOKEN}"

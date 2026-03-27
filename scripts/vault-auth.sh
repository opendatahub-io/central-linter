#!/usr/bin/env bash
#
# Authenticates with HashiCorp Vault using AppRole and prints the token to stdout.
#
# Required env vars: VAULT_ADDR, VAULT_ROLE_ID, VAULT_SECRET_ID
# Usage: export VAULT_TOKEN=$(scripts/vault-auth.sh)
#
set -euo pipefail

# renovate: datasource=github-releases depName=hashicorp/vault extractVersion=^v(?<version>.+)$
VAULT_VERSION=1.17.1
VAULT_URL="https://releases.hashicorp.com/vault/${VAULT_VERSION}/vault_${VAULT_VERSION}_linux_amd64.zip"

is_available() { command -v "$1" &> /dev/null; }

for var in VAULT_ADDR VAULT_ROLE_ID VAULT_SECRET_ID; do
  if [[ -z "${!var:-}" ]]; then
    echo "ERROR: ${var} is not set" >&2
    exit 1
  fi
done

if ! is_available vault; then
  if ! is_available unzip; then
    dnf install -y unzip >&2
  fi
  INSTALL_DIR="${HOME}/.local/bin"
  mkdir -p "${INSTALL_DIR}"
  curl -fsSL "${VAULT_URL}" -o /tmp/vault.zip
  unzip -o /tmp/vault.zip -d "${INSTALL_DIR}/" >&2 && rm /tmp/vault.zip
fi

VAULT_SKIP_VERIFY=1 vault write -field=token auth/approle/login \
  role_id="$VAULT_ROLE_ID" secret_id="$VAULT_SECRET_ID"

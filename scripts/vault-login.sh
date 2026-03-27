#!/usr/bin/env bash
#
# Authenticates with HashiCorp Vault using AppRole and prints the token to stdout.
#
# Required env vars: VAULT_ADDR, VAULT_ROLE_ID, VAULT_SECRET_ID
# Usage: export VAULT_TOKEN=$(scripts/vault-login.sh /path/to/vault)
#
set -euo pipefail

VAULT_BIN="${1:?Usage: $0 /path/to/vault}"

for var in VAULT_ADDR VAULT_ROLE_ID VAULT_SECRET_ID; do
  if [[ -z "${!var:-}" ]]; then
    echo "ERROR: ${var} is not set" >&2
    exit 1
  fi
done

VAULT_SKIP_VERIFY=1 "${VAULT_BIN}" write -field=token auth/approle/login \
  role_id="$VAULT_ROLE_ID" secret_id="$VAULT_SECRET_ID"
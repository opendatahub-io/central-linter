#!/usr/bin/env bash
#
# Installs the HashiCorp Vault CLI if not already available.
# Prints the full path to the vault binary on stdout.
#
# Usage: VAULT_BIN=$(scripts/vault-install.sh)
#
set -euo pipefail

# renovate: datasource=github-releases depName=hashicorp/vault extractVersion=^v(?<version>.+)$
VAULT_VERSION=1.17.1
VAULT_URL="https://releases.hashicorp.com/vault/${VAULT_VERSION}/vault_${VAULT_VERSION}_linux_amd64.zip"

VAULT_BIN="$(command -v vault 2>/dev/null || true)"
if [[ -n "${VAULT_BIN}" ]]; then
  echo "${VAULT_BIN}"
  exit 0
fi

if ! command -v unzip &> /dev/null; then
  dnf install -y unzip >&2
fi

INSTALL_DIR="$(mktemp -d)"
curl -fsSL "${VAULT_URL}" -o /tmp/vault.zip
unzip -o /tmp/vault.zip -d "${INSTALL_DIR}/" >&2 && rm /tmp/vault.zip

echo "${INSTALL_DIR}/vault"
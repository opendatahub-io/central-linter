#!/usr/bin/env bash
set -euo pipefail

: "${WORKSPACE:?WORKSPACE is required}"

podman run --rm \
  -v "${WORKSPACE}:/workspace:Z" \
  central-linter:local \
  bash -c "
    ruff --version
    yamllint --version
    renovate-config-validator
    shellcheck --version
    markdownlint --version
    pytest tests/ -v
  "

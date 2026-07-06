#!/usr/bin/env bash
set -euo pipefail

: "${IMAGE_NAME:?IMAGE_NAME is required}"
: "${GITHUB_SHA:?GITHUB_SHA is required}"
: "${GITHUB_REF:?GITHUB_REF is required}"
: "${GITHUB_REF_NAME:?GITHUB_REF_NAME is required}"

push_tag() {
  local tag=$1
  buildah tag central-linter:local "${IMAGE_NAME}:${tag}"
  buildah push "${IMAGE_NAME}:${tag}"
}

push_tag "${GITHUB_SHA}"

if [[ "${GITHUB_REF}" == refs/tags/* ]]; then
  push_tag "${GITHUB_REF_NAME}"
fi

if [[ "${GITHUB_REF}" == "refs/heads/main" ]]; then
  push_tag latest
fi

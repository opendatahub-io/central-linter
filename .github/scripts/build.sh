#!/usr/bin/env bash
set -euo pipefail

: "${IMAGE_TAG:?IMAGE_TAG is required}"
: "${CONTAINERFILE_PATH:?CONTAINERFILE_PATH is required}"
: "${CONTEXT_DIR:?CONTEXT_DIR is required}"

LOCAL_IMAGE="localhost/central-linter:${IMAGE_TAG}"

buildah bud --format docker \
  --tag "${LOCAL_IMAGE}" \
  --file "${CONTAINERFILE_PATH}" \
  "${CONTEXT_DIR}"

buildah push "${LOCAL_IMAGE}" \
  "oci-archive:/tmp/central-linter.tar"

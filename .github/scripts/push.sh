#!/usr/bin/env bash
set -euo pipefail

: "${IMAGE_NAME:?IMAGE_NAME is required}"
: "${IMAGE_TAG:?IMAGE_TAG is required}"
: "${GITHUB_REF:?GITHUB_REF is required}"
: "${GITHUB_REF_NAME:?GITHUB_REF_NAME is required}"

push_tag() {
  local tag=$1
  buildah tag central-linter:local "${IMAGE_NAME}:${tag}"
  buildah push "${IMAGE_NAME}:${tag}"
}

push_tag "${IMAGE_TAG::8}"

# Release version tags are pushed from a workflow_dispatch run on main (see
# the push job in ci.yml): the Quay OIDC federation only accepts subjects
# with ref refs/heads/main, so tag-triggered runs cannot log in.
if [[ -n "${DISPATCH_VERSION:-}" ]]; then
  if [[ ! "${DISPATCH_VERSION}" =~ ^v[0-9]+\.[0-9]+(\.[0-9]+)?$ ]]; then
    echo "ERROR: invalid version tag '${DISPATCH_VERSION}' (expected vX.Y or vX.Y.Z; '/' is not valid in an image tag)."
    exit 1
  fi
  git fetch --no-tags --depth=1 origin "refs/tags/${DISPATCH_VERSION}:refs/tags/${DISPATCH_VERSION}"
  TAG_SHA=$(git rev-parse "${DISPATCH_VERSION}^{commit}")
  if [[ "${TAG_SHA}" != "${GITHUB_SHA}" ]]; then
    echo "ERROR: tag ${DISPATCH_VERSION} points at ${TAG_SHA:0:8}, but this run built ${GITHUB_SHA:0:8} (main has moved past the tagged commit)."
    echo "Re-create the tag on the current main HEAD and dispatch again."
    exit 1
  fi
  push_tag "${DISPATCH_VERSION}"
fi

if [[ "${GITHUB_REF}" == "refs/heads/main" ]]; then
  push_tag latest
fi

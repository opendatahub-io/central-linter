#!/usr/bin/env bash
set -euo pipefail

: "${IMAGE_TAG:?IMAGE_TAG is required}"

buildah pull oci-archive:/tmp/central-linter.tar
buildah tag "localhost/central-linter:${IMAGE_TAG}" central-linter:local

#!/usr/bin/env bash
set -euo pipefail

IMAGE_ID=$(buildah pull oci-archive:/tmp/central-linter.tar)
buildah tag "${IMAGE_ID}" central-linter:local

#!/bin/bash
set -euo pipefail

command -v glab >/dev/null || { echo "Error: glab is not installed"; exit 1; }

PUBLISH=false
if [[ "${1:-}" == "--publish" ]]; then
    PUBLISH=true
    shift
fi

VERSION="${1:?Usage: $0 [--publish] <version> (e.g. v0.2.0)}"

# Validate format
if [[ ! "$VERSION" =~ ^v[0-9]+\.[0-9]+(\.[0-9]+)?$ ]]; then
    echo "Error: Version must match vX.Y or vX.Y.Z format"
    exit 1
fi

# Check for uncommitted changes
if ! git diff --quiet || ! git diff --cached --quiet; then
    echo "Error: Working directory has uncommitted changes. Please commit or stash them first."
    git status --short
    exit 1
fi

if $PUBLISH; then
    # ------------------------------------------------------------------
    # Phase 2: after the MR is merged — tag + GitLab Release
    # ------------------------------------------------------------------
    CURRENT_BRANCH=$(git rev-parse --abbrev-ref HEAD)
    if [[ "$CURRENT_BRANCH" != "main" ]]; then
        echo "Error: Must be on main branch to publish. Run: git checkout main && git pull"
        exit 1
    fi

    git pull --ff-only origin main

    if git rev-parse "$VERSION" >/dev/null 2>&1; then
        echo "Error: Tag $VERSION already exists"
        exit 1
    fi

    # Verify the version bump is already in main
    if ! grep -q "central-linter:${VERSION}" templates/linter-central.yml; then
        echo "Error: templates/linter-central.yml does not reference ${VERSION}."
        echo "Make sure the version bump MR is merged before publishing."
        exit 1
    fi

    # Build release notes from commits since the last tag
    LAST_TAG=$(git describe --tags --abbrev=0 2>/dev/null || echo "")
    if [[ -n "$LAST_TAG" ]]; then
        echo "Generating release notes from ${LAST_TAG}..HEAD..."
        NOTES=$(git log "${LAST_TAG}..HEAD~1" --pretty=format:"- %s" --no-merges)
        if [[ -z "$NOTES" ]]; then
            NOTES="- No changes recorded since ${LAST_TAG}"
        fi
    else
        NOTES="Initial release"
    fi

    echo "Creating GitLab Release ${VERSION}..."
    glab release create "${VERSION}" \
        --name "Release ${VERSION}" \
        --notes "${NOTES}" \
        --ref main

    echo ""
    echo "Done! GitLab Release ${VERSION} created."
    echo "CI is now building quay.io/aipcc-cicd/central-linter:${VERSION}."
    echo "Renovate will open update MRs on client repos once the release is visible."
else
    # ------------------------------------------------------------------
    # Phase 1: bump version, open MR
    # ------------------------------------------------------------------
    CURRENT_BRANCH=$(git rev-parse --abbrev-ref HEAD)
    if [[ "$CURRENT_BRANCH" != "main" ]]; then
        echo "Error: Must be on main branch to start a release."
        exit 1
    fi

    git pull --ff-only origin main

    if git rev-parse "$VERSION" >/dev/null 2>&1; then
        echo "Error: Tag $VERSION already exists"
        exit 1
    fi

    BRANCH="release/${VERSION}"
    git checkout -b "$BRANCH"

    perl -i -pe "s|quay.io/aipcc-cicd/central-linter:v[0-9][0-9.]*|quay.io/aipcc-cicd/central-linter:${VERSION}|g" \
        templates/linter-central.yml
    echo "Updated templates/linter-central.yml"

    git add templates/linter-central.yml
    git commit -s -m "INTERNAL: Release ${VERSION}"
    git push -u origin "$BRANCH"

    SOB="Signed-off-by: $(git config user.name) <$(git config user.email)>"
    glab mr create \
        --title "INTERNAL: Release ${VERSION}" \
        --description "Bumps the central-linter image reference to \`${VERSION}\` in the CI template.

${SOB}" \
        --target-branch main \
        --remove-source-branch \
        --yes

    echo ""
    echo "MR opened. After it is merged, run:"
    echo "  git checkout main && ./release.sh --publish ${VERSION}"
fi

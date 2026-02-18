#!/bin/bash
set -euo pipefail

VERSION="${1:?Usage: $0 <version> (e.g. v0.1.0)}"

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

# Check if tag already exists
if git rev-parse "$VERSION" >/dev/null 2>&1; then
    echo "Error: Tag $VERSION already exists"
    exit 1
fi

# Files containing the image version
FILES=(
    "templates/linter-central.yml"
)

for file in "${FILES[@]}"; do
    if [[ -f "$file" ]]; then
        sed -i "s|quay.io/aipcc-cicd/central-linter:v[0-9][0-9.]*|quay.io/aipcc-cicd/central-linter:${VERSION}|g" "$file"
        echo "Updated $file"
    else
        echo "Warning: $file not found, skipping"
    fi
done

git add "${FILES[@]}"
git commit -s -m "Release ${VERSION}"
git tag "${VERSION}"

echo ""
echo "Release ${VERSION} prepared. Run:"
echo "  git push && git push --tags"

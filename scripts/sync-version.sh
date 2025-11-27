#!/bin/bash
# Sync version from __version__.py to all other files
#
# Usage:
#   ./scripts/sync-version.sh           # Sync current version
#   ./scripts/sync-version.sh 2.6.0     # Set and sync specific version
#
# The master version lives in __version__.py. This script propagates it to:
#   - npm/package.json
#   - public/index.html (cache-busting query params and footer)

set -e

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_ROOT="$(dirname "$SCRIPT_DIR")"
cd "$PROJECT_ROOT"

# If version arg provided, update __version__.py first
if [ -n "$1" ]; then
    VERSION="$1"
    echo "Setting version to $VERSION"

    # Update __version__.py
    if [[ "$OSTYPE" == "darwin"* ]]; then
        # macOS sed requires empty string for -i
        sed -i '' "s/__version__ = \".*\"/__version__ = \"$VERSION\"/" __version__.py
        sed -i '' "s/__release_date__ = \".*\"/__release_date__ = \"$(date +%Y-%m-%d)\"/" __version__.py
    else
        sed -i "s/__version__ = \".*\"/__version__ = \"$VERSION\"/" __version__.py
        sed -i "s/__release_date__ = \".*\"/__release_date__ = \"$(date +%Y-%m-%d)\"/" __version__.py
    fi
else
    # Extract version from __version__.py
    VERSION=$(grep -o '__version__ = "[^"]*"' __version__.py | cut -d'"' -f2)
    echo "Syncing version $VERSION from __version__.py"
fi

# Validate version format
if ! [[ "$VERSION" =~ ^[0-9]+\.[0-9]+\.[0-9]+$ ]]; then
    echo "Error: Invalid version format '$VERSION'. Expected X.Y.Z"
    exit 1
fi

echo "=== Syncing to version $VERSION ==="

# Update npm/package.json
echo "Updating npm/package.json..."
cd npm && npm version "$VERSION" --no-git-tag-version --allow-same-version && cd ..

# Update public/index.html
echo "Updating public/index.html..."
if [[ "$OSTYPE" == "darwin"* ]]; then
    sed -i '' "s/\?v=[0-9.]*/?v=$VERSION/g" public/index.html
    sed -i '' "s/Version [0-9.]*</Version $VERSION</g" public/index.html
else
    sed -i "s/\?v=[0-9.]*/?v=$VERSION/g" public/index.html
    sed -i "s/Version [0-9.]*</Version $VERSION</g" public/index.html
fi

echo ""
echo "=== Version sync complete ==="
echo ""
echo "__version__.py:"
grep '__version__ = ' __version__.py

echo ""
echo "npm/package.json:"
grep '"version"' npm/package.json

echo ""
echo "public/index.html footer:"
grep "Version [0-9]" public/index.html || echo "(check manually)"

echo ""
echo "To release:"
echo "  git add -A && git commit -m \"chore: bump version to $VERSION\""
echo "  git tag v$VERSION"
echo "  git push origin main --tags"

#!/bin/bash
# Sync Docker dashboard files to npm package
# Run this before publishing to npm

set -e

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
ROOT_DIR="$(dirname "$SCRIPT_DIR")"
NPM_DIR="$ROOT_DIR/npm"

echo "Syncing dashboard files to npm package..."

# Sync Docker files (not Dockerfile - paths differ)
cp "$ROOT_DIR/docker-compose.yml" "$NPM_DIR/"
cp "$ROOT_DIR/nginx.conf" "$NPM_DIR/"

# Sync cf.html
cp "$ROOT_DIR/tools/evolution/cf.html" "$NPM_DIR/"

# Create npm-specific Dockerfile (cf.html is at root in npm package)
cat > "$NPM_DIR/Dockerfile" << 'EOF'
# Context Foundry Dashboard (Web UI only)
# The daemon runs on the host - this just serves the monitoring UI
FROM nginx:alpine

# Copy dashboard HTML
COPY cf.html /usr/share/nginx/html/index.html
COPY cf.html /usr/share/nginx/html/cf.html

# Copy nginx config
COPY nginx.conf /etc/nginx/conf.d/default.conf

# Expose dashboard port
EXPOSE 8421

# Health check
HEALTHCHECK --interval=30s --timeout=5s --retries=3 \
    CMD wget -q --spider http://localhost:8421/ || exit 1
EOF

# Sync version from Python package
VERSION=$(grep -E '^__version__' "$ROOT_DIR/__version__.py" | cut -d'"' -f2)
if [ -n "$VERSION" ]; then
    # Update npm package.json version
    cd "$NPM_DIR"
    npm version "$VERSION" --no-git-tag-version --allow-same-version 2>/dev/null || true
    echo "Updated npm version to $VERSION"
fi

echo "Done! Files synced to $NPM_DIR"
echo ""
echo "Synced files:"
ls -la "$NPM_DIR"/{Dockerfile,docker-compose.yml,nginx.conf,cf.html} 2>/dev/null

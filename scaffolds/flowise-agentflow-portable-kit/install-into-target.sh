#!/bin/bash
set -euo pipefail

TARGET_DIR="${1:-.}"
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"

mkdir -p "$TARGET_DIR"

cd "$SCRIPT_DIR"
find . -mindepth 1 -maxdepth 1 \
  ! -name 'README.md' \
  ! -name 'install-into-target.sh' \
  -exec cp -R {} "$TARGET_DIR"/ \;

echo "Installed flowise-agentflow-portable-kit into: $TARGET_DIR"

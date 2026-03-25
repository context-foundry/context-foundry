#!/usr/bin/env bash
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_ROOT="$(dirname "$SCRIPT_DIR")"
IMAGE_NAME="${1:-foundry-sandbox:latest}"

echo "Building sandbox image: ${IMAGE_NAME}"
echo "Context: ${PROJECT_ROOT}"

docker build \
  -t "${IMAGE_NAME}" \
  -f "${PROJECT_ROOT}/Dockerfile.sandbox" \
  "${PROJECT_ROOT}"

echo ""
echo "Build complete. Verifying..."
echo ""

echo "--- claude --version ---"
docker run --rm "${IMAGE_NAME}" claude --version

echo ""
echo "--- git --version ---"
docker run --rm "${IMAGE_NAME}" git --version

echo ""
echo "--- node --version ---"
docker run --rm "${IMAGE_NAME}" node --version

echo ""
echo "--- whoami ---"
docker run --rm "${IMAGE_NAME}" whoami

echo ""
echo "Sandbox image '${IMAGE_NAME}' built and verified successfully."

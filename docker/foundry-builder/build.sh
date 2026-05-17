#!/usr/bin/env bash
# Build the foundry-builder image.
#
# The Dockerfile `COPY foundry` from this directory, so the release binary is
# staged in first. Run from the repo root or anywhere — paths are resolved
# relative to this script.
set -euo pipefail

here="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
repo_root="$(cd "$here/../.." && pwd)"
tag="${1:-foundry-builder:latest}"

binary="$repo_root/target/release/foundry"
if [ ! -x "$binary" ]; then
  echo "building release binary ($binary missing) ..." >&2
  (cd "$repo_root" && cargo build --release)
fi

cp "$binary" "$here/foundry"
trap 'rm -f "$here/foundry"' EXIT

echo "docker build -t $tag $here" >&2
docker build -t "$tag" "$here"
echo "built $tag" >&2

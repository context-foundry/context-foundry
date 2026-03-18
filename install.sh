#!/bin/sh
# One-liner install: curl -fsSL https://raw.githubusercontent.com/context-foundry/context-foundry/main/install.sh | sh
set -e

REPO="context-foundry/context-foundry"
INSTALL_DIR="${FOUNDRY_INSTALL_DIR:-$HOME/.local/bin}"

# Detect platform
OS=$(uname -s | tr '[:upper:]' '[:lower:]')
ARCH=$(uname -m)

case "$OS" in
  darwin)
    case "$ARCH" in
      arm64|aarch64) TARGET="aarch64-apple-darwin" ;;
      x86_64)        TARGET="x86_64-apple-darwin" ;;
      *) echo "Unsupported architecture: $ARCH"; exit 1 ;;
    esac
    ;;
  linux)
    case "$ARCH" in
      x86_64|amd64) TARGET="x86_64-unknown-linux-gnu" ;;
      *) echo "Unsupported architecture: $ARCH"; exit 1 ;;
    esac
    ;;
  *)
    echo "Unsupported OS: $OS (use install.ps1 for Windows)"
    exit 1
    ;;
esac

# Get latest version tag
VERSION=$(curl -fsSL "https://api.github.com/repos/$REPO/releases/latest" | grep '"tag_name"' | sed -E 's/.*"([^"]+)".*/\1/')
if [ -z "$VERSION" ]; then
  echo "Failed to determine latest version"
  exit 1
fi

ARCHIVE="foundry-${TARGET}.tar.gz"
URL="https://github.com/${REPO}/releases/download/${VERSION}/${ARCHIVE}"

echo "Installing foundry ${VERSION} for ${TARGET}..."

# Download and extract
TMP=$(mktemp -d)
trap 'rm -rf "$TMP"' EXIT

curl -fsSL "$URL" -o "$TMP/$ARCHIVE"
tar xzf "$TMP/$ARCHIVE" -C "$TMP"

# Install
mkdir -p "$INSTALL_DIR"
cp "$TMP/foundry" "$INSTALL_DIR/foundry"
chmod +x "$INSTALL_DIR/foundry"

echo "Installed foundry to $INSTALL_DIR/foundry"

# Check if install dir is in PATH
case ":$PATH:" in
  *":$INSTALL_DIR:"*) ;;
  *) echo "Note: Add $INSTALL_DIR to your PATH if not already there" ;;
esac

echo "Run 'foundry' to get started."

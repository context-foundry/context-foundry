#!/bin/bash

#
# Backup Script for Context Foundry Patterns
#
# This script creates timestamped backups of the global pattern directory
# before any changes are made to the pattern files.
#
# Usage:
#   ./scripts/backup_patterns.sh
#
# Backups are stored in: ~/.context-foundry/backups/YYYYMMDD-HHMMSS/
#

set -e  # Exit on error

# Configuration
PATTERNS_DIR="$HOME/.context-foundry/patterns"
BACKUP_BASE_DIR="$HOME/.context-foundry/backups"
TIMESTAMP=$(date +%Y%m%d-%H%M%S)
BACKUP_DIR="$BACKUP_BASE_DIR/$TIMESTAMP"

# Colors for output
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
RED='\033[0;31m'
NC='\033[0m' # No Color

echo -e "${GREEN}Context Foundry Pattern Backup${NC}"
echo "======================================="
echo ""

# Check if patterns directory exists
if [ ! -d "$PATTERNS_DIR" ]; then
    echo -e "${YELLOW}⚠ Warning: Patterns directory does not exist yet${NC}"
    echo "  Location: $PATTERNS_DIR"
    echo "  This is normal for a fresh installation."
    echo ""
    echo "Creating patterns directory..."
    mkdir -p "$PATTERNS_DIR"
    echo -e "${GREEN}✓ Patterns directory created${NC}"
    echo ""
    echo "No patterns to backup yet. Exiting."
    exit 0
fi

# Check if there are any pattern files
PATTERN_COUNT=$(find "$PATTERNS_DIR" -name "*.json" 2>/dev/null | wc -l | tr -d ' ')

if [ "$PATTERN_COUNT" -eq 0 ]; then
    echo -e "${YELLOW}⚠ Warning: No pattern files found${NC}"
    echo "  Location: $PATTERNS_DIR"
    echo "  Nothing to backup. Exiting."
    exit 0
fi

# Create backup directory
echo "Creating backup directory..."
mkdir -p "$BACKUP_DIR"
echo -e "${GREEN}✓ Created: $BACKUP_DIR${NC}"
echo ""

# Copy pattern files
echo "Backing up $PATTERN_COUNT pattern file(s)..."
cp -r "$PATTERNS_DIR"/* "$BACKUP_DIR/" 2>/dev/null || true
echo -e "${GREEN}✓ Patterns backed up successfully${NC}"
echo ""

# Create backup metadata
cat > "$BACKUP_DIR/backup_info.txt" << EOF
Context Foundry Pattern Backup
===============================
Backup Date: $(date)
Backup Timestamp: $TIMESTAMP
Source Directory: $PATTERNS_DIR
Pattern Files Count: $PATTERN_COUNT

Files Backed Up:
$(ls -lh "$BACKUP_DIR" | grep -v "^total" | grep -v "backup_info.txt")

To Restore:
  cp -r $BACKUP_DIR/* $PATTERNS_DIR/

EOF

echo "Backup Summary:"
echo "  - Files backed up: $PATTERN_COUNT"
echo "  - Backup location: $BACKUP_DIR"
echo "  - Disk space used: $(du -sh "$BACKUP_DIR" | cut -f1)"
echo ""

# Clean up old backups (keep last 10)
echo "Cleaning up old backups..."
BACKUP_COUNT=$(ls -1 "$BACKUP_BASE_DIR" 2>/dev/null | wc -l | tr -d ' ')

if [ "$BACKUP_COUNT" -gt 10 ]; then
    OLD_BACKUPS=$(ls -1t "$BACKUP_BASE_DIR" | tail -n +11)
    for backup in $OLD_BACKUPS; do
        echo "  Removing old backup: $backup"
        rm -rf "$BACKUP_BASE_DIR/$backup"
    done
    echo -e "${GREEN}✓ Cleaned up $(echo "$OLD_BACKUPS" | wc -l | tr -d ' ') old backup(s)${NC}"
else
    echo "  No cleanup needed (only $BACKUP_COUNT backup(s) exist)"
fi

echo ""
echo -e "${GREEN}✓ Backup completed successfully!${NC}"
echo ""
echo "To restore from this backup:"
echo "  cp -r $BACKUP_DIR/* $PATTERNS_DIR/"
echo ""

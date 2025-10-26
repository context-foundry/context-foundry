#!/bin/bash
# Unset ANTHROPIC_API_KEY from current shell environment
# Run with: source unset_anthropic_key.sh

echo "🔧 Unsetting ANTHROPIC_API_KEY from environment..."

if [ -n "$ANTHROPIC_API_KEY" ]; then
    echo "   Found ANTHROPIC_API_KEY in environment"
    unset ANTHROPIC_API_KEY
    echo "   ✅ ANTHROPIC_API_KEY unset"
else
    echo "   ✅ ANTHROPIC_API_KEY was not set"
fi

# Verify it's gone
if [ -z "$ANTHROPIC_API_KEY" ]; then
    echo "   ✅ Verified: ANTHROPIC_API_KEY is not in environment"
else
    echo "   ❌ ERROR: ANTHROPIC_API_KEY still present!"
fi

echo ""
echo "Note: This only affects your CURRENT shell session."
echo "To make permanent:"
echo "  1. Check ~/.bashrc or ~/.zshrc for 'export ANTHROPIC_API_KEY'"
echo "  2. Remove or comment out that line"
echo "  3. Restart your shell or run: source ~/.bashrc (or ~/.zshrc)"

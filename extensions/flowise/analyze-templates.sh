#!/bin/bash
#
# Flowise Template Analysis Helper Script
#
# This script analyzes your Flowise templates and builds the expertise library
#

set -e  # Exit on error

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
TEMPLATES_DIR="$SCRIPT_DIR/templates"
PATTERNS_DIR="$SCRIPT_DIR/patterns"

echo "═══════════════════════════════════════════════════════════"
echo "  Flowise Template Analysis"
echo "═══════════════════════════════════════════════════════════"
echo

# Check if templates directory exists
if [ ! -d "$TEMPLATES_DIR" ]; then
    echo "❌ Error: Templates directory not found: $TEMPLATES_DIR"
    exit 1
fi

# Count JSON files in templates directory
TEMPLATE_COUNT=$(find "$TEMPLATES_DIR" -name "*.json" -type f | wc -l | tr -d ' ')

echo "📊 Found $TEMPLATE_COUNT template(s) in $TEMPLATES_DIR"
echo

if [ "$TEMPLATE_COUNT" -eq 0 ]; then
    echo "⚠️  No templates found!"
    echo
    echo "Please download your Flowise agent flows and place them in:"
    echo "  $TEMPLATES_DIR"
    echo
    echo "See templates/README.md for instructions."
    exit 1
fi

# List templates
echo "📁 Templates:"
find "$TEMPLATES_DIR" -name "*.json" -type f -exec basename {} \; | sort | sed 's/^/  - /'
echo

# Create patterns directory if it doesn't exist
mkdir -p "$PATTERNS_DIR"

# Step 1: Analyze all templates
echo "🔍 Step 1: Analyzing templates..."
python3 "$SCRIPT_DIR/analyzer.py" --analyze-all "$TEMPLATES_DIR"

if [ $? -ne 0 ]; then
    echo "❌ Analysis failed!"
    exit 1
fi

echo "✅ Analysis complete"
echo

# Step 2: Export patterns
echo "📤 Step 2: Exporting learned patterns..."
python3 "$SCRIPT_DIR/analyzer.py" --export-patterns "$PATTERNS_DIR/flowise-expertise.json"

if [ $? -ne 0 ]; then
    echo "❌ Export failed!"
    exit 1
fi

echo "✅ Patterns exported to: $PATTERNS_DIR/flowise-expertise.json"
echo

# Step 3: Show summary
if [ -f "$PATTERNS_DIR/flowise-expertise.json" ]; then
    echo "📋 Pattern Summary:"
    python3 -c "
import json
import sys

try:
    with open('$PATTERNS_DIR/flowise-expertise.json', 'r') as f:
        data = json.load(f)

    patterns = data.get('patterns', [])
    flow_types = set(p.get('flow_type', 'unknown') for p in patterns)
    node_types = set()
    for p in patterns:
        node_types.update(p.get('common_node_types', []))

    print(f'  - Total patterns learned: {len(patterns)}')
    print(f'  - Flow types covered: {len(flow_types)}')
    print(f'  - Unique node types: {len(node_types)}')
    print()
    print('  Flow types:', ', '.join(sorted(flow_types)))

except Exception as e:
    print(f'  Error reading patterns: {e}', file=sys.stderr)
    sys.exit(1)
"

    if [ $? -eq 0 ]; then
        echo
        echo "🎉 Success! Flowise expertise library is ready."
        echo
        echo "Next time you work on a Flowise project, Context Foundry will"
        echo "automatically detect it and apply this expertise."
    fi
else
    echo "⚠️  Warning: Pattern file not created"
fi

echo
echo "═══════════════════════════════════════════════════════════"

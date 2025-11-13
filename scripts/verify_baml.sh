#!/bin/bash
# BAML Setup Verification Script
# Run this after setting your API keys to verify everything works

echo "🔍 Verifying BAML Integration Setup..."
echo ""

# Check if in correct directory
if [ ! -f "tools/use_baml.py" ]; then
    echo "❌ Error: Run this from the context-foundry directory"
    exit 1
fi

# 1. Check BAML Python module
echo "1️⃣ Checking baml-py installation..."
if python3 -c "import baml_py" 2>/dev/null; then
    echo "   ✅ baml-py is installed"
else
    echo "   ❌ baml-py not installed. Run: pip3 install -r requirements-baml.txt"
    exit 1
fi

# 2. Check API keys
echo ""
echo "2️⃣ Checking API keys..."
HAS_API_KEY=0
if [ -n "$ANTHROPIC_API_KEY" ]; then
    echo "   ✅ ANTHROPIC_API_KEY is set (${ANTHROPIC_API_KEY:0:10}...)"
    HAS_API_KEY=1
fi
if [ -n "$OPENAI_API_KEY" ]; then
    echo "   ✅ OPENAI_API_KEY is set (${OPENAI_API_KEY:0:10}...)"
    HAS_API_KEY=1
fi

if [ $HAS_API_KEY -eq 0 ]; then
    echo "   ❌ No API keys set. BAML requires at least one API key."
    echo "   Set at least one:"
    echo "     export ANTHROPIC_API_KEY='your-key'"
    echo "     export OPENAI_API_KEY='your-key'"
    echo ""
    echo "   Alternative: Use MCP delegation mode (see integrations/baml/) for $0 API costs"
    exit 1
fi

# 3. Check BAML status
echo ""
echo "3️⃣ Checking BAML integration status..."
python3 tools/use_baml.py status
STATUS=$?

if [ $STATUS -eq 0 ]; then
    echo ""
    echo "✅ BAML is ready to use!"
    echo ""
    echo "🚀 Next steps:"
    echo "   - Run an autonomous build and BAML will be used automatically"
    echo "   - Check logs for 'Using BAML for type-safe outputs'"
    echo "   - See docs/BAML_INTEGRATION.md for more info"
else
    echo ""
    echo "⚠️  BAML status check failed"
    echo "   Review the errors above"
fi

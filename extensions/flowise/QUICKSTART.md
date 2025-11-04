# Quick Start - Flowise Agent Builder

> Build complete Flowise multi-agent workflows from single sentences in ~20 minutes.

This guide gets you from zero to your first successful Flowise flow build in **10 minutes**.

---

## Prerequisites (2 minutes)

Before starting, verify you have:

```bash
# 1. Context Foundry installed
which cf
# Expected: /usr/local/bin/cf (or your install path)

# 2. Claude Code CLI
which claude
# Expected: /opt/homebrew/bin/claude

# 3. Python 3.10+
python3 --version
# Expected: Python 3.10.x or higher

# 4. GitHub authentication
gh auth status
# Expected: ✓ Logged in to github.com as [username]
```

**Checklist**:
- ✅ Context Foundry installed and working
- ✅ Claude Code CLI in PATH
- ✅ Python 3.10+ available
- ✅ GitHub CLI authenticated

If any checks fail, see the [Context Foundry Installation Guide](../../README.md#quick-start).

---

## Installation (5 minutes)

### Step 1: Verify Extension Files

Check that the Flowise extension is installed:

```bash
# Navigate to Context Foundry directory
cd ~/homelab/context-foundry  # or your install path

# Check for Flowise extension
ls -lh extensions/flowise/AGENT_PATTERN_REFERENCE.md
# Expected: -rw-r--r-- 1 user staff 26K ... AGENT_PATTERN_REFERENCE.md
```

✅ **Success**: You should see the 26KB authoritative pattern reference file.

### Step 2: Verify Template Library

```bash
# Check templates directory
ls extensions/flowise/templates/ | wc -l
# Expected: 13 or more files

# List template files
ls extensions/flowise/templates/
# Expected: Simple Agent Agents.json, Supervisor Agent Agents.json, etc.
```

✅ **Success**: You should see 13+ Flowise template JSON files.

### Step 3: Verify Orchestrator Integration

```bash
# Check Scout phase integration
grep -n "AGENT_PATTERN_REFERENCE" tools/orchestrator_prompt.txt
# Expected: Line ~497 and ~685 (Scout and Architect phases)

# Verify Flowise specialization block exists
grep -A 5 "FLOWISE EXTENSION CHECK" tools/orchestrator_prompt.txt | head -10
```

✅ **Success**: You should see references to AGENT_PATTERN_REFERENCE.md in both Scout and Architect phases.

---

## Your First Build (10 minutes)

Let's build a simple customer service multi-agent flow!

### Step 1: Start Claude Code

```bash
# Start Claude Code CLI
claude
```

### Step 2: Request Your First Flowise Flow

In your Claude Code session, say:

```
Build a Flowise customer service multi-agent flow with routing for technical support,
billing questions, and general inquiries
```

**What happens next:**
1. Context Foundry detects this is a Flowise flow request
2. Automatically activates Flowise specialization mode
3. Runs through all phases autonomously (~10-15 minutes)

### Step 3: Expected Output

After ~10-15 minutes, you'll get:

```json
{
  "status": "completed",
  "phases_completed": ["scout", "architect", "builder", "test", "docs", "deploy"],
  "github_url": "https://github.com/[username]/customer-service-flow",
  "files_created": [
    "customer-service-flow.json",
    "README.md",
    "INTEGRATION_GUIDE.md",
    "tool-configs/email-notification.json",
    "knowledge-configs/kb-support.json",
    "docs/DEPLOYMENT.md",
    "docs/TESTING.md"
  ],
  "tests_passed": true,
  "test_iterations": 1,
  "duration_minutes": 12.3,
  "agents_created": 5
}
```

### Step 4: Explore the Generated Files

```bash
# Navigate to the generated project
cd /path/to/customer-service-flow  # Check the working_directory from output

# View the main Flowise JSON
ls -lh customer-service-flow.json
# Expected: ~400-600 lines of Flowise-compatible JSON

# Check the README
cat README.md
# Expected: Complete architecture overview, agent descriptions, integration guide
```

---

## Verify It Works

### ✅ Validation Checklist

Run these checks to ensure your build succeeded:

#### 1. JSON Structure Validation

```bash
# Verify valid JSON
jq . customer-service-flow.json > /dev/null && echo "✅ Valid JSON" || echo "❌ Invalid JSON"

# Check for self-contained agents (should be N where N = agent count)
grep -c '"name": "agentAgentflow"' customer-service-flow.json
# Expected: 4-5 (number of specialized agents)

# Check NO separate model nodes (should be 0)
grep -c '"name": "chatOpenAI"' customer-service-flow.json || echo "0"
# Expected: 0 (models are built INTO agents)

# Check asyncOptions present (should be > 0)
grep -c '"type": "asyncOptions"' customer-service-flow.json
# Expected: 5+ (one per agent model configuration)
```

#### 2. Import to Flowise

1. **Open Flowise UI** (http://localhost:3000 or your Flowise instance)
2. **Go to Agent Flows**
3. **Click "Import"**
4. **Select** `customer-service-flow.json`
5. **Verify** the flow renders with:
   - 1 start node
   - 1 condition/router node
   - 4-5 specialized agent nodes
   - All connections visible

✅ **Success**: If the flow imports cleanly and all nodes render, you have a complete working Flowise flow!

#### 3. Documentation Completeness

```bash
# Check all expected files exist
ls -1 | grep -E "README|INTEGRATION|DEPLOYMENT|TESTING"
# Expected: All 4 files present

# Verify tool configurations
ls tool-configs/ | wc -l
# Expected: 1-3 tool configuration files

# Check knowledge configurations
ls knowledge-configs/ | wc -l
# Expected: 1-2 knowledge source files
```

---

## Success Criteria

You've successfully completed the quick start if:

- ✅ **Build completed** in 10-15 minutes
- ✅ **JSON validates** (jq parsing succeeds)
- ✅ **No separate model/memory nodes** (self-contained architecture)
- ✅ **asyncOptions present** in all agents
- ✅ **Imports cleanly to Flowise** (no errors, all nodes render)
- ✅ **Documentation generated** (README, guides, configs)
- ✅ **Deployed to GitHub** (optional but recommended)

---

## Next Steps

### Learn More
- 📚 **[User Guide](USER_GUIDE.md)** - Comprehensive usage for simple, moderate, and complex flows
- 🎯 **[Test Prompts](TEST_PROMPTS.md)** - 20+ example prompts to try
- 🏗️ **[Architecture](ARCHITECTURE.md)** - How the extension integrates with Context Foundry
- 🔧 **[Troubleshooting](TROUBLESHOOTING.md)** - Solutions to common issues

### Try These Next

**Simple (3-5 agents, 10-15 min)**:
```
Build a Flowise IT helpdesk flow with password resets, software issues, and hardware problems
```

**Moderate (5-8 agents, 15-25 min)**:
```
Create a Flowise e-commerce order processing flow with inventory management, shipping coordination,
and customer notifications, integrating with Shopify and Shippo APIs
```

**Complex (8+ agents, 20-30 min)**:
```
Build a comprehensive Flowise warehouse operations workflow with Workday integration,
inventory tracking, order fulfillment, and equipment maintenance
```

### 🏆 Production Success Story

**Want to see a real enterprise build?** Check out the [Promotion Nomination Workflow](./SUCCESS_PROMOTION_NOMINATION.md):
- ✅ 11 nodes (7 agents + 2 HIL approval gates)
- ✅ 25 minutes build time
- ✅ Two-stage approval workflow (Local → Executive)
- ✅ Complete Workday HCM integration
- ✅ All 9 failure patterns prevented on first try

This was the **first successful Human-in-the-Loop implementation** and demonstrates the extension's production maturity for complex enterprise workflows.

### Get Help

- **Issues?** See [Troubleshooting Guide](TROUBLESHOOTING.md)
- **Questions?** Check [User Guide](USER_GUIDE.md)
- **Best Practices?** Read [Best Practices](BEST_PRACTICES.md)

---

🎉 **Congratulations!** You just built your first complete Flowise multi-agent workflow from a single sentence.

🤖 **Powered by Context Foundry Flowise Extension**

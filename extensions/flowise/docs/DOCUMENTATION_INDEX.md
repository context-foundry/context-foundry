# Flowise Extension Documentation Index

**Quick Navigation**: Find the right documentation for your Flowise development needs.

---

## 🎯 Start Here

### For New Users
1. **[Installation Guide](./INSTALLATION.md)** - Set up the Flowise extension
2. **[Usage Guide](./USAGE.md)** - Learn how to use the extension
3. **[Main README](../README.md)** - Overview and features

### For Developers/Architects
1. **[Authoritative Pattern Reference](../AGENT_PATTERN_REFERENCE.md)** ⭐ **START HERE** ⭐
   - The single source of truth for Flowise multi-agent systems
   - Complete node definitions, patterns, and implementation checklist

### For Extension Developers
1. **[Training Guide](./TRAINING_GUIDE.md)** 🎓 **NEW!** - Master how to teach the extension new capabilities
   - Complete masterclass on documentation-based training
   - Step-by-step process for adding new node types
   - Worked examples and troubleshooting

---

## 📖 Core Documentation

### Authoritative References

| Document | Purpose | When to Use |
|----------|---------|-------------|
| **[AGENT_PATTERN_REFERENCE.md](../AGENT_PATTERN_REFERENCE.md)** | **Canonical multi-agent pattern reference** | Designing/validating ANY Flowise agent flow |
| [SELF-CONTAINED-AGENTS-FIX.md](../SELF-CONTAINED-AGENTS-FIX.md) | Critical architectural fix | Debugging agent structure issues |
| [prompts/FLOWISE-STRUCTURE-AUTHORITY.md](../prompts/FLOWISE-STRUCTURE-AUTHORITY.md) | Structural validation checklist | Validating JSON structure |

### Runtime-Loaded During Builds

Files read automatically by Scout/Architect/Builder when `flowise_flow: True`:

| File | Consumed By | Read Count | Purpose |
|------|-------------|------------|---------|
| [AGENT_PATTERN_REFERENCE.md](../AGENT_PATTERN_REFERENCE.md) | Scout, Architect | 2x | Baseline structure and patterns |
| [FAILURE_PATTERNS.md](../FAILURE_PATTERNS.md) | Scout, Architect, Builder | 3x | Regression guardrails and remediation steps |
| [BEST_PRACTICES.md](../BEST_PRACTICES.md) | Scout | 1x | Prompting and planning guidance |
| [tool-configs/STANDARD_TOOLS.md](../tool-configs/STANDARD_TOOLS.md) | Scout | 1x | Required tools specification |
| [prompts/FLOWISE-STRUCTURE-AUTHORITY.md](../prompts/FLOWISE-STRUCTURE-AUTHORITY.md) | Architect | 1x | Validation checklist |
| [prompts/AGENT-NODE-TEMPLATE.json](../prompts/AGENT-NODE-TEMPLATE.json) | Builder | 1x | Canonical agent node schema |

**Total**: 9 explicit Read commands in orchestrator_prompt.txt

### Referenced But Not Automatically Read

Files mentioned in orchestrator but not loaded via Read commands:

| File | Purpose | When To Use |
|------|---------|-------------|
| [prompts/START-NODE-TEMPLATE.json](../prompts/START-NODE-TEMPLATE.json) | Start node structure | Manual reference (structure documented in AGENT_PATTERN_REFERENCE.md) |
| templates/*.json (15 files) | Real Flowise exports | Manual comparison/validation/debugging |

### Archived Files

Files not currently used by orchestrator (see [prompts/archive/README.md](../prompts/archive/README.md)):

| File | Original Purpose | Why Archived |
|------|------------------|--------------|
| prompts/archive/architect-enhancement.txt | Architect phase enhancement | Never referenced; content in AGENT_PATTERN_REFERENCE.md |
| prompts/archive/scout-enhancement.txt | Scout phase enhancement | Never referenced; content in AGENT_PATTERN_REFERENCE.md |
| prompts/archive/flowise-json-structure-guide.md | JSON structure guide | Never referenced; contains old patterns; superseded by AGENT_PATTERN_REFERENCE.md |

### Implementation Guides

| Document | Purpose |
|----------|---------|
| [prompts/AGENT-NODE-TEMPLATE.json](../prompts/AGENT-NODE-TEMPLATE.json) | Agent node template (canonical structure) |
| [prompts/START-NODE-TEMPLATE.json](../prompts/START-NODE-TEMPLATE.json) | Start node template (for reference) |

### Pattern Library

| Resource | Description |
|----------|-------------|
| [patterns/flowise-expertise.json](../patterns/flowise-expertise.json) | Analyzed patterns from 13 template flows |
| [patterns/flow-templates.json.example](../patterns/flow-templates.json.example) | Template catalog structure |
| [templates/](../templates/) | 13+ canonical Flowise flow examples |

### 🏆 Success Stories & Production Builds

Real-world builds demonstrating best practices and production readiness:

| Document | Date | Complexity | Highlights |
|----------|------|------------|------------|
| **[SUCCESS_PROMOTION_NOMINATION.md](../SUCCESS_PROMOTION_NOMINATION.md)** | Nov 4, 2025 | Complex (11 nodes) | ⭐ **First HIL gates!** Two-stage approval, Workday HCM, 25 min build |
| [SUCCESS_PERSONALIZED_ONBOARDING.md](../SUCCESS_PERSONALIZED_ONBOARDING.md) | Nov 2, 2025 | Moderate (10 nodes) | All patterns prevented, 17 min build |
| [SUCCESS_EXECUTEFLOW.md](../SUCCESS_EXECUTEFLOW.md) | Nov 2, 2025 | Feature | ExecuteFlow node validation |
| [SUCCESS_AUTO_INCLUDE_TOOLS.md](../SUCCESS_AUTO_INCLUDE_TOOLS.md) | Nov 2, 2025 | Feature | Auto-include standard tools |
| [SUCCESS_WORKFORCE_ALLOCATION.md](../SUCCESS_WORKFORCE_ALLOCATION.md) | Nov 1, 2025 | Moderate (8 nodes) | Warehouse operations |
| [SUCCESS_GIG_MARKETPLACE.md](../SUCCESS_GIG_MARKETPLACE.md) | Nov 1, 2025 | Moderate (9 nodes) | Multi-stakeholder coordination |

**Success Rate**: 100% first-iteration success across all documented builds
**Pattern Prevention**: 9/9 patterns prevented in recent builds

---

## 🔍 Documentation by Use Case

### "I need to build a multi-agent Flowise flow"

**Required Reading**:
1. [AGENT_PATTERN_REFERENCE.md](../AGENT_PATTERN_REFERENCE.md) - Complete pattern guide
2. [templates/Simple Agent Agents.json](../templates/Simple%20Agent%20Agents.json) - Canonical example

**Key Sections**:
- Agent Node Structure (agentAgentflow)
- Condition Node Structure (conditionAgentAgentflow)
- Intent Detection Architecture
- Agent Specialization Pattern
- Implementation Checklist

### "My generated flow won't import into Flowise"

**Troubleshooting Path**:
1. [SELF-CONTAINED-AGENTS-FIX.md](../SELF-CONTAINED-AGENTS-FIX.md) - Check for separate model/memory nodes
2. [AGENT_PATTERN_REFERENCE.md](../AGENT_PATTERN_REFERENCE.md) - Validate against canonical structure
3. [prompts/FLOWISE-STRUCTURE-AUTHORITY.md](../prompts/FLOWISE-STRUCTURE-AUTHORITY.md) - Run validation checklist

**Common Issues**:
- ❌ Separate chatOpenAI or windowMemory nodes
- ❌ Missing asyncOptions for model selection
- ❌ Incorrect outputAnchor ID format
- ❌ Missing inputParams structure

### "I want to understand agent personas and configuration"

**Reference Sections**:
- [AGENT_PATTERN_REFERENCE.md](../AGENT_PATTERN_REFERENCE.md):
  - Section: "Agent Persona Pattern"
  - Section: "Model Configuration"
  - Section: "Actual Configured Values"
  - Section: "Agent Input Parameters"

**Examples**:
- Navigation Agent persona
- Payroll Agent persona
- HCM Agent persona
- Temperature guidelines by use case

### "I need to connect agents with edges"

**Reference Sections**:
- [AGENT_PATTERN_REFERENCE.md](../AGENT_PATTERN_REFERENCE.md):
  - Section: "Edges Structure"
  - Section: "Critical Design Patterns > Multi-Level Routing"

**Key Patterns**:
- Condition → Agent routing
- Agent → Agent chaining
- Edge ID format
- Source/target handle naming

### "How do I add knowledge/tools to agents?"

**Reference Sections**:
- [AGENT_PATTERN_REFERENCE.md](../AGENT_PATTERN_REFERENCE.md):
  - Section: "Agent Input Parameters > Knowledge - Document Stores"
  - Section: "Agent Input Parameters > Knowledge - Vector Embeddings"
  - Section: "Agent Input Parameters > Custom Tools"
  - Section: "Critical Design Patterns > Knowledge Integration"

### "I want to teach the extension new node types"

**🎓 Start here**: [Training Guide](./TRAINING_GUIDE.md) → Complete masterclass on extension training

**Deep dive**:
- [AGENT_PATTERN_REFERENCE.md](../AGENT_PATTERN_REFERENCE.md) - Where to document node structures
- [FAILURE_PATTERNS.md](../FAILURE_PATTERNS.md) - How the system learns from mistakes
- [BEST_PRACTICES.md](../BEST_PRACTICES.md) - Where to document usage patterns
- [prompts/FLOWISE-STRUCTURE-AUTHORITY.md](../prompts/FLOWISE-STRUCTURE-AUTHORITY.md) - Where to add validation rules

**Key Concepts**:
- Training = Writing Documentation (no ML model retraining)
- AI reads docs during each build
- Changes take effect immediately
- Documentation is the source of truth

---

## 🛠️ Templates and Examples

### Canonical Templates

Located in `extensions/flowise/templates/`:

1. **Simple Agent Agents.json** - Basic multi-agent pattern ⭐ **Best Starting Point**
2. **Agentic RAG Agents.json** - RAG with intelligent retrieval
3. **Condition Agent Agents.json** - Intent detection routing
4. **Loop Agent Agents.json** - Iterative processing
5. **Sequential Agent Agents.json** - Linear workflow
6. **Supervisor Agent Agents.json** - Hierarchical coordination
7. ... (13+ total templates)

### How to Use Templates

```bash
# View template structure
cat extensions/flowise/templates/Simple\ Agent\ Agents.json | jq .

# Compare your flow against template
diff <(jq -S . my-flow.json) <(jq -S . templates/Simple\ Agent\ Agents.json)

# Extract specific node from template
jq '.nodes[] | select(.data.name == "agentAgentflow")' templates/Simple\ Agent\ Agents.json
```

---

## 🔧 Development Tools

### Analysis Tools

| Tool | Usage |
|------|-------|
| `detector.py` | Detect and classify Flowise flows |
| `analyzer.py` | Analyze templates and extract patterns |
| `extensions_loader.py` | Load patterns programmatically |

**Examples**:

```bash
# Detect flow type
python3 detector.py my-flow.json

# Analyze all templates
python3 analyzer.py --analyze-all templates/

# Export patterns
python3 analyzer.py --analyze-all templates/ --export-patterns patterns/custom.json
```

### Validation Commands

```bash
# Check for separate model nodes (should be 0)
grep -c '"name": "chatOpenAI"' flow.json

# Check for separate memory nodes (should be 0)
grep -c '"name": "windowMemory"' flow.json

# Check for agent nodes (should match agent count)
grep -c '"name": "agentAgentflow"' flow.json

# Check for asyncOptions (should exist)
grep -c '"type": "asyncOptions"' flow.json

# Check for agentModelConfig (should exist)
grep -c '"agentModelConfig"' flow.json

# Validate JSON structure
jq . flow.json > /dev/null && echo "Valid JSON" || echo "Invalid JSON"
```

---

## 📚 Integration with Context Foundry

### How Context Foundry Uses These Patterns

**During Scout Phase** (line 497-509 in `tools/orchestrator_prompt.txt`):
- Reads AGENT_PATTERN_REFERENCE.md
- Analyzes existing flow architecture
- Identifies anti-patterns

**During Architect Phase** (line 683-743 in `tools/orchestrator_prompt.txt`):
- Loads authoritative pattern reference
- Applies canonical structures
- Validates against templates

### File References in Orchestrator

The orchestrator prompt automatically references:
1. `/Users/name/homelab/context-foundry/extensions/flowise/AGENT_PATTERN_REFERENCE.md`
2. `/Users/name/homelab/context-foundry/extensions/flowise/prompts/FLOWISE-STRUCTURE-AUTHORITY.md`
3. Template files in `extensions/flowise/templates/`

---

## 🎓 Learning Path

### Beginner Path

1. **Read**: [Main README](../README.md)
2. **Read**: [AGENT_PATTERN_REFERENCE.md](../AGENT_PATTERN_REFERENCE.md) - Section: "Core Architecture"
3. **Study**: `templates/Simple Agent Agents.json`
4. **Practice**: Build a simple 2-agent flow
5. **Validate**: Use validation commands above

### Intermediate Path

1. **Read**: [AGENT_PATTERN_REFERENCE.md](../AGENT_PATTERN_REFERENCE.md) - All sections
2. **Study**: Multi-agent templates (Supervisor, Condition, Sequential)
3. **Read**: [SELF-CONTAINED-AGENTS-FIX.md](../SELF-CONTAINED-AGENTS-FIX.md)
4. **Practice**: Build multi-agent flow with intent detection
5. **Analyze**: Use `analyzer.py` on your flows

### Advanced Path (Extension Development)

1. **Read**: [Training Guide](./TRAINING_GUIDE.md) - Master extension training process
2. **Read**: [prompts/FLOWISE-STRUCTURE-AUTHORITY.md](../prompts/FLOWISE-STRUCTURE-AUTHORITY.md)
3. **Study**: All 13 templates to understand pattern variations
4. **Analyze**: `patterns/flowise-expertise.json` for frequency data
5. **Practice**: Build complex multi-level routing with knowledge integration
6. **Practice**: Add a new node type (follow HTTP node example in Training Guide)
7. **Contribute**: Add new patterns to pattern library

---

## 🆘 Quick Reference

### Node Types Quick Reference

| Node Type | Purpose | Key Fields |
|-----------|---------|------------|
| `agentAgentflow` | Specialized agent | `agentMessages`, `agentModel`, `agentTools` |
| `conditionAgentAgentflow` | Intent router | `conditionAgentScenarios`, `outputAnchors` |
| `startAgentflow` | Flow entry point | `startInputType`, `formInputTypes` |

### Common Patterns Quick Reference

| Pattern | Use Case | See |
|---------|----------|-----|
| Intent Detection | Route user to specialist | [AGENT_PATTERN_REFERENCE.md](../AGENT_PATTERN_REFERENCE.md)#1-intent-detection-architecture |
| Agent Specialization | Narrow domain expertise | [AGENT_PATTERN_REFERENCE.md](../AGENT_PATTERN_REFERENCE.md)#2-agent-specialization |
| Multi-Level Routing | Complex workflows | [AGENT_PATTERN_REFERENCE.md](../AGENT_PATTERN_REFERENCE.md)#4-multi-level-routing |
| Knowledge Integration | RAG patterns | [AGENT_PATTERN_REFERENCE.md](../AGENT_PATTERN_REFERENCE.md)#5-knowledge-integration |

### Anti-Patterns Quick Reference

| ❌ Anti-Pattern | ✅ Solution |
|----------------|-----------|
| Separate model nodes | Self-contained `agentModelConfig` |
| Separate memory nodes | Built-in `agentEnableMemory` |
| Missing asyncOptions | Add with `loadMethod: "listModels"` |
| Incorrect edge IDs | Use format: `{source}-{sourceHandle}-{target}-{targetHandle}` |

---

## 📝 Notes

- All paths are relative to `extensions/flowise/` unless absolute path specified
- JSON examples use JSONPath notation where helpful: `$.nodes[0].data.name`
- Template names with spaces need escaping in bash: `Simple\ Agent\ Agents.json`
- All templates validated against real Flowise exports

---

## 🔄 Version History

| Version | Date | Changes |
|---------|------|---------|
| 1.0 | 2025-10-31 | Initial documentation index with authoritative pattern reference |

---

## 🎯 Next Steps

After reading this index:

1. **For first-time users**: Start with [Installation Guide](./INSTALLATION.md)
2. **For developers**: Read [AGENT_PATTERN_REFERENCE.md](../AGENT_PATTERN_REFERENCE.md)
3. **For troubleshooting**: Check [SELF-CONTAINED-AGENTS-FIX.md](../SELF-CONTAINED-AGENTS-FIX.md)
4. **For examples**: Browse `templates/` directory

---

**Remember**: When in doubt, consult [AGENT_PATTERN_REFERENCE.md](../AGENT_PATTERN_REFERENCE.md) - it's the single source of truth!

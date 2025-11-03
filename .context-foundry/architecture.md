# Architecture: Flowise Mermaid Generator Enhancement

## Overview

Fix partially-implemented features in `mermaid_generator.py` by updating functions to use the new data structure (separate `shape`, `color`, `emoji` fields instead of `shape_color` tuple).

## File Structure

```
extensions/flowise/
├── mermaid_generator.py       # MODIFY: Fix generate_mermaid(), enhance interactive section, update CLI
├── BEST_PRACTICES.md          # MODIFY: Add diagram generation documentation
└── templates/                 # USE FOR TESTING: 14 real Flowise workflows
    ├── Simple Agent Agents.json
    ├── Agentic RAG Agents.json
    └── ...12 more

tools/
└── orchestrator_prompt.txt    # MODIFY: Update lines 1424-1485 with new CLI flags
```

## Module Specifications

### Module 1: mermaid_generator.py Core Fixes

**File**: `extensions/flowise/mermaid_generator.py`

**Changes Required**:

#### Change 1: Fix generate_mermaid() function (Lines 314-370)

**Current Issue**:
```python
# Line 334-336 (BROKEN):
shape_template, color = info["shape_color"]  # ❌ KeyError: 'shape_color'
safe_label = sanitize_label(info["label"])
node_def = f"    {node_id}{shape_template.format(safe_label)}"
```

**Fix**:
```python
# NEW (Lines 334-340):
shape_template = info["shape"]
color = info["color"]
emoji = info["emoji"]
safe_label = sanitize_label(info["label"])
# Include emoji in label
label_with_emoji = f"{emoji} {safe_label}"
node_def = f"    {node_id}{shape_template.format(label_with_emoji)}"
```

**Rationale**: 
- `extract_node_info()` now returns dict with separate keys (lines 126-159)
- Must access fields individually, not as tuple
- Emoji should be part of the node label for visual enhancement

#### Change 2: Dynamic Layout Direction (Line 329)

**Current**:
```python
# Line 329 (HARDCODED):
"graph TD"
```

**Fix**:
```python
# Line 329 (DYNAMIC):
direction = detect_layout_direction(nodes, edges)
mermaid_lines.append(f"graph {direction}")
```

**Rationale**:
- `detect_layout_direction()` already exists (lines 226-254)
- Returns "TD" for simple flows (≤5 nodes)
- Returns "LR" for complex flows (>10 nodes or ≥2 branches)
- Improves readability of generated diagrams

#### Change 3: Enhance generate_interactive_section() (Lines 373-399)

**Current**: Basic agent table only

**Add**:
1. Badges at top (before `<details>`)
2. Flow metadata section
3. Legend after details

**New Structure**:
```python
def generate_interactive_section(workflow_json: Dict, include_badges: bool = True, include_legend: bool = True) -> str:
    """Generate an interactive/collapsible section with agent details."""
    nodes = workflow_json.get("nodes", [])
    metadata = extract_flow_metadata(workflow_json)
    
    sections = []
    
    # 1. Add badges if requested
    if include_badges:
        badges = generate_badges(metadata)
        sections.extend([badges, "", "---", ""])
    
    # 2. Flow metadata
    sections.extend([
        f"**Total Nodes**: {metadata['total_nodes']} | ",
        f"**Agents**: {metadata['agent_count']} | ",
        f"**Complexity**: {metadata['complexity']}",
        "",
    ])
    
    # 3. Collapsible agent details
    sections.extend([
        "<details>",
        "<summary><b>🔍 View Agent Details (Click to Expand)</b></summary>",
        "",
        "| Agent | Type | Description |",
        "|-------|------|-------------|"
    ])
    
    for node in nodes:
        data = node.get("data", {})
        label = sanitize_label(data.get("label", "Unlabeled"))
        node_type = data.get("type", "Unknown")
        emoji = get_node_emoji(node_type)  # ADD emoji to table
        description = sanitize_label(data.get("description", "No description"))
        
        # Include emoji in agent column
        sections.append(f"| {emoji} {label} | {node_type} | {description} |")
    
    sections.extend(["", "</details>", ""])
    
    # 4. Add legend if requested
    if include_legend:
        sections.extend(["", generate_legend()])
    
    return "\n".join(sections)
```

**Rationale**:
- Badges provide quick overview (nodes, agents, complexity)
- Metadata shows key stats
- Emojis in table improve visual scanning
- Legend helps users understand node types

#### Change 4: Update main() CLI (Lines 402-447)

**Add new flags**:
```python
# Parse new arguments
include_badges = "--badges" in sys.argv or "--interactive" in sys.argv
include_legend = "--legend" in sys.argv or "--interactive" in sys.argv
# Make --interactive default if no other flags specified
if len(sys.argv) == 3:  # Only input and output files
    include_interactive = True
    include_badges = True
    include_legend = True
else:
    include_interactive = "--interactive" in sys.argv

# Update help text
print("Options:")
print("  --include-details    Include detailed node descriptions")
print("  --interactive        Include interactive/collapsible agent details (default if no flags)")
print("  --badges             Include flow metadata badges")
print("  --legend             Include node type legend")
print("  --no-interactive     Disable interactive features")
```

**Update interactive section call**:
```python
# Line 433-435 (CURRENT):
if include_interactive:
    interactive_section = generate_interactive_section(workflow_json)

# NEW:
if include_interactive:
    interactive_section = generate_interactive_section(
        workflow_json,
        include_badges=include_badges,
        include_legend=include_legend
    )
```

**Rationale**:
- `--interactive` becomes default (best UX)
- `--badges` and `--legend` control individual features
- `--no-interactive` allows disabling for minimal output
- Backward compatible: existing calls work unchanged

### Module 2: Documentation Updates

**File**: `extensions/flowise/BEST_PRACTICES.md`

**Add New Section** (after line 1018, before troubleshooting):

```markdown
---

## Mermaid Diagram Generation

Context Foundry automatically generates beautiful Mermaid diagrams for Flowise workflows.

### Features

**✅ Authentic Flowise Styling**
- 12+ node types with correct shapes and colors
- Emoji icons for quick visual identification
- Intelligent layout direction (TD vs LR based on complexity)

**✅ Flow Metadata Badges**
- Total nodes count
- Agent count
- Complexity level (Simple/Moderate/Complex)
- Memory and tools indicators

**✅ Interactive Documentation**
- Collapsible agent details table
- Visual node type legend
- Emoji-enhanced readability

### Generated Output Example

```markdown
![Nodes](https://img.shields.io/badge/Nodes-8-blue) ![Agents](https://img.shields.io/badge/Agents-5-green) ![Complexity](https://img.shields.io/badge/Complexity-Moderate-yellow)

---

**Total Nodes**: 8 | **Agents**: 5 | **Complexity**: Moderate

[Mermaid diagram here]

<details>
<summary><b>🔍 View Agent Details</b></summary>

| Agent | Type | Description |
|-------|------|-------------|
| 🚀 Start | Start | Workflow entry point |
| 🎯 Router | ConditionAgent | Intent detection |
| 🤖 Technical | Agent | Technical support |
...

</details>

### 🎨 Node Type Legend
| Icon | Type | Description |
|------|------|-------------|
| 🚀 | Start | Entry point |
| 🤖 | Agent | AI agent |
...
```

### CLI Usage

**Basic usage** (all features enabled by default):
```bash
python3 mermaid_generator.py workflow.json DIAGRAM.md
```

**Custom options**:
```bash
# Minimal output (no badges, no legend)
python3 mermaid_generator.py workflow.json DIAGRAM.md --no-interactive

# Badges only
python3 mermaid_generator.py workflow.json DIAGRAM.md --badges

# Legend only
python3 mermaid_generator.py workflow.json DIAGRAM.md --legend
```

### Layout Direction

The generator intelligently chooses graph direction:

**Top-Down (TD)** - Simple flows:
- ≤5 nodes
- Linear structure
- Easy to follow vertically

**Left-Right (LR)** - Complex flows:
- >10 nodes
- Multiple branches (≥2 branching points)
- Better horizontal space utilization

### Embedding in README

The orchestrator automatically embeds diagrams prominently in README:

```markdown
# Project Name

Description...

## 📊 Workflow Architecture

**[View Full Workflow Diagram →](./WORKFLOW-DIAGRAM.md)**

[Badges here]

[Mermaid diagram here]

[Interactive details here]

---

## Overview
...
```

### Node Type Reference

All 14 supported Flowise node types render with authentic colors:

| Type | Shape | Color | Icon |
|------|-------|-------|------|
| Start | Stadium | Green | 🚀 |
| Agent | Rectangle | Teal | 🤖 |
| ConditionAgent | Hexagon | Pink | 🎯 |
| LLM | Rounded | Blue | 💬 |
| Tool | Trapezoid | Brown | 🔧 |
| ExecuteFlow | Rectangle | Olive | ▶️ |
| CustomFunction | Rectangle | Purple | ⚙️ |
| HTTP | Rectangle | Red | 🌐 |
| HumanInput | Hexagon | Indigo | 👤 |
| DirectReply | Rectangle | Mint | 💭 |
| Loop | Stadium | Coral | 🔄 |
| Iteration | Rectangle | Lavender | 🔁 |
| StickyNote | Rectangle | Yellow | 📝 |
| Condition | Diamond | Orange | 🔀 |

---
```

**Rationale**: Comprehensive documentation for users and future maintainers

### Module 3: Orchestrator Prompt Update

**File**: `tools/orchestrator_prompt.txt`

**Lines to Modify**: 1424-1485 (Flowise diagram generation section)

**Current** (approximate line 1450):
```
python3 /Users/name/homelab/context-foundry/extensions/flowise/mermaid_generator.py \
  <workflow-name>.json \
  WORKFLOW-DIAGRAM.md \
  --interactive
```

**Update to**:
```
python3 /Users/name/homelab/context-foundry/extensions/flowise/mermaid_generator.py \
  <workflow-name>.json \
  WORKFLOW-DIAGRAM.md \
  --interactive \
  --badges \
  --legend
```

**Rationale**: Enable all new features by default in orchestrator

## Implementation Steps

1. **Fix generate_mermaid() critical bug**
   - Replace `shape_color` tuple access with individual field access
   - Add emoji to node labels
   - Use dynamic layout direction

2. **Enhance generate_interactive_section()**
   - Add badges parameter
   - Add legend parameter
   - Include metadata section
   - Use emojis in agent table

3. **Update main() CLI**
   - Add `--badges`, `--legend`, `--no-interactive` flags
   - Make `--interactive` default
   - Update help text

4. **Update BEST_PRACTICES.md**
   - Add Mermaid Diagram Generation section
   - Include examples and reference tables

5. **Update orchestrator_prompt.txt**
   - Add `--badges --legend` to CLI invocation

## Testing Requirements

### Unit Testing (Manual)

**Test 1: Simple Flow (TD Layout)**
```bash
python3 extensions/flowise/mermaid_generator.py \
  extensions/flowise/templates/Simple\ Agent\ Agents.json \
  /tmp/test-simple.md
```

**Verify**:
- Layout is `graph TD`
- All nodes have emojis: `🚀 Start`, `🎯 Router`, `🤖 Agent`
- Badges display correctly
- Legend includes all node types in the flow

**Test 2: Complex Flow (LR Layout)**
```bash
python3 extensions/flowise/mermaid_generator.py \
  extensions/flowise/templates/Warehouse\ Operations\ Agents.json \
  /tmp/test-complex.md
```

**Verify**:
- Layout is `graph LR` (8+ agents = complex)
- All node types render with correct shapes/colors
- Agent count badge shows correct number

**Test 3: All 14 Templates**
```bash
for template in extensions/flowise/templates/*.json; do
    echo "Testing: $template"
    python3 extensions/flowise/mermaid_generator.py "$template" /tmp/test-output.md
    if [ $? -ne 0 ]; then
        echo "FAILED: $template"
        exit 1
    fi
done
echo "✅ All 14 templates passed"
```

**Test 4: CLI Flags**
```bash
# Test --badges only
python3 mermaid_generator.py template.json /tmp/test.md --badges

# Test --legend only
python3 mermaid_generator.py template.json /tmp/test.md --legend

# Test --no-interactive
python3 mermaid_generator.py template.json /tmp/test.md --no-interactive
```

### Integration Testing

**Test 5: GitHub Markdown Rendering**
1. Generate diagram for Simple Agent template
2. Copy output to GitHub README
3. Verify:
   - Mermaid renders correctly
   - Emojis display
   - Badges load (shields.io URLs)
   - Interactive details expand/collapse

## Success Criteria

✅ `generate_mermaid()` uses new data structure (no KeyError)
✅ All node labels include emojis
✅ Layout direction is dynamic (TD for simple, LR for complex)
✅ Interactive section includes badges and legend
✅ CLI has `--badges`, `--legend`, `--no-interactive` flags
✅ All 14 template flows generate without errors
✅ Documentation updated with examples
✅ Orchestrator prompt updated with new flags
✅ Backward compatible (existing calls work)

## Risk Mitigation

**Risk**: Emoji rendering fails in some Markdown viewers
**Mitigation**: Test with GitHub (primary target), fall back gracefully

**Risk**: Badge URLs malformed
**Mitigation**: Use `urllib.parse.quote()` for special characters

**Risk**: Breaking existing users
**Mitigation**: Make features default but allow disabling with `--no-*` flags

**Risk**: Layout detection chooses wrong direction
**Mitigation**: Tune thresholds based on test results (currently: 5 nodes = TD, 10+ = LR)

# Codebase Analysis Report

## Project Overview
- **Type**: Python tool enhancement (Flowise Mermaid diagram generator)
- **Languages**: Python
- **Architecture**: CLI tool for converting Flowise JSON workflows to Mermaid diagrams

## Key Files to Modify
- **Entry point**: `extensions/flowise/mermaid_generator.py` (448 lines)
- **Documentation**: `extensions/flowise/BEST_PRACTICES.md` (1022 lines)
- **Orchestrator**: `tools/orchestrator_prompt.txt` (lines 1424-1485 need updates)

## Current State Analysis

### What's Already Enhanced (Partial)
✅ **get_node_style()** function (lines 48-124):
   - Returns tuple: `(shape, color, emoji)` instead of `(shape, color)`
   - Has 12+ node types with authentic Flowise colors
   - Includes emoji mapping

✅ **extract_node_info()** function (lines 126-159):
   - Returns dict with separate keys: `shape`, `color`, `emoji`
   - No longer returns `shape_color` tuple

✅ **Helper functions added** (lines 188-312):
   - `extract_flow_metadata()` - extracts badges data
   - `detect_layout_direction()` - intelligently chooses TD vs LR
   - `generate_badges()` - creates GitHub-style badges
   - `generate_legend()` - creates node type legend

### What Still Needs Updates (Critical)
❌ **generate_mermaid()** function (lines 314-370):
   - Line 334: Still references `info["shape_color"]` which no longer exists
   - Should use `info["shape"]`, `info["color"]`, `info["emoji"]` separately
   - Line 329: Hardcoded `"graph TD"` - should use `detect_layout_direction()`
   - Node labels don't include emojis

❌ **generate_interactive_section()** function (lines 373-399):
   - Doesn't include badges at top
   - Doesn't include flow metadata
   - Doesn't include legend
   - Agent details table doesn't use emojis

❌ **main()** CLI (lines 402-447):
   - Missing `--badges` flag
   - Missing `--legend` flag
   - `--interactive` not default

## Code to Modify

### Task Breakdown

**File 1: extensions/flowise/mermaid_generator.py**
- Fix `generate_mermaid()` to use new data structure
- Add emoji to node labels
- Use `detect_layout_direction()` for graph direction
- Enhance `generate_interactive_section()` with badges and legend
- Update `main()` CLI with new flags

**File 2: extensions/flowise/BEST_PRACTICES.md**
- Document new mermaid generator features
- Add section on diagram generation best practices
- Include examples of badges and legends

**File 3: tools/orchestrator_prompt.txt (lines 1424-1485)**
- Update CLI invocation to include `--badges --legend`
- Ensure README embedding includes badges prominently

## Dependencies
- No new dependencies needed
- Current dependencies (requirements.txt): fastmcp, nest-asyncio, tiktoken

## Test Strategy
- Test with all 14 template flows in `extensions/flowise/templates/`
- Verify all node types render correctly
- Check badges display properly
- Validate legend includes all node types
- Ensure layout direction is intelligent (TD for simple, LR for complex)

## Risks
1. **Breaking change**: `shape_color` tuple no longer exists - must update all references
2. **Layout detection**: May need tuning for optimal TD vs LR selection
3. **Emoji rendering**: GitHub markdown should support emojis natively
4. **Badge URL encoding**: Special characters in badge values need proper escaping

## Approach
1. Fix the critical bug in `generate_mermaid()` (references non-existent `shape_color`)
2. Add emojis to node labels
3. Implement dynamic layout direction
4. Enhance interactive section with metadata
5. Update CLI flags
6. Test with real Flowise templates
7. Update documentation

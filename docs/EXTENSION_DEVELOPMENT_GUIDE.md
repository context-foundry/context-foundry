# Context Foundry Extension Development Guide

**Version:** 2.3.0+
**Last Updated:** 2025-11-17

## Table of Contents

1. [Overview](#overview)
2. [Architecture](#architecture)
3. [Canonical Project Contract](#canonical-project-contract)
4. [Quick Start](#quick-start)
5. [Phase Integration](#phase-integration)
6. [Pattern Training](#pattern-training)
7. [Testing & Validation](#testing--validation)
8. [Reference Examples](#reference-examples)

---

## Overview

### What are Extensions?

Context Foundry extensions enable specialized support for specific frameworks, platforms, or project types. Each extension provides:

- **Detection logic** to identify project types
- **Domain-specific patterns** and best practices
- **Phase-specific guidance** for Scout, Architect, Builder, Tester, and Docs phases
- **Template projects** and code samples

### When to Create an Extension

Create an extension when:

- You're building multiple projects of the same type (e.g., Roblox games, Flowise workflows)
- The domain has specific patterns, anti-patterns, or security concerns
- Standard Context Foundry patterns aren't sufficient
- You want to train CF on specialized knowledge

**Don't create an extension if:**

- It's a one-off project type
- Patterns can be captured in the global codex alone
- The domain is already well-covered by existing extensions

### Extension Philosophy

Context Foundry uses **convention over configuration**:

- No central registry or manifest files
- Extensions self-register via directory presence
- Detection is automatic and graceful (no crashes on errors)
- Complete isolation between extensions

---

## Architecture

### Two-Tier Pattern Storage

Context Foundry uses a dual pattern system:

#### Tier 1: Global Codex (SQLite Database)

**Location:** `~/.context-foundry/patterns/codex.db`

**Purpose:** Shared knowledge across ALL projects

**Schema:**
```sql
knowledge_entries:
  - id (TEXT PRIMARY KEY)
  - type (TEXT: "issue", "pattern", "learning", "metric")
  - category (TEXT: namespace like "roblox", "flowise", "react")
  - title, description
  - severity (LOW/MEDIUM/HIGH/CRITICAL)
  - confidence (0.0-1.0)
  - frequency (usage counter)
  - project_types (comma-separated: "roblox-game,roblox-plugin")
  - tags (comma-separated)
  - metadata_json (flexible JSON data)
  - status (active/deprecated/superseded)
```

**Access:**
```python
from context_foundry.codex import KnowledgeStore

store = KnowledgeStore()
patterns = store.search_by_type("pattern", category="roblox")
```

#### Tier 2: Extension-Specific Patterns (JSON Files)

**Location:** `/extensions/{extension_name}/patterns/*.json`

**Purpose:** Extension-only detailed templates, examples, configurations

**Example:**
```json
{
  "version": "1.0",
  "patterns": [
    {
      "pattern_id": "unique-id",
      "category": "game-genre",
      "description": "...",
      "code_templates": {...},
      "examples": [...]
    }
  ]
}
```

### Detection → Codex → Orchestrator Flow

```
1. Project Scan (tools/mcp_utils/project_detection.py)
   ├─→ Loads all extension detectors
   ├─→ Runs detection on project directory
   └─→ Returns: {project_type, extension_metadata, confidence}

2. Orchestrator Reads CONFIGURATION
   ├─→ Checks for extension flags (e.g., roblox_project: True)
   └─→ Conditionally injects extension-specific prompts

3. Phase Execution
   ├─→ Scout: Queries codex by category + project_types
   ├─→ Architect: Applies patterns from codex + extension JSON
   ├─→ Builder: Uses code templates and best practices
   ├─→ Tester: Runs extension-specific validation
   └─→ Docs: Generates extension-specific documentation

4. Feedback Loop
   ├─→ Track pattern usage (increment frequency)
   ├─→ Record project success/failure
   └─→ Update codex confidence scores
```

### Isolation Guarantees

Extensions are **completely isolated**:

1. **Independent directories** - `/extensions/flowise/` and `/extensions/roblox/` share nothing
2. **Graceful ImportError handling** - Missing extensions don't crash detection
3. **Codex namespacing** - `category` field prevents collisions
4. **Conditional injection** - Prompts only active when extension detected
5. **No shared state** - Each extension manages its own patterns

**Critical:** All extension-specific prompts MUST be wrapped in detection flags:

```
if roblox_project: True:
    [inject Roblox guidance]
```

This prevents cross-contamination (e.g., Roblox patterns appearing in web app builds).

---

## Canonical Project Contract

Every extension MUST define what it produces. This contract ensures repeatability and sets clear expectations.

### Contract Checklist

Create `/extensions/{extension}/docs/ARTIFACT_CONTRACT.md` answering:

| Question | Example (Roblox) | Example (Flowise) |
|----------|------------------|-------------------|
| **Primary artifact** | `.rbxlx` place file | `.json` workflow |
| **Run locally** | Open in Roblox Studio, press Play | Import into Flowise UI |
| **Minimum toolchain** | Rojo ≥7.x, Stylua ≥0.20 | Node.js ≥18, Flowise ≥1.4 |
| **Deploy phase** | Build to `dist/`, document manual publish | Save JSON, document Flowise import |
| **Output location** | `dist/Game.rbxlx` | Root: `workflow-name.json` |

### Version Hints

**Include version information** even if loose:

```
Tested with:
- Rojo 7.4.0 (https://rojo.space)
- Stylua 0.20.0 (cargo install stylua)
- Selene 0.27.1 (cargo install selene)
- luau-analyze (from Roblox Studio distribution)
```

This prevents "works on my machine" issues when tool versions diverge.

### Directory Structure Template

Document the **exact** expected structure:

```
# Roblox Game (Rojo-based)
/
├── default.project.json
├── dist/
│   └── Game.rbxlx
├── src/
│   ├── ServerScriptService/
│   ├── ReplicatedStorage/
│   ├── StarterPlayer/
│   └── Workspace/
└── README_ROBLOX.md

# Flowise Workflow
/
├── workflow-name.json
├── diagram.mmd
└── README.md
```

---

## Quick Start

### Minimum Required Structure

```
/extensions/your_extension/
├── __init__.py                      # Python package marker
├── detector.py                      # REQUIRED: Project detection
├── extensions_loader.py             # REQUIRED: Safe loading interface
├── patterns/
│   └── your-expertise.json          # Pattern library
└── README.md                        # Extension overview
```

### Recommended Full Structure

```
/extensions/your_extension/
├── __init__.py
├── detector.py
├── extensions_loader.py
├── analyzer.py                      # Optional: Pattern extraction tool
│
├── patterns/
│   ├── your-expertise.json          # Main patterns
│   └── templates.json               # Code templates
│
├── prompts/                         # Phase-specific prompts
│   ├── SCOUT-PROJECT-ASSESSMENT.md
│   ├── ARCHITECT-SYSTEMS.md
│   ├── BUILDER-BEST-PRACTICES.md
│   ├── TESTER-STRATEGY.md
│   └── DOCS-README-GUIDE.md
│
├── templates/                       # Reference implementations
│   └── basic-project/
│
├── integration/                     # Integration hooks
│   ├── mcp_server_hook.py           # Detection code snippet
│   └── orchestrator_injection_snippet.txt
│
├── docs/
│   └── ARTIFACT_CONTRACT.md         # Project contract
│
├── tests/
│   ├── test_detector.py
│   ├── test_patterns.py
│   └── test_integration.py
│
└── README.md
```

### Step-by-Step Creation

1. **Create directory structure:**
   ```bash
   mkdir -p extensions/your_extension/{docs,patterns,prompts,templates,integration,tests}
   touch extensions/your_extension/__init__.py
   ```

2. **Implement detector.py:**
   ```python
   from pathlib import Path
   from typing import Dict, Any

   def detect_your_project(directory: Path) -> Dict[str, Any]:
       """
       Detect your project type.

       Returns:
           is_your_type: bool
           project_type: str (e.g., "your-game", "your-app")
           project_subtype: str (optional variant)
           confidence: "high" | "medium" | "low"
           complexity: "simple" | "moderate" | "complex"
       """
       # Check for indicators
       has_config = (directory / "your.config.json").exists()
       has_source = (directory / "src").exists()

       if not (has_config or has_source):
           return {"is_your_type": False}

       return {
           "is_your_type": True,
           "project_type": "your-app",
           "confidence": "high",
           "complexity": "moderate"
       }
   ```

3. **Implement extensions_loader.py:**
   ```python
   from pathlib import Path
   from typing import Dict, Optional, Any
   import json

   def load_extension_detectors() -> Dict[str, Any]:
       """Load detector modules."""
       try:
           from . import detector
           return {"your_extension": detector}
       except ImportError:
           return {}

   def load_extension_patterns(extension_name: str = "your_extension") -> Optional[Dict]:
       """Load pattern JSON files."""
       try:
           patterns_dir = Path(__file__).parent / "patterns"
           pattern_file = patterns_dir / "your-expertise.json"

           if pattern_file.exists():
               with open(pattern_file) as f:
                   return json.load(f)
       except Exception:
           pass
       return None

   def extension_exists(extension_name: str = "your_extension") -> bool:
       """Check if extension is available."""
       return Path(__file__).parent.exists()
   ```

4. **Create patterns/your-expertise.json:**
   ```json
   {
     "version": "1.0",
     "patterns": [
       {
         "pattern_id": "your-basic-pattern",
         "category": "architecture",
         "description": "Basic project structure",
         "applies_to": ["your-app"],
         "best_practices": [
           "Use X for Y",
           "Avoid Z in production"
         ]
       }
     ],
     "common_issues": [
       {
         "issue_id": "your-security-issue",
         "severity": "HIGH",
         "description": "Always validate input X",
         "solution": "Use validation library Y"
       }
     ]
   }
   ```

5. **Create integration hooks** (see [Phase Integration](#phase-integration))

6. **Write tests** (see [Testing & Validation](#testing--validation))

---

## Phase Integration

### Phase-to-Prompt Mapping Table

Every extension should provide phase-specific guidance:

| Phase | Required? | Purpose | Typical Prompts |
|-------|-----------|---------|-----------------|
| **Scout** | Yes | Research & assessment | `SCOUT-PROJECT-ASSESSMENT.md` |
| **Architect** | Yes | System design | `ARCHITECT-SYSTEMS.md` |
| **Builder** | Yes | Implementation standards | `BUILDER-BEST-PRACTICES.md` |
| **Tester** | Yes | Validation strategy | `TESTER-STRATEGY.md` |
| **Docs** | Yes | Documentation generation | `DOCS-README-GUIDE.md` |

### Anchor-Based Injection (NOT Line Numbers)

**Problem:** Line numbers drift as `orchestrator_prompt.txt` evolves.

**Solution:** Use anchor comments for stable injection points.

#### Adding Anchors to Orchestrator

File: `tools/orchestrator_prompt.txt`

Add anchor comments at each phase:

```
# Scout phase section (~line 545)
# === YOUR-EXTENSION-SCOUT-START ===
# Your extension will inject here
# === YOUR-EXTENSION-SCOUT-END ===

# Architect phase section (~line 790)
# === YOUR-EXTENSION-ARCHITECT-START ===
# Your extension will inject here
# === YOUR-EXTENSION-ARCHITECT-END ===

# Builder phase section (~line 1053)
# === YOUR-EXTENSION-BUILDER-START ===
# Your extension will inject here
# === YOUR-EXTENSION-BUILDER-END ===

# Tester phase section
# === YOUR-EXTENSION-TESTER-START ===
# Your extension will inject here
# === YOUR-EXTENSION-TESTER-END ===

# Docs phase section
# === YOUR-EXTENSION-DOCS-START ===
# Your extension will inject here
# === YOUR-EXTENSION-DOCS-END ===
```

#### Injection Snippet Template

File: `integration/orchestrator_injection_snippet.txt`

```
# === YOUR-EXTENSION-SCOUT-START ===
**YOUR EXTENSION CHECK** (CONDITIONAL)

If CONFIGURATION shows your_project: True:

🚨 **YOUR PROJECT TYPE DETECTED** 🚨

- Project Type: {your_project_type}
- Subtype: {project_subtype}
- Complexity: {complexity}

**This is a [YOUR TYPE] project, NOT a [OTHER TYPE]**

**DO NOT research:**
❌ [Things to avoid researching]

**DO research:**
✅ [Domain-specific things to research]

[Load detailed guidance from extensions/your_extension/prompts/SCOUT-PROJECT-ASSESSMENT.md]

# === YOUR-EXTENSION-SCOUT-END ===
```

**CRITICAL:** All injections MUST be wrapped in detection flags:

```
If CONFIGURATION shows your_project: True:
    [extension-specific guidance]
```

This prevents cross-contamination where extension prompts affect unrelated project types.

### MCP Server Detection Hook

File: `integration/mcp_server_hook.py`

Contains code to add to `tools/mcp_utils/project_detection.py`:

```python
# ═══════════════════════════════════════════════════════════════════
# YOUR_EXTENSION EXTENSION HOOK
# ═══════════════════════════════════════════════════════════════════
try:
    cf_base = Path(__file__).parent.parent.parent
    ext_path = cf_base / "extensions" / "your_extension"

    if ext_path.exists():
        ext_parent = str(ext_path.parent)
        if ext_parent not in sys.path:
            sys.path.insert(0, ext_parent)

        from your_extension import extensions_loader
        detectors = extensions_loader.load_extension_detectors()

        if detectors and "your_extension" in detectors:
            detection = detectors["your_extension"].detect_your_project(directory)

            if detection.get("is_your_type"):
                result["your_project"] = True
                result["your_project_type"] = detection["project_type"]
                result["project_type"] = detection["project_type"]
                result["confidence"] = detection.get("confidence", "high")

                # Add language if applicable
                if "your_language" not in result["languages"]:
                    result["languages"].append("your_language")

except ImportError:
    pass  # Graceful degradation
# ═══════════════════════════════════════════════════════════════════
```

---

## Pattern Training

### Populating the Global Codex

Create a bootstrap script to import extension patterns into the global codex:

**File:** `scripts/bootstrap_your_extension_patterns.py`

```python
#!/usr/bin/env python3
"""
Bootstrap patterns into global codex.
Idempotent: Safe to re-run after pattern updates.
"""

from context_foundry.codex import KnowledgeStore, KnowledgeEntry, KnowledgeType, Severity
import json
from pathlib import Path

def bootstrap_patterns():
    store = KnowledgeStore("~/.context-foundry/patterns/codex.db")

    # Load extension patterns
    patterns_file = Path("extensions/your_extension/patterns/your-expertise.json")
    with open(patterns_file) as f:
        data = json.load(f)

    new_count = 0
    updated_count = 0

    # Add patterns
    for pattern in data.get("patterns", []):
        entry_id = pattern["pattern_id"]
        existing = store.get_entry(entry_id)

        if existing:
            # Update existing
            store.update_entry(entry_id, metadata=pattern)
            updated_count += 1
        else:
            # Create new
            entry = KnowledgeEntry(
                id=entry_id,
                type=KnowledgeType.PATTERN,
                category="your_extension",  # IMPORTANT: namespace
                title=pattern["description"],
                project_types=pattern.get("applies_to", []),
                tags=["your_extension"] + pattern.get("tags", []),
                confidence=0.8,
                metadata=pattern
            )
            store.add_entry(entry)
            new_count += 1

    # Add common issues
    for issue in data.get("common_issues", []):
        entry_id = issue["issue_id"]
        existing = store.get_entry(entry_id)

        if existing:
            store.update_entry(entry_id, metadata=issue)
            updated_count += 1
        else:
            entry = KnowledgeEntry(
                id=entry_id,
                type=KnowledgeType.ISSUE,
                category="your_extension",
                title=issue["description"],
                severity=Severity[issue["severity"]],
                project_types=["your-app"],
                tags=["your_extension"],
                metadata=issue
            )
            store.add_entry(entry)
            new_count += 1

    print(f"✅ Bootstrap complete: {new_count} new, {updated_count} updated (category=your_extension)")

if __name__ == "__main__":
    bootstrap_patterns()
```

**Run once after creating extension:**
```bash
python scripts/bootstrap_your_extension_patterns.py
```

### Category Namespacing Best Practices

Always use consistent categories:

```python
# Good: Clear namespacing
entry = KnowledgeEntry(
    category="roblox",
    project_types=["roblox-game", "roblox-plugin"],
    tags=["roblox", "security"]
)

# Bad: Generic category (collision risk)
entry = KnowledgeEntry(
    category="game",  # Too broad
    project_types=["game"],
    tags=["generic"]
)
```

### Extension-Specific Patterns

Use JSON files in `/patterns/` for:

- **Detailed code templates** (too large for codex)
- **Configuration examples**
- **Complete workflows or blueprints**
- **Domain-specific metadata**

Example structure:
```json
{
  "version": "1.0",
  "patterns": [
    {
      "pattern_id": "unique-id",
      "category": "architecture",
      "applies_to": ["your-app:variant"],
      "description": "...",
      "constraints": {
        "must_use_tool_x": true
      },
      "directory_layout": {
        "src/components": ["ComponentA", "ComponentB"]
      },
      "code_templates": {
        "component_a": "templates/ComponentA.ext"
      }
    }
  ]
}
```

**Template paths:** Relative to `extensions/your_extension/templates/`

---

## Testing & Validation

### Unit Tests

**File:** `extensions/your_extension/tests/test_detector.py`

```python
import pytest
from pathlib import Path
from your_extension.detector import detect_your_project

def test_detects_valid_project(tmp_path):
    """Verify detection of valid project."""
    # Create test project structure
    (tmp_path / "your.config.json").write_text("{}")

    result = detect_your_project(tmp_path)

    assert result["is_your_type"] is True
    assert result["project_type"] == "your-app"
    assert result["confidence"] == "high"

def test_rejects_invalid_project(tmp_path):
    """Verify non-detection when indicators missing."""
    result = detect_your_project(tmp_path)

    assert result["is_your_type"] is False

def test_subtype_detection(tmp_path):
    """Verify project subtype detection."""
    (tmp_path / "advanced.config.json").write_text("{}")

    result = detect_your_project(tmp_path)

    assert result["project_subtype"] == "advanced"
```

**File:** `extensions/your_extension/tests/test_patterns.py`

```python
import pytest
import json
from pathlib import Path
from your_extension.extensions_loader import load_extension_patterns

def test_loads_patterns():
    """Verify pattern JSON loads without errors."""
    patterns = load_extension_patterns()

    assert patterns is not None
    assert "patterns" in patterns
    assert len(patterns["patterns"]) > 0

def test_pattern_structure():
    """Verify patterns have required fields."""
    patterns = load_extension_patterns()

    for pattern in patterns["patterns"]:
        assert "pattern_id" in pattern
        assert "category" in pattern
        assert "description" in pattern
        assert "applies_to" in pattern
```

**File:** `extensions/your_extension/tests/test_integration.py`

```python
import pytest
import subprocess
from pathlib import Path

def test_end_to_end_build(tmp_path):
    """Test full build pipeline."""
    # This requires Context Foundry to be installed
    # Generate a basic project
    # Verify artifact is created
    pass  # Implement based on your extension
```

### Integration Test Project

Create a test project for CI validation:

**Directory:** `/test_your_extension_project/`

```
test_your_extension_project/
├── your.config.json
├── src/
└── .claude-code
```

**File:** `.claude-code`
```
Build a basic [YOUR TYPE] project with [FEATURES]
```

This allows automated testing:
```bash
cd test_your_extension_project
claude-code --autonomous --task "$(cat .claude-code)"
# Verify output
```

### Local Smoke Test

**File:** `tools/run_extension_smoke_test.py`

```python
#!/usr/bin/env python3
"""
Local smoke test for extensions.
Usage: python tools/run_extension_smoke_test.py --extension your_extension
"""

import argparse
import subprocess
import sys
from pathlib import Path

def smoke_test_extension(extension_name: str) -> bool:
    """
    Run smoke test for extension:
    1. Verify directory exists
    2. Test detector import
    3. Test pattern loading
    4. Optionally: Generate test project

    Returns:
        True if all tests pass
    """
    print(f"Running smoke test for {extension_name}...")

    # Check directory
    ext_dir = Path(f"extensions/{extension_name}")
    if not ext_dir.exists():
        print(f"❌ Extension directory not found: {ext_dir}")
        return False

    print(f"✅ Extension directory exists: {ext_dir}")

    # Test detector import
    try:
        sys.path.insert(0, str(ext_dir.parent))
        mod = __import__(extension_name)
        detector = mod.extensions_loader.load_extension_detectors()
        print(f"✅ Detector loaded: {detector}")
    except Exception as e:
        print(f"❌ Failed to load detector: {e}")
        return False

    # Test pattern loading
    try:
        patterns = mod.extensions_loader.load_extension_patterns()
        if patterns:
            print(f"✅ Patterns loaded: {len(patterns.get('patterns', []))} patterns")
        else:
            print("⚠️  No patterns found")
    except Exception as e:
        print(f"❌ Failed to load patterns: {e}")
        return False

    print(f"✅ Smoke test passed for {extension_name}")
    return True

if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--extension", required=True)
    args = parser.parse_args()

    success = smoke_test_extension(args.extension)
    sys.exit(0 if success else 1)
```

Run locally:
```bash
python tools/run_extension_smoke_test.py --extension your_extension
```

### Toolchain Failure Modes

Handle missing tools gracefully:

```python
import shutil

def run_your_tool():
    if shutil.which("your_tool"):
        result = subprocess.run(["your_tool", "args"])
        return result
    else:
        print("⚠️  your_tool not found - skipping check")
        # V1: Don't fail
        # V2: Optionally fail if config flag strict_toolchain=true
        return None
```

Document tool versions in ARTIFACT_CONTRACT.md:
```
Tested with:
- your_tool 1.2.3 (install: npm install -g your_tool)
```

---

## Reference Examples

### Flowise Extension

**Directory:** `/extensions/flowise/`

**Key Features:**
- Detects Flowise workflow JSON files
- Classifies flow types (multi-agent, RAG, workflow, chatbot)
- Enforces self-contained agent architecture
- Validates against 14 known failure patterns
- Generates Mermaid diagrams
- Exclusive build mode (JSON only, no code)

**Detection Logic:** `detector.py:detect_flowise_flow()`
- Checks for JSON with specific node structure
- Analyzes node types, edge count, complexity
- Returns rich metadata: node_count, agent_count, has_memory, has_tools

**Patterns:** `patterns/flowise-expertise.json`
- 14 template flows analyzed
- Node type frequency data
- Common issues and solutions

**Prompts:**
- `FLOWISE-STRUCTURE-AUTHORITY.md` - Architectural rules
- `AGENT-NODE-TEMPLATE.json` - Node configuration templates

### Roblox Extension

**Directory:** `/extensions/roblox/`

**Key Features:**
- Detects Rojo-based Luau projects
- First-class obby-checkpoints-coin-shop pattern
- Security-focused prompts (RemoteEvent validation)
- Static analysis integration (stylua, selene, luau-analyze)
- Builds to `.rbxlx` place file

**Detection Logic:** `detector.py:detect_roblox_project()`
- Checks for Rojo config (`default.project.json`)
- Secondary: Placefile detection (`.rbxl`, `.rbxlx`)
- Computes has_tests, complexity
- Prefers Rojo when both exist

**Patterns:** `patterns/roblox-expertise.json`
- Obby pattern with required systems
- Security patterns (RemoteEvent validation)
- DataStore best practices

**Prompts:**
- Security emphasis in all phases
- Server-authoritative architecture enforcement
- Luau type safety and best practices

---

## Checklist for New Extensions

Before deploying your extension, verify:

### Required Files
- [ ] `__init__.py` - Package marker
- [ ] `detector.py` - Detection logic implemented
- [ ] `extensions_loader.py` - Safe loading interface
- [ ] `patterns/your-expertise.json` - Pattern library
- [ ] `docs/ARTIFACT_CONTRACT.md` - Project contract defined
- [ ] `README.md` - Extension overview

### Integration
- [ ] Detection hook added to `tools/mcp_utils/project_detection.py`
- [ ] Anchor comments added to `tools/orchestrator_prompt.txt` (5 phases)
- [ ] All prompts wrapped in detection flags (`if your_project: True`)
- [ ] Bootstrap script created and run (`scripts/bootstrap_your_patterns.py`)

### Phase Prompts
- [ ] Scout prompt created
- [ ] Architect prompt created
- [ ] Builder prompt created
- [ ] Tester prompt created
- [ ] Docs prompt created

### Testing
- [ ] Unit tests for detector
- [ ] Unit tests for pattern loading
- [ ] Integration test (optional but recommended)
- [ ] Test project for CI validation
- [ ] Smoke test passes (`run_extension_smoke_test.py`)

### Isolation Verification
- [ ] Tested with unrelated project type (no cross-contamination)
- [ ] Tested with extension's project type (activates correctly)
- [ ] Tested with extension removed (graceful degradation)

### Documentation
- [ ] Artifact contract complete (all checklist items)
- [ ] Toolchain versions documented
- [ ] Build/run/test instructions clear
- [ ] Template projects included

---

## Future Enhancements

Ideas for extension system evolution:

### V2.4+ Features
- Extension versioning and compatibility checks
- Extension marketplace/registry
- Hot-reload extensions without restart
- Extension dependencies
- Cross-extension pattern sharing
- Extension metrics and analytics

### Advanced Patterns
- Multi-extension projects (e.g., Roblox + TypeScript)
- Extension composition and inheritance
- Dynamic pattern generation from project history
- Community pattern sharing via S3
- Automated pattern extraction from successful builds

---

## Getting Help

- **Documentation:** https://code.claude.com/docs
- **Issues:** https://github.com/anthropics/context-foundry/issues
- **Examples:** `/extensions/flowise/` and `/extensions/roblox/`
- **Patterns:** `~/.context-foundry/patterns/codex.db`

---

**Version History:**
- 2.3.0 - Initial guide with Flowise and Roblox examples
- Future - TBD

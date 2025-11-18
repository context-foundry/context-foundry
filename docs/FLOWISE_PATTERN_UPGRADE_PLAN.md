# Flowise Pattern System Upgrade - Implementation Plan

**Date**: 2025-11-17
**Goal**: Transform Flowise from template-based to pattern-driven workflow matching Roblox's reliability

---

## Executive Summary

Upgrade Flowise extension to use the same pattern-driven, Codex-backed workflow that keeps the Roblox extension reliable. This involves converting scattered Flowise knowledge (32 templates + 6,984 lines of markdown) into structured pattern data, integrating with Context Codex, and enabling the bootstrap → build → merge → S3 sharing loop.

**Current State**:
- Flowise: 32 template files + extensive documentation, NO curated pattern library
- Roblox: 5 curated patterns + 4 common issues in structured JSON, full Codex integration

**Target State**:
- Flowise matches Roblox architecture: curated patterns → bootstrap → Codex → S3 sync
- Scout/Architect/Test phases query Codex for patterns (not read markdown docs)
- Pattern IDs referenced in prompts and validation (same as Roblox)

---

## Research Findings Summary

### Roblox Pattern System (Reference Model)

**Pattern Library**: `extensions/roblox/patterns/roblox-expertise.json` (525 lines)
- 5 curated patterns (obby-checkpoints-coin-shop, module-structure, datastore-best-practices, remote-events-security, beginner-foundations)
- 4 common issues (remote-security-001, datastore-failure-001, performance-001, memory-leak-001)
- **Total: 9 knowledge entries**

**Bootstrap Script**: `scripts/bootstrap_roblox_patterns.py` (171 lines)
- Loads JSON → imports to Codex via KnowledgeStore
- Idempotent (safe to re-run)
- CLI UX with emoji progress indicators

**Test Suite**: `extensions/roblox/tests/test_patterns.py` (71 lines)
- Validates JSON loads without errors
- Validates required fields (pattern_id, required_systems, etc.)
- Validates severity enums for issues

**Orchestrator Integration**: 6 dedicated sections in prompt
- Scout: Query Codex for patterns by ID
- Architect: Reference patterns in architecture.md
- Builder/Tester/Docs: Pattern-aware code generation

### Flowise Current State

**Documentation-Based Knowledge**:
- AGENT_PATTERN_REFERENCE.md: 3,495 lines, 13 AFv2 patterns + 7 design patterns
- FAILURE_PATTERNS.md: 3,489 lines, 15 anti-patterns
- **Total: 35+ documented patterns + 15 anti-patterns**

**Template Files**:
- 13 AFv2 pattern templates in `templates/afv2-patterns/`
- 19 real Flowise workflow exports
- 13 prompt templates
- **Total: 32 template JSON files**

**Orchestrator Integration**: 4 dedicated sections
- Scout/Architect/Builder/Docs: Read markdown docs (not Codex queries)

### Gap Analysis

| Feature | Roblox | Flowise | Gap |
|---------|--------|---------|-----|
| Curated Pattern Library | ✅ roblox-expertise.json | ❌ No curated library | **CRITICAL** |
| Bootstrap Script | ✅ bootstrap_roblox_patterns.py | ❌ No bootstrap | **HIGH** |
| Codex Integration | ✅ Query patterns during builds | ⚠️ Docs only | **HIGH** |
| Test Suite | ✅ test_patterns.py | ❌ No pattern tests | **MEDIUM** |
| S3 Sync Ready | ✅ JSON format compatible | ❌ Templates not in JSON | **MEDIUM** |

---

## Implementation Plan

### Phase 1: Create Curated Pattern Library

**File**: `extensions/flowise/patterns/flowise-expertise.json`

**Content to Migrate**:

1. **13 AFv2 Workflow Patterns** (from AGENT_PATTERN_REFERENCE.md):
   - afv2-chaining-pattern - Sequential processing pipeline
   - afv2-parallel-pattern - Multi-source research
   - afv2-routing-pattern - Intent classification
   - afv2-iteration-pattern - Quality refinement loop
   - afv2-looping-pattern - Validation retry
   - afv2-hierarchy-pattern - Task delegation
   - afv2-batch-processing - Array processing
   - afv2-conditional-retry - Score-based validation
   - afv2-api-integration - HTTP calls
   - afv2-rag-pattern - Document Q&A
   - afv2-smart-calculator - Cost optimization
   - afv2-doc-qa-confidence - Confidence routing
   - afv2-data-pipeline-etl - ETL validation

2. **15 Common Issues** (from FAILURE_PATTERNS.md):
   - flowise-missing-inputparams (Pattern #8) - CRITICAL
   - flowise-meta-description (Pattern #1) - CRITICAL
   - flowise-separate-configs (Pattern #3) - CRITICAL
   - flowise-incorrect-tool-structure (Pattern #6) - CRITICAL
   - flowise-missing-start-node (Pattern #15) - CRITICAL
   - flowise-disconnected-agents (Pattern #4) - MEDIUM
   - flowise-phantom-tools (Pattern #5) - HIGH
   - flowise-incomplete-scenarios (Pattern #7) - HIGH
   - flowise-missing-mermaid (Pattern #9) - HIGH
   - flowise-hil-invalid-params (Pattern #10) - MEDIUM
   - flowise-hil-missing-fields (Pattern #11) - HIGH
   - flowise-modular-prompt-tools (Pattern #12) - MEDIUM
   - flowise-variable-format (Pattern #13) - HIGH
   - flowise-node-type-mismatch (Pattern #14) - MEDIUM
   - flowise-missing-agent-nodes (Pattern #2) - HIGH

**Schema Structure** (based on Roblox template):

```json
{
  "version": "1.0.0",
  "last_updated": "2025-11-17",
  "description": "Flowise AgentFlow v2 workflow patterns, best practices, and anti-patterns",

  "patterns": [
    {
      "pattern_id": "afv2-chaining-pattern",
      "category": "workflow-pattern",
      "applies_to": ["flowise-agentflow"],
      "description": "Sequential processing pipeline with artifact handoffs between agents",
      "confidence": 0.95,
      "frequency": 1,

      "node_structure": {
        "start_node": {...},
        "chain_agents": [...],
        "hil_gates": [...],
        "edges": [...]
      },

      "code_templates": {
        "start_node": "templates/afv2-patterns/01-chaining.json#L10-50",
        "chain_agent": "templates/afv2-patterns/01-chaining.json#L100-200"
      },

      "implementation_notes": [
        "Each chain agent outputs artifacts consumed by next agent",
        "Use state variables to track pipeline progress",
        "HIL gates for human review between critical stages"
      ],

      "use_cases": [
        "Document review → Analysis → Report generation",
        "Data extraction → Validation → Enrichment → Storage"
      ],

      "testing_checklist": [
        "Verify each agent receives previous agent's output",
        "Test HIL gate approval/rejection paths",
        "Validate final output contains all pipeline artifacts"
      ]
    }
  ],

  "common_issues": [
    {
      "issue_id": "flowise-missing-inputparams",
      "severity": "CRITICAL",
      "category": "node-structure",
      "description": "Agent nodes missing inputParams array, preventing UI editability",
      "frequency": 1,
      "confidence": 1.0,

      "symptoms": [
        "Agent node appears in workflow but cannot be edited",
        "Double-clicking agent node does nothing",
        "Node configuration panel blank or errors"
      ],

      "root_cause": "Builder omitted inputParams array from agent node data structure",

      "solution": "Every agent node MUST include complete inputParams array with 15+ fields",

      "code_fix": "// Add to agent node data:\n\"inputParams\": [\n  {\"label\": \"Agent Name\", \"name\": \"agentName\", \"type\": \"string\"},\n  // ... 14 more params\n]",

      "prevention": [
        "Use AGENT-NODE-TEMPLATE.json as reference for all agent nodes",
        "Validate inputParams array presence in Test phase",
        "Check inputParams count >= 15 fields"
      ],

      "related_patterns": ["afv2-routing-pattern", "afv2-hierarchy-pattern"]
    }
  ],

  "project_types": {
    "flowise-agentflow": {
      "description": "Flowise AgentFlow v2 multi-agent workflow",
      "typical_structure": ["nodes", "edges", "connections"],
      "common_patterns": ["afv2-routing-pattern", "afv2-chaining-pattern"]
    }
  },

  "tags": ["flowise", "agentflow-v2", "multi-agent", "workflow", "llm-orchestration"]
}
```

**Key Schema Fields**:

| Field | Type | Required | Purpose |
|-------|------|----------|---------|
| `pattern_id` | string | Yes | Unique identifier (kebab-case) |
| `category` | string | Yes | Pattern category (workflow-pattern, node-structure, integration, security) |
| `applies_to` | array[string] | Yes | Project types (e.g., "flowise-agentflow") |
| `description` | string | Yes | Human-readable summary |
| `confidence` | float | Yes | Confidence score 0.0-1.0 |
| `frequency` | int | Yes | Times seen/used |
| `node_structure` | object | No | Node/edge definitions |
| `code_templates` | object | No | Template file references |
| `implementation_notes` | array[string] | No | Implementation guidance |
| `use_cases` | array[string] | No | Real-world applications |
| `testing_checklist` | array[string] | No | QA validation items |

---

### Phase 2: Create Bootstrap Script

**File**: `scripts/bootstrap_flowise_patterns.py`

**Implementation** (mirror `bootstrap_roblox_patterns.py`):

```python
#!/usr/bin/env python3
"""
Bootstrap Flowise Patterns into Global Codex

Idempotent: Safe to re-run after pattern updates.

Usage:
    python3 scripts/bootstrap_flowise_patterns.py
"""

import sys
import json
from pathlib import Path

# Add Context Foundry to path
cf_root = Path(__file__).parent.parent
sys.path.insert(0, str(cf_root))

from context_foundry.codex import KnowledgeStore, KnowledgeEntry, KnowledgeType, Severity


def bootstrap_flowise_patterns():
    """Bootstrap Flowise patterns into global codex"""

    # Header
    print("=" * 70)
    print("Bootstrap Flowise Patterns")
    print("=" * 70)

    # Load pattern file
    patterns_file = cf_root / "extensions" / "flowise" / "patterns" / "flowise-expertise.json"

    if not patterns_file.exists():
        print(f"❌ Error: Pattern file not found: {patterns_file}")
        return False

    print(f"\n📂 Loading patterns from: {patterns_file}")

    try:
        with open(patterns_file, 'r', encoding='utf-8') as f:
            data = json.load(f)
    except json.JSONDecodeError as e:
        print(f"❌ Error: Invalid JSON in pattern file: {e}")
        return False

    # Initialize Codex
    codex_path = Path.home() / ".context-foundry" / "patterns" / "codex.db"
    print(f"💾 Codex database: {codex_path}")

    try:
        store = KnowledgeStore(str(codex_path))
    except Exception as e:
        print(f"❌ Error: Could not open codex database: {e}")
        return False

    # Import patterns
    new_count = 0
    updated_count = 0

    print("\n🎯 Importing patterns...")
    for pattern in data.get("patterns", []):
        pattern_id = pattern.get("pattern_id")
        if not pattern_id:
            print(f"⚠️  Warning: Pattern missing pattern_id, skipping")
            continue

        # Check if exists (idempotent)
        existing = None
        try:
            existing = store.get_entry(pattern_id)
        except:
            pass

        try:
            if existing:
                # Update existing
                store.update_entry(pattern_id, metadata=pattern)
                updated_count += 1
                print(f"  ✓ Updated: {pattern_id}")
            else:
                # Create new
                entry = KnowledgeEntry(
                    id=pattern_id,
                    type=KnowledgeType.PATTERN,
                    category="flowise",
                    title=pattern.get("description", pattern_id),
                    description=pattern.get("description", ""),
                    project_types=pattern.get("applies_to", ["flowise-agentflow"]),
                    tags=["flowise"] + pattern.get("category", "").split(),
                    confidence=pattern.get("confidence", 0.9),
                    frequency=pattern.get("frequency", 1),
                    metadata=pattern  # Store full pattern as metadata
                )
                store.add_entry(entry)
                new_count += 1
                print(f"  + Added: {pattern_id}")
        except Exception as e:
            print(f"  ✗ Error with {pattern_id}: {e}")

    # Import common issues
    print("\n🚨 Importing common issues...")
    for issue in data.get("common_issues", []):
        issue_id = issue.get("issue_id")
        if not issue_id:
            print(f"⚠️  Warning: Issue missing issue_id, skipping")
            continue

        existing = None
        try:
            existing = store.get_entry(issue_id)
        except:
            pass

        try:
            if existing:
                store.update_entry(issue_id, metadata=issue)
                updated_count += 1
                print(f"  ✓ Updated: {issue_id}")
            else:
                # Map severity string to enum
                severity_map = {
                    "LOW": Severity.LOW,
                    "MEDIUM": Severity.MEDIUM,
                    "HIGH": Severity.HIGH,
                    "CRITICAL": Severity.CRITICAL,
                }
                severity = severity_map.get(issue.get("severity", "MEDIUM"), Severity.MEDIUM)

                entry = KnowledgeEntry(
                    id=issue_id,
                    type=KnowledgeType.ISSUE,
                    category="flowise",
                    title=issue.get("description", issue_id),
                    description=issue.get("description", ""),
                    severity=severity,
                    project_types=["flowise-agentflow"],
                    tags=["flowise"] + [issue.get("category", "")],
                    confidence=issue.get("confidence", 0.9),
                    frequency=issue.get("frequency", 1),
                    metadata=issue  # Store full issue as metadata
                )
                store.add_entry(entry)
                new_count += 1
                print(f"  + Added: {issue_id}")
        except Exception as e:
            print(f"  ✗ Error with {issue_id}: {e}")

    # Summary
    print("\n" + "=" * 70)
    print(f"✅ Bootstrap complete!")
    print(f"   New entries: {new_count}")
    print(f"   Updated entries: {updated_count}")
    print(f"   Category: flowise")
    print("=" * 70)

    return True


if __name__ == "__main__":
    success = bootstrap_flowise_patterns()
    sys.exit(0 if success else 1)
```

**Key Features**:
- Idempotent (safe to re-run)
- Error handling (try/catch blocks)
- CLI UX (emoji progress indicators)
- Validation (checks for required fields)
- Type safety (uses proper enums)
- Metadata preservation (stores full pattern object)

---

### Phase 3: Create Test Suite

**File**: `extensions/flowise/tests/test_patterns.py`

**Implementation** (mirror `test_roblox_patterns.py`):

```python
"""
Unit tests for Flowise patterns loading

Run with: pytest extensions/flowise/tests/test_patterns.py
"""

import pytest
from pathlib import Path
import json
import sys

# Add context-foundry to path
cf_root = Path(__file__).parent.parent.parent
sys.path.insert(0, str(cf_root))


class TestFlowisePatterns:
    """Test pattern loading and structure"""

    @pytest.fixture
    def patterns_data(self):
        """Load flowise-expertise.json"""
        patterns_file = cf_root / "extensions" / "flowise" / "patterns" / "flowise-expertise.json"
        with open(patterns_file, 'r') as f:
            return json.load(f)

    def test_loads_patterns(self, patterns_data):
        """Verify pattern JSON loads without errors"""
        assert patterns_data is not None
        assert "patterns" in patterns_data
        assert "common_issues" in patterns_data
        assert len(patterns_data["patterns"]) > 0

    def test_pattern_count(self, patterns_data):
        """Verify expected number of patterns"""
        assert len(patterns_data["patterns"]) == 13, "Should have 13 AFv2 workflow patterns"
        assert len(patterns_data["common_issues"]) == 15, "Should have 15 common issues"

    def test_pattern_structure(self, patterns_data):
        """Verify each pattern has required fields"""
        required_fields = ["pattern_id", "category", "applies_to", "description", "confidence"]

        for pattern in patterns_data["patterns"]:
            for field in required_fields:
                assert field in pattern, f"Pattern missing required field: {field}"

            # Validate types
            assert isinstance(pattern["pattern_id"], str)
            assert isinstance(pattern["category"], str)
            assert isinstance(pattern["applies_to"], list)
            assert isinstance(pattern["confidence"], (int, float))
            assert 0.0 <= pattern["confidence"] <= 1.0

    def test_chaining_pattern_details(self, patterns_data):
        """Verify chaining pattern has detailed structure"""
        chaining = None
        for pattern in patterns_data["patterns"]:
            if pattern["pattern_id"] == "afv2-chaining-pattern":
                chaining = pattern
                break

        assert chaining is not None, "Chaining pattern not found"
        assert "implementation_notes" in chaining
        assert "use_cases" in chaining
        assert "testing_checklist" in chaining

    def test_common_issues_structure(self, patterns_data):
        """Verify common issues have required fields"""
        required_fields = ["issue_id", "severity", "description", "symptoms", "solution", "prevention"]

        valid_severities = ["LOW", "MEDIUM", "HIGH", "CRITICAL"]

        for issue in patterns_data["common_issues"]:
            for field in required_fields:
                assert field in issue, f"Issue missing required field: {field}"

            # Validate severity
            assert issue["severity"] in valid_severities, f"Invalid severity: {issue['severity']}"

    def test_missing_inputparams_issue(self, patterns_data):
        """Verify critical missing inputParams issue is documented"""
        issue = None
        for i in patterns_data["common_issues"]:
            if i["issue_id"] == "flowise-missing-inputparams":
                issue = i
                break

        assert issue is not None, "Missing inputParams issue not found"
        assert issue["severity"] == "CRITICAL"
        assert "symptoms" in issue
        assert "code_fix" in issue
        assert len(issue["prevention"]) > 0

    def test_pattern_ids_unique(self, patterns_data):
        """Verify no duplicate pattern IDs"""
        pattern_ids = [p["pattern_id"] for p in patterns_data["patterns"]]
        assert len(pattern_ids) == len(set(pattern_ids)), "Duplicate pattern IDs found"

        issue_ids = [i["issue_id"] for i in patterns_data["common_issues"]]
        assert len(issue_ids) == len(set(issue_ids)), "Duplicate issue IDs found"

    def test_project_types_valid(self, patterns_data):
        """Verify project types are consistent"""
        for pattern in patterns_data["patterns"]:
            assert "flowise-agentflow" in pattern["applies_to"], \
                f"Pattern {pattern['pattern_id']} missing flowise-agentflow project type"
```

---

### Phase 4: Update Orchestrator Prompt Integration

**File**: `tools/orchestrator_prompt.txt`

**Changes Required**:

#### Scout Phase (around line 563):

**BEFORE**:
```markdown
1. **Read AGENT_PATTERN_REFERENCE.md** (the authority on Flowise structure):

   Read /Users/name/homelab/context-foundry/extensions/flowise/AGENT_PATTERN_REFERENCE.md
```

**AFTER**:
```markdown
1. **Query Context Codex for Flowise patterns** (the authority on Flowise structure):

   **CRITICAL: Use Codex queries instead of reading docs**

   ```
   # Query for workflow patterns
   codex_search("flowise routing pattern")
   codex_search("flowise chaining pattern")
   codex_search("flowise start node")

   # Query for known issues to avoid
   codex_search("flowise missing inputparams")
   codex_search("flowise disconnected agents")

   # Get specific pattern details
   codex_get_entry("afv2-routing-pattern")
   codex_get_entry("afv2-chaining-pattern")
   ```

   **Pattern IDs to Query Based on Flow Type**:
   - Sequential processing: `afv2-chaining-pattern`
   - Intent classification: `afv2-routing-pattern`
   - Multi-source research: `afv2-parallel-pattern`
   - Quality refinement: `afv2-iteration-pattern`
   - Validation retry: `afv2-looping-pattern`
   - Task delegation: `afv2-hierarchy-pattern`
   - Array processing: `afv2-batch-processing`
   - HTTP integration: `afv2-api-integration`
   - Document Q&A: `afv2-rag-pattern`
```

#### Architect Phase (around line 968):

**BEFORE**:
```markdown
1. **Read AGENT_PATTERN_REFERENCE.md**:

   Read /Users/name/homelab/context-foundry/extensions/flowise/AGENT_PATTERN_REFERENCE.md
```

**AFTER**:
```markdown
1. **Reference Flowise patterns by ID in architecture.md**:

   **CRITICAL: Architecture MUST reference specific pattern IDs from Codex**

   ```markdown
   ## Applied Patterns

   This architecture applies the following Flowise patterns:

   - **afv2-routing-pattern** (Primary): Intent classification with ConditionAgent
   - **afv2-chaining-pattern** (Secondary): Sequential processing pipeline
   - **afv2-api-integration** (Tools): Custom HTTP tool integration

   ### Node 0: Start Node (MANDATORY)
   Reference pattern: afv2-start-node-requirement
   - formTitle: "Workflow Title"
   - formDescription: "User instructions"
   - formInputTypes: [...]

   ### Node 1: Router (ConditionAgent)
   Reference pattern: afv2-routing-pattern
   - Scenarios: [12 intents]
   - Temperature: 0.2 (deterministic)
   - Routes to: [specialized agents]
   ```

   **Validation Checklist**:
   - [ ] All referenced pattern IDs exist in Codex
   - [ ] Pattern IDs listed in "Applied Patterns" section
   - [ ] Node specifications reference pattern templates
```

#### Test Phase (around line 2206):

**AFTER Start Node Validation** (add new section):
```markdown

# 5b. Validate Against Codex Pattern Definitions

echo "🔍 Validating workflow against Codex patterns..."

# Extract applied patterns from architecture.md
APPLIED_PATTERNS=$(grep -A 10 "## Applied Patterns" .context-foundry/architecture.md | grep "afv2-" || echo "")

if [ -z "$APPLIED_PATTERNS" ]; then
    echo "⚠️  WARNING: No Flowise patterns referenced in architecture.md"
    echo "    Architecture should list applied patterns (e.g., afv2-routing-pattern)"
fi

# For each pattern, verify workflow matches pattern definition
# (This would call a Python validator that queries Codex)

python3 /extensions/flowise/validate_against_patterns.py \
    "$WORKFLOW_FILE" \
    .context-foundry/architecture.md

PATTERN_VALIDATION_EXIT_CODE=$?

if [ "$PATTERN_VALIDATION_EXIT_CODE" -ne 0 ]; then
    echo "❌ CRITICAL FAILURE: Workflow does not match referenced patterns"
    echo "   See validation errors above"
    exit 1
fi

echo "✅ Pattern validation passed"
```

---

### Phase 5: Create Integration Tests

**File**: `extensions/flowise/tests/test_bootstrap_integration.py`

```python
"""
Integration tests for Flowise pattern bootstrap

Tests the complete flow: JSON → Bootstrap → Codex → Query

Run with: pytest extensions/flowise/tests/test_bootstrap_integration.py
"""

import pytest
from pathlib import Path
import subprocess
import sys

cf_root = Path(__file__).parent.parent.parent
sys.path.insert(0, str(cf_root))

from context_foundry.codex import KnowledgeStore


class TestBootstrapIntegration:
    """Test bootstrap script integration with Codex"""

    @pytest.fixture(scope="class")
    def bootstrap_result(self):
        """Run bootstrap script once for all tests"""
        script_path = cf_root / "scripts" / "bootstrap_flowise_patterns.py"
        result = subprocess.run(
            [sys.executable, str(script_path)],
            capture_output=True,
            text=True
        )
        return result

    @pytest.fixture
    def codex_store(self):
        """Initialize Codex connection"""
        codex_path = Path.home() / ".context-foundry" / "patterns" / "codex.db"
        return KnowledgeStore(str(codex_path))

    def test_bootstrap_runs_successfully(self, bootstrap_result):
        """Verify bootstrap script exits with code 0"""
        assert bootstrap_result.returncode == 0, \
            f"Bootstrap failed:\n{bootstrap_result.stderr}"

    def test_bootstrap_output_format(self, bootstrap_result):
        """Verify bootstrap output has expected format"""
        output = bootstrap_result.stdout
        assert "Bootstrap Flowise Patterns" in output
        assert "Importing patterns..." in output
        assert "Importing common issues..." in output
        assert "Bootstrap complete!" in output

    def test_codex_contains_patterns(self, codex_store):
        """Verify Codex contains all 13 patterns"""
        # Search for Flowise patterns
        results = codex_store.search("flowise", entry_type="pattern")

        # Should have 13 patterns
        assert len(results) >= 13, f"Expected 13+ patterns, found {len(results)}"

    def test_codex_contains_issues(self, codex_store):
        """Verify Codex contains all 15 issues"""
        # Search for Flowise issues
        results = codex_store.search("flowise", entry_type="issue")

        # Should have 15 issues
        assert len(results) >= 15, f"Expected 15+ issues, found {len(results)}"

    def test_chaining_pattern_in_codex(self, codex_store):
        """Verify specific pattern (chaining) is in Codex"""
        entry = codex_store.get_entry("afv2-chaining-pattern")

        assert entry is not None
        assert entry.id == "afv2-chaining-pattern"
        assert entry.type.value == "pattern"
        assert "flowise" in entry.category.lower()

    def test_missing_inputparams_issue_in_codex(self, codex_store):
        """Verify critical issue is in Codex"""
        entry = codex_store.get_entry("flowise-missing-inputparams")

        assert entry is not None
        assert entry.id == "flowise-missing-inputparams"
        assert entry.type.value == "issue"
        assert entry.severity.value == "CRITICAL"

    def test_pattern_search_works(self, codex_store):
        """Verify pattern search returns relevant results"""
        results = codex_store.search("routing pattern")

        # Should find routing pattern
        pattern_ids = [r.id for r in results]
        assert "afv2-routing-pattern" in pattern_ids

    def test_issue_search_works(self, codex_store):
        """Verify issue search returns relevant results"""
        results = codex_store.search("missing start node")

        # Should find start node issue
        issue_ids = [r.id for r in results]
        assert "flowise-missing-start-node" in issue_ids

    def test_rerun_bootstrap_is_idempotent(self):
        """Verify re-running bootstrap doesn't duplicate entries"""
        script_path = cf_root / "scripts" / "bootstrap_flowise_patterns.py"

        # Run bootstrap twice
        result1 = subprocess.run([sys.executable, str(script_path)], capture_output=True, text=True)
        result2 = subprocess.run([sys.executable, str(script_path)], capture_output=True, text=True)

        # Both should succeed
        assert result1.returncode == 0
        assert result2.returncode == 0

        # Second run should show "Updated" not "Added"
        assert "Updated:" in result2.stdout
```

---

### Phase 6: Documentation Updates

#### File 1: `extensions/flowise/README.md`

**Add Section** (after "Templates" section):

```markdown
## Pattern System

Flowise uses a pattern-driven workflow powered by the Context Codex knowledge base. This ensures consistent, validated workflow generation based on proven patterns.

### Architecture

```
flowise-expertise.json → Bootstrap → Context Codex → Scout/Architect/Test queries
                                           ↓
                                    S3 Community Patterns
```

**Components**:
1. **Pattern Library**: `extensions/flowise/patterns/flowise-expertise.json`
   - 13 curated AFv2 workflow patterns
   - 15 common issues and anti-patterns
   - Structured JSON with metadata

2. **Bootstrap Script**: `scripts/bootstrap_flowise_patterns.py`
   - Imports patterns into Context Codex
   - Idempotent (safe to re-run)
   - Run on installation or after pattern updates

3. **Codex Integration**: Patterns available during builds
   - Scout: Query patterns for architecture recommendations
   - Architect: Reference patterns by ID in architecture.md
   - Test: Validate workflows against pattern definitions

### Usage

#### Initial Setup

```bash
# Bootstrap Flowise patterns into Codex
python3 scripts/bootstrap_flowise_patterns.py

# Verify patterns loaded
python3 -c "from context_foundry.codex import KnowledgeStore; \
            store = KnowledgeStore(); \
            print(f'Patterns: {len(store.search(\"flowise\", entry_type=\"pattern\"))}')"
```

#### During Builds

Scout/Architect agents automatically query Codex for patterns:

```python
# Scout queries for relevant patterns
codex_search("flowise routing pattern")
codex_get_entry("afv2-chaining-pattern")

# Architect references patterns in architecture.md
"""
## Applied Patterns
- afv2-routing-pattern (Primary)
- afv2-api-integration (Tools)
"""
```

#### Adding New Patterns

1. Edit `extensions/flowise/patterns/flowise-expertise.json`
2. Add pattern to `patterns` array with required fields
3. Re-run bootstrap: `python3 scripts/bootstrap_flowise_patterns.py`
4. Patterns immediately available in Codex

### Available Patterns

**Workflow Patterns** (13):
- `afv2-chaining-pattern` - Sequential processing
- `afv2-parallel-pattern` - Multi-source research
- `afv2-routing-pattern` - Intent classification
- `afv2-iteration-pattern` - Quality refinement
- `afv2-looping-pattern` - Validation retry
- `afv2-hierarchy-pattern` - Task delegation
- `afv2-batch-processing` - Array processing
- `afv2-conditional-retry` - Score-based validation
- `afv2-api-integration` - HTTP integration
- `afv2-rag-pattern` - Document Q&A
- `afv2-smart-calculator` - Cost optimization
- `afv2-doc-qa-confidence` - Confidence routing
- `afv2-data-pipeline-etl` - ETL validation

**Common Issues** (15):
- `flowise-missing-inputparams` - Agent nodes not editable (CRITICAL)
- `flowise-missing-start-node` - No workflow entry point (CRITICAL)
- `flowise-separate-configs` - External config files (CRITICAL)
- `flowise-incorrect-tool-structure` - Tool import failures (CRITICAL)
- ... (see FAILURE_PATTERNS.md for complete list)

### Testing

```bash
# Run pattern tests
pytest extensions/flowise/tests/test_patterns.py -v

# Run bootstrap integration tests
pytest extensions/flowise/tests/test_bootstrap_integration.py -v
```

### Community Sharing

Patterns can be exported and synced to S3 for community sharing:

```bash
# Export Codex patterns to JSON
python3 -c "from context_foundry.codex import export_codex_to_patterns; \
            export_codex_to_patterns('all', sync_to_s3=True)"

# Pull community patterns from S3
python3 -c "from context_foundry.mcp import pull_patterns_from_s3; \
            pull_patterns_from_s3('scout-learnings')"
```
```

#### File 2: `extensions/flowise/PATTERN_DEVELOPMENT.md`

**Create New File**:

```markdown
# Flowise Pattern Development Guide

Guide for creating and maintaining Flowise workflow patterns in the Context Codex knowledge base.

## Pattern Lifecycle

```
Create Pattern → Add to JSON → Bootstrap → Codex → Build Usage → Feedback → Update Pattern
                                                          ↓
                                                   S3 Community Sync
```

## Creating a New Pattern

### 1. Identify the Pattern

**Criteria for a good pattern**:
- Solves a specific workflow need
- Reusable across multiple projects
- Has clear structure and constraints
- Validated by successful builds

**Pattern Categories**:
- `workflow-pattern` - Complete workflow topologies
- `node-structure` - Node configuration patterns
- `integration` - External system integration
- `security` - Security best practices
- `optimization` - Performance optimization

### 2. Define Pattern Structure

**Required Fields**:
```json
{
  "pattern_id": "afv2-your-pattern-name",
  "category": "workflow-pattern",
  "applies_to": ["flowise-agentflow"],
  "description": "Clear, concise description of what this pattern does",
  "confidence": 0.9,
  "frequency": 1
}
```

**Recommended Fields**:
```json
{
  "node_structure": {
    "start_node": {...},
    "processing_nodes": [...],
    "edges": [...]
  },
  "code_templates": {
    "example_node": "templates/path/to/template.json#L100-200"
  },
  "implementation_notes": [
    "Key insight 1",
    "Key insight 2"
  ],
  "use_cases": [
    "Real-world scenario 1",
    "Real-world scenario 2"
  ],
  "constraints": {
    "min_nodes": 3,
    "requires_start_node": true
  },
  "testing_checklist": [
    "Test case 1",
    "Test case 2"
  ]
}
```

### 3. Add to flowise-expertise.json

**Location**: `extensions/flowise/patterns/flowise-expertise.json`

**Steps**:
1. Open JSON file
2. Add pattern object to `patterns` array
3. Ensure valid JSON syntax
4. Validate required fields present

**Example**:
```json
{
  "patterns": [
    // ... existing patterns ...
    {
      "pattern_id": "afv2-webhook-integration",
      "category": "integration",
      "applies_to": ["flowise-agentflow"],
      "description": "Webhook-triggered workflow with async response",
      "confidence": 0.85,
      "frequency": 1,
      "node_structure": {
        "webhook_trigger": {
          "type": "Start",
          "inputs": {
            "formTitle": "Webhook Receiver",
            "webhookEnabled": true
          }
        }
      },
      "implementation_notes": [
        "Start node must have webhookEnabled: true",
        "Use state to track webhook request ID",
        "Return immediate 202 Accepted, process async"
      ],
      "testing_checklist": [
        "Send test webhook payload",
        "Verify 202 response received",
        "Confirm workflow triggered",
        "Validate async processing completed"
      ]
    }
  ]
}
```

### 4. Run Bootstrap

```bash
# Import new pattern into Codex
python3 scripts/bootstrap_flowise_patterns.py

# Verify pattern added
python3 -c "from context_foundry.codex import KnowledgeStore; \
            store = KnowledgeStore(); \
            entry = store.get_entry('afv2-webhook-integration'); \
            print(f'Pattern: {entry.title}')"
```

### 5. Test the Pattern

**Create Unit Test**:
```python
# extensions/flowise/tests/test_patterns.py

def test_webhook_pattern_details(self, patterns_data):
    """Verify webhook pattern has detailed structure"""
    webhook = None
    for pattern in patterns_data["patterns"]:
        if pattern["pattern_id"] == "afv2-webhook-integration":
            webhook = pattern
            break

    assert webhook is not None, "Webhook pattern not found"
    assert "node_structure" in webhook
    assert "webhook_trigger" in webhook["node_structure"]
    assert webhook["node_structure"]["webhook_trigger"]["inputs"]["webhookEnabled"] == True
```

**Run Tests**:
```bash
pytest extensions/flowise/tests/test_patterns.py::TestFlowisePatterns::test_webhook_pattern_details -v
```

### 6. Use in Builds

**Scout Phase** - Query pattern:
```python
# Scout queries Codex for webhook patterns
codex_search("flowise webhook")
codex_get_entry("afv2-webhook-integration")
```

**Architect Phase** - Reference pattern:
```markdown
## Applied Patterns

- **afv2-webhook-integration** (Primary): Async webhook processing

### Node 0: Webhook Receiver (Start)
Reference pattern: afv2-webhook-integration
- webhookEnabled: true
- Immediate 202 response
```

**Test Phase** - Validate against pattern:
```bash
# Validate workflow matches pattern structure
python3 extensions/flowise/validate_against_patterns.py \
    workflow.json \
    afv2-webhook-integration
```

## Creating a Common Issue

### 1. Identify the Issue

**Criteria**:
- Occurs repeatedly across builds
- Has clear symptoms and root cause
- Has proven solution/prevention
- Severity: LOW, MEDIUM, HIGH, or CRITICAL

### 2. Document the Issue

**Required Fields**:
```json
{
  "issue_id": "flowise-your-issue-name",
  "severity": "HIGH",
  "category": "node-structure",
  "description": "Brief description of the issue",
  "frequency": 1,
  "confidence": 1.0,
  "symptoms": [
    "Observable symptom 1",
    "Observable symptom 2"
  ],
  "root_cause": "Why this happens",
  "solution": "How to fix it",
  "prevention": [
    "Prevention step 1",
    "Prevention step 2"
  ]
}
```

**Recommended Fields**:
```json
{
  "code_fix": "// Before (broken)\n...\n// After (fixed)\n...",
  "related_patterns": ["pattern-id-1", "pattern-id-2"],
  "detection": {
    "test_command": "jq '.nodes[] | select(...)' workflow.json",
    "error_message": "Expected error message"
  }
}
```

### 3. Add to flowise-expertise.json

**Location**: `extensions/flowise/patterns/flowise-expertise.json`

**Add to `common_issues` array**:
```json
{
  "common_issues": [
    // ... existing issues ...
    {
      "issue_id": "flowise-callback-memory-leak",
      "severity": "MEDIUM",
      "category": "performance",
      "description": "Event listeners not cleaned up, causing memory leaks",
      "frequency": 1,
      "confidence": 0.9,
      "symptoms": [
        "Memory usage grows over time",
        "Duplicate event handlers firing",
        "Browser becomes slow after extended use"
      ],
      "root_cause": "addEventListener called without removeEventListener cleanup",
      "solution": "Store listener references and clean up in unmount/destroy hooks",
      "code_fix": "// Add cleanup:\ncomponentWillUnmount() {\n  window.removeEventListener('resize', this.handleResize);\n}",
      "prevention": [
        "Use cleanup functions in useEffect hooks",
        "Track all event listeners in component state",
        "Add tests that verify cleanup called"
      ],
      "related_patterns": ["afv2-parallel-pattern", "afv2-batch-processing"]
    }
  ]
}
```

### 4. Run Bootstrap and Test

```bash
# Bootstrap new issue into Codex
python3 scripts/bootstrap_flowise_patterns.py

# Verify issue added
python3 -c "from context_foundry.codex import KnowledgeStore; \
            store = KnowledgeStore(); \
            entry = store.get_entry('flowise-callback-memory-leak'); \
            print(f'Issue: {entry.title} (Severity: {entry.severity.value})')"

# Run tests
pytest extensions/flowise/tests/test_patterns.py -v
```

## Pattern Versioning

**Version Field**: `flowise-expertise.json` has top-level version field

**When to Increment**:
- **Patch (1.0.0 → 1.0.1)**: Add new pattern, update existing pattern metadata
- **Minor (1.0.0 → 1.1.0)**: Add new required field to schema
- **Major (1.0.0 → 2.0.0)**: Breaking schema changes

**Update Version**:
```json
{
  "version": "1.1.0",
  "last_updated": "2025-11-17"
}
```

## Community Sharing

### Export to S3

```bash
# Export all Codex patterns to JSON
python3 -c "from context_foundry.codex import export_codex_to_patterns; \
            export_codex_to_patterns('all', sync_to_s3=False)"

# Sync to S3 community repository
python3 -c "from context_foundry.mcp import sync_patterns_to_s3; \
            sync_patterns_to_s3('scout-learnings', force=False)"
```

### Pull from S3

```bash
# Download community patterns
python3 -c "from context_foundry.mcp import pull_patterns_from_s3; \
            pull_patterns_from_s3('common-issues')"

# Re-bootstrap to merge community patterns
python3 scripts/bootstrap_flowise_patterns.py
```

## Best Practices

### Pattern Design

1. **Single Responsibility** - Each pattern solves one specific problem
2. **Clear Constraints** - Document what must/mustn't be done
3. **Code Examples** - Include working code snippets
4. **Testing Guidance** - Provide validation checklist

### Issue Documentation

1. **Symptoms First** - Start with what users observe
2. **Root Cause** - Explain why it happens
3. **Proven Solution** - Only document solutions that work
4. **Prevention** - Help avoid the issue in future

### Maintenance

1. **Frequency Tracking** - Increment when pattern/issue seen again
2. **Confidence Scoring** - Adjust based on success rate
3. **Deprecation** - Mark outdated patterns with confidence < 0.5
4. **Review Cycle** - Quarterly review of all patterns

## Troubleshooting

### Bootstrap Fails

```bash
# Check JSON syntax
jq . extensions/flowise/patterns/flowise-expertise.json

# Validate schema
python3 -c "import json; \
            data = json.load(open('extensions/flowise/patterns/flowise-expertise.json')); \
            assert 'patterns' in data; \
            assert 'common_issues' in data; \
            print('✅ Schema valid')"
```

### Pattern Not Found in Codex

```bash
# Check Codex database
python3 -c "from context_foundry.codex import KnowledgeStore; \
            store = KnowledgeStore(); \
            results = store.search('your-pattern-id'); \
            print(f'Found: {len(results)} results')"

# Re-run bootstrap
python3 scripts/bootstrap_flowise_patterns.py
```

### Tests Failing

```bash
# Run specific test
pytest extensions/flowise/tests/test_patterns.py::TestFlowisePatterns::test_pattern_count -v

# Run with verbose output
pytest extensions/flowise/tests/test_patterns.py -vv
```

## References

- Roblox pattern system: `extensions/roblox/patterns/roblox-expertise.json`
- Codex documentation: `docs/CODEX_GUIDE.md`
- S3 sync guide: `docs/PATTERN_SHARING.md`
```

---

## Implementation Order

### Week 1: Foundation (Phase 1-2)

**Day 1-2**: Create flowise-expertise.json
- Extract 13 AFv2 patterns from AGENT_PATTERN_REFERENCE.md
- Convert to structured JSON format
- Add required fields, code templates, implementation notes

**Day 3**: Add common issues
- Extract 15 failure patterns from FAILURE_PATTERNS.md
- Convert to common_issues format
- Add symptoms, solutions, prevention steps

**Day 4**: Create bootstrap script
- Copy/modify bootstrap_roblox_patterns.py
- Update for Flowise patterns
- Test bootstrap runs successfully

**Day 5**: Create test suite
- Create test_patterns.py
- Add 8+ test cases
- Ensure all tests pass

### Week 2: Integration (Phase 3-4)

**Day 6-7**: Update orchestrator prompts
- Modify Scout phase (Codex queries)
- Modify Architect phase (pattern references)
- Modify Test phase (pattern validation)

**Day 8**: Create integration tests
- test_bootstrap_integration.py
- Test Codex queries work
- Test pattern search/retrieval

**Day 9**: End-to-end testing
- Run full build with new pattern system
- Verify patterns referenced in scout-report.md
- Verify architecture.md lists pattern IDs

**Day 10**: Documentation
- Update README.md
- Create PATTERN_DEVELOPMENT.md
- Update FLOWISE_VS_ROBLOX_PATTERNS.md

### Week 3: Validation (Phase 5-6-7)

**Day 11-12**: Pattern validation
- Create validate_against_patterns.py
- Integrate into Test phase
- Test blocking validation

**Day 13**: S3 sync verification
- Test export_codex_to_patterns()
- Test sync_patterns_to_s3()
- Test pull_patterns_from_s3()

**Day 14**: Final testing and cleanup
- Run complete test suite
- Fix any remaining issues
- Document lessons learned

---

## Success Criteria Checklist

### ✅ Pattern Library Created

- [ ] `flowise-expertise.json` exists with valid JSON
- [ ] Contains 13 AFv2 workflow patterns
- [ ] Contains 15 common issues
- [ ] All patterns have required fields
- [ ] All issues have severity, symptoms, solution, prevention
- [ ] Schema matches Roblox template structure

### ✅ Bootstrap Working

- [ ] `bootstrap_flowise_patterns.py` runs without errors
- [ ] Exits with code 0 on success
- [ ] CLI output shows progress indicators
- [ ] Codex contains all 28 entries (13 patterns + 15 issues)
- [ ] Re-running bootstrap updates existing (idempotent)
- [ ] Pattern metadata preserved in Codex

### ✅ Tests Passing

- [ ] `test_patterns.py` has 8+ test cases
- [ ] All unit tests pass
- [ ] `test_bootstrap_integration.py` validates end-to-end
- [ ] Integration tests verify Codex queries
- [ ] Tests run in CI/CD pipeline

### ✅ Orchestrator Integration

- [ ] Scout phase queries Codex (not reads markdown)
- [ ] Scout reports list applied pattern IDs
- [ ] Architect references patterns by ID in architecture.md
- [ ] Test phase validates against Codex patterns
- [ ] Build logs show pattern usage

### ✅ S3 Sync Working

- [ ] `export_codex_to_patterns()` exports Flowise patterns
- [ ] `sync_patterns_to_s3()` uploads to S3
- [ ] `pull_patterns_from_s3()` downloads patterns
- [ ] Flowise patterns visible in S3 bucket
- [ ] Community can share patterns

### ✅ Documentation Complete

- [ ] README.md has "Pattern System" section
- [ ] PATTERN_DEVELOPMENT.md created with full guide
- [ ] Examples show how to add patterns
- [ ] Troubleshooting guide included
- [ ] References to Roblox system

### ✅ Parity with Roblox

- [ ] Same bootstrap workflow (JSON → script → Codex)
- [ ] Same test structure (unit + integration)
- [ ] Same Codex integration (search, get_entry)
- [ ] Same S3 sync capability
- [ ] Same orchestrator integration pattern

---

## Files Created/Modified Summary

### New Files (7)

1. `extensions/flowise/patterns/flowise-expertise.json` (~1000 lines)
2. `scripts/bootstrap_flowise_patterns.py` (~180 lines)
3. `extensions/flowise/tests/test_patterns.py` (~120 lines)
4. `extensions/flowise/tests/test_bootstrap_integration.py` (~100 lines)
5. `extensions/flowise/PATTERN_DEVELOPMENT.md` (~400 lines)
6. `extensions/flowise/validate_against_patterns.py` (~200 lines)
7. `docs/FLOWISE_PATTERN_UPGRADE_PLAN.md` (this file, ~600 lines)

### Modified Files (3)

1. `tools/orchestrator_prompt.txt` (~150 lines modified across 3 sections)
2. `extensions/flowise/README.md` (~100 lines added)
3. `docs/FLOWISE_VS_ROBLOX_PATTERNS.md` (~50 lines updated)

**Total Lines**: ~2,900 new/modified

---

## Estimated Effort

- **Pattern Library Creation**: 6 hours (curating 28 entries with complete metadata)
- **Bootstrap Script**: 2 hours (mirror Roblox script)
- **Test Suite**: 2 hours (unit + integration tests)
- **Orchestrator Updates**: 3 hours (3 prompt sections)
- **Pattern Validation Tool**: 2 hours (validate_against_patterns.py)
- **Documentation**: 3 hours (README, guide, plan)
- **Testing and Refinement**: 2 hours

**Total: 20 hours** (~2.5 days)

---

## Next Steps

1. **Review this plan** - Ensure alignment with requirements
2. **Approve for implementation** - Get stakeholder sign-off
3. **Execute Phase 1** - Create flowise-expertise.json (foundation)
4. **Execute Phases 2-7** - Bootstrap → Tests → Integration → Docs → Validation
5. **Verify success criteria** - Check all ✅ boxes
6. **Deploy** - Merge to main, run bootstrap in production
7. **Monitor** - Track pattern usage in builds, gather feedback

---

**Status**: Ready for implementation
**Risk Level**: Low (following proven Roblox architecture)
**Dependencies**: Context Codex, KnowledgeStore class, MCP pattern tools
**Blockers**: None identified

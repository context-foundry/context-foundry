# Extension Learning System - Visual Guide

## The Complete Knowledge Flow

```
┌─────────────────────────────────────────────────────────────────────────────┐
│                      HOW LEARNINGS FLOW THROUGH THE SYSTEM                  │
└─────────────────────────────────────────────────────────────────────────────┘

                              ┌─────────────────┐
                              │  YOU DISCOVER   │
                              │  SOMETHING NEW  │
                              │  (during build) │
                              └────────┬────────┘
                                       │
                                       v
                        ┌──────────────────────────────┐
                        │   WHERE DO YOU ADD IT?       │
                        └──────────────────────────────┘
                                       │
                ┌──────────────────────┼──────────────────────┐
                │                      │                      │
                v                      v                      v
    ┌─────────────────────┐  ┌─────────────────┐  ┌──────────────────┐
    │  OPTION 1:          │  │  OPTION 2:      │  │  OPTION 3:       │
    │  Edit JSON File     │  │  Use MCP Tools  │  │  Let Builder     │
    │                     │  │                 │  │  Auto-Capture    │
    │  ✓ Simple           │  │  ✓ Programmatic │  │  ⚠️ Future       │
    │  ✓ See all patterns │  │  ✓ During build │  │     feature      │
    │  ✓ Works offline    │  │  ✓ Structured   │  │                  │
    └──────────┬──────────┘  └────────┬────────┘  └──────────────────┘
               │                      │
               v                      v
    ┌──────────────────────────────────────────────┐
    │  extensions/roblox/patterns/                 │
    │  roblox-expertise.json                       │
    │                                               │
    │  {                                            │
    │    "pattern_id": "roblox-new-2025",          │
    │    "title": "What I learned",                │
    │    "category": "performance",                │
    │    "description": "...",                     │
    │    "code_example": "...",                    │
    │    "tags": ["optimization"]                  │
    │  }                                            │
    └──────────────────┬───────────────────────────┘
                       │
                       v
            ┌──────────────────────┐
            │  BOOTSTRAP SCRIPT    │
            │                      │
            │  python3 scripts/    │
            │  bootstrap_roblox_   │
            │  patterns.py         │
            └──────────┬───────────┘
                       │
                       │ Reads JSON
                       │ Calls add_pattern()
                       │ For each entry
                       v
    ┌──────────────────────────────────────────────┐
    │  ~/.context-foundry/codex.db                 │
    │                                               │
    │  Global SQLite Database                      │
    │  - Searchable                                │
    │  - Queryable by agents                       │
    │  - Supports all extensions                   │
    │                                               │
    │  [roblox patterns] [flowise patterns]        │
    │  [python issues]   [common learnings]        │
    └──────────────────┬───────────────────────────┘
                       │
                       │ Agents query during builds:
                       │ codex_search("roblox checkpoint")
                       │
                       v
            ┌──────────────────────┐
            │  SCOUT/ARCHITECT     │
            │  Use patterns to     │
            │  inform design       │
            └──────────────────────┘


┌─────────────────────────────────────────────────────────────────────────────┐
│                         SHARING WITH COMMUNITY                              │
└─────────────────────────────────────────────────────────────────────────────┘

    ┌──────────────────────────────────────────────┐
    │  ~/.context-foundry/codex.db                 │
    │  (Your local knowledge)                      │
    └──────────────────┬───────────────────────────┘
                       │
                       │ export_codex_to_patterns()
                       │
                       v
    ┌──────────────────────────────────────────────┐
    │  ~/.context-foundry/patterns/                │
    │  - common-issues.json                        │
    │  - scout-learnings.json                      │
    │  - architecture-patterns.json                │
    └──────────────────┬───────────────────────────┘
                       │
                       │ sync_patterns_to_s3()
                       │
                       v
    ┌──────────────────────────────────────────────┐
    │  S3: Community Pattern Repository            │
    │  s3://bedrock-builder-kb-.../                │
    │  community-patterns/                         │
    │                                               │
    │  Available to ALL Context Foundry users      │
    └──────────────────┬───────────────────────────┘
                       │
                       │ pull_patterns_from_s3()
                       │
                       v
    ┌──────────────────────────────────────────────┐
    │  OTHER DEVELOPERS                            │
    │  Download patterns                           │
    │  Bootstrap into their Codex                  │
    │  Use in their builds                         │
    │  Contribute back new learnings               │
    └──────────────────────────────────────────────┘


┌─────────────────────────────────────────────────────────────────────────────┐
│                           TYPICAL WORKFLOW                                  │
└─────────────────────────────────────────────────────────────────────────────┘

Day 1: Discovery
┌─────────────────────────────────────────────────────────────────────┐
│  1. Building Roblox game                                            │
│  2. Discover: "DataStore needs pcall + retry logic"                 │
│  3. Fix the issue, build succeeds                                   │
│  4. Add to extensions/roblox/patterns/roblox-expertise.json:        │
│                                                                      │
│     {                                                                │
│       "issue_id": "roblox-datastore-no-retry-001",                  │
│       "title": "DataStore calls fail without retry",                │
│       "severity": "HIGH",                                            │
│       "solution": {                                                  │
│         "description": "Wrap in pcall with exponential backoff",    │
│         "code_example": "..."                                        │
│       }                                                              │
│     }                                                                │
│                                                                      │
│  5. python3 scripts/bootstrap_roblox_patterns.py                    │
│  6. Pattern now in Codex, will help future builds                   │
└─────────────────────────────────────────────────────────────────────┘

Day 2-7: Refinement
┌─────────────────────────────────────────────────────────────────────┐
│  - Build 3 more Roblox games                                        │
│  - Each time, pattern gets used successfully                        │
│  - Increment "frequency" field in JSON                              │
│  - Add more code examples                                           │
│  - Refine description based on edge cases                           │
└─────────────────────────────────────────────────────────────────────┘

Week 2: Share
┌─────────────────────────────────────────────────────────────────────┐
│  Pattern is proven valuable (frequency: 5)                          │
│                                                                      │
│  1. export_codex_to_patterns()                                      │
│  2. Review ~/.context-foundry/patterns/common-issues.json           │
│  3. sync_patterns_to_s3()                                           │
│  4. Pattern now available to community                              │
│  5. Other developers benefit from your learning                     │
└─────────────────────────────────────────────────────────────────────┘


┌─────────────────────────────────────────────────────────────────────────────┐
│                       EXTENSION COMPARISON                                  │
└─────────────────────────────────────────────────────────────────────────────┘

Roblox Extension                        Flowise Extension
─────────────────────                   ──────────────────────

Pattern File:                           Pattern File:
└─ roblox-expertise.json                └─ flowise-expertise.json

Bootstrap:                              Bootstrap:
└─ bootstrap_roblox_patterns.py         └─ bootstrap_flowise_patterns.py
                                            (needs creation)

Pattern Categories:                     Pattern Categories:
├─ security                             ├─ workflow-design
├─ performance                          ├─ agent-orchestration
├─ datastore                            ├─ node-configuration
├─ remote-events                        ├─ tool-integration
└─ education                            └─ error-handling

Common Issues:                          Common Issues:
├─ RemoteEvent validation               ├─ Node type mismatches
├─ DataStore throttling                 ├─ Tool scope problems
├─ Memory leaks                         ├─ Agent state bugs
└─ Infinite loops                       └─ Workflow routing errors

Both flow through same Codex → Same S3 bucket → Global community


┌─────────────────────────────────────────────────────────────────────────────┐
│                            QUICK COMMANDS                                   │
└─────────────────────────────────────────────────────────────────────────────┘

Add Pattern (Manual):
  1. vim extensions/roblox/patterns/roblox-expertise.json
  2. python3 -m json.tool <file> > /dev/null  # Validate
  3. python3 scripts/bootstrap_roblox_patterns.py

Add Pattern (MCP):
  codex_add_pattern(title="...", category="...", ...)
  export_codex_to_patterns()

Search Patterns:
  codex_search(query="roblox datastore", category="roblox")

Share to Community:
  export_codex_to_patterns(sync_to_s3=True)

Get Community Patterns:
  pull_patterns_from_s3(pattern_type="all")

Check What's Available:
  list_s3_community_patterns()


┌─────────────────────────────────────────────────────────────────────────────┐
│                         KEY FILES REFERENCE                                 │
└─────────────────────────────────────────────────────────────────────────────┘

Extension Pattern Files (Source of Truth for that extension):
  extensions/roblox/patterns/roblox-expertise.json
  extensions/flowise/patterns/flowise-expertise.json

Global Codex (Centralized Query Engine):
  ~/.context-foundry/codex.db

Global Pattern Exports (For S3 sync):
  ~/.context-foundry/patterns/common-issues.json
  ~/.context-foundry/patterns/scout-learnings.json
  ~/.context-foundry/patterns/architecture-patterns.json
  ~/.context-foundry/patterns/test-patterns.json

Community Repository (Global Knowledge):
  s3://bedrock-builder-kb-898587418237/community-patterns/

Bootstrap Scripts:
  scripts/bootstrap_roblox_patterns.py
  scripts/bootstrap_flowise_patterns.py (create this)

Smoke Tests:
  tools/run_extension_smoke_test.py --extension roblox
  tools/run_extension_smoke_test.py --extension flowise

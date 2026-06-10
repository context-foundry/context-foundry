---
name: compliance-agent-architecture
description: Use when the user is building a standalone Workday-Marketplace compliance rule engine (ACA, multi-state tax, Davis-Bacon, or similar). Covers rule-function signatures, rule ID naming, input normalization, ordering dependencies, and the Phase 2 Workday bridge.
---

# Workday Compliance Agent Extension

## Overview

This extension covers the development of standalone compliance rule engines designed to eventually integrate with Workday via the "Built on Workday" Marketplace program. Each agent follows the same architecture pattern and connects to Workday through a thin bridge adapter.

## When to Use

Read this extension before building any new Workday-targeted compliance agent (ACA, multi-state tax, Davis-Bacon, or similar).

## Architecture Pattern

Every agent follows this structure:

```
agent-name/
├── SPEC.md                    # What this agent does, IRS/regulatory sources
├── TASKS.md                   # QRPBA task queue
├── .foundry.json              # extensions: ["extend", "workday-agents"]
├── pyproject.toml             # Python 3.10+, FastAPI, Pydantic, pytest
├── src/<package>/
│   ├── models/
│   │   ├── <domain>.py        # Input: the record being audited (employee, worker, etc.)
│   │   └── finding.py         # Output: audit findings with severity, citation, remediation
│   ├── rules/
│   │   ├── __init__.py        # ALL_RULE_CHECKS list aggregating all modules
│   │   ├── <category_1>.py    # One module per rule category
│   │   ├── <category_2>.py    # Each exports check_<category>_rules(record) -> list[Finding]
│   │   └── ...
│   ├── engine/
│   │   └── auditor.py         # Stateless engine: loops ALL_RULE_CHECKS over records
│   ├── api/
│   │   └── routes.py          # FastAPI: POST /audit, GET /health, GET /findings/{id}
│   └── bridge/
│       └── workday.py         # Phase 2 stub: NotImplementedError, scopes documented
├── tests/
│   ├── conftest.py            # Fixture: engine instance
│   ├── fixtures/
│   │   └── scenarios.py       # Regulatory-derived test scenarios with known outcomes
│   ├── test_<category>.py     # One test file per rule category
│   └── test_api.py            # Endpoint tests
└── .buildloop/
```

## Key Design Rules

### Rule Functions
- Signature: `check_<category>_rules(record: InputModel) -> list[AuditFinding]`
- Stateless -- no side effects, no database, no external calls
- Return empty list when the rule category doesn't apply (e.g., no rehire data)
- Each finding includes: rule_id, severity, description, current vs. correct determination, penalty/impact estimate, regulatory citation, remediation

### Rule ID Naming
- Format: `CATEGORY-NNN` (e.g., REHIRE-001, NEXUS-003, SAFE-002)
- When a generic rule and a specific rule can both fire for the same entity, the specific rule REPLACES the generic one (not supplements). Guard the generic rule with a method/type check.

### Input Normalization
- All user-provided codes (state codes, category enums) must be normalized at the Pydantic model level via `field_validator`
- This includes dict KEYS, not just values (e.g., `ytd_days_by_state`, `current_allocations`)
- Never rely on case-sensitive lookups against user input

### Regulatory Rule Compilation
- Rules come from public sources (IRS CFR, state statutes, DOL wage determinations)
- Compile rules into Python data structures, not a database
- Each rule must cite its source (CFR section, state statute, etc.)
- Rules change annually -- document the indexed year in constants

### Ordering Dependencies
- Exemptions/reciprocity must resolve BEFORE general rules fire
- Specific overrides (convenience rule) must check BEFORE generic fallbacks (de minimis)
- When multiple rule categories interact, document the ordering in the engine

### Testing
- Derive scenarios from regulatory guidance examples (IRS worked examples, state DOR publications)
- Every rule ID needs at least one positive test (the rule fires) and one negative test (clean record, no finding)
- Test the exact scenario from every Doubt/auditor finding as a regression

### Workday Bridge (Phase 2)
- Document required API scopes in the bridge stub docstring
- Read-only access only -- agents audit, they don't write back
- Scopes needed vary by domain:
  - ACA: Benefits, Human_Resources, Time_Tracking, Absence_Management, Payroll
  - Multi-state tax: Time_Tracking, Human_Resources, Payroll
- Rate limit: ~10 calls/sec per tenant. Batch operations, don't stream.

### SPEC.md Accuracy
- The SPEC overview must reflect the current phase (standalone engine vs. integrated marketplace app)
- Counts (rules, states, tests) must match the implementation -- update on every commit
- If the bridge is a stub, say so in the spec

## Agent Roster

### Complete (Phase 1)

| Agent | Repo | Rules | Tests | Status |
|-------|------|-------|-------|--------|
| ACA Edge-Case Auditor | `~/homelab/aca-auditor` | 22 finding IDs across 5 modules | 21 | Phase 1 complete |
| Multi-State Tax Allocator | `~/homelab/multistate-tax` | 14 finding IDs across 4 modules + 31-state matrix | 23 | Phase 1 complete |

### Ready to Build (SPEC + TASKS written, run `foundry` in the directory)

| Priority | Agent | Repo | Regulatory Source | Key Selling Point |
|----------|-------|------|-------------------|-------------------|
| 1 | I-9 Re-verification | `~/homelab/i9-reverification` | 8 CFR 274a | $288-$28,619/violation, ICE running 12K+ audits/year |
| 2 | FLSA Exemption Auditor | `~/homelab/flsa-exemption` | 29 CFR 541 | Universal market, class action exposure, Workday stores a static flag only |
| 3 | PFML Cross-State | `~/homelab/pfml-crossstate` | 14 state statutes | Companion to multistate-tax, market growing yearly |
| 4 | FMLA Eligibility | `~/homelab/fmla-eligibility` | 29 CFR 825 | Huge market, litigation avoidance (softer ROI story) |

### Killed (researched, not viable)

| Agent | Reason |
|-------|--------|
| Workers' Comp Classification | Rule data is proprietary (NCCI), judgment is subjective, penalty is premium adjustment |
| COBRA Continuation | Workday + ecosystem already covers well, penalties modest |
| Grant Effort Reconciliation | Too niche (higher ed only), Workday has dedicated Grants module |

## After Building a New Agent

1. Add it to the table above
2. Capture lessons from Doubt/auditor findings as a new skill: `plugins/workday-agents/skills/<slug>/SKILL.md`
3. If broadly applicable, also copy to `~/.foundry/skills/<slug>/SKILL.md`

# Plan: Recon Extension v1

Date: 2026-03-12
Version: v1
Status: in-progress

## Context

Sysadmin runs quick fleet checks from a management server against Dell servers
via iDRAC. Current workflow is ad-hoc shell one-liners that require remembering
CSV column numbers, racadm syntax, and loop boilerplate. Recon captures this
knowledge as a Context Foundry extension so Claude can generate commands
instantly from natural language descriptions.

## Current State

- Extension folder structure created
- CLAUDE.md, README.md written
- Initial inventory schema, patterns, and templates seeded
- Not yet integrated into Context Foundry's extension index

## Implementation Steps

### Phase 1: Foundation (scaffold + knowledge capture)
- [x] T1.1: Create extension folder structure following conventions
- [x] T1.2: Write CLAUDE.md with domain rules and key files
- [x] T1.3: Define inventory schema config (inventory-schema.json)
- [x] T1.4: Seed initial patterns (grep substring, SSH hang, unlabeled output)
- [x] T1.5: Create idrac-checks template with proven racadm commands
- [x] T1.6: Create batch-loops template with loop patterns
- [x] T1.7: Create network-checks template
- [x] T1.8: Write README with architecture diagrams

### Phase 2: Integration
- [ ] T2.1: Register recon in Context Foundry's extension index (extensions table in CLAUDE.md)
- [ ] T2.2: Add recon trigger rules (when to load this extension)
- [ ] T2.3: Test pattern matching -- verify recon patterns load for ops-related prompts

### Phase 3: Inventory completion
- [ ] T3.1: Map all sourceoftruth.csv columns (requires user input on actual CSV headers)
- [ ] T3.2: Document host file naming conventions and locations
- [ ] T3.3: Add iDRAC credential storage conventions (sshpass file location, etc.)

### Phase 4: Advanced templates
- [ ] T4.1: Add SNMP check templates (for switches, PDUs, non-Dell gear)
- [ ] T4.2: Add output-to-CSV template for structured recon results
- [ ] T4.3: Add drift detection template (compare current vs expected baseline)
- [ ] T4.4: Add parallel execution templates with proper error aggregation

### Phase 5: Pattern learning loop
- [ ] T5.1: Define workflow for capturing new patterns from real recon sessions
- [ ] T5.2: Add auto-save hook -- when Claude generates a useful one-liner, prompt to save as template
- [ ] T5.3: Merge recon patterns to global pattern store

## Architecture Decisions

- **Extension, not a tool**: Recon is knowledge (schemas, templates, patterns), not executable code.
  Claude reads it and generates commands. No new binaries or daemons.
- **Inventory schema is the key**: The single most valuable file is inventory-schema.json.
  Everything else is convenience. If Claude knows which column is which, it can generate any lookup.
- **Templates over scripts**: Prefer inline templates that Claude adapts over rigid scripts.
  The user wants one-liners, not a CLI tool to learn.

## Risks & Open Questions

- Actual sourceoftruth.csv column mapping unknown -- T3.1 requires user to provide headers
- iDRAC credential management varies -- need to confirm sshpass vs SSH key setup
- Some environments may use Redfish API instead of racadm -- may need Redfish templates later
- Pattern matching integration (T2.3) depends on how Context Foundry selects extensions for a given prompt

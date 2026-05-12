---
name: workday-agents-common-pitfalls
description: Workday Marketplace compliance agent pitfalls — dict-key normalization, inclusive date ranges, rule-id overlap, exemption ordering, jurisdiction-specific thresholds, SPEC drift. Use when building compliance rule engines.
metadata:
  cf-stage: both
  cf-keywords: [workday, compliance, aca, tax, pydantic, rules-engine]
  cf-severity: HIGH
  cf-citations-pass: 0
  cf-citations-wip: 0
---

# Workday Agents Common Pitfalls

Aggregated pitfalls migrated from the legacy `patterns/` JSON store. Each section is one pitfall; the planner should treat them as independent checks.

## Normalize dict keys from user input, not just values

**ID:** `dict-key-normalization` &nbsp;&nbsp; **Severity:** HIGH

**Issue.**

Pydantic field_validators on string fields normalize values (e.g., state codes to uppercase), but dict keys passed by the user are NOT normalized. Rule lookups then fail silently because the engine uses normalized codes but the dict has lowercase keys. Example: current_allocations={'pa': 1.0} vs lookup for 'PA'.

**Planner action.**

For every dict field whose keys are user-provided codes, add a field_validator(mode='before') that normalizes the keys. Do this at model definition time, not at lookup time.

**Reviewer check.**

Check every dict field on input models. If the keys are codes that get compared against normalized values elsewhere, verify a key-normalizing validator exists.

## Date range month counting must be inclusive (+1)

**ID:** `inclusive-date-range-off-by-one` &nbsp;&nbsp; **Severity:** HIGH

**Issue.**

Counting months in a date range as (end.year - start.year)*12 + (end.month - start.month) gives 11 for Jan-Dec instead of 12. This propagates into averaging calculations (hours/months) and can flip full-time/part-time determinations. The fix is +1 for inclusive ranges.

**Planner action.**

When writing date-range month counting functions, explicitly document whether the range is inclusive or exclusive. Default to inclusive (+1) for measurement periods that include both the start and end month.

**Reviewer check.**

Find every months_in_range or similar function. Verify the formula produces the correct count for Jan 1 - Dec 31 (should be 12, not 11) and Jan 1 - Jan 31 (should be 1, not 0).

## Specific rules must replace generic rules, not supplement them

**ID:** `rule-id-overlap-generic-vs-specific` &nbsp;&nbsp; **Severity:** HIGH

**Issue.**

When a generic rule (WITH-001: under-withholding) and a specific rule (WITH-003: convenience-rule under-withholding) both check the same condition, both fire for the same entity. The specific rule should REPLACE the generic, not supplement it. Without a guard, the consumer gets duplicate/confusing findings.

**Planner action.**

When adding a specific rule that covers a subset of a generic rule's cases, add an exclusion guard to the generic rule (e.g., 'and correct.method != convenience_rule'). Document which rule takes precedence.

**Reviewer check.**

For every rule module, check if any two rules can fire for the same entity/state/month. If so, verify one has a guard excluding the other's cases.

## Resolve exemptions and reciprocity before evaluating general rules

**ID:** `exemption-before-general-rules` &nbsp;&nbsp; **Severity:** HIGH

**Issue.**

General rules (NEXUS-004: withhold from day 1) fired for states covered by reciprocity agreements, producing false positives. Similarly, de minimis exemption was checked before convenience rule, incorrectly exempting NY. Rule evaluation order matters: specific overrides and exemptions must resolve first.

**Planner action.**

In the engine orchestration, explicitly order: 1) reciprocity resolution, 2) exemption/override checks (convenience rule), 3) threshold checks (de minimis), 4) general rules. Document this ordering in the engine module.

**Reviewer check.**

Trace the execution path for a state that has both a special rule (convenience, reciprocity) and a general rule (de minimis, day-1 withholding). Verify the special rule takes precedence.

## Threshold comparisons (> vs >=) vary by jurisdiction -- make configurable

**ID:** `jurisdiction-comparison-semantics` &nbsp;&nbsp; **Severity:** MEDIUM

**Issue.**

CT says 'more than 15 days' (strictly greater than), NY says '14 or more days' (greater than or equal). Using a single comparison operator for all states triggered withholding 1 day too early for CT/IL/OK. The comparison type must be a per-jurisdiction configuration field.

**Planner action.**

When modeling threshold rules, add a comparison field ('gt' or 'gte') to the rule data structure. Never hardcode the comparison operator. Read the statute language carefully: 'more than N' = gt, 'N or more' = gte.

**Reviewer check.**

For every threshold check, verify the code uses the configured comparison operator, not a hardcoded >= or >. Spot-check against the source statute for 2-3 states.

## SPEC.md counts and phase descriptions drift from implementation

**ID:** `spec-implementation-drift` &nbsp;&nbsp; **Severity:** MEDIUM

**Issue.**

SPEC.md said '~25 states' when implementation had 31. Said 'Workday Marketplace agent' when it was a standalone engine. Said '17 rules' when there were 22. Auditors caught this every round. The spec must be updated on every commit that changes counts or phase status.

**Planner action.**

After implementation, update SPEC.md counts (rules, states, tests) and phase description to match reality. Include this as a step in the plan.

**Reviewer check.**

Grep SPEC.md for numeric claims (N rules, N states, ~N). Verify each against the actual implementation. Check that phase language ('Marketplace agent' vs 'standalone engine') matches the bridge status.

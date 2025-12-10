# Gherkin Acceptance Criteria

**Version:** 2.5.4
**Added:** December 2025

## Overview

Context Foundry now includes Gherkin acceptance criteria as part of the Architect phase output. While AI agents can parse natural language equally well, Gherkin provides significant value for **Human-in-the-Loop (HIL)** workflows.

## Why Gherkin?

### Not for Machines

AI agents don't need the `Given/When/Then` scaffolding to understand intent. They parse natural language and structured markdown equally well. A bullet list of requirements works just as well for the Builder agent.

### For Humans

Gherkin shines in human-readable behavior specification:

- **Non-technical stakeholders** can review and understand acceptance criteria
- **Clear sign-off checkpoint** before Builder phase begins
- **Explicit, testable scenarios** that define exactly what "done" looks like
- **Industry standard** format many teams already know (BDD/Cucumber)

## Data Flow

```
Architect                    Human                    Builder                  Test
    │                          │                         │                       │
    ├─▶ Writes Gherkin ───────▶│                         │                       │
    │   scenarios              │                         │                       │
    │                          ├─▶ Reviews/Approves ────▶│                       │
    │                          │   (sign-off gate)       │                       │
    │                          │                         ├─▶ Reads Gherkin ─────▶│
    │                          │                         │   implements against  │
    │                          │                         │   those specs         │
    │                          │                         │                       ├─▶ Validates each
    │                          │                         │                       │   Gherkin scenario
    │                          │                         │                       │   passed
```

## Example Output

The Architect's `architecture.md` now includes:

```gherkin
Feature: User Authentication
  Users can securely log in and out of the application

  Background:
    Given the authentication service is running
    And the user database is accessible

  Scenario: Successful login with valid credentials
    Given a registered user with email "alice@example.com"
    And their password is "SecurePass123!"
    When they submit the login form with those credentials
    Then they should be redirected to "/dashboard"
    And a session cookie "auth_token" should be set
    And the cookie should expire in 24 hours

  Scenario: Failed login with incorrect password
    Given a registered user with email "alice@example.com"
    When they submit the login form with password "WrongPassword"
    Then they should see error message "Invalid email or password"
    And no session cookie should be set
    And the failed attempt should be logged

  Scenario: Account lockout after repeated failures
    Given a user with email "alice@example.com"
    And they have 2 failed login attempts in the last 15 minutes
    When they fail a third login attempt
    Then their account should be locked for 15 minutes
    And they should see "Account temporarily locked. Try again in 15 minutes."
    And an alert should be sent to security monitoring
```

## Phase Integration

### Architect Phase

Produces Gherkin scenarios in `architecture.md` under the `## Acceptance Criteria (Gherkin)` section.

**Guidelines enforced:**
- 3-7 scenarios per major feature
- Cover: happy path, error cases, edge cases, security boundaries
- Use concrete examples (real values, not placeholders)
- Each scenario should be independently testable

### Builder Phase

Pre-flight checklist now includes:
- `[x] Acceptance criteria (Gherkin scenarios) reviewed`

Verification checklist includes:
- `[ ] All Gherkin scenarios have corresponding implementation`

### Test Phase

Test report now includes an **Acceptance Criteria Validation** table:

| Scenario | Test(s) | Status | Notes |
|----------|---------|--------|-------|
| Successful login with valid credentials | `test_user_can_login` | PASS | |
| Account lockout after repeated failures | `test_account_lockout` | FAIL | See Failure #1 |

**Acceptance Criteria Coverage:** X/Y scenarios validated (Z%)

## Human-in-the-Loop Mode

When running Context Foundry in HIL mode, Gherkin scenarios serve as the primary **approval gate**:

1. Orchestrator pauses after Architect phase
2. Human reviews `architecture.md`, focusing on Gherkin scenarios
3. Human approves, edits, or rejects the acceptance criteria
4. Only after approval does Builder phase begin
5. Test phase validates against the human-approved scenarios

This ensures the final build matches human intent, not just AI interpretation.

## Related Documentation

- [Phase Handoff Flow](phase-handoff-flow.md)
- [Architecture Phase](../tools/prompts/phases/phase_architect.txt)
- [Builder Phase](../tools/prompts/phases/phase_builder.txt)
- [Test Phase](../tools/prompts/phases/phase_test.txt)

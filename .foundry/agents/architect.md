# Architect Agent Configuration

## Role
Planning specialist that creates detailed specifications and implementation plans from research.

## Input
- RESEARCH.md from Scout
- User requirements/task description

## Process
1. Analyze research findings
2. Create user stories and success criteria
3. Design technical approach with alternatives
4. Evaluate tradeoffs
5. Decompose into atomic tasks
6. Define validation criteria
7. Identify risks and mitigations

## Output Files

### SPEC.md Format
```markdown
# Specification: [Project Name]
Generated: [timestamp]
Context Usage: [X%]

## Goal
[One sentence description]

## User Stories
- As a [user], I want [feature] so that [benefit]

## Success Criteria
- [ ] [Measurable criterion 1]
- [ ] [Measurable criterion 2]

## Technical Requirements
- [Requirement 1]
- [Requirement 2]

## Out of Scope
- [What we're NOT building]
```

### PLAN.md Format
```markdown
# Implementation Plan: [Project Name]
Generated: [timestamp]
Context Usage: [X%]

## Approach
[Technical strategy]

## Architecture Decisions
| Decision | Options Considered | Choice | Rationale |
|----------|-------------------|---------|-----------|
| [Area]   | [A, B, C]         | [B]     | [Why B]   |

## Implementation Phases
1. **Phase 1**: [Description]
2. **Phase 2**: [Description]

## Testing Strategy
[How we'll validate]

## Risks & Mitigations
| Risk | Probability | Impact | Mitigation |
|------|------------|---------|------------|
```

### TASKS.md Format
```markdown
# Task Breakdown: [Project Name]
Generated: [timestamp]
Context Usage: [X%]

## Task Execution Order

### Task 1: [Name]
- **Files**: [files to modify]
- **Changes**: [specific changes]
- **Tests**: [test requirements]
- **Dependencies**: None
- **Estimated Context**: [20%]

### Task 2: [Name]
- **Dependencies**: Task 1
[etc...]
```

# Builder Agent Configuration

## Role
Implementation specialist that executes tasks from TASKS.md with continuous testing and validation.

## Process
1. Read current task from TASKS.md
2. Check context utilization
3. If >50%, trigger compaction
4. Generate tests FIRST (test-driven development)
5. Implement the solution
6. Run tests
7. Create git commit
8. Update PROGRESS.md
9. Move to next task

## Context Management
- Check utilization before EVERY task
- Compact if >50%
- Clear conversation history after compaction
- Reload only essential files

## Git Workflow
```bash
# For each task
git add [modified files]
git commit -m "Task [N]: [description]

- Implements: [what it does]
- Tests: [test coverage]
- Context: [X% utilization]"
```

## Progress Tracking (PROGRESS.md)
```markdown
# Build Progress: [Project Name]
Session: [timestamp]
Current Context: [X%]

## Completed Tasks
- [x] Task 1: [Name] (Context: 25%)
- [x] Task 2: [Name] (Context: 31%)

## Current Task
- [ ] Task 3: [Name]
  - Status: Writing tests...
  - Context: 43%

## Remaining Tasks
- [ ] Task 4: [Name]
- [ ] Task 5: [Name]

## Test Results
- Tests Passed: 12/12
- Coverage: 87%

## Notes
[Any important observations]
```

## Quality Rules
- Tests before implementation
- Each task must be atomic
- Commits must include test results
- No proceeding without passing tests
- Document unexpected challenges

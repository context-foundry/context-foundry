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

## HTML File Path Best Practices
When creating HTML files for web projects, follow these rules for file references:

### Rule 1: Use Relative Paths from HTML File Location
- If `public/index.html` references `public/styles.css`, use `href="styles.css"` (NOT `href="public/styles.css"`)
- If `public/index.html` references `public/js/app.js`, use `src="js/app.js"` (NOT `src="public/js/app.js"`)

### Rule 2: Use ./ for Same Directory
```html
<!-- Good: Same directory reference -->
<link rel="stylesheet" href="./styles.css" />
<script src="./script.js"></script>

<!-- Bad: Incorrect path -->
<link rel="stylesheet" href="public/styles.css" />
```

### Rule 3: Use ../ for Parent Directory
```html
<!-- Good: Parent directory reference -->
<link rel="stylesheet" href="../css/styles.css" />

<!-- Bad: Absolute path that won't work -->
<link rel="stylesheet" href="/css/styles.css" />
```

### Rule 4: Avoid Absolute Paths for Local Files
```html
<!-- Bad: Absolute paths break in different environments -->
<link rel="stylesheet" href="/styles.css" />

<!-- Good: Relative paths work everywhere -->
<link rel="stylesheet" href="styles.css" />
```

### Examples by Project Structure

**Structure 1: Flat public/ directory**
```
public/
  index.html
  styles.css
  script.js
```
In `index.html`:
```html
<link rel="stylesheet" href="styles.css" />
<script src="script.js"></script>
```

**Structure 2: Nested directories**
```
public/
  index.html
  css/
    styles.css
  js/
    app.js
```
In `index.html`:
```html
<link rel="stylesheet" href="css/styles.css" />
<script src="js/app.js"></script>
```

**Structure 3: HTML in subdirectory**
```
public/
  pages/
    index.html
  css/
    styles.css
```
In `pages/index.html`:
```html
<link rel="stylesheet" href="../css/styles.css" />
```

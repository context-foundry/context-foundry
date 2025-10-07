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

## Express.js Web Application Pattern

When building Express.js applications with frontend, follow these critical patterns:

### Rule 1: Serve Static Files
If project has HTML/CSS/JS files, **MUST** add static file middleware:

```javascript
const express = require('express');
const app = express();

// If frontend is in root directory
app.use(express.static(__dirname));

// OR if frontend is in public/ directory
app.use(express.static('public'));

// OR if frontend is in specific directory
app.use(express.static(path.join(__dirname, 'public')));
```

**Common mistake:**
```javascript
// BAD: No static file serving - results in "Cannot GET /"
app.get('/api/weather', (req, res) => {...});
app.listen(3000);
```

**Correct:**
```javascript
// GOOD: Serves static files first, then API routes
app.use(express.static(__dirname));
app.get('/api/weather', (req, res) => {...});
app.listen(3000);
```

### Rule 2: Implement ALL Contract Endpoints
**CRITICAL:** Every endpoint in SPEC.yaml MUST be implemented exactly as specified.

Example SPEC.yaml:
```yaml
contract:
  endpoints:
    - path: /weather/current
      method: GET
    - path: /weather/forecast
      method: GET
```

**MUST implement:**
```javascript
app.get('/weather/current', (req, res) => {...});
app.get('/weather/forecast', (req, res) => {...});
```

**NOT:**
```javascript
// BAD: Doesn't match SPEC.yaml paths
app.get('/weather', (req, res) => {...});
```

### Rule 3: Root Route or Static Files Required
Server **MUST** handle root `/` route without returning 404:

Option A: Static file serving (preferred for web apps):
```javascript
app.use(express.static(__dirname));
```

Option B: Explicit root route:
```javascript
app.get('/', (req, res) => {
    res.send('Welcome to Weather Service');
});
```

### Rule 4: Frontend/Backend Integration
If project has both frontend (HTML/JS) and backend (Express):

1. **Frontend must call backend endpoints:**
```javascript
// In frontend app.js
fetch('http://localhost:3000/api/weather?city=London')
```

2. **Backend must serve frontend:**
```javascript
// In server.js
app.use(express.static(__dirname));  // Serves index.html, css/, js/
app.get('/api/weather', (req, res) => {...});  // API endpoint
```

3. **Enable CORS if needed:**
```javascript
const cors = require('cors');
app.use(cors());
```

### Complete Express.js Template

```javascript
const express = require('express');
const path = require('path');
const app = express();
const PORT = process.env.PORT || 3000;

// Middleware
app.use(express.json());
app.use(express.static(path.join(__dirname)));  // Serve static files

// API Routes (implement ALL from SPEC.yaml)
app.get('/weather/current', async (req, res) => {
    const { city } = req.query;
    // Implementation
});

app.get('/weather/forecast', async (req, res) => {
    const { city } = req.query;
    // Implementation
});

// Start server
app.listen(PORT, () => {
    console.log(`Server running on http://localhost:${PORT}`);
});
```

### Checklist Before Completing Task
- [ ] Static file middleware added (if frontend exists)
- [ ] ALL SPEC.yaml endpoints implemented with exact paths
- [ ] Root `/` route returns 200 (not 404)
- [ ] Frontend API calls match backend endpoints
- [ ] No "Cannot GET /" errors

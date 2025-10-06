# Context Foundry TODO - 2025-10-05

## Current Issue: Weather App Search Not Working

### Problem
- Weather app loads but search button does nothing
- Recent searches display (houston, los angeles, toledo) but clicking them doesn't show weather
- No API calls being made when searching

### Root Cause
Builder (gpt-4o-mini) generated **placeholder/stub code** instead of working implementations:

1. **Incomplete function** (`frontend/app.js:32-35`):
   ```javascript
   function performSearch(search) {
       // Perform the weather search logic here (API call, etc.)  ← PLACEHOLDER!
       saveSearchToLocal(search);
   }
   ```
   No actual API call or weather display logic!

2. **Missing file**: Tasks.md specified creating `js/weather-api.js` but file doesn't exist

3. **Wrong paths**: Files created in `frontend/` instead of `js/` as task specified

### Impact
This is a **critical quality issue** - users get non-functional apps that look complete but don't work.

---

## Fixes Already Implemented Today ✅

### 1. npm Command Detection
- **File**: `tools/cli.py:326` and `workflows/autonomous_orchestrator.py:1805`
- **Fix**: Read package.json to detect correct npm command
- **Result**: Shows `npm start` for CRA, `npm run dev` for Vite

### 2. Path Resolution (FOUNDRY_ROOT)
- **File**: `workflows/autonomous_orchestrator.py:17-18, 67, 69-70, 265, 451`
- **Fix**: Use `FOUNDRY_ROOT` constant for all paths
- **Result**: Works from any directory, no more Trash folder issues

### 3. CRA Structure Requirements
- **File**: `workflows/autonomous_orchestrator.py:738-772`
- **Fix**: Added builder prompt section with:
  - public/index.html template
  - react-scripts dependency requirement
  - Common CRA files (index.css, App.css)
- **Result**: Creates proper CRA structure

### 4. CSS Import Validation
- **File**: `workflows/autonomous_orchestrator.py:1445-1447`
- **Fix**: Check file extension before adding .js (was looking for `index.css.js`)
- **Result**: Properly detects missing CSS files

### 5. Absolute Project Paths
- **File**: `workflows/autonomous_orchestrator.py:67, 69-70`
- **Fix**: Use `FOUNDRY_ROOT / "examples" / project_name`
- **Result**: Projects always created in correct location

### 6. CRA File Path Requirements (Architect)
- **File**: `workflows/autonomous_orchestrator.py:466-484`
- **Fix**: Added requirements for full paths (`src/components/*.js`)
- **Result**: Architect generates correct full paths for CRA

### 7. JSON Import Shadowing
- **File**: `workflows/autonomous_orchestrator.py` (5 locations)
- **Fix**: Removed all local `import json` statements
- **Result**: No more UnboundLocalError

---

## TODO: Fix Placeholder Code Issue

### Option 1: Add Placeholder Detection (Recommended)
**Location**: `workflows/autonomous_orchestrator.py` - Add to validation section

**Implementation**:
```python
def _detect_placeholder_code(self, all_files: List[str]) -> Dict[str, List[str]]:
    """Detect placeholder/stub code in generated files."""
    issues = []

    placeholder_patterns = [
        r'//\s*(TODO|FIXME|IMPLEMENT|ADD LOGIC|PERFORM THE)',
        r'#\s*(TODO|FIXME|IMPLEMENT)',
        r'/\*\s*(TODO|FIXME)',
        r'console\.log\(["\']Not implemented',
        r'raise NotImplementedError',
        r'pass\s*#.*implement',
    ]

    for file_path in all_files:
        if not file_path.endswith(('.js', '.py', '.ts', '.jsx', '.tsx')):
            continue

        file_full_path = self.project_dir / file_path
        if not file_full_path.exists():
            continue

        try:
            content = file_full_path.read_text()
            for pattern in placeholder_patterns:
                matches = re.findall(pattern, content, re.IGNORECASE)
                if matches:
                    issues.append(f"{file_path} contains placeholder code: {matches[0]}")
        except:
            pass

    return {"issues": issues}
```

**Call from**: `_run_builder_for_tasks()` after file creation, before final validation

### Option 2: Strengthen Builder Prompt
**Location**: `workflows/autonomous_orchestrator.py:700-702`

**Add after "DO:" section**:
```
⚠️  CRITICAL - NO PLACEHOLDER CODE:
□ NEVER use TODO comments or placeholder logic
□ NEVER use comments like "// Implement this", "// Add logic here", "// Perform the..."
□ Every function MUST have complete working implementation
□ API calls must use actual fetch/axios with real endpoints
□ Example of WRONG code:
  function performSearch(city) {
      // TODO: Fetch weather data  ❌ NEVER DO THIS
  }
□ Example of CORRECT code:
  async function performSearch(city) {
      const response = await fetch(`https://api.openweathermap.org/data/2.5/weather?q=${city}&appid=${API_KEY}`);
      const data = await response.json();
      displayWeather(data);
  }
```

### Option 3: Both (Recommended)
Implement both Option 1 (detection) and Option 2 (prevention) for defense in depth.

---

## Additional Issues to Investigate

### File Path Mismatch
- Tasks.md says create `js/weather-api.js`
- Builder created `frontend/app.js` instead
- Why is builder ignoring task file paths?
- **Check**: Builder file path extraction logic

### Project Type Detection
- README says "Static HTML" but has mixed structure (frontend/, src/)
- Should clarify detection logic
- **Check**: `_generate_readme()` project type detection

---

## Testing Checklist

After implementing placeholder detection:

- [ ] Build new weather app with foundry
- [ ] Verify no placeholder comments in generated code
- [ ] Check that search functionality works
- [ ] Confirm API calls are made
- [ ] Verify weather data displays correctly
- [ ] Test with both gpt-4o-mini and other models

---

## Notes

- gpt-4o-mini tends to generate stub code more than claude models
- May need to switch to stronger model for builder phase
- Or add explicit validation that fails build if placeholders detected
- Consider adding "smoke test" that actually runs the code and checks for basic functionality

---

## Future Enhancements

### Git as Memory System

**Concept**: Treat agent knowledge evolution as git history, not just timestamped snapshots.

**Current State**:
- `.context-foundry/history/` stores timestamped blueprint snapshots
- Difficult to diff between sessions (files have timestamps in names)
- Can't trace when specific ideas/decisions appeared
- Can't branch/merge knowledge exploration
- Manual cleanup needed (history folder grows forever)

**Proposed Enhancement**:
Commit `.context-foundry/` files to git after each agent phase, making knowledge evolution transparent and auditable.

**Benefits**:
1. ✅ `git log .context-foundry/` shows complete knowledge timeline
2. ✅ `git blame .context-foundry/PLAN.md` traces when decisions were made
3. ✅ `git diff session-1..session-5` compares how understanding evolved
4. ✅ `git branch` to explore alternative architectural approaches
5. ✅ `git checkout HEAD~10` to reconstruct what agent knew at any point
6. ✅ Standard tooling (gitk, tig, GitHub) works out of the box
7. ✅ Human-readable and transparent - anyone can audit agent reasoning

**Implementation Ideas**:

**Option 1: Commit after each agent phase (Recommended)**
```bash
# After Scout
git add .context-foundry/RESEARCH.md
git commit -m "scout: Research weather app architecture

- Identified OpenWeatherMap API
- Designed component structure
- Context: 25%"

# After Architect
git add .context-foundry/{SPEC,PLAN,TASKS}.md
git commit -m "architect: Created implementation plan

- 6 tasks identified
- CRA architecture chosen
- Estimated 2hr build time"

# After Builder Task 1
git add .context-foundry/PROGRESS.md src/components/
git commit -m "builder(task-1): Created Header component

- Files: src/components/Header.js
- Tests: 5/5 passing
- Context: 30%"
```

**Option 2: Separate git repo for knowledge**
```
project-name/
├── .git/              ← Project code commits
└── .context-foundry/
    ├── .git/          ← Agent knowledge commits (separate repo)
    ├── RESEARCH.md
    └── ...
```

**Option 3: Git notes (lightweight)**
```bash
# Attach knowledge metadata to project commits
git notes add -m "Agent context: 45%
Scout identified: OpenWeatherMap API
Architect planned: 6-task breakdown"
```

**Challenges**:
- Merge conflicts if multiple agents update same blueprint
- Commit granularity (every API call vs. batched by task?)
- Repo bloat with many .context-foundry/ commits
- Need to teach agents git commands

**Use Cases**:
```bash
# When did agent decide to use Redux?
git log -S "Redux" .context-foundry/

# What was the agent's plan 2 weeks ago?
git show HEAD~20:.context-foundry/PLAN.md

# How did the architecture decision change?
git diff v1.0..v2.0 .context-foundry/

# Explore alternative approaches
git checkout -b explore-graphql
# ... architect runs with GraphQL instead of REST
git diff main .context-foundry/PLAN.md
```

**Recommended Approach**:
- Start simple: Commit `.context-foundry/` after each major phase (Scout/Architect/Builder)
- Use conventional commits: `scout:`, `architect:`, `builder(task-N):`
- Store in same git repo as project (not separate)
- Add `.context-foundry/.git` to `.gitignore` if using Option 2

**Related Tools**:
- Could build web UI showing knowledge evolution timeline
- Integration with GitHub/GitLab for collaborative agent memory
- Export git history as "reasoning trace" for transparency
- Use git bisect to find when a bad decision was introduced

**Priority**: Medium (nice to have, not critical for core functionality)

**Effort**: ~2-3 days to implement basic version with commit hooks

---

### Git Workflow for This Feature

**Branch**: `feature/git-as-memory`

**Setup** (already done):
```bash
git checkout -b feature/git-as-memory
git push -u origin feature/git-as-memory
```

**Development workflow**:
```bash
# Make changes
vim workflows/autonomous_orchestrator.py

# Commit with conventional commit messages
git add workflows/autonomous_orchestrator.py
git commit -m "feat(memory): Add git commit after Scout phase"

# Push to GitHub
git push

# Switch back to main anytime
git checkout main

# Return to feature branch
git checkout feature/git-as-memory

# Keep feature branch up to date with main (if main gets updates)
git checkout main
git pull
git checkout feature/git-as-memory
git merge main  # Or: git rebase main
```

**When ready to merge**:
```bash
# Option 1: Direct merge
git checkout main
git merge feature/git-as-memory
git push origin main

# Option 2: Pull Request (recommended)
# - Push feature branch to GitHub
# - Create PR on GitHub: feature/git-as-memory → main
# - Review changes, run tests
# - Merge via GitHub UI
```

**Testing before merge**:
```bash
# On feature branch
cd examples/
foundry new test-memory-app "simple todo app"
# Verify git commits are created in .context-foundry/
cd test-memory-app
git log .context-foundry/  # Should show scout/architect/builder commits
```

**Clean up after merge**:
```bash
git branch -d feature/git-as-memory
git push origin --delete feature/git-as-memory
```

---

### Headless Browser Smoke Test (The Real Solution)

**Problem**: Current validation (CSS imports, file references) doesn't catch runtime bugs:
- DOM errors (getElementById returning null)
- ID mismatches between HTML/JS
- API integration failures
- Missing function definitions
- Race conditions
- Any bug that only appears when code runs

**Solution**: Run actual headless browser test after build completes

**Why This Matters**: Only way to catch bugs you haven't thought of yet. Current approach is whack-a-mole (fix DOM bug, next time it's an API bug, etc.). This solves the root cause, not symptoms.

**Implementation Phases**:

**Phase 1: Detect + Report (1-2 hours)**
- After Builder completes, detect project type (HTML/React/etc.)
- If web app, spin up Puppeteer/Playwright headless browser
- Load index.html or localhost:3000
- Capture console errors, uncaught exceptions, failed network requests
- Report to user: "⚠️  Found 2 errors: ..."
- Flag: `foundry build app "..." --verify`

**Phase 2: Auto-Fix Loop (2-3 hours)**
- After smoke test finds errors, send them back to Builder
- Builder creates "fix" tasks to resolve errors
- Re-run smoke test
- Repeat up to 3 times
- Flag: `foundry build app "..." --verify --auto-fix`
- **This is self-healing code** ⭐

**Phase 3: Interactive Testing (1 week)**
- Automated clicks, form fills, navigation
- Test user workflows, not just page load
- Flag: `foundry build app "..." --verify --interactive`

**Technical Details**:
- Use Playwright (supports Chromium, Firefox, WebKit)
- `pip install playwright` (optional dependency)
- Gracefully skip if not installed
- For static HTML: `file:///path/to/index.html`
- For React/dev servers: Start server first, then test `localhost:3000`

**Challenges**:
- API keys / external dependencies (401 errors aren't bugs)
- Dev servers (need to start server before testing)
- False positives (CORS in file://, missing favicon)
- Time overhead (5-15 seconds per test)

**Filtering Strategy**:
- JavaScript errors → MUST FIX (bugs)
- Network 4xx/5xx → WARN USER (config issue, not bug)
- Missing resources (favicon.ico) → IGNORE (not critical)
- CORS in file:// → IGNORE (expected for local HTML)

**Benefits**:
- Catches ALL runtime bugs, not just known patterns
- Turns foundry from "might work" to "definitely works"
- Reduces manual testing/debugging time
- Self-healing with --auto-fix flag

**Example Output**:
```bash
foundry build weather-app "..." --verify --auto-fix

# After build:
🧪 Running smoke test...
❌ Found 2 errors:
   • TypeError: Cannot read 'addEventListener' of null (app.js:39)
   • GET api.openweathermap.org 401 Unauthorized

🔄 Auto-fixing JavaScript errors...
   Task fix-1: Fix DOM loading in app.js

🧪 Running smoke test...
✅ All tests passed!

⚠️  Configuration warnings:
   • API returned 401 - check your API key in config.js
```

**Priority**: High (solves root cause, not symptoms)

**Effort**: 3-4 hours for full implementation

**Dependencies**: `playwright` (optional pip install)

**Location to Implement**:
- `workflows/autonomous_orchestrator.py` after line ~1620 (existing `_run_smoke_test` method)
- Add new method: `_run_headless_browser_test()`
- Add auto-fix loop in `_run_builder_for_tasks()` after all tasks complete

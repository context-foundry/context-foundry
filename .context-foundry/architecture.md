# Architecture: Security Fix for exec() Vulnerability

## System Overview
This is a targeted security fix to eliminate code injection vulnerability in setup.py. The change is minimal and focused on replacing unsafe exec() with safe regex-based version extraction.

## File Structure
```
context-foundry/
├── setup.py              ← MODIFY (lines 30-33)
├── __version__.py        ← NO CHANGE (read-only)
├── tests/                ← Verify existing tests pass
└── .context-foundry/     ← Build artifacts
```

## Component Specifications

### Modified Component: setup.py

**Current Implementation (VULNERABLE):**
```python
# Lines 30-33 - BEFORE
version_file = Path(__file__).parent / "__version__.py"
version_info = {}
exec(version_file.read_text(), version_info)
```

**New Implementation (SECURE):**
```python
# Lines 30-37 - AFTER
import re

# Read version from __version__.py safely without code execution
version_file = Path(__file__).parent / "__version__.py"
version_content = version_file.read_text(encoding='utf-8')
version_match = re.search(
    r'^__version__\s*=\s*["\']([^"\']+)["\']',
    version_content,
    re.MULTILINE
)
if not version_match:
    raise RuntimeError(
        "Unable to find version string in __version__.py. "
        "Expected format: __version__ = \"x.y.z\""
    )
version = version_match.group(1)
```

**Then update setup() call:**
```python
# Line 41 - CHANGE
version=version,  # Changed from: version_info["__version__"]
```

### Security Improvements

**Before:**
- `exec()` executes arbitrary Python code from __version__.py
- Attacker modifying __version__.py could execute code during pip install
- No validation or sandboxing

**After:**
- Regex parsing extracts only the version string
- No code execution at all
- Clear validation with error message
- Fails safely if format unexpected

### Regex Pattern Explanation
```
^__version__\s*=\s*["\']([^"\']+)["\']
│           │  │ │    │         │
│           │  │ │    │         └─ Closing quote (single or double)
│           │  │ │    └─────────── Capture group: version string (anything except quotes)
│           │  │ └──────────────── Opening quote (single or double)
│           │  └─────────────────── Optional whitespace around =
│           └────────────────────── __version__ identifier
└────────────────────────────────── Start of line (re.MULTILINE)
```

**Supported Formats:**
- `__version__ = "2.2.0"` ✅
- `__version__ = '2.2.0'` ✅
- `__version__="2.2.0"` ✅ (no spaces)
- `__version__  =  "2.2.0"` ✅ (extra spaces)

**Rejected Formats:**
- `__version__ = variable` ❌ (not a string literal)
- `# __version__ = "2.2.0"` ❌ (commented out)
- Missing __version__ entirely ❌

## Implementation Steps

### Step 1: Add re import
- Location: Top of setup.py (line 7, after other imports)
- Action: Add `import re` to imports section
- Note: `re` is stdlib, no new dependencies

### Step 2: Replace exec() block
- Location: Lines 30-33 in setup.py
- Action: Replace 4 lines with 13 lines of safe code
- Preserve: Comments explaining purpose

### Step 3: Update version reference
- Location: Line 41 in setup.py (setup() call)
- Action: Change `version_info["__version__"]` to `version`
- Reason: New implementation stores in `version` variable

### Step 4: Code formatting
- Ensure consistent indentation
- Maintain existing code style
- Keep line lengths reasonable

## Testing Strategy

### Pre-Implementation Validation
1. **Backup check**: Verify we're on feature branch
2. **Working tree**: Ensure clean git status before changes

### Post-Implementation Testing

#### Phase 1: Installation Testing
```bash
# Test 1: Local editable install
pip install -e .

# Test 2: Verify version extraction
python3 -c "from setuptools import setup; exec(open('setup.py').read())"

# Test 3: CLI command works
cf --version

# Test 4: Clean install
pip uninstall -y context-foundry
pip install .
```

#### Phase 2: Regression Testing
```bash
# Test 5: Run full test suite
pytest

# Test 6: Check for any security warnings
bandit -r . -ll

# Test 7: Verify package metadata
pip show context-foundry
```

#### Phase 3: Security Validation
```bash
# Test 8: Confirm no exec/eval in setup.py
grep -n "exec\|eval" setup.py

# Test 9: Verify regex parsing works
python3 -c "
import re
from pathlib import Path
content = Path('__version__.py').read_text()
match = re.search(r'^__version__\s*=\s*[\"']([^\"']+)[\"']', content, re.MULTILINE)
print(f'Extracted version: {match.group(1)}')
"
```

### Success Criteria
- ✅ `pip install -e .` completes successfully
- ✅ Correct version extracted (2.2.0)
- ✅ All existing tests pass
- ✅ No exec() in setup.py
- ✅ CLI command `cf` works
- ✅ Package metadata correct

### Edge Cases to Test
1. **Missing __version__.py**: Should raise RuntimeError
2. **Malformed version**: Should raise RuntimeError with clear message
3. **Different quotes**: Should work with both ' and "
4. **Extra whitespace**: Should handle variations

## Error Handling

### Clear Error Messages
```python
if not version_match:
    raise RuntimeError(
        "Unable to find version string in __version__.py. "
        "Expected format: __version__ = \"x.y.z\""
    )
```

**Benefits:**
- Developer-friendly error message
- Shows expected format
- Fails during setup, not runtime
- Easy to debug if __version__.py format changes

## Rollback Plan
If issues arise:
1. Git branch already created: `self-improvement/task-f4c4a009`
2. Can easily revert: `git checkout main`
3. Original code preserved in git history
4. No changes to __version__.py (only setup.py modified)

## Documentation Updates
- Commit message will reference issue #108
- PR description will explain security fix
- No user-facing docs need updating (internal change)

## Security Checklist
- [ ] No exec() or eval() in modified code
- [ ] No dynamic code execution
- [ ] Input validation (regex match check)
- [ ] Clear error messages
- [ ] Fails safely if input unexpected
- [ ] Uses only standard library (re module)
- [ ] No new dependencies introduced
- [ ] Code is readable and maintainable

## Deployment Process
1. Commit changes with security-focused message
2. Push to branch: `self-improvement/task-f4c4a009`
3. Create PR with title: "Security: Fix code injection risk in setup.py exec()"
4. PR description references: "Fixes #108"
5. Request review from maintainers
6. Merge after approval

## Impact Assessment
- **Users**: No impact (internal change only)
- **Installation**: No change in behavior
- **Dependencies**: No new dependencies
- **Performance**: Negligible (regex vs exec)
- **Security**: HIGH improvement (removes code execution)

## Architecture Complete
This is a minimal, focused security fix that eliminates the exec() vulnerability while maintaining all existing functionality.

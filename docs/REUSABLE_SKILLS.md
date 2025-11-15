# Reusable Skills Development

**Pattern from**: [Anthropic's Code Execution with MCP](https://www.anthropic.com/news/building-effective-agents-with-code-execution-and-mcp)

Context Foundry implements Anthropic's **Reusable Skills Development** pattern to automatically capture, index, and reuse successful code implementations across projects.

---

## Overview

Instead of researching and implementing the same solutions repeatedly (JWT auth, database connections, API clients, etc.), Context Foundry:

1. **Searches** existing skills library before building from scratch (Scout phase)
2. **Captures** successful implementations after tests pass (Test phase)
3. **Tracks** success rates across projects (Feedback phase)
4. **Recommends** high-quality skills (≥70% success rate) for future builds

This creates a **self-improving system** where each successful build contributes reusable components for future projects.

---

## How It Works

### Phase 1: Scout - Search Before Building

When starting a new project, Scout agents first search the skills library:

```python
# Scout searches for existing skills
results = search_skills(
    query="JWT authentication FastAPI",
    project_type="fastapi",
    min_success_rate=0.7  # Only high-quality skills
)

if results:
    # Reuse existing implementation
    skill = load_skill(results[0]["skill_id"])
    # Copy skill["implementation"]["code"] to project
else:
    # Research from scratch, flag for capture
```

**Benefits**:
- Saves research time
- Proven implementations (>70% success rate)
- Consistent patterns across projects

### Phase 2: Test - Capture After Success

When tests pass, the Test agent identifies reusable components:

```python
# After tests PASS, identify reusable code
if test_status == "PASSED":
    save_skill(
        title="JWT Authentication with FastAPI",
        description="Complete JWT auth with login, refresh, protected routes",
        code=implementation_code,  # Full implementation
        file_type="python",
        project_type="fastapi",
        tags=["authentication", "jwt", "security"],
        requirements=["fastapi", "python-jose[cryptography]", "passlib"],
        file_path="auth/jwt_auth.py",
        example=usage_example
    )
```

**What Gets Captured**:
- ✅ Authentication implementations
- ✅ Database configurations
- ✅ API client wrappers
- ✅ Testing utilities
- ✅ Deployment scripts
- ✅ UI components with tests

**What Doesn't**:
- ❌ Project-specific business logic
- ❌ One-off scripts
- ❌ Hardcoded configurations

### Phase 3: Feedback - Track Success Rates

After each build, metrics are updated:

```python
# If skill was reused and build succeeded
update_skill_metrics(
    skill_id="skl-jwt-authentication-001",
    project_name="my-api-project",
    success=True  # Tests passed!
)

# Success rate improves over time
# 3 successes / 4 uses = 75% success rate
```

Skills with high success rates get recommended more frequently. Skills with <50% success rate after 10+ uses are candidates for removal.

---

## Storage Architecture

### Hybrid Storage (JSON + Database + Markdown)

Each skill is stored in three formats:

**1. JSON (Primary Storage)**
```
~/.context-foundry/skills/{category}/{skill_id}.json
```

Example structure:
```json
{
  "skill_id": "skl-jwt-authentication-001",
  "version": "1.0",
  "created_at": "2025-01-15T10:00:00Z",
  "metadata": {
    "title": "JWT Authentication with FastAPI",
    "description": "Complete JWT auth implementation",
    "category": "authentication",
    "project_type": "fastapi"
  },
  "implementation": {
    "code": "... full implementation ...",
    "file_path": "auth/jwt_auth.py",
    "dependencies": ["fastapi", "python-jose"]
  },
  "metrics": {
    "usage_count": 12,
    "success_rate": 0.85,
    "projects_used": [...]
  },
  "tags": ["authentication", "jwt", "security"]
}
```

**2. Markdown (Human-Readable)**
```
~/.context-foundry/skills/{category}/{skill_id}.md
```

Auto-generated documentation with:
- Overview and description
- Full implementation code
- Usage examples
- Dependencies
- Success metrics

**3. Context Codex (Fast Search)**

Skills are indexed in the SQLite Context Codex for fast full-text search.

---

## MCP Tools

Four MCP tools are available to agents:

### save_skill()

```python
save_skill(
    title: str,              # "JWT Authentication"
    description: str,        # What it does
    code: str,              # Full implementation
    file_type: str,         # python, typescript, etc.
    project_type: str,      # fastapi, react, etc.
    tags: List[str],        # ["authentication", "jwt"]
    requirements: List[str], # Dependencies
    file_path: str,         # Suggested path
    example: str            # Usage example
) -> str                    # Returns skill_id
```

### search_skills()

```python
search_skills(
    query: str,                    # "JWT authentication"
    project_type: Optional[str],   # Filter by project type
    min_success_rate: float = 0.0, # Minimum quality threshold
    limit: int = 10               # Max results
) -> List[Dict]                   # Skill summaries
```

### load_skill()

```python
load_skill(
    skill_id: str
) -> Optional[Dict]  # Full skill details
```

### update_skill_metrics()

```python
update_skill_metrics(
    skill_id: str,
    project_name: str,
    success: bool  # Did the build succeed?
) -> bool
```

---

## Integration with Build Pipeline

### Scout Phase

```markdown
**REUSABLE SKILLS CHECK:**

Before researching from scratch, search for existing implementations!

1. Extract key technical requirements
2. Search: search_skills(query, project_type, min_success_rate=0.7)
3. If found ≥70% success: USE THE EXISTING SKILL
4. If not found: Research from scratch, flag for capture
```

### Test Phase

```markdown
**SKILL CAPTURE (WHEN TESTS PASS):**

After successful testing, identify reusable implementations:

1. Identify components solving common problems
2. Use save_skill() to capture each one
3. Document in test-report.md
```

### Feedback Phase

```markdown
**UPDATE SKILL METRICS:**

Track success rates of reused skills:

1. Read scout-report.md for skills that were reused
2. For each skill: update_skill_metrics(skill_id, project_name, success)
3. Success rates improve over time
```

---

## Example: Full Lifecycle

### Build #1: Create FastAPI JWT Auth

1. **Scout**: No existing JWT auth for FastAPI → Research from scratch
2. **Architect**: Design JWT auth with login, refresh, protected routes
3. **Builder**: Implement authentication system
4. **Test**: ✅ All tests pass
5. **Test (Capture)**:
   ```python
   save_skill(
       title="JWT Authentication with FastAPI",
       code=jwt_implementation,
       tags=["authentication", "jwt", "fastapi"]
   )
   # Returns: "skl-jwt-authentication-001"
   ```
6. **Feedback**: Skill created, success_rate=0.0 (not yet used)

### Build #2: Another FastAPI App Needs Auth

1. **Scout**:
   ```python
   results = search_skills(
       "JWT authentication",
       project_type="fastapi",
       min_success_rate=0.7
   )
   # Finds skl-jwt-authentication-001 but success_rate=0.0 (below threshold)
   # Still shown as "new skill worth trying"
   ```
2. **Builder**: Reuses the skill implementation
3. **Test**: ✅ All tests pass
4. **Feedback**:
   ```python
   update_skill_metrics(
       skill_id="skl-jwt-authentication-001",
       project_name="my-second-api",
       success=True
   )
   # Success rate: 1/1 = 100%
   ```

### Build #3-5: More Projects Use the Skill

Each successful use increments usage_count and updates success_rate:

- Build #3: Success → 2/2 = 100%
- Build #4: Success → 3/3 = 100%
- Build #5: Failed (needed customization) → 3/4 = 75%

### Build #6+: High-Confidence Recommendations

```python
results = search_skills(
    "JWT authentication",
    project_type="fastapi",
    min_success_rate=0.7  # High-quality only
)

# Returns skl-jwt-authentication-001 with:
# - success_rate: 0.75 (above threshold!)
# - usage_count: 4
# - High confidence this will work
```

---

## Skill Categories

Skills are automatically categorized based on tags:

| Category | Tags | Examples |
|----------|------|----------|
| **authentication** | authentication, auth, jwt, oauth, session | JWT auth, OAuth2 flow, session management |
| **database** | database, db, sql, postgres, mysql, mongodb | Connection pools, migrations, ORM setup |
| **api** | api, rest, graphql, client, wrapper | API clients, error handling, rate limiting |
| **testing** | testing, test, mock, fixture | Test fixtures, mocks, data generators |
| **deployment** | deployment, deploy, docker, ci, cd | Docker configs, CI/CD workflows |
| **ui** | ui, component, react, vue, frontend | Reusable React/Vue components |
| **utils** | Default for all others | Data validation, formatting, parsing |

---

## Success Rate Thresholds

| Success Rate | Interpretation | Action |
|--------------|----------------|--------|
| ≥ 90% | Highly reliable | Always recommend |
| 70-89% | Good quality | Recommend by default |
| 50-69% | Moderate quality | Show with warning |
| < 50% | Poor quality | Review or remove after 10+ uses |
| None (0.0) | New skill | Worth trying, no track record |

---

## Benefits

### For Individual Projects

- **Faster Development**: Skip research for common patterns
- **Proven Implementations**: Reuse code with 70%+ success rate
- **Consistency**: Same auth/DB patterns across all your projects

### Across All Builds (Self-Improvement)

- **Knowledge Accumulation**: Each successful build adds to the library
- **Cross-Project Learning**: Pattern from API build #1 prevents issue in API build #50
- **Quality Filtering**: High success rate = reliable implementation
- **Continuous Improvement**: Success rates guide future recommendations

### Comparison to Traditional Approach

| Traditional | Reusable Skills |
|------------|-----------------|
| Research JWT auth every time | Search existing library first |
| No tracking of what works | Success rates tracked automatically |
| Copy-paste between projects manually | Automated capture and reuse |
| No quality metrics | 70%+ success rate threshold |
| Knowledge stays local | Builds from all projects improve the library |

---

## Implementation Details

### File Structure

```
~/.context-foundry/skills/
├── index.json                    # Fast lookup index
├── authentication/
│   ├── skl-jwt-authentication-001.json
│   ├── skl-jwt-authentication-001.md
│   ├── skl-oauth2-flow-001.json
│   └── skl-oauth2-flow-001.md
├── database/
│   ├── skl-postgres-pool-001.json
│   ├── skl-postgres-pool-001.md
│   └── ...
├── api/
├── testing/
├── deployment/
├── ui/
└── utils/
```

### SkillsManager Class

Core Python class handling all skill operations:

```python
from tools.skills.manager import SkillsManager

manager = SkillsManager()

# Save a skill
skill_id = manager.save_skill(
    title="...",
    code="...",
    # ...
)

# Search skills
results = manager.search_skills("JWT", min_success_rate=0.7)

# Load skill
skill = manager.load_skill("skl-jwt-authentication-001")

# Update metrics
manager.update_metrics("skl-jwt-authentication-001", "my-project", True)
```

### Context Codex Integration

Skills are automatically indexed in the Context Codex database for fast full-text search:

```python
# Codex entry created automatically when saving skill
codex_entry_id = manager._save_to_codex(skill)

# Enables fast search across thousands of skills
# Falls back to JSON-based search if Codex unavailable
```

---

## Testing

Comprehensive test suite with 21 tests covering:

```bash
pytest tests/test_skills_manager.py -v

# Test categories:
# - Save operations (JSON + markdown + Codex)
# - Search functionality (query, filters, thresholds)
# - Load operations
# - Metrics tracking
# - Markdown generation
# - Full lifecycle integration
# - Edge cases
```

---

## Future Enhancements

- **Skill versioning**: Track evolution of implementations over time
- **Skill dependencies**: Link related skills (e.g., JWT auth requires token utils)
- **Community sharing**: Share anonymized successful patterns with other Context Foundry users
- **Auto-detection**: Automatically suggest skill capture during builds
- **Skill composition**: Combine multiple skills into higher-level patterns

---

## See Also

- [Anthropic's Code Execution Guide](https://www.anthropic.com/news/building-effective-agents-with-code-execution-and-mcp)
- [Context Codex Documentation](CONTEXT_CODEX.md)
- [Build Pipeline Documentation](BUILD_PIPELINE.md)
- [SkillsManager API Reference](../tools/skills/README.md)

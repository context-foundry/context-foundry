# Pattern Library

Self-improving system that learns from each successful build and suggests proven patterns for future projects.

## Quick Start

### 1. Extract Patterns from a Session

```bash
cd ~/context-foundry

# Extract patterns from a completed session
python3 foundry/patterns/pattern_extractor.py --session checkpoints/ralph/session_123
```

### 2. Search for Patterns

```python
from foundry.patterns import PatternLibrary

lib = PatternLibrary()

# Semantic search
results = lib.search_patterns("FastAPI CRUD endpoints")

for pattern_id, code, description, similarity in results:
    print(f"Pattern #{pattern_id}: {description} ({similarity:.0%} match)")
    print(code[:200])  # Preview
```

### 3. Use Pattern Injection

```python
from foundry.patterns import PatternLibrary
from ace.pattern_injection import PatternInjector

lib = PatternLibrary()
injector = PatternInjector(lib)

# Enhance a prompt with relevant patterns
enhanced_prompt, pattern_ids = injector.enhance_prompt(
    original_prompt="Build a REST API",
    task_description="Create FastAPI endpoints for user management"
)

print(enhanced_prompt)  # Now includes relevant patterns!
```

### 4. Analyze Session Metrics

```bash
# Analyze a completed session
python3 tools/analyze_session.py session_123 --patterns-db foundry/patterns/patterns.db

# Analyze recent sessions
python3 tools/analyze_session.py --recent 5

# Compare two sessions
python3 tools/analyze_session.py --compare session_123 session_456
```

## Components

### PatternLibrary

Central pattern storage and retrieval with semantic search.

**Features:**
- SQLite database with embeddings
- Semantic search using sentence-transformers
- Pattern effectiveness tracking
- Deduplication
- Usage statistics

### PatternExtractor

Automatically extract patterns from successful code.

**Extraction Logic:**
- AST parsing for Python
- Cyclomatic complexity analysis
- Framework detection
- Test pattern extraction
- Similarity checking

### PatternInjector

Inject relevant patterns into prompts.

**Features:**
- Semantic pattern matching
- Success rate filtering
- Phase-specific injection (Scout/Architect/Builder)
- Usage tracking

### SessionAnalyzer

Post-run analysis and metrics.

**Metrics Tracked:**
- Completion rate
- Context efficiency
- Time per task
- Token usage
- Cost estimation
- Pattern effectiveness

## Database Schema

```sql
-- Patterns table
CREATE TABLE patterns (
    id INTEGER PRIMARY KEY,
    code TEXT NOT NULL,
    description TEXT,
    tags TEXT,
    language TEXT,
    framework TEXT,
    usage_count INTEGER DEFAULT 0,
    success_count INTEGER DEFAULT 0,
    avg_rating REAL DEFAULT 0.0,
    embedding BLOB,
    created_at TIMESTAMP,
    updated_at TIMESTAMP
);

-- Pattern usage tracking
CREATE TABLE pattern_usage (
    id INTEGER PRIMARY KEY,
    pattern_id INTEGER,
    session_id TEXT,
    task_id TEXT,
    rating INTEGER,
    timestamp TIMESTAMP
);

-- Session metrics
CREATE TABLE sessions (
    id TEXT PRIMARY KEY,
    project_name TEXT,
    completion_rate REAL,
    metrics_json TEXT,
    created_at TIMESTAMP
);
```

## Configuration

Edit `foundry/patterns/config.yaml`:

```yaml
extraction:
  min_complexity: 3      # Minimum cyclomatic complexity
  min_lines: 5           # Minimum lines of code
  max_similarity: 0.9    # Deduplication threshold

search:
  default_limit: 5       # Results to return
  min_relevance: 0.6     # Similarity threshold

injection:
  enabled: true
  max_patterns: 3        # Patterns per prompt
  min_success_rate: 70   # Only inject 70%+ success patterns
```

## Integration

### Automatic Integration

Pattern injection is automatically enabled when using:
- `workflows/autonomous_orchestrator.py`
- `ace/ralph_wiggum.py`
- `tools/overnight_session.sh`

### Manual Integration

```python
from foundry.patterns import PatternLibrary
from ace.pattern_injection import PatternInjector

# Initialize
lib = PatternLibrary()
injector = PatternInjector(lib, max_patterns=3, min_success_rate=70)

# In your workflow
enhanced_prompt, pattern_ids = injector.inject_into_builder_prompt(
    base_prompt=builder_prompt,
    project_name="my-app",
    task="Build API",
    spec=spec_content
)

# Use enhanced_prompt with Claude API
response = claude_client.call_claude(enhanced_prompt)

# After completion, rate patterns
for pattern_id in pattern_ids:
    lib.rate_pattern(pattern_id, rating=5, session_id=session_id)
```

## Workflow

### 1. During Build

Patterns are automatically injected into prompts based on task description.

### 2. After Build

Extract patterns from successful code:

```bash
python3 foundry/patterns/pattern_extractor.py --session checkpoints/ralph/session_123
```

### 3. Post-Analysis

Analyze metrics and update pattern ratings:

```bash
python3 tools/analyze_session.py session_123 --patterns-db foundry/patterns/patterns.db
```

## Expected Benefits

**After 10 sessions:**
- 50+ patterns extracted
- 80% faster task completion
- Higher quality code
- Lower costs (less trial and error)

**After 100 sessions:**
- 500+ patterns extracted
- Framework-specific libraries
- Project templates auto-generated
- Best practices codified

## Example Patterns

### Authentication Pattern

```python
from fastapi import Depends, HTTPException, status
from fastapi.security import OAuth2PasswordBearer

oauth2_scheme = OAuth2PasswordBearer(tokenUrl="token")

async def get_current_user(token: str = Depends(oauth2_scheme)):
    user = decode_token(token)
    if not user:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid credentials"
        )
    return user
```

**Success Rate**: 95%
**Used**: 12 times
**Tags**: authentication, fastapi, oauth2

### Validation Pattern

```python
from pydantic import BaseModel, validator

class UserCreate(BaseModel):
    email: str
    password: str

    @validator('email')
    def validate_email(cls, v):
        if '@' not in v:
            raise ValueError('Invalid email')
        return v.lower()

    @validator('password')
    def validate_password(cls, v):
        if len(v) < 8:
            raise ValueError('Password too short')
        return v
```

**Success Rate**: 92%
**Used**: 8 times
**Tags**: validation, pydantic, api

## Troubleshooting

### Database Not Found

```bash
# Database is created automatically on first use
python3 -c "from foundry.patterns import PatternLibrary; PatternLibrary()"
```

### No Patterns Found

```bash
# Extract from a session first
python3 foundry/patterns/pattern_extractor.py --session checkpoints/ralph/session_123
```

### Import Errors

```bash
# Install dependencies
pip3 install sentence-transformers numpy
```

## Testing

```bash
# Test PatternLibrary
python3 foundry/patterns/pattern_manager.py

# Test PatternExtractor
python3 foundry/patterns/pattern_extractor.py --session examples/first-project

# Test PatternInjector
python3 ace/pattern_injection.py

# Test SessionAnalyzer
python3 tools/analyze_session.py --recent 1
```

## Performance

- **Embedding Generation**: ~50ms per pattern
- **Similarity Search**: ~10ms for 1000 patterns
- **Storage**: ~100MB for 1000 patterns
- **Additional API Cost**: $0 (uses local embeddings)

## Future Enhancements

- [ ] Multi-language support (JavaScript, TypeScript, Go)
- [ ] Visual pattern browser (web UI)
- [ ] Pattern marketplace (share across teams)
- [ ] Auto-templating (generate project scaffolds)
- [ ] A/B testing (compare pattern effectiveness)
- [ ] Pattern versioning
- [ ] Conflict detection
- [ ] Performance profiling

---

**Self-improving Context Foundry that gets better with every build!**

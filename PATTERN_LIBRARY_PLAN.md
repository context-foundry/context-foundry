# Pattern Library & Continuous Learning System - Implementation Plan

## Overview

Create a self-improving system that learns from each successful build, extracts reusable patterns, and suggests them for future projects.

## Status: READY FOR IMPLEMENTATION

This document provides complete specifications. Implement in phases:
1. Pattern storage (SQLite + embeddings)
2. Pattern extraction from successful builds
3. Session analysis and metrics
4. Pattern injection into prompts

## Core Components

### 1. Pattern Manager (`foundry/patterns/pattern_manager.py`)

**Purpose**: Central pattern library management

**Dependencies**:
```bash
pip3 install sentence-transformers sqlite3 numpy
```

**Class Structure**:
```python
class PatternLibrary:
    def __init__(self, db_path="foundry/patterns/patterns.db"):
        self.db = sqlite3.connect(db_path)
        self.model = SentenceTransformer('all-MiniLM-L6-v2')  # For embeddings
        self._init_database()

    def extract_pattern(self, code, metadata):
        """Extract pattern from successful code."""
        # Generate embedding
        embedding = self.model.encode(code)

        # Store in database
        cursor = self.db.execute(
            """INSERT INTO patterns
               (code, description, tags, language, framework, embedding)
               VALUES (?, ?, ?, ?, ?, ?)""",
            (code, metadata['description'], json.dumps(metadata['tags']),
             metadata['language'], metadata['framework'], embedding.tobytes())
        )

        return cursor.lastrowid

    def search_patterns(self, query, limit=5):
        """Semantic search for relevant patterns."""
        # Encode query
        query_embedding = self.model.encode(query)

        # Get all patterns with embeddings
        patterns = self.db.execute(
            "SELECT id, code, description, embedding FROM patterns"
        ).fetchall()

        # Calculate cosine similarity
        similarities = []
        for p_id, code, desc, emb_bytes in patterns:
            p_embedding = np.frombuffer(emb_bytes, dtype=np.float32)
            similarity = np.dot(query_embedding, p_embedding) / (
                np.linalg.norm(query_embedding) * np.linalg.norm(p_embedding)
            )
            similarities.append((p_id, code, desc, similarity))

        # Return top N
        similarities.sort(key=lambda x: x[3], reverse=True)
        return similarities[:limit]

    def apply_pattern(self, pattern_id, context):
        """Get pattern for injection into prompt."""
        pattern = self.db.execute(
            "SELECT code, description, usage_count, success_count FROM patterns WHERE id=?",
            (pattern_id,)
        ).fetchone()

        if not pattern:
            return None

        code, desc, usage, success = pattern
        success_rate = (success / usage * 100) if usage > 0 else 0

        return {
            'id': pattern_id,
            'code': code,
            'description': desc,
            'success_rate': success_rate,
            'usage_count': usage
        }

    def rate_pattern(self, pattern_id, rating, session_id):
        """Track pattern effectiveness."""
        # Update pattern stats
        self.db.execute(
            """UPDATE patterns
               SET usage_count = usage_count + 1,
                   success_count = success_count + ?,
                   avg_rating = (avg_rating * usage_count + ?) / (usage_count + 1)
               WHERE id = ?""",
            (1 if rating >= 4 else 0, rating, pattern_id)
        )

        # Record usage
        self.db.execute(
            """INSERT INTO pattern_usage (pattern_id, session_id, rating)
               VALUES (?, ?, ?)""",
            (pattern_id, session_id, rating)
        )

        self.db.commit()
```

**Key Features**:
- **Embeddings**: Use sentence-transformers for semantic search
- **Deduplication**: Check similarity before storing new patterns
- **Ratings**: Track success/failure to improve suggestions
- **Metadata**: Tags, language, framework for filtering

---

### 2. Pattern Extractor (`foundry/patterns/pattern_extractor.py`)

**Purpose**: Automatically extract patterns from successful builds

**Extraction Logic**:
```python
class PatternExtractor:
    def __init__(self, pattern_library):
        self.library = pattern_library

    def extract_from_session(self, session_dir):
        """Extract patterns from completed session."""
        patterns_found = []

        # 1. Find all code files
        code_files = self._discover_code_files(session_dir)

        # 2. Parse and analyze each file
        for file_path in code_files:
            # AST parsing for Python
            if file_path.endswith('.py'):
                patterns = self._extract_python_patterns(file_path)
                patterns_found.extend(patterns)

        # 3. Extract test patterns
        test_files = self._discover_test_files(session_dir)
        for file_path in test_files:
            test_patterns = self._extract_test_patterns(file_path)
            patterns_found.extend(test_patterns)

        # 4. Store unique patterns
        for pattern in patterns_found:
            # Check if similar pattern exists
            similar = self.library.search_patterns(pattern['code'], limit=1)
            if not similar or similar[0][3] < 0.9:  # 90% similarity threshold
                self.library.extract_pattern(pattern['code'], pattern)

        return len(patterns_found)

    def _extract_python_patterns(self, file_path):
        """Extract patterns from Python file using AST."""
        import ast

        with open(file_path) as f:
            tree = ast.parse(f.read())

        patterns = []

        for node in ast.walk(tree):
            # Extract class definitions
            if isinstance(node, ast.ClassDef):
                pattern = {
                    'code': ast.get_source_segment(open(file_path).read(), node),
                    'description': f"Class pattern: {node.name}",
                    'tags': ['class', 'python'],
                    'language': 'python',
                    'framework': self._detect_framework(node)
                }
                patterns.append(pattern)

            # Extract reusable functions
            if isinstance(node, ast.FunctionDef):
                # Skip __init__, test functions, etc.
                if not node.name.startswith('_') and not node.name.startswith('test_'):
                    # Check complexity
                    if self._calculate_complexity(node) > 3:  # Non-trivial
                        pattern = {
                            'code': ast.get_source_segment(open(file_path).read(), node),
                            'description': f"Function: {node.name}",
                            'tags': ['function', 'python'],
                            'language': 'python',
                            'framework': self._detect_framework(node)
                        }
                        patterns.append(pattern)

        return patterns

    def _extract_test_patterns(self, file_path):
        """Extract successful test patterns."""
        # Run tests, track which passed
        # Extract those test structures as patterns
        pass

    def _calculate_complexity(self, node):
        """Calculate cyclomatic complexity."""
        # Simple heuristic: count branches
        complexity = 1
        for child in ast.walk(node):
            if isinstance(child, (ast.If, ast.For, ast.While, ast.ExceptHandler)):
                complexity += 1
        return complexity

    def _detect_framework(self, node):
        """Detect framework from imports."""
        # Check for FastAPI, Flask, Django, etc.
        pass
```

**Extraction Triggers**:
1. After each successful build (Builder phase complete)
2. Manual: `python extract_patterns.py --session session_id`
3. Batch: `python extract_patterns.py --all`

---

### 3. Session Analyzer (`tools/analyze_session.py`)

**Purpose**: Post-run analysis and continuous improvement

**Metrics Tracked**:
```python
class SessionAnalyzer:
    def analyze(self, session_id):
        """Analyze completed session."""
        metrics = {
            'completion': self._calculate_completion_rate(session_id),
            'context': self._analyze_context_efficiency(session_id),
            'tests': self._calculate_test_coverage(session_id),
            'time': self._analyze_time_metrics(session_id),
            'tokens': self._analyze_token_usage(session_id),
            'cost': self._calculate_cost(session_id),
            'patterns': self._analyze_pattern_usage(session_id)
        }

        # Generate report
        self._generate_report(session_id, metrics)

        # Update pattern ratings based on success
        self._update_pattern_ratings(session_id, metrics)

        return metrics

    def _calculate_completion_rate(self, session_id):
        """Tasks completed / total tasks."""
        progress = load_progress(session_id)
        completed = len(progress['completed'])
        total = completed + len(progress['remaining'])
        return (completed / total * 100) if total > 0 else 0

    def _analyze_context_efficiency(self, session_id):
        """Average context usage per iteration."""
        # Read from session logs
        iterations = read_session_iterations(session_id)
        avg_context = sum(i['context_pct'] for i in iterations) / len(iterations)
        return {
            'average': avg_context,
            'max': max(i['context_pct'] for i in iterations),
            'compactions': sum(1 for i in iterations if i.get('compacted'))
        }

    def _calculate_test_coverage(self, session_id):
        """Run coverage analysis on generated code."""
        # Use pytest-cov or similar
        pass

    def _analyze_pattern_usage(self, session_id):
        """Which patterns were used and how effective."""
        # Read pattern_usage table
        # Calculate success correlation
        pass

    def _generate_report(self, session_id, metrics):
        """Generate Markdown report."""
        report = f"""# Session Analysis: {session_id}

## Metrics

- **Completion Rate**: {metrics['completion']:.1f}%
- **Avg Context Usage**: {metrics['context']['average']:.1f}%
- **Context Compactions**: {metrics['context']['compactions']}
- **Test Coverage**: {metrics['tests']:.1f}%
- **Total Cost**: ${metrics['cost']:.2f}

## Performance

- Time per task: {metrics['time']['avg_per_task']:.1f}m
- Total tokens: {metrics['tokens']['total']:,}
- Tokens per task: {metrics['tokens']['per_task']:,}

## Pattern Usage

Most effective patterns:
"""
        for pattern in metrics['patterns']['top']:
            report += f"- Pattern #{pattern['id']}: {pattern['name']} ({pattern['success_rate']:.0f}% success)\n"

        # Save report
        report_file = Path(f"checkpoints/sessions/{session_id}_analysis.md")
        report_file.write_text(report)
```

**Usage**:
```bash
# Analyze single session
python tools/analyze_session.py session_id

# Analyze all recent sessions
python tools/analyze_session.py --recent 10

# Generate comparative report
python tools/analyze_session.py --compare session1 session2
```

---

### 4. Pattern Injection (`ace/pattern_injection.py`)

**Purpose**: Inject relevant patterns into Claude prompts

**Implementation**:
```python
class PatternInjector:
    def __init__(self, pattern_library):
        self.library = pattern_library

    def enhance_prompt(self, original_prompt, task_description):
        """Add relevant patterns to prompt."""
        # Search for relevant patterns
        patterns = self.library.search_patterns(task_description, limit=3)

        if not patterns:
            return original_prompt

        # Build pattern section
        pattern_section = "\n## Relevant Patterns from Past Successes\n\n"
        pattern_section += "Based on similar projects, these patterns have been effective:\n\n"

        for i, (p_id, code, desc, similarity) in enumerate(patterns, 1):
            pattern_data = self.library.apply_pattern(p_id, task_description)

            pattern_section += f"""### Pattern #{i}: {desc}
- **Success Rate**: {pattern_data['success_rate']:.0f}%
- **Used**: {pattern_data['usage_count']} times
- **Relevance**: {similarity * 100:.0f}%

```python
{code}
```

"""

        # Inject into prompt
        enhanced = f"""{original_prompt}

{pattern_section}

Consider these patterns when implementing. They've proven successful in similar contexts.
"""

        # Track usage
        for p_id, _, _, _ in patterns:
            # Will be rated after task completes
            self.library.db.execute(
                "INSERT INTO pattern_pending_usage (pattern_id, task_description) VALUES (?, ?)",
                (p_id, task_description)
            )
            self.library.db.commit()

        return enhanced
```

**Integration Points**:
1. `autonomous_orchestrator.py` - Builder phase prompts
2. `ralph_wiggum.py` - Iteration prompts
3. `prompt_generator.py` - Generated prompts

---

## Database Schema

```sql
-- foundry/patterns/schema.sql

CREATE TABLE IF NOT EXISTS patterns (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    code TEXT NOT NULL,
    description TEXT,
    tags TEXT,  -- JSON array
    language TEXT,
    framework TEXT,
    usage_count INTEGER DEFAULT 0,
    success_count INTEGER DEFAULT 0,
    avg_rating REAL DEFAULT 0.0,
    embedding BLOB,  -- NumPy array bytes
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

CREATE TABLE IF NOT EXISTS pattern_usage (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    pattern_id INTEGER,
    session_id TEXT,
    task_id TEXT,
    rating INTEGER,  -- 1-5
    timestamp TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY (pattern_id) REFERENCES patterns(id)
);

CREATE TABLE IF NOT EXISTS sessions (
    id TEXT PRIMARY KEY,
    project_name TEXT,
    completion_rate REAL,
    metrics_json TEXT,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

CREATE INDEX idx_patterns_language ON patterns(language);
CREATE INDEX idx_patterns_framework ON patterns(framework);
CREATE INDEX idx_pattern_usage_session ON pattern_usage(session_id);
```

---

## Configuration

**`foundry/patterns/config.yaml`**:
```yaml
extraction:
  min_complexity: 3  # Cyclomatic complexity threshold
  min_lines: 5       # Minimum lines of code
  max_similarity: 0.9  # Deduplication threshold

  languages:
    - python
    - javascript
    - typescript

  frameworks:
    - fastapi
    - flask
    - django
    - react
    - express

search:
  default_limit: 5
  min_relevance: 0.6  # Similarity threshold

injection:
  enabled: true
  max_patterns: 3
  min_success_rate: 70  # Only inject patterns with 70%+ success
```

---

## Testing

**Test Pattern Library**:
```bash
# Extract patterns from test session
python foundry/patterns/pattern_extractor.py --session test_123

# Search patterns
python -c "
from foundry.patterns.pattern_manager import PatternLibrary
lib = PatternLibrary()
results = lib.search_patterns('FastAPI CRUD endpoints')
for p_id, code, desc, sim in results:
    print(f'{p_id}: {desc} ({sim:.2f})')
"

# Analyze session
python tools/analyze_session.py test_123

# Check database
sqlite3 foundry/patterns/patterns.db "SELECT COUNT(*) FROM patterns;"
```

---

## Integration Timeline

**Phase 1** (Week 1): Core infrastructure
- ✓ Database schema
- ✓ PatternLibrary class
- ✓ Basic search

**Phase 2** (Week 2): Extraction
- ✓ Pattern extractor
- ✓ AST analysis
- ✓ Auto-extraction after builds

**Phase 3** (Week 3): Analysis
- ✓ Session analyzer
- ✓ Metrics calculation
- ✓ Report generation

**Phase 4** (Week 4): Injection
- ✓ Pattern injector
- ✓ Integration with orchestrator
- ✓ Feedback loop

---

## Expected Benefits

After 10 sessions:
- **50+ patterns** extracted
- **80% faster** task completion (using proven patterns)
- **Higher quality** code (tested patterns)
- **Lower costs** (less trial and error)

After 100 sessions:
- **500+ patterns** extracted
- **Framework-specific** libraries built
- **Project templates** auto-generated
- **Best practices** codified

---

## Future Enhancements

1. **Multi-language support**: JavaScript, TypeScript, Go, Rust
2. **Visual pattern browser**: Web UI for pattern library
3. **Pattern marketplace**: Share patterns across teams
4. **Auto-templating**: Generate project scaffolds from patterns
5. **A/B testing**: Compare pattern effectiveness
6. **Pattern versioning**: Track pattern evolution
7. **Conflict detection**: Warn about incompatible patterns
8. **Performance profiling**: Track pattern impact on speed

---

## Cost Analysis

**Storage**:
- SQLite database: ~100MB for 1000 patterns
- Embeddings: ~1KB per pattern
- Total: ~101MB

**Computation**:
- Embedding generation: ~50ms per pattern
- Similarity search: ~10ms for 1000 patterns
- Negligible impact on session runtime

**API Costs**:
- $0 additional (uses local embeddings)
- Optional: Use Claude for pattern descriptions (~$0.01 per pattern)

---

## Implementation Checklist

- [ ] Install dependencies (`sentence-transformers`)
- [ ] Create database schema
- [ ] Implement PatternLibrary class
- [ ] Implement PatternExtractor class
- [ ] Implement SessionAnalyzer class
- [ ] Implement PatternInjector class
- [ ] Integrate with autonomous_orchestrator.py
- [ ] Test with sample session
- [ ] Extract first 10 patterns
- [ ] Validate pattern injection works
- [ ] Generate first analysis report

---

**This is the foundation for a self-improving Context Foundry that gets better with every build!**

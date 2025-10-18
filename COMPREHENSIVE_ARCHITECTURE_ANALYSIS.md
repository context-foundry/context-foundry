## Comprehensive Architecture Analysis: Context Foundry

Based on my exploration, this is a **sophisticated AI-powered autonomous development system** called "Context Foundry" that implements a systematic three-phase workflow for software project generation.

---

### 1. PROJECT STRUCTURE AND ORGANIZATION

The codebase follows a clean modular architecture:

```
context-foundry/
├── .foundry/              # Agent role definitions & system identity
├── ace/                   # Core engine (47 Python modules)
├── workflows/             # Orchestration engines
├── foundry/               # Knowledge base & pattern library
├── blueprints/            # Generated specifications (30+ projects)
├── checkpoints/           # Session management & progress tracking
├── tools/                 # CLI interface & utilities
├── examples/              # Generated output projects
├── docs/                  # Comprehensive documentation
└── tests/                 # Test suite
```

**Key Insight:** The system separates concerns cleanly - configuration in `.foundry/`, execution logic in `ace/`, orchestration in `workflows/`, and knowledge in `foundry/`.

---

### 2. MAIN COMPONENTS AND THEIR RESPONSIBILITIES

#### **Core Three-Phase Workflow**

**Scout Phase** (`ace/scouts/`)
- Systematically explores existing codebases
- Maps dependencies and execution paths
- Generates RESEARCH.md artifacts (max 5K tokens)
- Context target: <30% utilization

**Architect Phase** (`ace/architects/`)
- Transforms research into specifications (SPEC.md, SPEC.yaml)
- Generates technical implementation plans (PLAN.md)
- Decomposes work into atomic tasks (TASKS.md)
- Creates contract tests
- **Human review checkpoint** - maximum leverage point

**Builder Phase** (`ace/builders/`)
- Executes tasks sequentially with test-first approach
- Creates git commits per task
- Automatic context compaction
- Context target: <50% utilization

#### **Multi-Provider AI Integration** (`ace/providers/`)

**9 AI Providers Supported:**
1. Anthropic (Claude) - Default
2. OpenAI (GPT-4o/GPT-4o-mini)
3. Google Gemini (2M context window)
4. Groq (ultra-fast inference)
5. GitHub Models (FREE GPT-4o access)
6. Cloudflare, Fireworks, Mistral, Z.ai

**Unified Interface:** `ace/ai_client.py` routes calls to appropriate providers per phase via environment variables (`SCOUT_PROVIDER`, `ARCHITECT_PROVIDER`, `BUILDER_PROVIDER`)

#### **Context Management** (`ace/context_manager.py`)
- Real-time token tracking against 200K window
- Automatic compaction at 40-50% threshold
- Summarization strategy (200K → 1-2K summaries)
- Emergency thresholds at 70-80%

#### **Self-Improving Pattern Library** (`foundry/patterns/`)
- SQLite database (16.9 MB) with semantic embeddings
- Extracts patterns from successful builds
- Semantic search using sentence-transformers
- Success rate tracking (>70% threshold)
- Automatic injection into prompts

#### **Cost Tracking** (`ace/cost_tracker.py`)
- Real-time tracking across 9 providers
- Per-phase cost breakdown
- Automatic pricing updates
- Token usage monitoring

---

### 3. KEY TECHNOLOGIES AND FRAMEWORKS

**Core Stack:**
- **Python 3.8+** - Primary language (85 Python files)
- **SQLite** - Pattern library & pricing database
- **Git** - Version control integration

**Key Dependencies:**
- `anthropic>=0.40.0` - Claude API client
- `click>=8.0.0` - CLI framework
- `rich>=13.0.0` - Terminal UI
- `sentence-transformers>=2.2.0` - Semantic search embeddings
- `python-dotenv>=1.0.0` - Configuration management
- `pyyaml>=6.0` - YAML config files
- `fastmcp` (optional) - Model Context Protocol server

**Optional Provider SDKs:**
- OpenAI, Google Generative AI, Groq, Mistral clients

---

### 4. DESIGN PATTERNS AND ARCHITECTURAL DECISIONS

**Key Patterns:**

1. **Three-Phase Workflow Pattern** - Research → Planning → Implementation with human checkpoint
2. **Strategy Pattern** - Each AI provider implements `BaseProvider` interface
3. **Event-Driven Architecture** - EventBroadcaster with WebSocket livestream
4. **Self-Improving System** - Pattern library learns from successful builds
5. **Context Windowing** - Sophisticated token management with thresholds
6. **Blueprint Architecture** - Local `.context-foundry/` directories preserve build context
7. **Test-Driven Development** - Contract tests + test-first builder
8. **Multi-Agent Orchestration** - Parallel Scout + Builder (67% faster)
9. **Continuous Loop Strategy** - "Ralph Wiggum" runner for overnight builds
10. **Session State Management** - File-based checkpoints, no conversation memory

**Architectural Decisions:**

- **Specs/plans are permanent, code is disposable** - Can regenerate from blueprints
- **Per-phase provider selection** - Use cheaper models for token-heavy phases
- **Human review at architect phase** - Maximum leverage point
- **Subagent isolation** - Separate conversations for efficient exploration
- **File-based state over memory** - Survive context resets

---

### 5. ENTRY POINTS AND SYSTEM FLOW

#### **Entry Point: CLI Command**
```bash
foundry build project-name "task description"
```

**File:** `tools/cli.py` → Installed as `foundry` command via setuptools

#### **Alternative Entry Point: MCP Server**
```bash
python tools/mcp_server.py
```
Exposes tools for Claude Desktop integration

#### **Execution Flow:**

```
User Command
    ↓
CLI Validation (auth, connectivity)
    ↓
AutonomousOrchestrator Init
    ↓
┌─────────────────────────────────────┐
│ Scout Phase                         │
│ - Explore codebase                  │
│ - Generate RESEARCH.md              │
└──────────────┬──────────────────────┘
               ↓
┌─────────────────────────────────────┐
│ Architect Phase                     │
│ - Generate SPEC/PLAN/TASKS          │
│ - Create contract tests             │
│ ⚠️  HUMAN REVIEW CHECKPOINT          │
└──────────────┬──────────────────────┘
               ↓
┌─────────────────────────────────────┐
│ Builder Phase                       │
│ For each task:                      │
│   - Write tests first               │
│   - Implement code                  │
│   - Compact context if needed       │
│   - Create git commit               │
└──────────────┬──────────────────────┘
               ↓
Generated Project + Session Analysis
```

#### **Supporting Systems (run in parallel):**
- **AIClient** - Routes to providers
- **ContextManager** - Tracks tokens, triggers compaction
- **CostTracker** - Calculates costs
- **PatternLibrary** - Injects relevant patterns
- **EventBroadcaster** - Livestream dashboard updates

---

### 6. NOTABLE DEPENDENCIES AND INTEGRATIONS

#### **External AI Services (9 Providers)**
- Pricing ranges from $0.05/1M (Groq) to $75/1M (Claude Opus) tokens
- GitHub Models offers FREE GPT-4o access
- Per-phase provider switching for cost optimization

#### **Databases**
1. `foundry/patterns/patterns.db` (16.9 MB) - Pattern library with embeddings
2. `ace/pricing.db` - Provider pricing information

#### **Optional Integrations**
- **Slack** - Webhooks for notifications
- **GitHub** - Token for GitHub Models provider + PR creation
- **Livestream Dashboard** - WebSocket server for real-time progress

#### **Semantic Search**
- Model: `all-MiniLM-L6-v2` via sentence-transformers
- Used for pattern matching and similarity scoring

---

### 7. TESTING STRUCTURE

**Test Files:** `tests/`
- `test_code_extraction_fix.py` - Code parsing tests
- `test_github_provider.py` - GitHub provider integration
- `test_zai_provider.py` - Z.ai provider integration

**Built-in Testing Features:**
- **Contract Test Generation** - Architect phase creates tests from specs
- **Test-First Builder** - Builder writes tests before implementation
- **Verification Harness** - `ace/verifiers/harness.py` validates tests pass
- **Continuous Testing** - Tests run after each task
- **Git Integration** - Each passing task gets a commit

**Generated Project Testing:**
- Unit tests for each module
- Integration tests for components
- Test coverage reporting

---

## Key Statistics

| Metric | Value |
|--------|-------|
| Total Python Files | 85 |
| Core Engine Modules | 47 (in `ace/`) |
| AI Providers | 9 |
| Workflow Phases | 3 (Scout → Architect → Builder) |
| Context Window | 200K tokens |
| Pattern Database Size | 16.9 MB |
| Generated Projects | 30+ in blueprints/ |
| Entry Commands | `foundry` CLI + MCP server |
| Main Orchestrator Size | 140KB |

---

## Philosophy: "Anti-Vibe Coding"

This system implements systematic, research-driven development instead of "vibes-based" prompting. The three-phase workflow ensures thorough research, careful planning with human review, and test-driven implementation - all while maintaining efficient context usage through sophisticated token management.

The self-improving pattern library means the system gets better with each successful project, and the multi-provider support enables cost optimization by using cheaper models for token-heavy research phases while reserving expensive models for critical planning.

# Enhancement: The Triune Mind - Self-Learning Architecture

## 🎯 Vision

Build an intelligent, context-aware learning system for Context Foundry that learns through three distinct methods:

1. **Autonomous Testing Discovery** (✅ exists) - Learning from test failures
2. **Human Observed Correction** (🟡 partial) - Learning from human-guided fixes via Claude Code
3. **Human Directed Research** (❌ new) - Learning through natural language teaching commands

**The Key Innovation:** Smart, context-aware pattern matching that understands what kind of project is being built and only applies relevant patterns (e.g., Roblox patterns for games, Next.js patterns for web apps, C++ patterns for systems code).

## 📖 Documentation

See the full architectural design: [`docs/enhancements/SELF_LEARNING_ARCHITECTURE.md`](https://github.com/context-foundry/context-foundry/blob/main/docs/enhancements/SELF_LEARNING_ARCHITECTURE.md)

## 🎨 Philosophy

> *"Learning is the only thing the mind never exhausts, never fears, and never regrets."* — Leonardo da Vinci

This system embodies three forms of learning that mirror human cognition:
- **Experience**: Learning through trial and error
- **Observation**: Learning by watching a master solve problems
- **Instruction**: Learning through direct teaching and guidance

## 🏗️ Key Components

### 1. Pattern Metadata Schema
Each pattern carries rich metadata describing:
- Languages, frameworks, domains, project types
- Confidence scores and validation status
- Applicability rules and exclusions
- Learning source (test/human/research)

### 2. Context-Aware Pattern Matching
Smart relevance scoring algorithm that:
- Analyzes project context from task description
- Scores each pattern's relevance (0.0 - 1.0)
- Only loads patterns above threshold
- Prevents pattern pollution across domains

**Example:**
```
Building Roblox game → Roblox patterns: 0.95 ✅
                     → Web patterns: 0.05 ⏭️

Building Next.js app → Web patterns: 0.90 ✅
                     → Roblox patterns: 0.05 ⏭️
```

### 3. Extension System
Modular knowledge domains (like existing `extensions/flowise/`):

```
extensions/
├── flowise/          # ✅ Multi-agent workflow patterns
├── roblox/           # 🆕 Game development patterns
├── nextjs/           # 🆕 Web app patterns
├── cpp/              # 🆕 Systems programming patterns
└── [user-defined]/   # 🆕 Custom domains
```

Each extension has:
- `EXTENSION_MANIFEST.json` - Defines scope and applicability
- `patterns/` - Domain-specific patterns with metadata
- `patterns/index.json` - Fast lookup table
- `templates/` - Reusable project templates
- `[DOMAIN]_REFERENCE.md` - Human-readable documentation

### 4. Research Agent
Natural language interface for human teaching:

```bash
# Domain research
cf research "Roblox game development best practices"

# Source-specific
cf research github "owner/repo" --extract-patterns
cf research docs "https://nextjs.org/docs" --domain nextjs

# Comparative
cf research compare "React vs Vue" --extract-differences
```

Agent workflow:
1. Parse natural language intent
2. Fetch from multiple sources (docs, GitHub, articles)
3. Synthesize patterns with LLM analysis
4. Enrich with metadata and context tags
5. Store in appropriate extension
6. Present summary for human validation

## 📋 Implementation Roadmap

### Phase 1: Foundation (Weeks 1-2)
- [ ] Design pattern metadata schema (JSON schema definition)
- [ ] Implement relevance scoring algorithm
- [ ] Create extension manifest system
- [ ] Build project context analyzer
- [ ] Update Scout to use context-aware pattern loading

### Phase 2: Extension System (Weeks 3-4)
- [ ] Refactor existing patterns to new schema
- [ ] Migrate Flowise patterns to extension format
- [ ] Create extension discovery mechanism
- [ ] Build pattern index for fast lookup
- [ ] Implement extension activation logic

### Phase 3: Human Observed Correction (Weeks 5-6)
- [ ] Design Claude Code integration for pattern capture
- [ ] Build session observer to track fixes
- [ ] Implement before/after state capture
- [ ] Create pattern extraction from fix sessions
- [ ] Add human-validated confidence boosting

### Phase 4: Research Agent (Weeks 7-9)
- [ ] Design Research Agent architecture
- [ ] Implement natural language command parsing
- [ ] Build multi-source research orchestration
- [ ] Create pattern synthesis engine
- [ ] Develop extension creation from research
- [ ] Add human review/approval workflow

### Phase 5: Intelligence & Optimization (Weeks 10-12)
- [ ] Tune relevance scoring weights
- [ ] Add pattern usage analytics
- [ ] Implement pattern deprecation for low-value patterns
- [ ] Build pattern conflict resolution
- [ ] Create dashboard for pattern library insights
- [ ] Add A/B testing for pattern effectiveness

## 📊 Success Metrics

**Quantitative:**
- Pattern Relevance Accuracy: % of loaded patterns actually used
- First-Time Success Rate: % of builds without pattern conflicts
- Pattern Application Rate: Patterns applied per build (by project type)
- Research Efficiency: Time from research command to usable patterns
- False Positive Rate: Patterns loaded but not applicable

**Qualitative:**
- Pattern Quality Score: Human rating of usefulness (1-5)
- Extension Coverage: Number of domains with extensions
- Learning Velocity: Rate of new pattern acquisition
- Human Teaching Engagement: Frequency of research commands

## 🎬 Example Scenarios

### Scenario A: Building a Roblox Game
```
Human: "Build a multiplayer racing game in Roblox"

Scout detects:
  - Language: Lua
  - Framework: Roblox
  - Domain: game_development
  - Project Type: roblox_game

Extension Activation:
  ✅ Roblox extension (score: 0.98)
  ⏭️ Flowise extension (score: 0.12)
  ⏭️ Next.js extension (score: 0.05)

Result: 47 Roblox patterns loaded, 0 web patterns
```

### Scenario B: Human Teaching
```
Human: "Research Roblox DataStore best practices"

Research Agent:
  1. Fetches Roblox Creator Hub docs
  2. Analyzes DataStore documentation
  3. Extracts 8 patterns:
     - Retry logic with exponential backoff
     - Request budgeting
     - Data versioning
     - Memory caching strategies
     - Error recovery
     - Testing with mocks
  4. Stores in extensions/roblox/patterns/
  5. Updates manifest and index

Result: 8 new patterns, ready for next Roblox build
```

## 🔗 Related Work

- Existing Flowise extension: `extensions/flowise/` - Demonstrates extension system
- Global pattern library: `~/.context-foundry/patterns/` - Foundation for metadata
- Scout agent: `foundry/agents/scout.py` - Entry point for context analysis
- Pattern merging: Already implemented in MCP server tools

## 💡 Community Involvement

We invite the community to:
1. Review and provide feedback on the architecture
2. Suggest additional domains for extensions
3. Contribute patterns to existing extensions
4. Build custom extensions for niche domains
5. Help tune the relevance scoring algorithm

## 📚 References

- Full Design Document: `docs/enhancements/SELF_LEARNING_ARCHITECTURE.md`
- Flowise Extension Example: `extensions/flowise/`
- Pattern Library Schema: `~/.context-foundry/patterns/`

---

**Labels:** `enhancement`, `architecture`, `learning`, `patterns`, `extensions`, `research-agent`

**Estimated Effort:** 12 weeks (3 months)

**Priority:** High - Core differentiator for Context Foundry

**Status:** 📝 Proposal / Design Phase

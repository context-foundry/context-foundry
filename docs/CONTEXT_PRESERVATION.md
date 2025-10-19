# Context Preservation in Context Foundry

**How Ephemeral Agents + Persistent Files = Zero Information Loss**

> **Core Question:** If agents disappear after each phase, how does information persist across the 7-phase build workflow?
>
> **Answer:** File-based artifacts! Each agent writes comprehensive documentation that the next agent reads.

---

## Table of Contents

1. [The Paradox](#the-paradox)
2. [How Context Flows](#how-context-flows)
3. [Step-by-Step Trace](#step-by-step-trace)
4. [Token Budget Allocation](#token-budget-allocation)
5. [Why Agents Are Ephemeral](#why-agents-are-ephemeral)
6. [Why Files Persist](#why-files-persist)
7. [Information Loss Analysis](#information-loss-analysis)
8. [Comparison with Persistent Agents](#comparison-with-persistent-agents)
9. [Visual Diagrams](#visual-diagrams)
10. [FAQ](#faq)

---

## The Paradox

**Observation:**
- Scout agent creates research report, then disappears
- Architect agent has never "talked" to Scout
- Yet Architect has ALL Scout's knowledge

**How is this possible?**

```
Scout Agent                    Architect Agent
    |                               |
    | Creates                       | Reads
    | scout-report.md               | scout-report.md
    |                               |
    ↓                               ↓
   DIES                      Has Scout's knowledge!
(context discarded)          (via file reading)
```

---

## How Context Flows

### Information Transfer Mechanism

**Traditional LLM Conversation:**
```
User: "What's the weather?"
LLM:  "It's sunny"
User: "How about tomorrow?"
LLM:  [Remembers previous message, knows we're talking about weather]
```

**Context Foundry Agent Handoff:**
```
Scout Agent:
  Research → Write scout-report.md → Die

Architect Agent:
  Read scout-report.md → Design → Write architecture.md → Die

Builder Agent:
  Read architecture.md → Implement → Write code files → Die
```

**Key Insight:** File system is the shared memory between agents!

---

## Step-by-Step Trace

### Complete Information Flow

Let's trace a real build: **"Build a weather app"**

#### Phase 1: Scout (Research)

**Input:**
- Task: "Build a weather app"
- Working directory: `/tmp/weather-app`
- Pattern library: `~/.context-foundry/patterns/common-issues.json`

**Processing:**
```
Scout Agent Context Window (fresh 200K tokens):
┌────────────────────────────────────────────────────────┐
│ System Prompt: [Standard Claude Code system]           │
│ User Message: "You are Scout. Research weather APIs..." │
│                                                          │
│ Agent's Actions:                                        │
│ 1. Web search: "weather API comparison"                │
│ 2. Read patterns: common-issues.json                   │
│ 3. Check: CORS issues for browser apps?                │
│ 4. Research: OpenWeatherMap vs WeatherAPI             │
│ 5. Decision: Recommend OpenWeatherMap (free tier)      │
│                                                          │
│ Token Usage: ~10,000 tokens                            │
└────────────────────────────────────────────────────────┘
```

**Output:**
- File created: `.context-foundry/scout-report.md` (40KB)

**scout-report.md contents:**
```markdown
# Scout Report: Weather App

## Project Summary
Build a weather application with current weather display and forecasts.

## Technology Recommendations

### Weather API
**Chosen: OpenWeatherMap API**
- Free tier: 1000 calls/day
- Supports current weather + 5-day forecast
- Good documentation
- RESTful JSON API

**Rejected Alternatives:**
- WeatherAPI.com: Smaller free tier (1M calls/month but requires credit card)
- NOAA API: US-only, complex response format

### Frontend Stack
**Chosen: React + Vite**
- Fast development server
- ES6 modules support
- Built-in dev server (prevents CORS issues - see pattern CORS-ES6-001)

**Warning from Pattern Library:**
Pattern ID: cors-es6-modules
Severity: HIGH
Issue: ES6 modules fail when loaded from file:// protocol
Solution: Use Vite dev server (configured in package.json)

### State Management
**Chosen: useState (React hooks)**
- Simple app, no global state needed
- Avoid Redux complexity for this scope

## Architecture Recommendations
- Component structure: App > WeatherDisplay > ForecastCard
- API service layer: weather-api.js
- Error handling: try-catch with user-friendly messages
- Loading states: skeleton screens during fetch

## Risks Identified
1. API key exposure (solution: use Vite env vars)
2. Rate limiting (solution: cache results for 10 min)
3. CORS errors (solution: dev server - already chosen)

## Next Steps for Architect
- Design component hierarchy following recommendations above
- Plan API service integration
- Specify error handling strategy
- Create file structure plan
```

**Agent Death:**
```
Scout Agent exits
    ↓
Context window: DISCARDED
    ↓
All conversation history: GONE FOREVER
    ↓
But scout-report.md: PERSISTS ON DISK
```

---

#### Phase 2: Architect (Design)

**Input:**
- File: `.context-foundry/scout-report.md` (just created)
- Task: "Design architecture for weather app"
- Working directory: `/tmp/weather-app`

**Processing:**
```
Architect Agent Context Window (fresh 200K tokens):
┌────────────────────────────────────────────────────────┐
│ System Prompt: [Standard Claude Code system]           │
│ User Message: "You are Architect. Read scout-report.md │
│                and design the architecture..."          │
│                                                          │
│ Agent's Actions:                                        │
│ 1. Read .context-foundry/scout-report.md (40KB)        │
│    → Entire Scout knowledge now in Architect's context │
│ 2. Design component tree                                │
│ 3. Plan API integration                                 │
│ 4. Specify file structure                               │
│ 5. Create implementation plan                           │
│                                                          │
│ Token Usage: ~15,000 tokens                            │
│   ├─ scout-report.md: ~5,000 tokens                    │
│   └─ architecture design: ~10,000 tokens               │
└────────────────────────────────────────────────────────┘
```

**Output:**
- File created: `.context-foundry/architecture.md` (60KB)

**architecture.md contents (excerpt):**
```markdown
# Architecture: Weather App

## Overview
React SPA with OpenWeatherMap API integration, built with Vite.

## File Structure
weather-app/
├── src/
│   ├── App.jsx                   # Root component
│   ├── components/
│   │   ├── WeatherDisplay.jsx    # Main weather UI
│   │   ├── ForecastCard.jsx      # Individual forecast card
│   │   └── LoadingSpinner.jsx    # Loading state
│   ├── services/
│   │   └── weatherApi.js         # OpenWeatherMap API calls
│   ├── utils/
│   │   └── formatters.js         # Date/temp formatting
│   └── index.css                 # Tailwind imports
├── .env.example                  # API key template
├── package.json                  # Dependencies
└── vite.config.js                # Vite configuration

## Component Specifications

### App.jsx
**Responsibilities:**
- Manage global state (city, weatherData, forecast)
- Handle API calls via weatherApi service
- Coordinate loading/error states
- Render WeatherDisplay and ForecastCard children

**State:**
{
  city: string,
  weatherData: object | null,
  forecast: array | null,
  loading: boolean,
  error: string | null
}

**Key Functions:**
- fetchWeather(city): Call API, update state
- handleCityChange(newCity): Update city, trigger fetch

### WeatherDisplay.jsx
**Props:** { weatherData: object }
**Displays:**
- Current temperature (convert Kelvin → Celsius)
- Weather description (capitalize)
- Humidity, wind speed
- Weather icon (use OpenWeatherMap icon URLs)

... [60KB of detailed specifications]
```

**Agent Death:**
```
Architect Agent exits
    ↓
Context window: DISCARDED (including scout-report.md that was in context)
    ↓
But architecture.md: PERSISTS ON DISK
    ↓
Contains ALL relevant knowledge from Scout + Architect's design decisions
```

---

#### Phase 3: Builder (Implementation)

**Input:**
- File: `.context-foundry/architecture.md` (just created)
- Task: "Implement weather app according to architecture"
- Working directory: `/tmp/weather-app`

**Processing:**
```
Builder Agent Context Window (fresh 200K tokens):
┌────────────────────────────────────────────────────────┐
│ System Prompt: [Standard Claude Code system]           │
│ User Message: "You are Builder. Read architecture.md   │
│                and implement all files..."              │
│                                                          │
│ Agent's Actions:                                        │
│ 1. Read .context-foundry/architecture.md (60KB)        │
│    → Now has Scout + Architect knowledge combined      │
│ 2. Create package.json (Vite, React, Tailwind)         │
│ 3. Implement src/App.jsx (API calls, state mgmt)       │
│ 4. Implement src/components/WeatherDisplay.jsx         │
│ 5. Implement src/services/weatherApi.js                │
│ 6. Create tests (Jest + React Testing Library)         │
│ 7. Write build-log.md documenting what was created     │
│                                                          │
│ Token Usage: ~30,000 tokens                            │
│   ├─ architecture.md: ~8,000 tokens                    │
│   └─ code generation: ~22,000 tokens                   │
└────────────────────────────────────────────────────────┘
```

**Output:**
- Files created: 12 source files (`src/`, `tests/`, config files)
- File created: `.context-foundry/build-log.md`

**build-log.md contents:**
```markdown
# Build Log: Weather App

## Files Created

### 1. package.json
Dependencies installed:
- react@^18.2.0
- vite@^5.0.0
- tailwindcss@^3.4.0
- axios@^1.6.0 (API calls)

Dev dependencies:
- @vitejs/plugin-react
- vitest (testing)
- @testing-library/react

**Rationale:** Following Architect's spec, using Vite for dev server (prevents CORS issue per Scout's warning)

### 2. src/App.jsx (120 lines)
State management:
- city (default: "London")
- weatherData (null | WeatherResponse)
- loading (boolean)
- error (string | null)

API integration:
- fetchWeather() calls weatherApi.getCurrentWeather()
- 10-minute caching to avoid rate limits (per Scout recommendation)

### 3. src/services/weatherApi.js (80 lines)
OpenWeatherMap integration:
- API_KEY from import.meta.env.VITE_API_KEY
- getCurrentWeather(city): Returns current weather
- getForecast(city): Returns 5-day forecast
- Error handling: Network errors, 404 (city not found), 401 (invalid API key)

**Implementation Note:** Used axios for HTTP (better error handling than fetch)

... [Detailed log of all 12 files]
```

**Agent Death:**
```
Builder Agent exits
    ↓
Context window: DISCARDED
    ↓
But 12 source files + build-log.md: PERSIST ON DISK
```

---

#### Phase 4: Test (Quality Assurance)

**Input:**
- Files: All source code (just created)
- File: `.context-foundry/architecture.md` (testing plan section)
- Task: "Run tests, fix failures"

**Processing:**
```
Test Agent Context Window (fresh 200K tokens):
┌────────────────────────────────────────────────────────┐
│ System Prompt: [Standard Claude Code system]           │
│ User Message: "You are Tester. Run tests..."           │
│                                                          │
│ Agent's Actions:                                        │
│ 1. Run: npm test                                        │
│ 2. Parse test output                                    │
│ 3. IF failures:                                         │
│    a. Read failing test file                            │
│    b. Read source file being tested                     │
│    c. Analyze root cause                                │
│    d. Write fixes-iteration-1.md                        │
│    e. Update source files                               │
│    f. Re-run tests                                      │
│ 4. Write test-final-report.md                          │
│                                                          │
│ Token Usage: ~8,000 tokens (with self-healing)         │
└────────────────────────────────────────────────────────┘
```

**Output:**
- File created: `.context-foundry/test-final-report.md`
- Possibly: `.context-foundry/test-results-iteration-1.md`, `fixes-iteration-1.md`

---

#### Phases 5-7: Documentation, Deployment, Feedback

**Phase 5:** Reads source code → Creates README.md, usage guides
**Phase 6:** Runs git commands → Creates GitHub repo, pushes code
**Phase 7:** Analyzes build → Extracts patterns → Updates pattern library

Each phase follows the same pattern:
1. Read previous artifacts
2. Perform work
3. Write new artifacts
4. Agent dies (context discarded)

---

## Token Budget Allocation

### Main Claude Code Window

```
User Request (100 tokens):
"Build a weather app with current conditions and 5-day forecast"

MCP Tool Call (200 tokens):
{
  "tool": "autonomous_build_and_deploy_async",
  "params": {...}
}

MCP Response (100 tokens):
{
  "task_id": "abc-123",
  "status": "started"
}

Status Check (100 tokens):
"What's the status of task abc-123?"

Status Response (500 tokens):
{
  "status": "completed",
  "github_url": "...",
  "tests_passed": true,
  ...
}

Claude's Summary (300 tokens):
"Your weather app is ready! Deployed to GitHub..."

───────────────────────────────────────────────────
TOTAL MAIN WINDOW: ~1,300 tokens (0.65% of 200K)
───────────────────────────────────────────────────
```

### Delegated Claude Instance

```
Orchestrator Prompt (5,000 tokens):
Full instructions for 7-phase workflow

Phase 1: Scout (10,000 tokens):
├─ Web research: 3,000 tokens
├─ Pattern library reading: 2,000 tokens
├─ Analysis and recommendations: 3,000 tokens
└─ Writing scout-report.md: 2,000 tokens

Phase 2: Architect (15,000 tokens):
├─ Reading scout-report.md: 5,000 tokens
├─ Architecture design: 7,000 tokens
└─ Writing architecture.md: 3,000 tokens

Phase 3: Builder (30,000 tokens):
├─ Reading architecture.md: 8,000 tokens
├─ Code generation (12 files): 20,000 tokens
└─ Writing build-log.md: 2,000 tokens

Phase 4: Test (8,000 tokens):
├─ Running tests: 1,000 tokens
├─ Reading test files: 2,000 tokens
├─ Self-healing (if needed): 4,000 tokens
└─ Writing test-final-report.md: 1,000 tokens

Phase 5: Docs (3,000 tokens):
├─ Reading source code: 1,000 tokens
└─ Writing README.md: 2,000 tokens

Phase 6: Deploy (2,000 tokens):
├─ Git operations: 1,000 tokens
└─ GitHub CLI calls: 1,000 tokens

Phase 7: Feedback (5,000 tokens):
├─ Analyzing build: 2,000 tokens
├─ Pattern extraction: 2,000 tokens
└─ Updating pattern library: 1,000 tokens

───────────────────────────────────────────────────
TOTAL DELEGATED: ~78,000 tokens (39% of 200K)
───────────────────────────────────────────────────

IMPACT ON MAIN WINDOW: 0 tokens (separate process!)
```

---

## Why Agents Are Ephemeral

**Advantages of Ephemeral Agents:**

### 1. **Clean Slate Each Phase**

```
Traditional Persistent Agent:
Scout → Architect (in same conversation)
    ├─ Architect has ALL Scout's raw research
    ├─ Architect has ALL Scout's tangential thoughts
    ├─ Architect has ALL Scout's discarded ideas
    └─ Context window filling up with irrelevant history

Context Foundry:
Scout writes report → Scout dies → Architect reads report
    ├─ Architect gets ONLY the essential findings
    ├─ Architect's context is clean and focused
    └─ No cognitive load from Scout's internal deliberation
```

### 2. **Focused Attention**

```
Architect Agent sees:
✅ scout-report.md (curated knowledge)

Architect Agent does NOT see:
❌ Scout's web search queries
❌ Scout's pattern library exploration
❌ Scout's internal reasoning
❌ Scout's discarded alternatives

Result: Cleaner, more focused design decisions
```

### 3. **Predictable Behavior**

```
Persistent Agent State:
Build 1: Scout discovers issue X
Build 2: Scout might remember issue X (unpredictable!)
    └─ May bias future builds based on past experiences

Ephemeral Agent State:
Build 1: Scout discovers issue X → Pattern library
Build 2: Scout reads pattern library (predictable!)
    └─ Consistent behavior driven by patterns, not memory
```

### 4. **No State Pollution**

```
If Architect agent persisted:
Build 1: Designs React app
Build 2: Designs Python API
    └─ Might leak React assumptions into Python design

With ephemeral agents:
Build 1: Architect designs React → Dies
Build 2: Fresh Architect designs Python
    └─ No cross-contamination!
```

---

## Why Files Persist

**Files as the Single Source of Truth:**

### 1. **Durability**

```
Agent Context (RAM):
    ├─ Process dies → Context lost
    └─ Volatile, temporary

File System (Disk):
    ├─ Process dies → Files remain
    └─ Durable, permanent
```

### 2. **Reviewability**

```
You can review:
✅ .context-foundry/scout-report.md        (Scout's findings)
✅ .context-foundry/architecture.md        (Architect's plan)
✅ .context-foundry/build-log.md           (Builder's implementation log)

You CANNOT review:
❌ Scout agent's conversation history       (discarded)
❌ Architect agent's internal reasoning     (discarded)
```

### 3. **Debuggability**

```
Build fails at Phase 4 (Test):
✅ Can read architecture.md to see what was planned
✅ Can read build-log.md to see what was built
✅ Can compare plan vs implementation to find discrepancy

If using persistent agents:
❌ Can't easily review what Scout decided
❌ Can't easily review Architect's original plan
❌ Would need to scroll through long conversation
```

### 4. **Composability**

```
File-based workflow:
    ├─ Scout writes scout-report.md
    ├─ Architect reads scout-report.md + writes architecture.md
    ├─ Builder reads architecture.md + writes code
    ├─ Test reads code + writes test-final-report.md
    └─ Each phase is a pure function: Input Files → Output Files

Agent-based workflow (without files):
    ├─ Scout remembers findings
    ├─ Architect remembers Scout + own decisions
    ├─ Builder remembers Scout + Architect + implementation
    └─ Accumulating context, tight coupling, hard to modify
```

---

## Information Loss Analysis

**Question:** Does anything get lost when agents die?

**Analysis:**

### What IS Lost (By Design)

```
✅ Good to lose:
├─ Scout's web search queries ("weather api" → 10 results)
├─ Scout's exploration of dead-ends (considered WeatherStack API, rejected it)
├─ Architect's internal deliberation ("should I use Redux? No, too heavy for this.")
├─ Builder's intermediate attempts (tried import X, syntax error, used import Y instead)
└─ All conversation turns between agent and Claude Code

Why good to lose:
→ Reduces noise
→ Focuses on decisions, not process
→ Keeps subsequent phases efficient
→ Prevents context window bloat
```

### What Is NOT Lost (Preserved in Files)

```
✅ Preserved:
├─ Scout's recommendations (in scout-report.md)
├─ Scout's risk warnings (in scout-report.md)
├─ Architect's complete plan (in architecture.md)
├─ Architect's file specifications (in architecture.md)
├─ Builder's implementation log (in build-log.md)
├─ Test results and fixes (in test-final-report.md)
└─ Pattern library updates (in patterns/*.json)

Why preserved:
→ Essential knowledge
→ Needed by subsequent phases
→ Needed for debugging
→ Needed for pattern learning
```

### Test: Can You Reconstruct the Build?

```
Given ONLY the artifacts:
✅ scout-report.md → Understand why tech choices were made
✅ architecture.md → Understand system design
✅ build-log.md → Understand implementation details
✅ test-final-report.md → Understand quality validation
✅ session-summary.json → Understand build outcome

Could you understand the project without agent conversations?
→ YES! Files contain all essential knowledge.

Could you continue development without agent conversations?
→ YES! Future builds read artifacts + pattern library.
```

**Conclusion:** Zero essential information loss!

---

## Comparison with Persistent Agents

### Persistent Agent Architecture (Hypothetical)

```
┌──────────────────────────────────────────────────────────┐
│ Single Persistent Agent (200K token context)              │
├──────────────────────────────────────────────────────────┤
│                                                            │
│ Phase 1: Scout Research (10,000 tokens)                   │
│    Context: [System + Scout work] = 15,000 tokens         │
│                                                            │
│ Phase 2: Architect Design (15,000 tokens)                 │
│    Context: [System + Scout + Architect] = 30,000 tokens  │
│                                                            │
│ Phase 3: Builder Implement (30,000 tokens)                │
│    Context: [System + Scout + Arch + Builder] = 60K       │
│                                                            │
│ Phase 4: Test Validate (8,000 tokens)                     │
│    Context: [All above + Test] = 68,000 tokens            │
│                                                            │
│ Phase 5: Documentation (3,000 tokens)                     │
│    Context: [All above + Docs] = 71,000 tokens            │
│                                                            │
│ Phase 6: Deploy (2,000 tokens)                            │
│    Context: [All above + Deploy] = 73,000 tokens          │
│                                                            │
│ Phase 7: Feedback (5,000 tokens)                          │
│    Context: [All above + Feedback] = 78,000 tokens        │
│                                                            │
│ Problems:                                                  │
│ ❌ Single build uses 39% of context (can only do 2-3)     │
│ ❌ Each build adds to context (eventually hits limit)     │
│ ❌ Earlier phases get truncated as context fills          │
│ ❌ Agent accumulates bias from previous builds            │
│ ❌ Can't parallelize (one agent, one context)             │
└──────────────────────────────────────────────────────────┘
```

### Context Foundry Architecture (Actual)

```
┌──────────────────────────────────────────────────────────┐
│ Ephemeral Agents + Files (200K tokens per agent)          │
├──────────────────────────────────────────────────────────┤
│                                                            │
│ Phase 1: Scout Agent (fresh 200K context)                 │
│    Context: [System + Scout] = 15,000 tokens              │
│    Output: scout-report.md → Disk                         │
│    Agent: DIES (context freed)                            │
│                                                            │
│ Phase 2: Architect Agent (fresh 200K context)             │
│    Input: scout-report.md from disk                       │
│    Context: [System + scout-report.md + Arch] = 18,000    │
│    Output: architecture.md → Disk                         │
│    Agent: DIES (context freed)                            │
│                                                            │
│ Phase 3: Builder Agent (fresh 200K context)               │
│    Input: architecture.md from disk                       │
│    Context: [System + architecture.md + Build] = 38,000   │
│    Output: source code → Disk                             │
│    Agent: DIES (context freed)                            │
│                                                            │
│ ... Phases 4-7 follow same pattern ...                    │
│                                                            │
│ Benefits:                                                  │
│ ✅ Each agent gets fresh 200K context                     │
│ ✅ No context accumulation across builds                  │
│ ✅ No truncation of earlier phases                        │
│ ✅ Can run infinite builds without filling context        │
│ ✅ Can parallelize (spawn multiple delegated instances)   │
│ ✅ Each build is deterministic (no accumulated bias)      │
└──────────────────────────────────────────────────────────┘
```

---

## Visual Diagrams

### Context Flow Diagram

```
USER REQUEST
     │
     │ "Build weather app"
     │
     ↓
┌────────────────────────────────────────────────────┐
│ MAIN CLAUDE WINDOW (stays clean)                   │
│ Context Used: < 1%                                 │
└─────────────────┬──────────────────────────────────┘
                  │
                  │ Spawns subprocess
                  │
                  ↓
┌─────────────────────────────────────────────────────┐
│ DELEGATED INSTANCE (isolated context)               │
│                                                      │
│ ┌──────────────────────────────────────────────┐   │
│ │ PHASE 1: SCOUT AGENT                          │   │
│ │ Context: [System + Task] = 15K tokens        │   │
│ │                                               │   │
│ │ Actions:                                      │   │
│ │  - Web research                               │   │
│ │  - Pattern library check                      │   │
│ │  - Technology recommendations                 │   │
│ │                                               │   │
│ │ Output: scout-report.md ──┐                  │   │
│ └───────────────────────────┼──────────────────┘   │
│                              │                       │
│                              ↓ File persists         │
│                            DISK                      │
│ [Agent dies, context freed]  │                      │
│                              ↓ Next agent reads     │
│                                                      │
│ ┌──────────────────────────────────────────────┐   │
│ │ PHASE 2: ARCHITECT AGENT                      │   │
│ │ Context: [System + scout-report.md] = 18K    │   │
│ │                                               │   │
│ │ Actions:                                      │   │
│ │  - Read scout-report.md (5K tokens)          │   │
│ │  - Design architecture                        │   │
│ │  - Plan file structure                        │   │
│ │                                               │   │
│ │ Output: architecture.md ──┐                  │   │
│ └───────────────────────────┼──────────────────┘   │
│                              │                       │
│                              ↓ File persists         │
│                            DISK                      │
│ [Agent dies, context freed]  │                      │
│                              ↓ Next agent reads     │
│                                                      │
│ ┌──────────────────────────────────────────────┐   │
│ │ PHASE 3: BUILDER AGENT                        │   │
│ │ Context: [System + architecture.md] = 38K    │   │
│ │                                               │   │
│ │ Actions:                                      │   │
│ │  - Read architecture.md (8K tokens)          │   │
│ │  - Implement all source files                │   │
│ │  - Create tests                               │   │
│ │                                               │   │
│ │ Output: 12 source files ──┐                  │   │
│ │         build-log.md ──────┤                 │   │
│ └────────────────────────────┼─────────────────┘   │
│                              │                       │
│                              ↓ Files persist         │
│                            DISK                      │
│ [Agent dies, context freed]  │                      │
│                              ↓ Test phase runs       │
│                                                      │
│ ... Phases 4-7 continue ...                         │
│                                                      │
│ Final Output:                                       │
│  - Complete project on disk                         │
│  - GitHub repository                                │
│  - Pattern library updated                          │
│  - session-summary.json                             │
└─────────────────────────────────────────────────────┘
                       │
                       │ Returns summary
                       ↓
┌─────────────────────────────────────────────────────┐
│ MAIN CLAUDE WINDOW                                   │
│ Shows: "Build complete! GitHub: github.com/..."     │
│ Context Used: Still < 1%                            │
└─────────────────────────────────────────────────────┘
```

---

## FAQ

### Q: If Scout's context is discarded, how does Architect know what Scout researched?

**A:** Architect reads `scout-report.md` which contains Scout's findings.

**Analogy:** Scout writes a research paper, then quits the job. Architect reads the research paper and has all the knowledge needed.

---

### Q: Doesn't Architect miss nuance by only reading the report, not seeing Scout's reasoning?

**A:** The report IS the refined reasoning. Scout's job is to distill research into actionable recommendations. Raw exploration (dead ends, tangents) is noise, not signal.

**Analogy:** You read a scientific paper's conclusion and methodology. You don't need to see the researcher's 1000 failed experiments.

---

### Q: What if Scout made a mistake that's not obvious from the report?

**A:** Two-layer validation:

1. **Architect reviews Scout's recommendations**
   - Can disagree with Scout
   - Can add missing considerations
   - Can flag risks Scout missed

2. **Test phase validates Builder's implementation**
   - Self-healing catches bugs
   - Can trace back to Architect → Scout if needed

**Pattern library prevents repeated mistakes** - if Scout misses something and it causes issues, Feedback phase adds it to patterns for future builds.

---

### Q: Is there a performance cost to reading files vs. having conversation context?

**A:** No meaningful cost:

```
Reading scout-report.md (40KB):
- Time: < 100ms
- Tokens: ~5,000 (well within budget)

Persistent conversation (hypothetical):
- Time: 0ms (already in context)
- Tokens: ~10,000 (raw research + report)

Trade-off:
✅ File reading: Cleaner context, better for parallel builds
❌ Persistent conversation: Marginally faster (by 100ms), but context bloats
```

**Verdict:** 100ms is negligible compared to 7-15 minute build time. Clean context is worth it.

---

### Q: Could agents share context via message passing instead of files?

**A:** Technically yes, but defeats the purpose:

```
Message Passing:
Scout Agent → [sends JSON] → Architect Agent
    ├─ Both must be alive simultaneously (no parallelization)
    ├─ Tight coupling (can't inspect messages easily)
    └─ Not persistent (message lost if crash)

File-Based:
Scout Agent → [writes file] → Dies → Architect Agent → [reads file]
    ├─ Agents can run sequentially or in parallel
    ├─ Loose coupling (can inspect/edit files)
    └─ Persistent (survives crashes, user can review)
```

**File-based is superior for this use case.**

---

### Q: What's the largest file an agent writes?

**A:** Measured in production builds:

| File | Typical Size | Max Tokens |
|------|--------------|------------|
| scout-report.md | 30-60KB | ~8,000 |
| architecture.md | 40-90KB | ~12,000 |
| build-log.md | 10-30KB | ~4,000 |
| test-final-report.md | 5-15KB | ~2,000 |

**All well within** Claude's 200K token context window.

---

### Q: Can I review the artifacts while build is running?

**A:** YES! Files are written in real-time:

```bash
# Start build
# Build a weather app in /tmp/weather-app

# In another terminal, tail the scout report as it's being written:
tail -f /tmp/weather-app/.context-foundry/scout-report.md

# Or check which phase is currently running:
ls -lt /tmp/weather-app/.context-foundry/
```

**Real-time transparency** into the build process.

---

## Summary

**How Context Foundry Preserves Context:**

✅ **Agents are ephemeral** (context discarded after each phase)
✅ **Files are persistent** (knowledge written to disk)
✅ **Agents read previous artifacts** (file-based information transfer)
✅ **No information loss** (all essential knowledge preserved)
✅ **Clean context each phase** (no accumulated noise)
✅ **Reviewable artifacts** (you can inspect files anytime)
✅ **Debuggable builds** (trace decisions through artifacts)

**The Result:**
Perfect information continuity with zero context bloat. Agents disappear, knowledge persists.

---

**For More Information:**
- [MCP_SERVER_ARCHITECTURE.md](MCP_SERVER_ARCHITECTURE.md) - Technical implementation
- [DELEGATION_MODEL.md](DELEGATION_MODEL.md) - Why delegation keeps main context clean
- [FAQ.md](../FAQ.md) - Frequently asked questions
- [README.md](../README.md) - Quick start guide

---

**Version:** 2.0.1 | **Last Updated:** October 2025

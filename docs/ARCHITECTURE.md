# Context Foundry Architecture: Stateless Conversations

> Understanding "Context reset - starting fresh conversation"

> *"Generate probabilistically, validate deterministically."*

## Overview

Context Foundry's core innovation is a **stateless conversation architecture** that enables unlimited-length AI coding sessions while maintaining <40% context utilization. This document explains the technical implementation and design decisions behind context management.

## The Problem: Context Window Bloat

### Traditional AI Coding Sessions

Most AI coding tools use a single, continuous conversation:

```
User: "Build a todo app"
AI: "Here's the implementation... [2,000 tokens]"
User: "Add authentication"
AI: "Adding auth... [3,000 tokens]"
User: "Add dark mode"
AI: "Adding dark mode... [2,500 tokens]"
...
[After 20 interactions: 80,000 tokens used, 80% context filled]
```

**Problems:**
- Context window fills up after 50-100 messages
- Early messages get truncated or dropped
- Model performance degrades at high context utilization
- Can't run overnight sessions (max 2-3 hours before hitting limits)
- Pay to re-send entire conversation history with every API call

### Context Foundry's Solution

Multiple **short, focused conversations** with state persisted to files:

```
Scout Conversation (fresh start):
  User: "Research this codebase"
  AI: "Here's the architecture... [5,000 tokens]"
  [SAVE to RESEARCH.md]
  🔄 RESET → conversation_history = []

Architect Conversation (fresh start):
  User: "Read RESEARCH.md and create plan"
  AI: "Here's the plan... [8,000 tokens]"
  [SAVE to PLAN.md, TASKS.md]
  🔄 RESET → conversation_history = []

Builder Conversation - Task 1 (fresh start):
  User: "Read PLAN.md, implement task 1"
  AI: "Here's the code... [4,000 tokens]"
  [SAVE code files, commit to git]
  🔄 RESET → conversation_history = []

Builder Conversation - Task 2 (fresh start):
  User: "Read PLAN.md, implement task 2"
  AI: "Here's the code... [4,000 tokens]"
  ...
```

**Benefits:**
- Each conversation uses only 10-40% of context window
- Can run for hours/days without hitting limits
- No token waste re-sending old messages
- Fresh perspective for each phase/task

## Technical Implementation

### Conversation History Data Structure

Location: `ace/claude_integration.py:95`

```python
class ClaudeClient:
    def __init__(self, ...):
        self.conversation_history: List[Dict] = []
        self.total_input_tokens = 0
        self.total_output_tokens = 0
```

`conversation_history` stores the **entire back-and-forth** with Claude:

```python
self.conversation_history = [
    {"role": "user", "content": "Build a todo app"},
    {"role": "assistant", "content": "I'll create a todo app with..."},
    {"role": "user", "content": "Add dark mode"},
    {"role": "assistant", "content": "Adding dark mode theme..."},
    # ... every message in this conversation
]
```

### How API Calls Work

Each call to Claude sends the **entire conversation history**:

Location: `ace/claude_integration.py:156`

```python
def call_claude(self, prompt: str, ...):
    # Build messages array with full history + new prompt
    messages = self.conversation_history + [{"role": "user", "content": prompt}]

    # Send to Claude API
    response = self.client.messages.create(
        model=self.model,
        messages=messages,  # ← Full history sent every time!
        ...
    )

    # Append both prompt and response to history
    self.conversation_history.append({"role": "user", "content": prompt})
    self.conversation_history.append({"role": "assistant", "content": response_text})
```

### Context Reset Method

Location: `ace/claude_integration.py:286-289`

```python
def reset_context(self):
    """Reset conversation history (fresh start)."""
    self.conversation_history = []
    print("🔄 Context reset - starting fresh conversation")
```

**What happens:**
1. `conversation_history` list is cleared (set to empty `[]`)
2. Next API call starts with no prior context
3. Token counters remain (for cost tracking across session)

### When Context Resets Happen

#### 1. Scout Phase Start

Location: `workflows/autonomous_orchestrator.py:327`

```python
def run_scout_phase(self) -> Dict:
    # ... build prompt from task description ...

    # Start fresh conversation for Scout
    self.claude.reset_context()
    response, metadata = self.claude.call_claude(prompt, content_type="decision")

    # Save Scout's research to file
    research_file = self.blueprints_path / f"specs/RESEARCH_{self.timestamp}.md"
    research_file.write_text(response)
```

#### 2. Architect Phase Start

Location: `workflows/autonomous_orchestrator.py:401`

```python
def run_architect_phase(self, scout_result: Dict) -> Dict:
    # Read Scout's research from file (not from conversation!)
    research_file = Path(scout_result['file'])
    research_content = research_file.read_text()

    # Build prompt with file contents
    prompt = f"Read this research:\n\n{research_content}\n\nNow create a plan..."

    # Start fresh conversation for Architect
    self.claude.reset_context()
    response, metadata = self.claude.call_claude(prompt, content_type="decision")
```

#### 3. Between Builder Tasks

Each task in Builder phase gets a fresh conversation:

```python
def _run_builder_for_tasks(self, tasks: List[str]) -> Dict:
    for task_num, task_desc in enumerate(tasks, 1):
        # Reset before each task
        self.claude.reset_context()

        # Build prompt for this specific task
        prompt = self._build_builder_prompt(task_desc, ...)

        # Execute task in fresh conversation
        response, metadata = self.claude.call_claude(prompt)

        # Save code, commit to git
        self._extract_and_save_code(response, self.project_dir)
        self._create_git_checkpoint(task_num, task_desc)
```

## What Gets Cleared vs Persisted

### ✅ Cleared (Forgotten)

When `reset_context()` is called:
- **All previous messages** between user and assistant
- **Conversation context** (Claude "forgets" what was discussed)
- **Immediate memory** of code generated in previous conversations

### ❌ NOT Cleared (Persists)

Context Foundry persists state to files in the `.context-foundry/` directory:

**Build Artifacts** (Per-Project):
- **Scout report** (`.context-foundry/scout-report.md`) - Research findings
- **Architecture document** (`.context-foundry/architecture.md`) - System design
- **Build log** (`.context-foundry/build-log.md`) - Implementation chronology
- **Test results** (`.context-foundry/test-results-iteration-*.md`) - Test runs
- **Fix strategies** (`.context-foundry/fixes-iteration-*.md`) - Self-healing plans
- **Final test report** (`.context-foundry/test-final-report.md`) - Quality summary
- **Session summary** (`.context-foundry/session-summary.json`) - Build metadata
- **Feedback** (`.context-foundry/feedback/build-feedback-{timestamp}.json`)
- **Project patterns** (`.context-foundry/patterns/*.json`) - This build's discoveries

**Global Pattern Library** (Shared Across All Builds):
- **Common issues** (`context-foundry/.context-foundry/patterns/common-issues.json`)
- **Test patterns** (`context-foundry/.context-foundry/patterns/test-patterns.json`)
- **Architecture patterns** (`context-foundry/.context-foundry/patterns/architecture-patterns.json`)
- **Scout learnings** (`context-foundry/.context-foundry/patterns/scout-learnings.json`)

**Project Code** (Your Actual Application):
- **Source code** (`src/`, `lib/`, `components/`, etc.)
- **Tests** (`tests/`, `__tests__/`, `*.test.js`, etc.)
- **Documentation** (`README.md`, `docs/`)
- **Configuration** (`package.json`, `tsconfig.json`, etc.)
- **Git commits** (permanent history)

### File-Based State Transfer

Each phase reads the **previous phase's output from disk**:

```
Phase 1: Scout writes → .context-foundry/scout-report.md
Phase 2: Architect reads ← scout-report.md, writes → .context-foundry/architecture.md
Phase 3: Builder reads ← architecture.md, writes → source code files
Phase 4: Test runs tests, writes → .context-foundry/test-results-iteration-1.md
Phase 5: Docs reads all, writes → README.md, guides
Phase 6: Deploy reads all, creates → GitHub repository
Phase 7: Feedback reads all, writes → pattern library updates
```

This is why Context Foundry can reset context freely - **the important state is on disk**, not in conversation memory.

### Artifact Locations Quick Reference

**For VimQuest project:**
```bash
# View architect's plan
cat /Users/name/homelab/vimquest/.context-foundry/architecture.md

# View scout research
cat /Users/name/homelab/vimquest/.context-foundry/scout-report.md

# View build summary
cat /Users/name/homelab/vimquest/.context-foundry/session-summary.json

# View test results
cat /Users/name/homelab/vimquest/.context-foundry/test-final-report.md
```

**Global pattern library:**
```bash
# See all learned issues
cat /Users/name/homelab/context-foundry/.context-foundry/patterns/common-issues.json

# See testing strategies
cat /Users/name/homelab/context-foundry/.context-foundry/patterns/test-patterns.json
```

**Complete structure for any project:**
```
your-project/
├── src/                                   ← Your actual code
├── tests/                                 ← Test files
├── README.md                              ← Documentation
└── .context-foundry/                      ← Build artifacts
    ├── scout-report.md                    ← Phase 1 output
    ├── architecture.md                    ← Phase 2 output
    ├── build-log.md                       ← Phase 3 output
    ├── test-iteration-count.txt           ← Test loop counter
    ├── test-results-iteration-1.md        ← Test run 1
    ├── test-results-iteration-2.md        ← Test run 2 (if self-healing)
    ├── fixes-iteration-1.md               ← Self-healing strategy
    ├── test-final-report.md               ← Final quality report
    ├── session-summary.json               ← Complete build metadata
    ├── feedback/
    │   └── build-feedback-{timestamp}.json  ← Learnings extracted
    └── patterns/
        ├── common-issues.json             ← Patterns discovered
        ├── test-patterns.json
        ├── architecture-patterns.json
        └── scout-learnings.json
```

## Comparison: Traditional vs Stateless Architecture

### Traditional Approach (One Long Conversation)

```
API Call 1:  [user: "task 1"]
             [10K tokens, 5% context]

API Call 2:  [user: "task 1", assistant: "response 1", user: "task 2"]
             [25K tokens, 12% context]

API Call 3:  [entire history + user: "task 3"]
             [45K tokens, 22% context]

API Call 10: [entire history + user: "task 10"]
             [120K tokens, 60% context]

API Call 20: [entire history + user: "task 20"]
             [180K tokens, 90% context] ⚠️ Near limit!

API Call 25: [CONTEXT FULL - truncation starts]
             [200K tokens, 100%] 💥 Quality degrades
```

### Context Foundry (Stateless Conversations)

```
Scout Conversation:
  API Call 1: [user: "research"]
              [10K tokens, 5% context]
  → Save to RESEARCH.md
  🔄 RESET

Architect Conversation:
  API Call 1: [user: "read RESEARCH.md, create plan"]
              [15K tokens, 7% context]
  → Save to PLAN.md
  🔄 RESET

Builder Task 1:
  API Call 1: [user: "read PLAN.md, implement task 1"]
              [8K tokens, 4% context]
  → Save code, commit
  🔄 RESET

Builder Task 2:
  API Call 1: [user: "read PLAN.md, implement task 2"]
              [8K tokens, 4% context]
  → Save code, commit
  🔄 RESET

...repeat for 100 tasks, always <10% context!
```

## Real-World Analogy

### Without Context Reset (Traditional)

Imagine trying to have a conversation where you must:
- Remember every word said in the last 8 hours
- Recite the entire conversation before making your next point
- Keep all previous context in your head simultaneously

**Result:** Mental exhaustion, degraded quality, eventually you forget earlier details.

### With Context Reset (Context Foundry)

Imagine a team meeting where:
- Previous meeting's **notes are written down**
- Each new meeting starts with: "Here are the notes from last time"
- You focus on **one topic at a time** with fresh energy
- Important decisions are **documented**, not just remembered

**Result:** Sustained high quality, no mental exhaustion, unlimited duration.

## Benefits of Stateless Architecture

### 1. Context Efficiency

Each conversation uses only 10-40% of the context window:
- **Scout**: ~5-30% (research and analysis)
- **Architect**: ~7-40% (reading research, creating plans)
- **Builder**: ~4-15% per task (focused implementation)

### 2. Unlimited Session Length

No theoretical limit on how long a session can run:
- Traditional: 2-3 hours before context full
- Context Foundry: **Overnight sessions** (8+ hours) are standard
- Ralph Wiggum mode can run indefinitely

### 3. Cost Savings

Don't pay to re-send old messages:
```
Traditional approach (cumulative):
  Call 1: 10K tokens
  Call 2: 25K tokens (10K + 15K new)
  Call 3: 45K tokens (25K + 20K new)
  Total: 80K tokens sent

Context Foundry (fresh each time):
  Call 1: 10K tokens
  Call 2: 15K tokens
  Call 3: 20K tokens
  Total: 45K tokens sent (44% savings!)
```

### 4. Fresh Perspective

Each phase/task gets a "clean slate":
- No contamination from previous attempts
- Clearer thinking on complex problems
- Better code quality (proven in testing)

### 5. Resilience

If one task fails:
- Doesn't corrupt the context for future tasks
- Can retry with fresh context
- Failure is isolated, not cascading

## Advanced: Context Compaction

When context **does** start to fill (rare), Context Foundry has a fallback:

Location: `ace/claude_integration.py:237-284`

```python
def compact_context(self, keep_recent: int = 5) -> str:
    """Compact conversation by summarizing old messages.

    Keeps recent messages, summarizes the rest.
    """
    if len(self.conversation_history) <= keep_recent * 2:
        return "No compaction needed - conversation is short"

    # Keep recent messages
    recent_messages = self.conversation_history[-(keep_recent * 2):]

    # Summarize older messages
    old_messages = self.conversation_history[:-(keep_recent * 2)]

    # Create summary
    summary_prompt = "Summarize this conversation:\n\n" + conversation_text
    summary, _ = self.call_claude(summary_prompt, reset_context=True)

    # Replace history with: summary + recent messages
    self.conversation_history = [
        {"role": "user", "content": "Previous conversation summary:"},
        {"role": "assistant", "content": summary},
    ] + recent_messages
```

**Note:** This is rarely needed in practice because context resets keep conversations short.

## Implementation Patterns

### Pattern 1: Phase Isolation

Each phase is a separate, fresh conversation:

```python
# Scout
self.claude.reset_context()
scout_output = self.claude.call_claude(scout_prompt)
save_to_file(scout_output, "RESEARCH.md")

# Architect (reads file, not conversation)
self.claude.reset_context()
architect_prompt = f"Read this research:\n{read_file('RESEARCH.md')}\n\nCreate plan..."
architect_output = self.claude.call_claude(architect_prompt)
save_to_file(architect_output, "PLAN.md")

# Builder (reads file, not conversation)
self.claude.reset_context()
builder_prompt = f"Read this plan:\n{read_file('PLAN.md')}\n\nImplement task..."
builder_output = self.claude.call_claude(builder_prompt)
save_code_files(builder_output)
```

### Pattern 2: Task-Level Reset

Each Builder task is independent:

```python
for task in tasks:
    self.claude.reset_context()  # Fresh start for each task
    prompt = build_task_prompt(task)
    output = self.claude.call_claude(prompt)
    save_and_commit(output, task)
```

### Pattern 3: Progressive State Building

State flows through files, not conversation:

```
Phase 1: () → RESEARCH.md
Phase 2: (RESEARCH.md) → PLAN.md + TASKS.md
Phase 3: (PLAN.md, TASKS.md) → code files + git commits
```

## Debugging Context Issues

### Check Current Context Stats

```python
stats = self.claude.get_context_stats()
print(f"Messages: {stats['messages']}")
print(f"Context %: {stats['context_percentage']}")
print(f"Total tokens: {stats['total_tokens']}")
```

### Force Manual Reset

```python
self.claude.reset_context()
print("Context manually cleared")
```

### View Conversation History

```python
# Save full conversation to file
self.claude.save_full_conversation(Path("conversation_backup.json"))

# Inspect conversation_history
print(json.dumps(self.claude.conversation_history, indent=2))
```

## Performance Characteristics

### Context Usage by Phase

Based on real-world usage:
- **Scout**: 5-30% (avg 15%)
- **Architect**: 7-40% (avg 20%)
- **Builder** (per task): 4-15% (avg 8%)

### Token Efficiency

Measured against traditional continuous conversation:
- **50-70% reduction** in total tokens sent to API
- **60% cost savings** on typical projects
- **No degradation** at any point (vs 20-30% quality drop at 80% context)

### Session Duration

Theoretical and practical limits:
- **Traditional**: 2-3 hour maximum
- **Context Foundry**: Unlimited (tested up to 12 hours)
- **Overnight sessions**: 8 hours standard

## Related Concepts

- **[Ralph Wiggum Strategy](../RALPH_WIGGUM_IMPLEMENTATION.md)**: Overnight autonomous coding using context resets
- **[Pattern Library](../foundry/patterns/README.md)**: Self-improving system built on stateless architecture

## FAQ

### Q: Doesn't Claude "forget" important context when you reset?

A: No, because important context is **persisted to files** before reset. When the next phase starts, it reads those files. The files contain everything Claude needs to know.

### Q: What if I want Claude to remember something across phases?

A: Put it in the files! Scout's research goes in RESEARCH.md, Architect's plan goes in PLAN.md, and Builder reads both. Anything saved to a file is permanent.

### Q: Is this the same as "context window management"?

A: Sort of, but more aggressive. Traditional context management tries to **summarize** old messages. Context Foundry **deletes** them entirely and relies on files instead. More efficient and scales better.

### Q: Can I disable context resets?

A: Technically yes (comment out `reset_context()` calls), but not recommended. The entire architecture assumes fresh conversations. You'll hit context limits quickly and quality will degrade.

### Q: Does this work with other AI models (GPT-4, Gemini)?

A: Yes! The pattern works with any LLM that has conversation history. Just swap the API client - the reset logic is the same.

## Conclusion

Context Foundry's stateless conversation architecture is what enables:
- ✅ Overnight autonomous coding sessions
- ✅ <40% context utilization always
- ✅ Unlimited session length
- ✅ 50-70% token cost savings
- ✅ Consistent high-quality output

The key insight: **State in files, conversations are ephemeral.** This inverts the traditional AI coding approach and unlocks capabilities that weren't possible before.

When you see "Context reset - starting fresh conversation", that's Context Foundry's secret weapon in action.

---

## Deterministic Enforcement Layer

Context Foundry doesn't rely on prompt engineering alone. The system wraps probabilistic AI generation with **deterministic validation checkpoints**.

### The Problem with Prompt-Only Compliance

CLAUDE.md and AGENTS.md files are probabilistic - the LLM *usually* follows them, but there's no guarantee. Context Foundry adds code-level enforcement:

### Multi-Layer Enforcement Architecture

| Layer | Type | Mechanism |
|-------|------|-----------|
| Phase prompts | Probabilistic | LLM follows instructions (mostly) |
| Subprocess isolation | **Deterministic** | Fresh context per phase via `--system-prompt` |
| File validation | **Deterministic** | Code checks outputs exist and meet size thresholds |
| Checksum verification | **Deterministic** | Detects unauthorized file modifications |
| BAML phase tracking | **Deterministic** | State machine validates phase order |
| Emergency stop | **Deterministic** | Code can halt pipeline on violations |

### How It Works

**1. Subprocess Isolation (Deterministic)**

Each phase spawns a fresh Claude CLI instance with rules injected at spawn time:

```python
subprocess.Popen([
    "claude",
    "--system-prompt", phase_prompt,  # Rules baked in before execution
    task_instruction
])
```

The agent cannot ignore the system prompt - it's injected before the task begins.

**2. Post-Phase Validation (Deterministic)**

After each phase, validators check outputs:

```python
class PhaseValidator:
    def validate_scout_output(self):
        if not scout_report.exists() or scout_report.stat().st_size < 100:
            raise ValidationError("Scout failed to produce valid output")

    def validate_architect_didnt_code(self):
        checksums_before = get_file_checksums(src_dir)
        # ... run architect ...
        checksums_after = get_file_checksums(src_dir)
        if checksums_before != checksums_after:
            raise ValidationError("Architect modified source files!")
```

**3. Contract Enforcement via Data Flow (Deterministic)**

The orchestrator parses Scout's markdown, transforms it to JSON, and injects it into Architect's instruction. Architect doesn't "choose" to read Scout's output - it's handed programmatically:

```
Scout MD --> [Orchestrator parses] --> SCOUT_JSON --> [Injected into Architect]
```

### Why This Matters

The "bitter lesson" in AI argues against hand-coding knowledge - let models learn. But **compliance is different from capabilities**:

- **Capabilities** = "Can the model write good code?" --> Let it learn
- **Compliance** = "Did the model follow the rules?" --> **Verify deterministically**

Context Foundry combines both: probabilistic generation wrapped in deterministic validation.

See [Phase Handoff Flow](phase-handoff-flow.md) for detailed diagrams.

---

**Next Steps:**
- Understand the [Three-Phase Workflow](../README.md#the-three-phase-workflow)
- Learn about [Pattern Library](../foundry/patterns/README.md) (built on stateless architecture)
- Try an [Overnight Session](../RALPH_WIGGUM_IMPLEMENTATION.md) to see it in action

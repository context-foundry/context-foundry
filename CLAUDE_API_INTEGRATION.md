# Claude API Integration - Complete Implementation

## What Was Built

Context Foundry now has **full Claude API integration** with three operational modes:

### 1. Interactive Mode (Manual Copy/Paste)
- Original workflow: generate prompts → paste to Claude → save responses
- No API key required
- Full manual control at each step
- **Use:** `python3 prompt_generator.py todo-app "description"`

### 2. API Mode (Semi-Automated)
- Uses Claude API directly
- Human checkpoints at Scout, Architect, and Builder phases
- Real code generation (not placeholders)
- **Use:** `python3 prompt_generator.py todo-app "description" --api`

### 3. Autonomous Mode (Fully Automated)
- Runs overnight without human intervention
- Auto-approves all checkpoints
- Complete end-to-end automation
- **Use:** `python3 prompt_generator.py todo-app "description" --autonomous`

## New Components

### 1. `ace/claude_integration.py`
**Full-featured Claude API client:**
- Connects to Anthropic API using `ANTHROPIC_API_KEY`
- `call_claude()` method with exponential backoff retries
- Automatic token usage tracking
- Context percentage calculation (relative to 200K window)
- Auto-compaction when context >50%
- Complete conversation logging to `logs/{timestamp}/`
- JSONL session logs for debugging

**Features:**
- Rate limit handling
- API error retry logic
- Context reset between phases
- Conversation history management
- Full conversation export

### 2. `workflows/autonomous_orchestrator.py`
**Real implementation engine:**

**Scout Phase:**
- Calls Claude with architecture research prompt
- Generates real RESEARCH.md (not placeholder)
- Tracks context usage
- Saves to `blueprints/specs/`

**Architect Phase:**
- Reads RESEARCH.md
- Calls Claude for planning
- Generates SPEC.md, PLAN.md, TASKS.md
- Parses response to extract three files
- Human checkpoint (unless autonomous)

**Builder Phase:**
- Parses TASKS.md to extract individual tasks
- For each task:
  - Calls Claude with TDD prompt (tests first)
  - Extracts code from response
  - Saves files to project directory
  - Creates git commit
  - Updates progress tracking
  - Compacts context if >50%

**Progress Tracking:**
- Real-time `PROGRESS_{timestamp}.md` updates
- Shows completed/remaining tasks
- Tracks context usage per task
- Token usage statistics

**Git Integration:**
- Auto-commits after each task
- Commit messages include context usage
- Optional (skips if git not available)

### 3. Updated `prompt_generator.py`
**Three-mode launcher:**
- Argument parsing for mode selection
- Routes to interactive or autonomous flow
- Help menu with examples
- Validates API key for API/autonomous modes

## File Structure

```
context-foundry/
├── ace/
│   └── claude_integration.py      # Claude API client (NEW)
├── workflows/
│   ├── orchestrate.py              # Demo/simulation (existing)
│   └── autonomous_orchestrator.py  # Real implementation (NEW)
├── prompt_generator.py             # Updated with mode flags
├── requirements.txt                # Python dependencies (NEW)
├── .env.example                    # Environment template (NEW)
├── SETUP.md                        # Setup guide (NEW)
└── CLAUDE_API_INTEGRATION.md       # This file (NEW)
```

## Usage Examples

### Install Dependencies
```bash
cd ~/context-foundry
pip3 install -r requirements.txt
```

### Configure API Key
```bash
cp .env.example .env
# Edit .env and add: ANTHROPIC_API_KEY=your_key_here
```

### Interactive Mode (No API Key)
```bash
python3 prompt_generator.py todo-app "Build CLI todo app"
# Generates prompts to copy/paste
```

### API Mode (With Checkpoints)
```bash
python3 prompt_generator.py todo-app "Build CLI todo app" --api
# Uses API, asks approval at each phase
```

### Autonomous Mode (Overnight)
```bash
python3 prompt_generator.py api-server "REST API with JWT auth" --autonomous
# Runs completely automated
# Check results in the morning!
```

### Direct Orchestrator Call
```bash
python3 workflows/autonomous_orchestrator.py my-app "Build user auth system"
# Direct API mode with checkpoints

python3 workflows/autonomous_orchestrator.py my-app "Build user auth system" --autonomous
# Direct autonomous mode
```

## Testing

### Test Claude API Client
```bash
python3 ace/claude_integration.py
# Runs built-in test suite
# Checks API connection, context tracking, logging
```

### Test Interactive Mode
```bash
python3 prompt_generator.py test-app "Simple calculator"
# No API key needed
# Generates prompts to verify workflow
```

### Test API Mode (Requires API Key)
```bash
export ANTHROPIC_API_KEY=your_key
python3 workflows/autonomous_orchestrator.py test-todo "CLI todo app"
# Runs real Scout → Architect → Builder
# Check generated files in examples/test-todo/
```

## Output Artifacts

After running autonomous mode, you'll find:

### Generated Code
```
examples/{project-name}/
├── {project files}   # Real working code
└── tests/            # Test files
```

### Planning Artifacts
```
blueprints/
├── specs/
│   ├── RESEARCH_{timestamp}.md   # Architecture research
│   └── SPEC_{timestamp}.md       # Specifications
├── plans/
│   └── PLAN_{timestamp}.md       # Implementation plan
└── tasks/
    └── TASKS_{timestamp}.md      # Task breakdown
```

### Session Logs
```
logs/{timestamp}/
├── session.jsonl              # All API interactions
├── full_conversation.json     # Complete conversation history
├── task_1_output.md          # Builder task outputs
├── task_2_output.md
└── ...
```

### Progress Tracking
```
checkpoints/sessions/
├── PROGRESS_{timestamp}.md    # Real-time progress
└── {session_id}.json         # Final session summary
```

## Context Management

**Automatic Features:**
- Tracks token usage for every API call
- Calculates context percentage (0-100%)
- Warns when approaching 50%
- Auto-compacts at >50% usage
- Resets context between phases
- Logs all context statistics

**Manual Control:**
- `claude.reset_context()` - Fresh start
- `claude.compact_context()` - Summarize history
- `claude.get_context_stats()` - Current stats

## Cost Estimation

Using Claude Sonnet 4:
- Input: ~$3 per 1M tokens
- Output: ~$15 per 1M tokens

**Typical Project:**
- Scout: ~5K tokens input, ~2K output
- Architect: ~10K input, ~5K output
- Builder (6 tasks): ~30K input, ~20K output
- **Total: ~$0.40 per project**

**Overnight Run:**
- Large feature: ~100K input, ~50K output
- **Cost: ~$1.00**

## Workflow Comparison

| Mode | API Key | Speed | Control | Use Case |
|------|---------|-------|---------|----------|
| Interactive | No | Slow | Full | Learning |
| API | Yes | Fast | Checkpoints | Daily dev |
| Autonomous | Yes | Fastest | Auto | Overnight |

## Next Steps

1. **Install**: `pip3 install -r requirements.txt`
2. **Configure**: Set `ANTHROPIC_API_KEY` in `.env`
3. **Test**: Run `python3 ace/claude_integration.py`
4. **Build**: `python3 prompt_generator.py my-app "description" --api`

## Architecture Notes

**Three-Phase Isolation:**
- Each phase gets fresh context (no bloat)
- Scout → Architect → Builder pipeline
- Clean handoffs via artifact files

**Error Handling:**
- Exponential backoff for rate limits
- Retry logic for transient errors
- Graceful degradation (skip git if unavailable)
- Detailed error logging

**Testing Strategy:**
- Unit tests for ClaudeClient
- Integration tests for orchestrator
- End-to-end validation with real projects

## Limitations & Future Work

**Current Limitations:**
- Simple file extraction (regex-based)
- Basic task parsing (header detection)
- No parallel task execution
- Limited error recovery

**Planned Enhancements:**
- More robust code extraction
- Parallel Builder tasks
- Resume from checkpoint
- Cost tracking dashboard
- Test execution validation
- PR creation automation

---

Built with ❤️ for the anti-vibe coding movement. Workflow over vibes. Specs before code. Context is everything.

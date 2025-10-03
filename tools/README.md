# Overnight Tools - Ralph Wiggum Runner

> **"I'm helping! I'm helping!"** - Ralph Wiggum, continuously

## Overview

The overnight tools implement **Jeff Huntley's "Ralph Wiggum" strategy**: Run the same prompt in a loop with fresh context each iteration, while progress persists via checkpoint files.

This allows truly autonomous overnight coding sessions that can run for hours while maintaining context quality.

## Core Components

### 1. `overnight_session.sh`
Bash wrapper that manages the overnight session.

**Features:**
- Time-based loop control (default 8 hours)
- Fresh context each iteration
- Progress persistence
- Graceful shutdown on SIGINT/SIGTERM
- Comprehensive logging
- Early exit on completion

**Usage:**
```bash
./tools/overnight_session.sh <project> <description> [hours]

# Examples:
./tools/overnight_session.sh todo-app "Build CLI todo app" 4
./tools/overnight_session.sh api "REST API with auth" 8
```

### 2. `ace/ralph_wiggum.py`
Python implementation of the continuous loop strategy.

**Key Methods:**
- `run_iteration()` - Execute one iteration
- `reset_context()` - Fresh Claude context
- `load_progress()` - Read what's been done
- `save_progress()` - Persist state
- `check_completion()` - Validate completion
- `run_until_complete()` - Full autonomous run

**Usage:**
```bash
# Single iteration (called by overnight_session.sh)
python3 ace/ralph_wiggum.py \
  --project my-app \
  --task "Build feature" \
  --session session_id \
  --iteration 5

# Continuous mode (standalone)
python3 ace/ralph_wiggum.py \
  --project my-app \
  --task "Build feature" \
  --session session_id \
  --continuous
```

### 3. `schedule_overnight.py`
Task scheduler for managing queued overnight sessions.

**Features:**
- Queue management
- Retry logic (3 attempts)
- Email notifications
- Slack webhooks
- Desktop notifications

**Usage:**
```bash
# Add task to queue
python3 tools/schedule_overnight.py add \
  my-app "Build user auth" \
  --hours 6 \
  --priority 10

# List queued tasks
python3 tools/schedule_overnight.py list

# Process all queued tasks
python3 tools/schedule_overnight.py process
```

## How It Works

### The Ralph Wiggum Strategy

```
Iteration 1:
  - Fresh Claude context
  - Read: What has been done? (nothing)
  - Ask: Build authentication system
  - Claude: Creates research + plan
  - Save: Progress checkpoint

Iteration 2:
  - Fresh Claude context (no bloat!)
  - Read: Research + plan exists
  - Ask: Continue from where we left off
  - Claude: Implements Task 1
  - Save: Updated progress

Iteration 3:
  - Fresh Claude context
  - Read: Task 1 complete
  - Ask: Continue with Task 2
  - Claude: Implements Task 2
  - Save: Updated progress

... continues until all tasks done or time limit reached
```

### Why It Works

1. **Fresh Context** - Each iteration starts with 0% context usage
2. **Persistent Progress** - Checkpoint files remember what's been done
3. **Continuous Forward Progress** - Always building on previous work
4. **No Context Bloat** - Never exceeds 40% context in any iteration
5. **Resilient** - Errors don't break the whole session

## Setup

### 1. Prerequisites
```bash
# Install dependencies
pip3 install -r requirements.txt

# Set API key
export ANTHROPIC_API_KEY=your_key
```

### 2. Configure Notifications (Optional)

**Email:**
```bash
export SMTP_HOST=smtp.gmail.com
export SMTP_PORT=587
export SMTP_USER=your@email.com
export SMTP_PASS=your_app_password
export NOTIFICATION_EMAIL=notify@example.com
```

**Slack:**
```bash
export SLACK_WEBHOOK_URL=https://hooks.slack.com/services/YOUR/WEBHOOK/URL
```

### 3. Make Scripts Executable
```bash
chmod +x tools/overnight_session.sh
chmod +x tools/schedule_overnight.py
chmod +x ace/ralph_wiggum.py
```

## Usage Examples

### Quick Overnight Run
```bash
# Start before bed, check in the morning
./tools/overnight_session.sh my-app "Build complete user auth system" 8
```

### Queue Multiple Tasks
```bash
# Add tasks to queue
python3 tools/schedule_overnight.py add \
  todo-app "CLI todo app" --hours 4 --priority 10

python3 tools/schedule_overnight.py add \
  api-server "REST API" --hours 6 --priority 5

# Process queue (runs highest priority first)
python3 tools/schedule_overnight.py process
```

### Use as Cron Job
```bash
# Add to crontab (runs nightly at 11 PM)
0 23 * * * cd ~/context-foundry && python3 tools/schedule_overnight.py process
```

## Monitoring

### Check Progress During Run
```bash
# View current progress
cat checkpoints/ralph/*/progress.json

# View state
cat checkpoints/ralph/*/state.json

# Tail the log
tail -f logs/overnight_*.log
```

### Early Termination
```bash
# Graceful shutdown (saves progress)
Ctrl+C  # or send SIGTERM

# Force completion (creates COMPLETE flag)
touch checkpoints/ralph/session_id/COMPLETE
```

## Output Structure

After an overnight run:

```
examples/my-app/          # Generated project code
checkpoints/ralph/
  session_id/
    progress.json         # What's been completed
    state.json           # Current iteration state
    COMPLETE             # Flag when done
logs/
  ralph_session_id/      # Claude API logs
  overnight_*.log        # Session log
```

## Safety Features

1. **Time Limits** - Maximum 24 hours per session
2. **Iteration Limits** - Maximum 100 iterations
3. **Graceful Shutdown** - Saves state on interrupt
4. **Retry Logic** - Handles transient errors
5. **Progress Checkpoints** - Never lose work

## Cost Estimation

**Typical overnight run (8 hours):**
- ~50-100 iterations
- ~500K tokens total (input + output)
- Cost: ~$2-5 depending on complexity

**Large feature (full night):**
- ~100-150 iterations
- ~1M tokens total
- Cost: ~$5-10

## Troubleshooting

### Session Not Starting
```bash
# Check API key
echo $ANTHROPIC_API_KEY

# Check permissions
ls -l tools/overnight_session.sh

# View logs
cat logs/overnight_*.log
```

### Session Stuck
```bash
# Check current iteration
cat checkpoints/ralph/*/state.json

# Manually mark complete
touch checkpoints/ralph/session_id/COMPLETE
```

### High API Costs
- Reduce max hours
- Use smaller task descriptions
- Review progress - may be looping on same task

## Best Practices

1. **Clear Task Descriptions** - Be specific about what you want
2. **Reasonable Timeframes** - 4-8 hours for most features
3. **Monitor First Run** - Watch first few iterations to ensure progress
4. **Review in Morning** - Check logs and generated code
5. **Use Queue System** - Batch multiple tasks overnight

## Advanced Usage

### Custom Iteration Logic
Edit `ace/ralph_wiggum.py` to customize:
- `_build_iteration_prompt()` - How context is built
- `check_completion()` - Completion criteria
- `_process_response()` - Response handling

### Integration with CI/CD
```bash
# In your CI pipeline
python3 tools/schedule_overnight.py add \
  feature-branch "Implement feature X" \
  --hours 4

# Webhook on completion notifies CI
```

### Multiple Concurrent Sessions
```bash
# Run different projects simultaneously
./tools/overnight_session.sh app1 "Feature A" 8 &
./tools/overnight_session.sh app2 "Feature B" 8 &
```

---

**Remember**: Ralph Wiggum keeps going with fresh enthusiasm! Same prompt, fresh context, continuous progress.

"I'm learnding!" - Ralph Wiggum (and so is your overnight coder)

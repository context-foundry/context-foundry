# CF Daemon Independent Testing Guide

## Mission

You are tasked with independently testing the Context Foundry Daemon (cfd) to validate:
1. All bug fixes from the audit are working correctly
2. Core functionality operates as expected
3. Documentation is accurate and complete
4. Any additional issues are identified

## Background Context

The daemon was recently completed with bug fixes for:
- Config environment variable parsing
- Worker polling delays (reduced from 5s to 0.5s)
- Config reload propagation (SIGHUP handler)
- Foreground-only limitation documentation

Previous testing found 3 minor issues:
1. Graceful shutdown requires SIGKILL
2. Running jobs can't be cancelled mid-execution
3. First daemon instance didn't pick up jobs (required restart)

## Your Testing Checklist

### Phase 1: Basic Functionality ✓

#### Test 1.1: Daemon Lifecycle
```bash
cd /Users/name/homelab/context-foundry

# Start daemon
./tools/cfd start --foreground &
DAEMON_PID=$!
sleep 3

# Verify daemon is running
./tools/cfd status --verbose

# Expected output:
# - Daemon is running (PID xxx)
# - Job Statistics: (empty initially)
# - Max concurrent jobs: 3

# Stop daemon
./tools/cfd stop

# Verify stopped
./tools/cfd status
# Expected: "Daemon is not running"
```

**✅ Pass Criteria:**
- Daemon starts without errors
- PID file created at `~/.context-foundry/cfd/daemon.pid`
- Status command shows correct info
- Daemon stops cleanly (or note if SIGKILL required)

**❌ Failure Indicators:**
- Daemon crashes on startup
- PID file not created
- Status command errors
- Daemon can't be stopped

---

#### Test 1.2: Job Submission and Execution
```bash
# Start daemon in background
./tools/cfd start --foreground > /tmp/cfd-test.log 2>&1 &
sleep 2

# Create test project
mkdir -p /tmp/cfd-test-project
cat > /tmp/cfd-test-project/hello.py << 'EOF'
def greet(name):
    return f"Hello, {name}!"

if __name__ == "__main__":
    print(greet("CF Daemon"))
EOF

# Submit job
JOB_ID=$(./tools/cfd submit \
  --type testing \
  --params '{"working_directory": "/tmp/cfd-test-project", "task": "Run hello.py and verify it works", "timeout_minutes": 5}' \
  --priority 5 | grep "Job submitted:" | awk '{print $3}')

echo "Submitted job: $JOB_ID"

# Wait a few seconds for job to start
sleep 3

# Check job status
./tools/cfd show $JOB_ID

# Monitor logs
./tools/cfd logs $JOB_ID --limit 50

# Wait for completion (up to 2 minutes)
for i in {1..24}; do
  STATUS=$(./tools/cfd show $JOB_ID | grep "^Status:" | awk '{print $2}')
  echo "Attempt $i: Job status = $STATUS"

  if [ "$STATUS" = "succeeded" ] || [ "$STATUS" = "failed" ]; then
    break
  fi

  sleep 5
done

# Final status
./tools/cfd show $JOB_ID
```

**✅ Pass Criteria:**
- Job transitions: queued → running → succeeded
- Job completes within 2 minutes
- Job result shows `"success": true, "exit_code": 0`
- No errors in logs

**❌ Failure Indicators:**
- Job stuck in "queued" status for > 5 seconds
- Job fails with error
- Job never starts
- Timeout after 2 minutes

**🔍 Investigation Steps if Failed:**
```bash
# Check daemon logs
tail -50 /tmp/cfd-test.log

# Check database
sqlite3 ~/.context-foundry/cfd/jobs.db "SELECT id, status, error FROM jobs WHERE id = '$JOB_ID';"

# Check if workers started
grep "Worker started" /tmp/cfd-test.log

# Check if job was picked up
grep "Executing job" /tmp/cfd-test.log
```

---

#### Test 1.3: Concurrent Job Execution
```bash
# Submit 3 jobs simultaneously
JOB1=$(./tools/cfd submit --type testing --params '{"task": "Job A", "working_directory": "/tmp"}' --priority 8 | grep "Job submitted:" | awk '{print $3}')
JOB2=$(./tools/cfd submit --type testing --params '{"task": "Job B", "working_directory": "/tmp"}' --priority 7 | grep "Job submitted:" | awk '{print $3}')
JOB3=$(./tools/cfd submit --type testing --params '{"task": "Job C", "working_directory": "/tmp"}' --priority 6 | grep "Job submitted:" | awk '{print $3}')

echo "Jobs submitted: $JOB1, $JOB2, $JOB3"

# Check how many are running immediately
sleep 2
./tools/cfd list --status running

# Wait for completion
sleep 20

# Verify all succeeded
./tools/cfd show $JOB1 | grep Status
./tools/cfd show $JOB2 | grep Status
./tools/cfd show $JOB3 | grep Status
```

**✅ Pass Criteria:**
- At least 2 jobs running simultaneously within 2 seconds
- All 3 jobs complete successfully
- Jobs picked up within ~1 second each
- Priority ordering respected (Job A with priority 8 starts first)

**❌ Failure Indicators:**
- Only 1 job running at a time
- Jobs wait > 5 seconds to start
- Any jobs fail

---

#### Test 1.4: Priority Queue
```bash
# Submit jobs in reverse priority order
LOW=$(./tools/cfd submit --type testing --params '{"task": "Low priority"}' --priority 1 | grep "Job submitted:" | awk '{print $3}')
MED=$(./tools/cfd submit --type testing --params '{"task": "Medium priority"}' --priority 5 | grep "Job submitted:" | awk '{print $3}')
HIGH=$(./tools/cfd submit --type testing --params '{"task": "High priority"}' --priority 10 | grep "Job submitted:" | awk '{print $3}')

# Check execution order
sleep 2
./tools/cfd list --limit 10

# Verify high priority job started first
HIGH_START=$(sqlite3 ~/.context-foundry/cfd/jobs.db "SELECT started_at FROM jobs WHERE id = '$HIGH';")
MED_START=$(sqlite3 ~/.context-foundry/cfd/jobs.db "SELECT started_at FROM jobs WHERE id = '$MED';")
LOW_START=$(sqlite3 ~/.context-foundry/cfd/jobs.db "SELECT started_at FROM jobs WHERE id = '$LOW';")

echo "High priority started: $HIGH_START"
echo "Medium priority started: $MED_START"
echo "Low priority started: $LOW_START"

# High should be earliest timestamp
```

**✅ Pass Criteria:**
- High priority job starts before medium and low
- Jobs execute in priority order when queued

---

#### Test 1.5: Job Cancellation
```bash
# Test cancelling queued job
QUEUED1=$(./tools/cfd submit --type testing --params '{"task": "Will cancel"}' --priority 1 | grep "Job submitted:" | awk '{print $3}')
QUEUED2=$(./tools/cfd submit --type testing --params '{"task": "Will cancel"}' --priority 1 | grep "Job submitted:" | awk '{print $3}')
QUEUED3=$(./tools/cfd submit --type testing --params '{"task": "Will cancel"}' --priority 1 | grep "Job submitted:" | awk '{print $3}')
QUEUED4=$(./tools/cfd submit --type testing --params '{"task": "Will cancel"}' --priority 1 | grep "Job submitted:" | awk '{print $3}')

# Cancel one that's still queued
sleep 1
./tools/cfd cancel $QUEUED4

# Check status
./tools/cfd show $QUEUED4 | grep Status
# Expected: Status: cancelled
```

**✅ Pass Criteria:**
- Cancelled job shows status "cancelled"
- Cancelled job never starts executing

**⚠️ Known Limitation to Verify:**
- Running jobs cannot be cancelled mid-execution (status changes to cancelled but job continues)

---

### Phase 2: Bug Fix Verification ✓

#### Test 2.1: Worker Polling Speed (Bug Fix #3)
```bash
# This tests that workers pick up jobs within ~1 second (not 5 seconds)

# Submit job and measure time to start
START_TIME=$(date +%s)
JOB=$(./tools/cfd submit --type testing --params '{"task": "Speed test"}' --priority 5 | grep "Job submitted:" | awk '{print $3}')

# Poll until job starts
while true; do
  STATUS=$(./tools/cfd show $JOB | grep "^Status:" | awk '{print $2}')
  if [ "$STATUS" = "running" ] || [ "$STATUS" = "succeeded" ]; then
    END_TIME=$(date +%s)
    ELAPSED=$((END_TIME - START_TIME))
    echo "Job started in $ELAPSED seconds"
    break
  fi
  sleep 0.2
done

# Expected: < 2 seconds
# If > 5 seconds, bug fix didn't work
```

**✅ Pass Criteria:**
- Job starts within 2 seconds of submission

**❌ Failure Indicator:**
- Job takes > 5 seconds to start (indicates worker polling bug not fixed)

---

#### Test 2.2: Config Environment Variables (Bug Fix #1)
```bash
# Test that CFD_MAX_CONCURRENT is properly parsed as integer

# Stop current daemon
./tools/cfd stop
sleep 2

# Set environment variable
export CFD_MAX_CONCURRENT=5
export CFD_LOG_LEVEL=DEBUG

# Start with env vars
./tools/cfd start --foreground > /tmp/cfd-envtest.log 2>&1 &
sleep 3

# Check config
./tools/cfd status --verbose

# Verify max_concurrent_jobs is 5 (not "5" as string)
WORKERS=$(grep "JobManager started with" /tmp/cfd-envtest.log | tail -1)
echo "$WORKERS"
# Expected: "JobManager started with 5 workers"

# Clean up
unset CFD_MAX_CONCURRENT
unset CFD_LOG_LEVEL
./tools/cfd stop
```

**✅ Pass Criteria:**
- Daemon starts with 5 workers (from env var)
- No type errors in logs

**❌ Failure Indicator:**
- Daemon starts with default 3 workers (env var ignored)
- Type error in logs about max_concurrent_jobs

---

#### Test 2.3: Config Reload (Bug Fix #4)
```bash
# Start daemon
./tools/cfd start --foreground > /tmp/cfd-reload.log 2>&1 &
sleep 3

DAEMON_PID=$(cat ~/.context-foundry/cfd/daemon.pid)

# Modify config
cat > ~/.context-foundry/cfd/config.json << 'EOF'
{
  "log_level": "DEBUG",
  "max_concurrent_jobs": 5
}
EOF

# Send SIGHUP to reload
kill -HUP $DAEMON_PID

# Wait for reload
sleep 2

# Check logs for reload confirmation
grep "Configuration reloaded" /tmp/cfd-reload.log
grep "Log level updated" /tmp/cfd-reload.log

# Verify DEBUG logs now appear
./tools/cfd submit --type testing --params '{"task": "Test"}' --priority 5
sleep 2
grep "DEBUG" /tmp/cfd-reload.log

# Clean up
./tools/cfd stop
rm ~/.context-foundry/cfd/config.json
```

**✅ Pass Criteria:**
- SIGHUP triggers config reload
- Log level changes to DEBUG
- Warning shown for worker count change

**❌ Failure Indicator:**
- SIGHUP doesn't reload config
- Log level stays at INFO
- No reload messages in logs

---

#### Test 2.4: Foreground-Only Limitation Documented (Bug Fix #5)
```bash
# Verify warning appears when background mode requested
./tools/cfd start > /tmp/cfd-bg-test.log 2>&1 &
sleep 3

# Check for warning in logs
grep "Background mode requested but not implemented" /tmp/cfd-bg-test.log

# Check CLI help text
./tools/cfd start --help | grep "background daemonization not yet implemented"

# Clean up
./tools/cfd stop
```

**✅ Pass Criteria:**
- Warning appears in logs when starting without --foreground
- CLI help mentions limitation

---

### Phase 3: Real-World Integration ✓

#### Test 3.1: Real CF Build Task
```bash
# Create actual project to build
mkdir -p /tmp/real-cf-test
cd /tmp/real-cf-test

# Initialize Python project
cat > app.py << 'EOF'
from flask import Flask

app = Flask(__name__)

@app.route('/')
def hello():
    return "Hello from CF Daemon real test!"

@app.route('/status')
def status():
    return {"status": "ok"}

if __name__ == '__main__':
    app.run(debug=True)
EOF

cat > requirements.txt << 'EOF'
flask
EOF

cat > test_app.py << 'EOF'
import pytest
from app import app

def test_hello():
    client = app.test_client()
    response = client.get('/')
    assert response.status_code == 200
    assert b"Hello" in response.data

def test_status():
    client = app.test_client()
    response = client.get('/status')
    assert response.status_code == 200
    assert response.json['status'] == 'ok'
EOF

# Submit real build job
cd /Users/name/homelab/context-foundry
JOB=$(./tools/cfd submit \
  --type testing \
  --params '{"working_directory": "/tmp/real-cf-test", "task": "Install dependencies, run tests, and verify the Flask app works correctly", "timeout_minutes": 10}' \
  --priority 8 | grep "Job submitted:" | awk '{print $3}')

echo "Real build job: $JOB"

# Monitor progress
./tools/cfd logs $JOB --follow &
LOGS_PID=$!

# Wait for completion (up to 10 minutes)
for i in {1..120}; do
  STATUS=$(./tools/cfd show $JOB | grep "^Status:" | awk '{print $2}')
  echo "[$i/120] Job status: $STATUS"

  if [ "$STATUS" = "succeeded" ] || [ "$STATUS" = "failed" ]; then
    break
  fi

  sleep 5
done

# Stop log following
kill $LOGS_PID 2>/dev/null

# Show final results
./tools/cfd show $JOB
```

**✅ Pass Criteria:**
- Job completes successfully
- Tests pass
- Flask app validated
- Phase transitions visible in logs (Scout → Architect → Builder → Test)

**❌ Failure Indicators:**
- Job fails
- Tests don't run
- Timeout after 10 minutes

---

#### Test 3.2: Pattern Merge Validation
```bash
# Check if pattern merge happened for real build
ls -la /tmp/real-cf-test/.context-foundry/patterns/

# Check if patterns were merged to global library
ls -la ~/.context-foundry/patterns/

# View merged patterns
cat ~/.context-foundry/patterns/common-issues.json | jq '.'

# Check logs for merge confirmation
./tools/cfd logs $JOB | grep "pattern"
```

**✅ Pass Criteria:**
- Patterns created in project `.context-foundry/patterns/`
- Patterns merged to global library
- Log entry confirms merge

**⚠️ Known Behavior:**
- If no patterns generated, merge is skipped (not a failure)

---

#### Test 3.3: Phase Tracking
```bash
# Check phase events for real build job
sqlite3 ~/.context-foundry/cfd/jobs.db << EOF
SELECT phase, status, timestamp
FROM phase_events
WHERE job_id = '$JOB'
ORDER BY timestamp;
EOF

# Expected output:
# scout|in_progress|2025-11-13 12:00:00
# architect|in_progress|2025-11-13 12:01:00
# builder|in_progress|2025-11-13 12:02:00
# test|completed|2025-11-13 12:05:00
```

**✅ Pass Criteria:**
- Phase events recorded for Scout, Architect, Builder, Test
- Phases transition in correct order
- Timestamps show progression

---

### Phase 4: Stress Testing ✓

#### Test 4.1: Many Jobs
```bash
# Submit 20 jobs
for i in {1..20}; do
  ./tools/cfd submit --type testing --params "{\"task\": \"Stress test job $i\"}" --priority $((i % 10)) > /dev/null &
done
wait

# Monitor queue
watch -n 1 './tools/cfd list --limit 20'

# Wait for all to complete (up to 20 minutes)
sleep 600

# Check statistics
./tools/cfd status --verbose
```

**✅ Pass Criteria:**
- All 20 jobs complete
- No crashes or hangs
- Worker pool handles load

**❌ Failure Indicators:**
- Jobs stuck indefinitely
- Daemon crashes
- Database corruption

---

### Phase 5: Edge Cases ✓

#### Test 5.1: Job Timeout
```bash
# Submit job that will timeout
TIMEOUT_JOB=$(./tools/cfd submit \
  --type testing \
  --params '{"task": "Sleep for 100 hours", "working_directory": "/tmp", "timeout_minutes": 0.05}' \
  --priority 5 | grep "Job submitted:" | awk '{print $3}')

# Wait for timeout
sleep 10

# Check if marked as failed
./tools/cfd show $TIMEOUT_JOB
```

**✅ Pass Criteria:**
- Job times out and fails
- Error message mentions timeout

---

#### Test 5.2: Database Concurrency
```bash
# Multiple CLI commands hitting database simultaneously
./tools/cfd list &
./tools/cfd status --verbose &
./tools/cfd submit --type testing --params '{"task": "Concurrent test"}' &
wait

# No database locked errors expected
```

**✅ Pass Criteria:**
- No "database is locked" errors
- All commands succeed

---

## Testing Report Template

After completing tests, fill out this report:

```markdown
# CF Daemon Independent Test Report

**Tester:** [Your agent name]
**Date:** [Date]
**Commit:** [Git commit hash]

## Test Results Summary

- Phase 1 (Basic Functionality): X/5 passed
- Phase 2 (Bug Fix Verification): X/4 passed
- Phase 3 (Real-World Integration): X/3 passed
- Phase 4 (Stress Testing): X/1 passed
- Phase 5 (Edge Cases): X/2 passed

**Overall: X/15 tests passed**

## Detailed Results

### ✅ Passing Tests
[List all tests that passed]

### ❌ Failing Tests
[List all tests that failed with error details]

### ⚠️ Observations
[Note any unexpected behavior, performance issues, or concerns]

## Known Issues Verification

1. **Graceful shutdown requires SIGKILL**: [Confirmed/Not observed]
2. **Running jobs can't be cancelled**: [Confirmed/Not observed]
3. **First instance hung**: [Confirmed/Not observed/Could not reproduce]

## New Issues Found
[List any new bugs or issues discovered during testing]

## Performance Metrics

- Average job pickup time: X seconds
- Average job execution time: X seconds
- Max concurrent jobs observed: X
- Total jobs tested: X

## Recommendations

[Suggestions for fixes, improvements, or next steps]

## Overall Assessment

**Status:** [PASS / FAIL / PASS WITH CONCERNS]

[Summary paragraph]
```

## Cleanup After Testing

```bash
# Stop daemon
./tools/cfd stop

# Clean test database
rm -rf ~/.context-foundry/cfd/

# Remove test projects
rm -rf /tmp/cfd-test-project /tmp/real-cf-test

# Remove log files
rm -f /tmp/cfd-*.log
```

## Getting Help

If you encounter issues:

1. **Check daemon logs:**
   ```bash
   tail -100 ~/.context-foundry/cfd/logs/cfd.log
   ```

2. **Check database:**
   ```bash
   sqlite3 ~/.context-foundry/cfd/jobs.db ".tables"
   sqlite3 ~/.context-foundry/cfd/jobs.db "SELECT * FROM jobs;"
   ```

3. **Read architecture docs:**
   ```bash
   cat /Users/name/homelab/context-foundry/docs/CF_DAEMON_ARCHITECTURE.md
   ```

4. **Run unit tests:**
   ```bash
   python3 -m pytest tests/test_daemon_*.py -v
   ```

Good luck with testing! 🚀

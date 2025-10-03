#!/bin/bash
#
# Overnight Session Runner - Ralph Wiggum Strategy
# Implements Jeff Huntley's approach: Same prompt, fresh context, persistent progress
#
# Usage: ./overnight_session.sh <project_name> <task_description> [hours]
#

set -euo pipefail

# Colors for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m' # No Color

# Configuration
PROJECT_NAME="${1:-}"
TASK_DESCRIPTION="${2:-}"
MAX_HOURS="${3:-8}"
TIMESTAMP=$(date +"%Y%m%d_%H%M%S")
LOG_FILE="logs/overnight_${TIMESTAMP}.log"
COMPLETION_FLAG="checkpoints/ralph/${PROJECT_NAME}_${TIMESTAMP}/COMPLETE"

# Validate arguments
if [ -z "$PROJECT_NAME" ] || [ -z "$TASK_DESCRIPTION" ]; then
    echo "Usage: $0 <project_name> <task_description> [hours]"
    echo ""
    echo "Examples:"
    echo "  $0 my-app 'Build user authentication' 4"
    echo "  $0 api-server 'REST API with JWT auth' 8"
    echo ""
    echo "Default duration: 8 hours"
    exit 1
fi

# Create log directory
mkdir -p logs
mkdir -p "checkpoints/ralph/${PROJECT_NAME}_${TIMESTAMP}"

# Logging function
log() {
    echo -e "${1}" | tee -a "$LOG_FILE"
}

# Trap signals for graceful shutdown
cleanup() {
    log "${YELLOW}⚠️  Received shutdown signal${NC}"
    log "${BLUE}📊 Session statistics:${NC}"
    log "   Iterations completed: $ITERATION"
    log "   Duration: $(($(date +%s) - START_TIME)) seconds"
    log "   Project: $PROJECT_NAME"
    exit 0
}

trap cleanup SIGINT SIGTERM

# Header
log "${GREEN}🌙 OVERNIGHT SESSION STARTED${NC}"
log "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
log "📋 Project: ${BLUE}$PROJECT_NAME${NC}"
log "📝 Task: ${BLUE}$TASK_DESCRIPTION${NC}"
log "⏰ Duration: ${BLUE}$MAX_HOURS hours${NC}"
log "📄 Log: ${BLUE}$LOG_FILE${NC}"
log "🕐 Started: $(date)"
log "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"

# Check for API key
if [ -z "${ANTHROPIC_API_KEY:-}" ]; then
    log "${RED}❌ Error: ANTHROPIC_API_KEY not set${NC}"
    log "   Set it with: export ANTHROPIC_API_KEY=your_key"
    exit 1
fi

# Check for Python
if ! command -v python3 &> /dev/null; then
    log "${RED}❌ Error: python3 not found${NC}"
    exit 1
fi

# Start time tracking
START_TIME=$(date +%s)
END_TIME=$((START_TIME + MAX_HOURS * 3600))
ITERATION=0

log "${GREEN}🚀 Starting Ralph Wiggum runner...${NC}\n"

# Main loop
while true; do
    CURRENT_TIME=$(date +%s)
    ITERATION=$((ITERATION + 1))

    # Check time limit
    if [ "$CURRENT_TIME" -ge "$END_TIME" ]; then
        log "${YELLOW}⏰ Time limit reached ($MAX_HOURS hours)${NC}"
        break
    fi

    # Check completion flag
    if [ -f "$COMPLETION_FLAG" ]; then
        log "${GREEN}✅ Completion flag detected!${NC}"
        log "${GREEN}🎉 Task completed successfully${NC}"
        break
    fi

    # Calculate remaining time
    REMAINING_SECONDS=$((END_TIME - CURRENT_TIME))
    REMAINING_HOURS=$((REMAINING_SECONDS / 3600))
    REMAINING_MINS=$(((REMAINING_SECONDS % 3600) / 60))

    log "${BLUE}━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━${NC}"
    log "${YELLOW}🔄 Iteration $ITERATION${NC}"
    log "   Time remaining: ${REMAINING_HOURS}h ${REMAINING_MINS}m"
    log "   Current time: $(date)"
    log "${BLUE}━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━${NC}\n"

    # Run the Ralph Wiggum runner
    # This calls the Python implementation which handles:
    # - Loading previous progress
    # - Fresh Claude context
    # - Running one iteration
    # - Saving updated progress

    if python3 ace/ralph_wiggum.py \
        --project "$PROJECT_NAME" \
        --task "$TASK_DESCRIPTION" \
        --session "${PROJECT_NAME}_${TIMESTAMP}" \
        --iteration "$ITERATION" 2>&1 | tee -a "$LOG_FILE"; then

        log "${GREEN}✅ Iteration $ITERATION completed${NC}\n"
    else
        EXIT_CODE=$?
        log "${YELLOW}⚠️  Iteration $ITERATION returned exit code: $EXIT_CODE${NC}"

        # Exit code 42 means task is complete
        if [ "$EXIT_CODE" -eq 42 ]; then
            log "${GREEN}🎉 Task marked as complete by runner${NC}"
            break
        fi

        # Exit code 99 means unrecoverable error
        if [ "$EXIT_CODE" -eq 99 ]; then
            log "${RED}❌ Unrecoverable error, aborting${NC}"
            break
        fi

        log "${YELLOW}⏸️  Waiting 30s before retry...${NC}\n"
        sleep 30
    fi

    # Safety check: max 100 iterations
    if [ "$ITERATION" -ge 100 ]; then
        log "${RED}⚠️  Maximum iterations (100) reached${NC}"
        log "${YELLOW}   This is a safety limit. Check if task is too complex.${NC}"
        break
    fi

    # Brief pause between iterations
    sleep 5
done

# Final statistics
TOTAL_DURATION=$(($(date +%s) - START_TIME))
HOURS=$((TOTAL_DURATION / 3600))
MINUTES=$(((TOTAL_DURATION % 3600) / 60))

log "\n${GREEN}━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━${NC}"
log "${GREEN}🌅 OVERNIGHT SESSION COMPLETE${NC}"
log "${GREEN}━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━${NC}"
log "📊 ${BLUE}Final Statistics:${NC}"
log "   Total iterations: $ITERATION"
log "   Total duration: ${HOURS}h ${MINUTES}m"
log "   Project: $PROJECT_NAME"
log "   Ended: $(date)"
log ""
log "📁 ${BLUE}Check results:${NC}"
log "   Project files: examples/$PROJECT_NAME/"
log "   Progress: checkpoints/ralph/${PROJECT_NAME}_${TIMESTAMP}/"
log "   Full log: $LOG_FILE"
log "${GREEN}━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━${NC}"

# Exit with success if completed, otherwise exit with error
if [ -f "$COMPLETION_FLAG" ]; then
    exit 0
else
    exit 1
fi

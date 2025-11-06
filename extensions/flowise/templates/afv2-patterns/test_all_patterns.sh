#!/bin/bash

# AFv2 Patterns - Comprehensive Test Suite
# Tests all 9 patterns (6 existing + 3 new)
# Version: 1.0
# Last Updated: 2025-11-05

set -e  # Exit on error

SCRIPT_DIR="$( cd "$( dirname "${BASH_SOURCE[0]}" )" && pwd )"
VALIDATOR_PATH="$SCRIPT_DIR/../../validate_workflow.py"

# Colors for output
GREEN='\033[0;32m'
RED='\033[0;31m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m' # No Color

# Counters
TOTAL_TESTS=0
PASSED_TESTS=0
FAILED_TESTS=0

echo ""
echo "╔════════════════════════════════════════════════════════════════╗"
echo "║         AFv2 PATTERNS - COMPREHENSIVE TEST SUITE              ║"
echo "╚════════════════════════════════════════════════════════════════╝"
echo ""

# Function to test a single pattern
test_pattern() {
    local file=$1
    local pattern_name=$2
    local pattern_num=$3

    TOTAL_TESTS=$((TOTAL_TESTS + 1))

    echo -e "${BLUE}━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━${NC}"
    echo -e "${YELLOW}[TEST $TOTAL_TESTS] Pattern #$pattern_num: $pattern_name${NC}"
    echo -e "${BLUE}━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━${NC}"

    # Check file exists
    if [ ! -f "$file" ]; then
        echo -e "${RED}❌ FAIL: File not found: $file${NC}"
        FAILED_TESTS=$((FAILED_TESTS + 1))
        return 1
    fi

    # Get file size and line count
    local file_size=$(du -h "$file" | cut -f1)
    local line_count=$(wc -l < "$file")

    echo "   File: $file"
    echo "   Size: $file_size"
    echo "   Lines: $line_count"

    # Check JSON validity
    echo -n "   [1/5] JSON validity check... "
    if jq empty "$file" 2>/dev/null; then
        echo -e "${GREEN}✅ PASS${NC}"
    else
        echo -e "${RED}❌ FAIL${NC}"
        FAILED_TESTS=$((FAILED_TESTS + 1))
        return 1
    fi

    # Get node and edge counts
    local node_count=$(jq '.nodes | length' "$file")
    local edge_count=$(jq '.edges | length' "$file")

    echo -n "   [2/5] Structure check (nodes: $node_count, edges: $edge_count)... "
    if [ "$node_count" -gt 0 ] && [ "$edge_count" -gt 0 ]; then
        echo -e "${GREEN}✅ PASS${NC}"
    else
        echo -e "${RED}❌ FAIL${NC}"
        FAILED_TESTS=$((FAILED_TESTS + 1))
        return 1
    fi

    # Check for required node types
    echo -n "   [3/5] Required nodes check (Start, Agent, Direct Reply)... "
    local has_start=$(jq '.nodes[] | select(.data.name == "start") | .id' "$file" | wc -l)
    local has_agent=$(jq '.nodes[] | select(.data.name == "agentAgentflow") | .id' "$file" | wc -l)
    local has_reply=$(jq '.nodes[] | select(.data.name == "directReplyAgentflow") | .id' "$file" | wc -l)

    if [ "$has_start" -gt 0 ] && [ "$has_agent" -gt 0 ] && [ "$has_reply" -gt 0 ]; then
        echo -e "${GREEN}✅ PASS${NC}"
    else
        echo -e "${YELLOW}⚠️  WARN (Start: $has_start, Agent: $has_agent, Reply: $has_reply)${NC}"
    fi

    # Run full validation with validate_workflow.py
    echo -n "   [4/5] Full pattern validation (validate_workflow.py)... "
    if python3 "$VALIDATOR_PATH" "$file" 2>&1 | grep -q "✅ ALL VALIDATIONS PASSED"; then
        echo -e "${GREEN}✅ PASS${NC}"
    else
        echo -e "${RED}❌ FAIL${NC}"
        echo ""
        echo "   Full validation output:"
        python3 "$VALIDATOR_PATH" "$file" 2>&1 | grep -A 20 "VALIDATION SUMMARY" || true
        FAILED_TESTS=$((FAILED_TESTS + 1))
        return 1
    fi

    # Check specific pattern features
    echo -n "   [5/5] Pattern-specific features... "
    case $pattern_num in
        7)
            # Pattern #7: Check for Iteration Node
            local has_iteration=$(jq '.nodes[] | select(.data.name == "iterationAgentflow") | .id' "$file" | wc -l)
            if [ "$has_iteration" -gt 0 ]; then
                echo -e "${GREEN}✅ PASS (Iteration Node found)${NC}"
            else
                echo -e "${RED}❌ FAIL (No Iteration Node)${NC}"
                FAILED_TESTS=$((FAILED_TESTS + 1))
                return 1
            fi
            ;;
        8)
            # Pattern #8: Check for Condition Node and loop-back edge
            local has_condition=$(jq '.nodes[] | select(.data.name == "conditionAgentflow") | .id' "$file" | wc -l)
            local has_animated=$(jq '.edges[] | select(.animated == true) | .id' "$file" | wc -l)
            if [ "$has_condition" -gt 0 ] && [ "$has_animated" -gt 0 ]; then
                echo -e "${GREEN}✅ PASS (Condition Node + animated loop-back)${NC}"
            else
                echo -e "${RED}❌ FAIL (Condition: $has_condition, Loop: $has_animated)${NC}"
                FAILED_TESTS=$((FAILED_TESTS + 1))
                return 1
            fi
            ;;
        9)
            # Pattern #9: Check for HTTP Request Node
            local has_http=$(jq '.nodes[] | select(.data.name == "httpRequestAgentflow") | .id' "$file" | wc -l)
            if [ "$has_http" -gt 0 ]; then
                echo -e "${GREEN}✅ PASS (HTTP Request Node found)${NC}"
            else
                echo -e "${RED}❌ FAIL (No HTTP Request Node)${NC}"
                FAILED_TESTS=$((FAILED_TESTS + 1))
                return 1
            fi
            ;;
        *)
            # Patterns 1-6: Just check for Direct Reply terminal
            local reply_hideOutput=$(jq '.nodes[] | select(.data.name == "directReplyAgentflow") | .data.hideOutput' "$file" | grep -c "true" || echo 0)
            if [ "$reply_hideOutput" -gt 0 ]; then
                echo -e "${GREEN}✅ PASS (Direct Reply terminal configured)${NC}"
            else
                echo -e "${YELLOW}⚠️  WARN (Check Direct Reply hideOutput)${NC}"
            fi
            ;;
    esac

    PASSED_TESTS=$((PASSED_TESTS + 1))
    echo -e "${GREEN}✅ OVERALL: PASS${NC}"
    echo ""

    return 0
}

# Test all 9 patterns
cd "$SCRIPT_DIR"

test_pattern "01-chaining.json" "Chaining" "1"
test_pattern "02-parallel.json" "Parallel" "2"
test_pattern "03-routing.json" "Routing" "3"
test_pattern "04-iteration.json" "Iteration" "4"
test_pattern "05-looping.json" "Looping" "5"
test_pattern "06-hierarchy.json" "Hierarchy" "6"
test_pattern "07-batch-processing.json" "Batch Processing" "7"
test_pattern "08-conditional-retry.json" "Conditional Retry" "8"
test_pattern "09-api-integration.json" "API Integration" "9"

# Summary
echo ""
echo "╔════════════════════════════════════════════════════════════════╗"
echo "║                      TEST SUMMARY                              ║"
echo "╚════════════════════════════════════════════════════════════════╝"
echo ""
echo "   Total Tests:   $TOTAL_TESTS"
echo -e "   ${GREEN}Passed:        $PASSED_TESTS${NC}"
echo -e "   ${RED}Failed:        $FAILED_TESTS${NC}"
echo ""

if [ $FAILED_TESTS -eq 0 ]; then
    echo -e "${GREEN}╔═══════════════════════════════════════════════════════════╗${NC}"
    echo -e "${GREEN}║  ✅ ALL PATTERNS PASSED - READY FOR FLOWISE TESTING!     ║${NC}"
    echo -e "${GREEN}╚═══════════════════════════════════════════════════════════╝${NC}"
    echo ""
    echo "Next steps:"
    echo "  1. Import patterns into Flowise UI"
    echo "  2. Follow TESTING_GUIDE.md for test cases"
    echo "  3. Run comprehensive functional tests"
    echo ""
    exit 0
else
    echo -e "${RED}╔═══════════════════════════════════════════════════════════╗${NC}"
    echo -e "${RED}║  ❌ SOME PATTERNS FAILED - REVIEW OUTPUT ABOVE           ║${NC}"
    echo -e "${RED}╚═══════════════════════════════════════════════════════════╝${NC}"
    echo ""
    echo "Action required:"
    echo "  1. Review failed test output above"
    echo "  2. Fix validation errors"
    echo "  3. Re-run test suite"
    echo ""
    exit 1
fi

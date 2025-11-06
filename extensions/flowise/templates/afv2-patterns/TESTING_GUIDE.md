# AFv2 Patterns Testing Guide

**Version:** 1.0
**Last Updated:** 2025-11-05
**Patterns Tested:** 7 (Batch Processing), 8 (Conditional Retry), 9 (API Integration)

---

## 🎯 Testing Objectives

This guide provides comprehensive test cases for the 3 new AgentFlow v2 patterns:
- **Pattern #7:** Batch Processing (Iteration Node)
- **Pattern #8:** Conditional Retry (Condition Node + Loop)
- **Pattern #9:** API Integration (HTTP Request Node)

---

## 🛠️ Prerequisites

### Flowise Setup
- ✅ Flowise instance running (local or cloud)
- ✅ Anthropic API key configured in Flowise credentials
- ✅ Access to Flowise UI (typically http://localhost:3000)

### Test Environment
- ✅ Network access for HTTP requests (Pattern #9)
- ✅ Valid test data for array processing (Pattern #7)

---

## 📋 Test Case Matrix

| Pattern | Test Case | Input Type | Expected Outcome | Validation Criteria |
|---------|-----------|------------|------------------|---------------------|
| #7 | TC-7.1: Basic Array | Array of 3 items | Processes each item, returns aggregated results | All 3 items processed |
| #7 | TC-7.2: Empty Array | Empty array `[]` | Handles gracefully with empty results | No errors, returns empty aggregation |
| #7 | TC-7.3: Large Array | Array of 10 items | Processes all items efficiently | Completes within 2 minutes |
| #8 | TC-8.1: Pass First Try | High-quality input | Passes validation immediately (score ≥ 0.85) | SUCCESS path, 0 retries |
| #8 | TC-8.2: Retry Success | Medium-quality input | Retries 1-2 times, then passes | SUCCESS path, 1-2 retries |
| #8 | TC-8.3: Max Retries Fail | Low-quality input | Exhausts 3 retries, fails gracefully | FAIL path, 3 retries |
| #9 | TC-9.1: Success (200) | Valid API request | Returns formatted response | SUCCESS path, 1 attempt |
| #9 | TC-9.2: Retry (5xx) | Simulated server error | Retries up to 3 times with backoff | ERROR → RETRY path |
| #9 | TC-9.3: Fatal (4xx) | Invalid request | Fails immediately without retry | FATAL path, 1 attempt |

---

## 🧪 Pattern #7: Batch Processing Tests

### Test Case TC-7.1: Basic Array Processing

**Objective:** Validate Iteration Node processes array correctly

**Import Steps:**
1. Open Flowise UI → Agentflows → Add New
2. Click "Load Agentflow"
3. Select `07-batch-processing.json`
4. Verify all nodes load correctly (9 nodes visible)
5. Click "Save Agentflow"

**Configuration:**
- **Credentials:** Set "Anthropic API Key" for all 3 agents (Planner, Processor, Aggregator)
- **Model:** Verify `claude-sonnet-4-5-20250929` is selected

**Test Input:**
```
Analyze sentiment for these reviews:
1. "This product is amazing! Best purchase ever."
2. "Terrible quality, broke after one day."
3. "It's okay, nothing special but works fine."
```

**Expected Output:**
- **Planner:** Extracts 3 reviews into array
- **Iteration Node:** Loops 3 times (once per review)
- **Processor:** Analyzes each review sentiment (Positive/Negative/Neutral)
- **Aggregator:** Returns summary with:
  - Total items processed: 3
  - Sentiment breakdown: 1 positive, 1 negative, 1 neutral
  - Individual results array

**Validation Checklist:**
- [ ] All 3 reviews processed (check aggregator output)
- [ ] Iteration counter increments correctly (1→2→3)
- [ ] No errors in execution log
- [ ] Direct Reply terminal node fires (workflow ends cleanly)
- [ ] Execution time < 60 seconds

**Debugging Tips:**
- If Iteration Node doesn't loop: Check `iterationInput` is set to `{{ planner.output.items }}` or similar array variable
- If Processor runs only once: Verify Iteration Node → Processor edge is connected correctly

---

### Test Case TC-7.2: Empty Array Handling

**Test Input:**
```
Process this list of items: (none provided)
```

**Expected Behavior:**
- Planner detects empty array
- Iteration Node skips loop (0 iterations)
- Aggregator returns: "No items to process"

**Validation Checklist:**
- [ ] No errors (graceful handling)
- [ ] Aggregator acknowledges empty input
- [ ] Workflow completes successfully

---

### Test Case TC-7.3: Large Array Stress Test

**Test Input:**
```
Analyze sentiment for these 10 product reviews:
1. "Great product, highly recommend!"
2. "Poor quality, very disappointed."
3. "Average, meets basic expectations."
4. "Excellent value for money!"
5. "Broke within a week, waste of money."
6. "Good quality, would buy again."
7. "Not worth the price, too expensive."
8. "Perfectly fine, does the job."
9. "Outstanding product, exceeded expectations!"
10. "Terrible experience, do not buy."
```

**Expected Output:**
- All 10 reviews processed sequentially
- Execution time: 90-120 seconds (10 reviews × ~10 sec per review)
- Aggregator returns full breakdown

**Validation Checklist:**
- [ ] All 10 items in aggregated results
- [ ] No timeouts or errors
- [ ] Memory usage remains stable

---

## 🔄 Pattern #8: Conditional Retry Tests

### Test Case TC-8.1: Pass First Try (High Quality)

**Objective:** Validate Condition Node routes to SUCCESS path when score ≥ 0.85

**Import Steps:**
1. Open Flowise UI → Agentflows → Add New
2. Click "Load Agentflow"
3. Select `08-conditional-retry.json`
4. Verify all nodes load (11 nodes: 1 Start, 4 Agents, 1 Condition Node, 1 Condition Agent, 2 Direct Reply, 3 Sticky Notes)
5. Click "Save Agentflow"

**Configuration:**
- **Credentials:** Set "Anthropic API Key" for all agents
- **Condition Node Threshold:** Verify set to `0.85` (line 247 in JSON: `"value": "0.85"`)
- **Retry Controller Model:** Verify using `claude-3-5-haiku-20241022` (cost optimization)

**Test Input:**
```
Generate a professional email to a client apologizing for a delayed shipment and offering a 10% discount.
```

**Expected Output:**
- **Generator:** Creates well-formatted, professional email
- **Validator:** Scores email quality → 0.90 (above 0.85 threshold)
- **Condition Node:** Routes to scenario 0 (PASS)
- **Success Agent:** Formats final output with validation badge
- **Direct Reply (Success):** Returns approved email + metadata
  - Score: 0.90
  - Retries: 0
  - Status: PASS

**Validation Checklist:**
- [ ] Condition Node routes to PASS (scenario 0)
- [ ] Retry count = 0
- [ ] Success Direct Reply node fires (not Fail node)
- [ ] No loop-back edge triggered
- [ ] Execution time < 30 seconds

**Debugging Tips:**
- If routes to RETRY despite high score: Check Condition Node operator is `larger` (≥) not `equal`
- If Validator score format wrong: Ensure Validator returns numeric score in format `{{ $flow.state.validation_score }}`

---

### Test Case TC-8.2: Retry Success (Medium Quality)

**Test Input:**
```
Write a quick email saying the shipment is late.
```

**Expected Output:**
- **Iteration 1:**
  - Generator: Creates basic email (too brief)
  - Validator: Scores 0.60 (below 0.85)
  - Condition Node: Routes to RETRY
  - Retry Controller (Condition Agent): Analyzes issues → "Add more details, professional tone"
  - Loop-back edge: Returns to Generator

- **Iteration 2:**
  - Generator: Creates improved email (more details, professional tone)
  - Validator: Scores 0.88 (above 0.85)
  - Condition Node: Routes to PASS
  - Success Agent: Returns final email

**Expected Metadata:**
- Score: 0.88
- Retries: 1
- Status: PASS
- Retry History: ["Add more details, professional tone"]

**Validation Checklist:**
- [ ] Loop-back edge fires (animated edge visible during execution)
- [ ] Retry counter increments: 0 → 1
- [ ] Generator receives feedback from Retry Controller
- [ ] Second attempt has higher score (0.60 → 0.88)
- [ ] SUCCESS path eventually reached

---

### Test Case TC-8.3: Max Retries Failure (Low Quality)

**Test Input:**
```
email late
```

**Expected Output:**
- **Iteration 1:** Score 0.40 → RETRY (attempt 1/3)
- **Iteration 2:** Score 0.55 → RETRY (attempt 2/3)
- **Iteration 3:** Score 0.70 → FAIL (max retries exhausted)
- **Fail Agent:** Returns error message with retry history
- **Direct Reply (Fail):** Terminal FAIL path

**Expected Metadata:**
- Final Score: 0.70 (below 0.85)
- Retries: 3 (max reached)
- Status: FAIL
- Retry History: [attempt 1 feedback, attempt 2 feedback, attempt 3 feedback]

**Validation Checklist:**
- [ ] Exactly 3 retry attempts (not more)
- [ ] Retry Controller logic prevents 4th retry
- [ ] FAIL Direct Reply node fires (not Success node)
- [ ] Error message includes all 3 retry attempts
- [ ] Workflow terminates cleanly (no infinite loop)

**Critical Validation:**
- **MUST NOT** enter infinite loop (max 3 retries enforced)
- **MUST** route to FAIL path after 3rd retry

---

## 🌐 Pattern #9: API Integration Tests

### Test Case TC-9.1: Success (200 OK)

**Objective:** Validate HTTP Request Node + SUCCESS path routing

**Import Steps:**
1. Open Flowise UI → Agentflows → Add New
2. Click "Load Agentflow"
3. Select `09-api-integration.json`
4. Verify all nodes load (10 nodes)
5. Click "Save Agentflow"

**Configuration:**
- **HTTP Request Node:**
  - Method: GET
  - URL: `https://api.github.com/users/anthropics` (public API, no auth required)
  - Headers: `Accept: application/json`
- **Condition Node:** Configure status code scenarios:
  - Scenario 0 (SUCCESS): `statusCode == 200`
  - Scenario 1 (ERROR): `statusCode >= 500`
  - Scenario 2 (FATAL): `statusCode >= 400 && statusCode < 500`

**Test Input:**
```
Fetch user information for GitHub user 'anthropics'
```

**Expected Output:**
- **Parameter Extractor:** Extracts username → "anthropics"
- **HTTP Request Node:**
  - Sends GET request to https://api.github.com/users/anthropics
  - Receives 200 OK response
  - Stores response body in `{{ $flow.state.api_response }}`
- **Condition Node:** Routes to scenario 0 (SUCCESS)
- **Format Agent:** Parses JSON response, formats user data
- **Direct Reply (Success):** Returns formatted data:
  - Username: anthropics
  - Name: Anthropic
  - Public repos: (count)
  - Followers: (count)
  - Status: SUCCESS (200)

**Validation Checklist:**
- [ ] HTTP Request completes successfully
- [ ] Status code = 200
- [ ] Response body is valid JSON
- [ ] Condition Node routes to SUCCESS (scenario 0)
- [ ] Format Agent parses JSON correctly
- [ ] Success Direct Reply node fires
- [ ] Execution time < 15 seconds

---

### Test Case TC-9.2: Retry on Server Error (5xx)

**Configuration:**
- **HTTP Request Node:**
  - URL: `https://httpstat.us/503` (simulates 503 Service Unavailable)
  - Method: GET

**Test Input:**
```
Test server error handling with retry logic
```

**Expected Output:**
- **Attempt 1:**
  - HTTP Request: Returns 503 error
  - Condition Node: Routes to scenario 1 (ERROR - retryable)
  - Retry Agent: Analyzes error → "Service unavailable, retry with exponential backoff"
  - Loop-back edge: Returns to HTTP Request
  - Wait: 2 seconds (backoff)

- **Attempt 2:**
  - HTTP Request: Returns 503 again
  - Retry Agent: Retry 2/3, wait 4 seconds

- **Attempt 3:**
  - HTTP Request: Returns 503 again
  - Retry Agent: Max retries exhausted → FATAL
  - Error Handler: Returns error summary
  - Direct Reply (Error): Terminal error message

**Expected Metadata:**
- Status: FAILED (max retries)
- HTTP Status: 503
- Retry Count: 3
- Retry History: [2s wait, 4s wait, 8s wait]

**Validation Checklist:**
- [ ] Condition Node routes to ERROR (scenario 1) on 5xx
- [ ] Loop-back edge fires (retry triggered)
- [ ] Exponential backoff delays observed (2s, 4s, 8s)
- [ ] Max 3 retries enforced
- [ ] Error Direct Reply node fires after 3rd retry

---

### Test Case TC-9.3: Fatal Error (4xx)

**Configuration:**
- **HTTP Request Node:**
  - URL: `https://api.github.com/users/THIS_USER_DOES_NOT_EXIST_12345`
  - Method: GET

**Test Input:**
```
Fetch user information for a non-existent GitHub user
```

**Expected Output:**
- **HTTP Request:** Returns 404 Not Found
- **Condition Node:** Routes to scenario 2 (FATAL - non-retryable)
- **Error Handler:** Formats error message:
  - "User not found (404)"
  - "Client error - no retry attempted"
- **Direct Reply (Fatal):** Returns error immediately (no retries)

**Expected Metadata:**
- Status: FATAL
- HTTP Status: 404
- Retry Count: 0 (no retries for 4xx)
- Message: "Client error - request cannot be retried"

**Validation Checklist:**
- [ ] Condition Node routes to FATAL (scenario 2) on 4xx
- [ ] NO loop-back edge triggered (4xx = client error, non-retryable)
- [ ] Retry count = 0
- [ ] Fatal Direct Reply node fires immediately
- [ ] Execution time < 10 seconds (single attempt)

**Critical Validation:**
- **MUST NOT** retry on 4xx errors (waste of API calls)
- **MUST** distinguish between retryable (5xx) and non-retryable (4xx) errors

---

## 🎯 Validation Summary Checklist

After completing all test cases, verify:

### Pattern #7 (Batch Processing)
- [ ] TC-7.1: Basic array (3 items) ✅ PASS
- [ ] TC-7.2: Empty array ✅ PASS
- [ ] TC-7.3: Large array (10 items) ✅ PASS
- [ ] Iteration Node loops correctly for all cases
- [ ] Aggregator combines results properly

### Pattern #8 (Conditional Retry)
- [ ] TC-8.1: Pass first try (score ≥ 0.85) ✅ PASS
- [ ] TC-8.2: Retry success (1-2 retries) ✅ PASS
- [ ] TC-8.3: Max retries fail (3 retries) ✅ PASS
- [ ] Condition Node threshold check works (deterministic)
- [ ] Retry loop-back edge triggers correctly
- [ ] Max retry limit enforced (no infinite loops)

### Pattern #9 (API Integration)
- [ ] TC-9.1: Success (200 OK) ✅ PASS
- [ ] TC-9.2: Retry (5xx errors) ✅ PASS
- [ ] TC-9.3: Fatal (4xx errors) ✅ PASS
- [ ] HTTP Request Node executes correctly
- [ ] Condition Node routes by status code
- [ ] Retry logic with exponential backoff
- [ ] 4xx errors don't trigger retries

---

## 🐛 Common Issues & Troubleshooting

### Issue: Iteration Node doesn't loop
**Symptom:** Processor agent runs only once instead of N times

**Root Cause:** `iterationInput` not set to array variable

**Fix:**
1. Click Iteration Node
2. Check "Array Input" field
3. Ensure it references Planner output: `{{ planner.output.items }}`
4. Verify Planner agent outputs array format: `["item1", "item2", "item3"]`

---

### Issue: Condition Node always takes Else path
**Symptom:** All test cases route to "Else" scenario regardless of input

**Root Cause:** Condition expression syntax error or wrong variable reference

**Fix:**
1. Click Condition Node
2. Check "Conditions" array:
   - Scenario 0: `{{ $flow.state.validation_score }} >= 0.85`
   - Ensure variable exists in flow state
3. Test with explicit values: `0.90 >= 0.85` (should be true)

---

### Issue: Loop-back edge creates infinite loop
**Symptom:** Workflow never terminates, keeps retrying forever

**Root Cause:** Retry counter not incrementing or max check missing

**Fix:**
1. Check Retry Controller agent has:
   - `agentStateUpdates`: `retry.count: {{ $flow.state.retry.count + 1 }}`
2. Verify Condition Agent (Retry Controller) logic includes:
   - "If retry_count >= 3, return FAIL"
   - Don't route back to loop if max retries reached

---

### Issue: HTTP Request Node fails with CORS error
**Symptom:** "CORS policy" error in execution log

**Root Cause:** Flowise backend can't access external API (rare, but possible in some deployments)

**Fix:**
1. Use public APIs without CORS restrictions (e.g., `httpstat.us`, `api.github.com`)
2. Check Flowise is running in server mode (not browser-only)
3. Test with `curl` first to verify API is accessible from server

---

### Issue: Direct Reply node doesn't terminate workflow
**Symptom:** Workflow continues after Direct Reply, agent keeps thinking

**Root Cause:** `hideOutput: true` missing or extra output anchors present

**Fix:**
1. Click Direct Reply node
2. Verify `hideOutput: true` in node data
3. Ensure `outputAnchors: []` (empty array, no output connections)
4. Check no edges originate from Direct Reply node

---

## 📊 Test Execution Report Template

Use this template to document your test results:

```markdown
# AFv2 Patterns Test Execution Report

**Date:** 2025-11-05
**Tester:** [Your Name]
**Flowise Version:** [e.g., v2.1.0]
**Environment:** [Local/Cloud]

## Pattern #7: Batch Processing

| Test Case | Status | Duration | Notes |
|-----------|--------|----------|-------|
| TC-7.1: Basic Array | ✅ PASS | 35s | All 3 items processed correctly |
| TC-7.2: Empty Array | ✅ PASS | 8s | Graceful handling, no errors |
| TC-7.3: Large Array | ✅ PASS | 118s | All 10 items processed |

**Overall:** ✅ PASS (3/3 test cases)

## Pattern #8: Conditional Retry

| Test Case | Status | Duration | Notes |
|-----------|--------|----------|-------|
| TC-8.1: Pass First Try | ✅ PASS | 22s | Score 0.91, no retries |
| TC-8.2: Retry Success | ✅ PASS | 48s | 2 retries, final score 0.87 |
| TC-8.3: Max Retries Fail | ✅ PASS | 71s | 3 retries, FAIL path correctly |

**Overall:** ✅ PASS (3/3 test cases)

## Pattern #9: API Integration

| Test Case | Status | Duration | Notes |
|-----------|--------|----------|-------|
| TC-9.1: Success (200) | ✅ PASS | 12s | GitHub API returned valid data |
| TC-9.2: Retry (5xx) | ✅ PASS | 38s | 3 retries with exponential backoff |
| TC-9.3: Fatal (4xx) | ✅ PASS | 9s | Immediate fail, no retries |

**Overall:** ✅ PASS (3/3 test cases)

## Summary

**Total Test Cases:** 9
**Passed:** 9
**Failed:** 0
**Pass Rate:** 100% ✅

**Issues Found:** None

**Recommendation:** All 3 patterns ready for production use.
```

---

## 🚀 Next Steps After Testing

Once all tests pass:

1. **Production Deployment:**
   - Copy tested patterns to production Flowise instance
   - Configure production API credentials
   - Set up monitoring/logging

2. **Documentation:**
   - Share test results with team
   - Update README.md with any findings
   - Create user guides for each pattern

3. **Phase 3 Planning:**
   - Identify remaining node types to implement (LLM, Tool, Retriever, Custom Function)
   - Prioritize based on user demand
   - Plan next pattern template additions

---

## 📞 Support

**Issues:** https://github.com/context-foundry/issues
**Documentation:** `/extensions/flowise/templates/afv2-patterns/README.md`
**Validation Script:** `/extensions/flowise/validate_workflow.py`

---

**Last Updated:** 2025-11-05
**Version:** 1.0

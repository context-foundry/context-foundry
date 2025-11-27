# Real-World Incremental Build Test

## Test Plan

**Objective:** Validate 30-50% speedup with actual Context Foundry builds

**Test App:** Simple browser-based Snake game

**Test Phases:**
1. Build #1: Baseline (incremental=False) - Full build, no cache
2. Build #2: Similar task (incremental=True) - Should hit Scout cache
3. Measure actual time savings and validate speedup

**Expected Results:**
- Build #1: ~7-12 minutes (baseline)
- Build #2: ~4-7 minutes (with Scout cache hit)
- Speedup: 30-50% faster

**Build Specifications:**

### Build #1 (Baseline - No Incremental)
```
Task: "Build a simple Snake game in JavaScript with HTML5 Canvas. Include player movement with arrow keys, collision detection, score tracking, and game over screen."

Parameters:
- working_directory: "snake-game-baseline"
- incremental: False
- enable_test_loop: True
```

### Build #2 (Incremental Mode)
```
Task: "Build a simple Snake game in JavaScript with HTML5 Canvas. Include player movement with arrow keys, collision detection, scoring system, and game over screen."

Parameters:
- working_directory: "snake-game-incremental"
- incremental: True
- enable_test_loop: True
```

Note: Tasks are intentionally similar (96% overlap) to test Scout cache hit rate.

## Execution

Run these builds sequentially and track timing for each phase.

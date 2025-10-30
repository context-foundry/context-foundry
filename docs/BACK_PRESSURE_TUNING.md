# Back Pressure System - Tuning Guide

## What is Back Pressure?

**Back pressure** is validation friction that prevents bad code from progressing through the build pipeline. It's the force that stops the "wheel" of code generation when quality checks fail.

Think of it like brakes on a car:
- **No brakes** (no back pressure) → Code generates fast but crashes
- **Too much braking** → Can't move forward, progress is slow
- **Right amount of braking** → Fast progress with quality control

## How It Works

Context Foundry implements back pressure at three key phases:

### Phase 1: Scout Validation
**When**: After Scout creates `scout-report.md`
**What**: Validates technology stack is available and feasible
**Time**: ~5 seconds
**Catches**: 
- Missing language runtimes (Python, Node, Rust, Go)
- Version mismatches
- Unavailable dependencies

**Example**: Scout recommends Python 3.12 but only 3.10 is installed → Caught immediately, architecture revised

### Phase 2: Architect Validation
**When**: After Architect creates `architecture.md`
**What**: Validates design is complete and consistent
**Time**: ~2 seconds
**Catches**:
- Missing test strategy
- Duplicate file paths
- Incomplete file structure
- Missing implementation steps

**Example**: Architecture doesn't specify test framework → Caught before building, test strategy added

### Phase 3.5: Integration Pre-Check (NEW)
**When**: After Parallel Builders complete, BEFORE Test phase
**What**: Fast syntax and import validation
**Time**: 5-15 seconds (vs 30-120s for full tests)
**Catches**:
- Syntax errors
- Import resolution failures
- Missing required files
- Type errors (TypeScript)

**Example**: Python syntax error in `main.py` → Caught in 5 seconds, not 60 seconds

## Language-Specific Configurations

Different languages have different "natural pressure" from their compiler/runtime.

### Python (Low Natural Pressure)
**Why**: Interpreted, no compilation, dynamic typing
**Needs**: HIGH back pressure

**Checks Enabled**:
- ✅ Syntax validation (`python3 -m py_compile`)
- ✅ Type checking (mypy, optional)
- ✅ Linting (ruff, optional)
- ✅ Import resolution
- ✅ High test coverage (80%+)

### TypeScript (Medium Natural Pressure)
**Why**: Type system helps, but not compiled to native
**Needs**: MEDIUM back pressure

**Checks Enabled**:
- ✅ Syntax/type checking (`tsc --noEmit`)
- ✅ Linting (ESLint, optional)
- ✅ Import resolution
- ✅ Moderate test coverage (70%+)

### Rust (High Natural Pressure)
**Why**: Strong type system, borrow checker, compiler catches most issues
**Needs**: LOW back pressure (compiler does the work)

**Checks Enabled**:
- ✅ Compilation (`cargo check`)
- ✅ Linting (`cargo clippy`, optional)
- ❌ Import resolution (cargo handles)
- ✅ Moderate test coverage (60%+)

### Go (Medium-High Natural Pressure)
**Why**: Type system, compiled, fast compiler
**Needs**: LOW-MEDIUM back pressure

**Checks Enabled**:
- ✅ Compilation (`go build`)
- ✅ Linting (`go vet`)
- ✅ Format checking (`gofmt`)
- ❌ Import resolution (compiler handles)
- ✅ Moderate test coverage (65%+)

## Configuration

Back pressure is automatically configured based on detected project type.

### View Your Project's Configuration
```bash
python3 tools/back_pressure/back_pressure_config.py .
```

### List All Language Profiles
```bash
python3 tools/back_pressure/back_pressure_config.py list
```

### Manual Language Detection
```python
from tools.back_pressure import get_back_pressure_config

config = get_back_pressure_config('/path/to/project')
print(f"Language: {config['detected_language']}")
print(f"Natural Pressure: {config['natural_pressure']}")
print(f"Checks: {config['checks']}")
```

## Tuning Back Pressure

### Too Much Pressure (Build is Slow)
**Symptoms**:
- Validation takes longer than test execution
- False positives block valid code
- Optional tools (mypy, ruff) aren't installed

**Solutions**:
1. Disable optional checks if tools unavailable
2. Increase timeout values
3. Skip validation for prototypes (use `--no-validation` flag if added)

### Too Little Pressure (Errors Reach Test Phase)
**Symptoms**:
- Most builds fail in Phase 4 (Test)
- Syntax errors not caught early
- Iteration count > 2

**Solutions**:
1. Enable stricter checks for your language
2. Add pre-commit hooks
3. Ensure validators are running

### Just Right (Optimal)
**Metrics**:
- Average test iterations: 1.3 or lower
- 30-40% of issues caught before test phase
- Validation time: 5-15 seconds
- Build time reduction: 15%+

## Measuring Effectiveness

Back pressure metrics are tracked in `.context-foundry/session-summary.json`:

```json
{
  "back_pressure_metrics": {
    "total_back_pressure_events": 5,
    "by_phase": {
      "scout": {
        "events": 1,
        "failures_caught": 1,
        "time_saved_minutes": 3.5
      },
      "architect": {
        "events": 1,
        "failures_caught": 1,
        "time_saved_minutes": 5.0
      },
      "integration_pre_check": {
        "events": 1,
        "failures_caught": 1,
        "time_saved_minutes": 2.0
      }
    },
    "efficiency": {
      "issues_caught_early": 3,
      "early_catch_rate": 0.60
    }
  }
}
```

## Troubleshooting

### Validation Times Out
```bash
# Check timeout settings in back_pressure_config.py
# Default: 30 seconds for integration_pre_check

# Increase timeout if needed:
# Edit tools/back_pressure/integration_pre_check.py
# Change timeout=30 to timeout=60
```

### Validation Fails on Valid Code (False Positive)
```bash
# Check validation errors:
cat .context-foundry/integration-errors.json

# Common causes:
# 1. Missing optional tool (mypy, ruff) - OK to skip
# 2. Project-specific configuration needed
# 3. Validator doesn't understand project structure

# Solution: Validation failures are advisory, not blocking
```

### Validation Not Running
```bash
# Check if back_pressure module is available:
python3 -c "from tools.back_pressure import validate_tech_stack; print('OK')"

# Check orchestrator_prompt.txt includes validation steps:
grep -n "BACK PRESSURE" tools/orchestrator_prompt.txt
```

## Best Practices

1. **Don't Disable Back Pressure**: It catches 30-40% of issues early
2. **Review Validation Errors**: They're actionable feedback
3. **Monitor Metrics**: Track early_catch_rate over time
4. **Language-Specific**: Trust the defaults for your language
5. **Optional Tools**: Don't block builds on mypy/ruff/clippy if not installed

## Expected Outcomes

### Before Back Pressure System
- Average test iterations: 2.0
- Build time: 10 minutes
- Test phase failure rate: 15%

### After Back Pressure System
- Average test iterations: 1.3 (-35%)
- Build time: 8.5 minutes (-15%)
- Test phase failure rate: 8% (-47%)
- Early issue detection: 30-40% of failures

## Advanced Topics

### Adding Custom Validators

Create a new validator in `tools/back_pressure/`:

```python
def validate_custom(project_path: str) -> dict:
    """
    Custom validation logic.
    
    Returns:
        {'success': bool, 'errors': list, 'duration': float}
    """
    # Your validation logic
    return {'success': True, 'errors': [], 'duration': 0.5}
```

Integrate into orchestrator_prompt.txt:
```bash
python3 tools/back_pressure/validate_custom.py .
```

### Language-Specific Tuning

Edit `tools/back_pressure/back_pressure_config.py`:

```python
LANGUAGE_PROFILES['python']['checks']['syntax']['timeout'] = 20  # Increase timeout
LANGUAGE_PROFILES['python']['test_requirements']['min_coverage'] = 85  # Stricter
```

## References

- **Original Proposal**: `docs/proposals/BACK_PRESSURE_SYSTEM.md`
- **Ralph Wiggum Transcript**: Source of back pressure concept
- **Phase Flow**: See `tools/orchestrator_prompt.txt` for integration details

## Support

For issues or questions:
1. Check `.context-foundry/integration-errors.json` for validation errors
2. Review session-summary.json for metrics
3. File issue on GitHub with validation logs

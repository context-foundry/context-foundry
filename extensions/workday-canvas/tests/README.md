# Canvas Kit Extension Tests

## Status: Placeholder

This directory is reserved for future pytest-based test suites for the Canvas Kit extension.

## Current Testing

The main test suite currently lives at: `scripts/test_canvas_kit_extension.py`

Run tests:
```bash
python3 scripts/test_canvas_kit_extension.py
```

This script tests:
- ✅ Extension structure (files exist)
- ✅ Pattern file validity (JSON, required sections)
- ✅ Detector module import
- ✅ Prompt keyword detection

## Planned Tests

Future pytest tests to add here:

### Unit Tests
- `test_detector.py` - Unit tests for detector.py functions
- `test_extensions_loader.py` - Pattern loading tests
- `test_patterns.py` - Pattern file schema validation

### Integration Tests
- `test_project_detection.py` - Full project detection workflow
- `test_pattern_loading.py` - Extension loading in CF context

### Example Tests
- `test_coi_example.py` - Validate COI example structure
- `test_workflow_patterns.py` - Workflow pattern validation

## Contributing

To add pytest tests:

1. Install pytest: `pip install pytest`
2. Create test file: `tests/test_*.py`
3. Follow pytest conventions
4. Run: `pytest extensions/workday-canvas/tests/`

## Migration Plan

Eventually migrate tests from `scripts/test_canvas_kit_extension.py` to this directory using pytest framework for better test organization and CI/CD integration.

# Testing Guide for Context Foundry

## S3 Pattern Client Tests

The S3 pattern client has comprehensive test coverage that works **with or without** AWS dependencies.

**Test Suite Summary**: 21 tests total
- **20 runnable tests**: 9 work without AWS deps, 20 with AWS deps
- **1 integration test**: Marked `@pytest.mark.integration`, always skipped (requires live AWS credentials)

### Quick Start

**Option 1: Test without AWS dependencies (offline behavior)**
```bash
# Uses only requirements.txt (no boto3/moto needed)
pytest tests/test_s3_client.py -v

# Expected: 9 passed, 12 skipped
# Skipped: 11 tests requiring moto + 1 integration test
```

**Option 2: Test with full AWS mocking**
```bash
# Install AWS dependencies first
pip install -r requirements-aws.txt

# Run all tests
pytest tests/test_s3_client.py -v

# Expected: 20 passed, 1 skipped
# Skipped: 1 integration test (requires live AWS credentials)
```

---

## Test Categories

### Tests That Work Without AWS Dependencies (9 tests)

These tests verify offline behavior and graceful degradation:

1. **S3 Client Initialization**
   - `test_client_disabled_without_boto3` - Client gracefully handles missing boto3

2. **S3 Disabled Behavior** (3 tests)
   - `test_upload_fails_gracefully_without_boto3` - Upload returns error when boto3 unavailable
   - `test_download_fallback_to_cache_without_boto3` - Download falls back to cache
   - `test_list_fails_gracefully_without_boto3` - List returns error when boto3 unavailable

3. **Cached Pattern Reading** (2 tests)
   - `test_get_cached_pattern_success` - Read from local cache
   - `test_get_cached_pattern_not_found` - Cache miss handling

4. **Offline Fallback Tests** (3 tests)
   - `test_upload_pattern_s3_disabled` - Upload fails gracefully
   - `test_download_pattern_offline_fallback` - Download uses cache
   - `test_list_community_patterns_s3_disabled` - List fails gracefully

### Tests That Require AWS Dependencies (11 tests)

These tests require `requirements-aws.txt` (boto3 + moto):

1. **S3 Client Initialization** (2 tests)
   - `test_client_enabled_with_boto3` - Client initializes with boto3
   - `test_client_configuration` - Client configuration verified

2. **Upload Pattern Tests** (4 tests)
   - `test_upload_pattern_success` - Successful upload
   - `test_upload_pattern_file_not_found` - Error when file missing
   - `test_upload_pattern_conflict_detection` - Detects newer S3 versions
   - `test_upload_pattern_force_override` - Force upload works

3. **Download Pattern Tests** (2 tests)
   - `test_download_pattern_success` - Successful download
   - `test_download_pattern_not_in_s3` - Error when pattern not in S3

4. **List Patterns Tests** (2 tests)
   - `test_list_community_patterns_success` - List all patterns
   - `test_list_community_patterns_filtered` - Filter by type

5. **Sync Metadata Test** (1 test)
   - `test_sync_metadata_saved_after_upload` - Metadata persisted correctly

### Integration Test (1 test - always skipped)

This test is marked `@pytest.mark.integration` and requires live AWS credentials:

1. **Real S3 Upload Test** (1 test)
   - `test_real_s3_upload` - Tests real S3 upload (skipped by default)
   - To run: `pytest tests/test_s3_client.py -v -m integration` (requires AWS credentials)

---

## Installation

### Minimal Installation (9 tests)
```bash
pip install -r requirements.txt
pytest tests/test_s3_client.py -v
```

### Full Installation (20 tests)
```bash
pip install -r requirements.txt
pip install -r requirements-aws.txt
pytest tests/test_s3_client.py -v
```

---

## CI/CD Integration

### GitHub Actions Example

**Option 1: Test without AWS dependencies (fast)**
```yaml
- name: Install dependencies
  run: pip install -r requirements.txt

- name: Run offline tests
  run: pytest tests/test_s3_client.py -v
  # Expected: 9 passed, 12 skipped
```

**Option 2: Test with full coverage (recommended)**
```yaml
- name: Install dependencies
  run: |
    pip install -r requirements.txt
    pip install -r requirements-aws.txt

- name: Run all tests
  run: pytest tests/test_s3_client.py -v
  # Expected: 20 passed, 1 skipped
```

---

## Test Coverage Report

```bash
# Install coverage tool
pip install pytest-cov

# Run with coverage
pytest tests/test_s3_client.py --cov=context_foundry.storage --cov-report=term-missing

# Expected coverage: >90% for s3_client.py
```

---

## Troubleshooting

### "12 skipped tests" when running without moto

This is **expected behavior**. Without `requirements-aws.txt` installed:
- 9 tests verify offline behavior (PASSED)
- 11 tests require moto for S3 mocking (SKIPPED)
- 1 integration test always skipped (SKIPPED)
- **Total: 9 passed, 12 skipped**

To run all runnable tests:
```bash
pip install -r requirements-aws.txt
pytest tests/test_s3_client.py -v
# Expected: 20 passed, 1 skipped (integration test)
```

### "1 skipped test" when running with moto

This is **expected behavior**. With `requirements-aws.txt` installed:
- 20 runnable tests execute successfully (PASSED)
- 1 integration test remains skipped unless you use `-m integration` flag (SKIPPED)
- **Total: 20 passed, 1 skipped**

The integration test (`test_real_s3_upload`) is marked `@pytest.mark.integration` and requires live AWS credentials. It's intentionally skipped in normal test runs to avoid requiring production AWS access.

### "moto not available" error

Install AWS dependencies:
```bash
pip install -r requirements-aws.txt
```

### Tests fail with "NoCredentialsError"

This should **not** happen - tests use moto to mock S3, no real credentials needed.

If you see this error, verify moto is installed:
```bash
pip show moto
```

---

## Writing New Tests

### Template for Tests That Work Without AWS

```python
def test_offline_behavior(self, monkeypatch, temp_patterns_dir):
    """Test works without boto3/moto installed"""
    # Mock boto3 as unavailable
    monkeypatch.setattr("context_foundry.storage.s3_client.BOTO3_AVAILABLE", False)
    monkeypatch.setattr(S3PatternClient, "CACHE_DIR", temp_patterns_dir)

    client = S3PatternClient()
    result = client.some_method()

    assert result["success"] is False  # or True for cache reads
```

### Template for Tests That Require AWS

```python
def test_s3_integration(self, client_with_mock_s3, temp_patterns_dir):
    """Test requires moto for S3 mocking"""
    # client_with_mock_s3 fixture automatically skips if moto unavailable

    result = client_with_mock_s3.upload_pattern("test")

    assert result["success"] is True
```

---

## Best Practices

1. **Write offline tests first** - Verify graceful degradation
2. **Use descriptive test names** - Include "(works without moto)" or "(requires moto)"
3. **Test both success and failure paths** - Error handling is critical
4. **Mock at the right level** - Use `monkeypatch` for imports, `client_with_mock_s3` for S3
5. **Keep tests fast** - Offline tests should run in <100ms each

---

## Related Documentation

- [AWS Migration Guide](AWS_MIGRATION.md) - Overall AWS integration
- [pytest documentation](https://docs.pytest.org/) - Test framework
- [moto documentation](https://docs.getmoto.org/) - AWS mocking library

---

*Last Updated: 2025-11-15*
*Test Suite: 21 tests total (20 runnable: 9 work without AWS deps, 20 with AWS deps; 1 integration test always skipped)*

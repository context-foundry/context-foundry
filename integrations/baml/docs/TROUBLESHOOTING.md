# Troubleshooting

Common issues and solutions for BAML + Anthropic integration.

## Installation Issues

### BAML CLI not found
**Error**: `baml-cli: command not found`

**Solution**:
```bash
npm install -g @boundaryml/baml
baml-cli --version
```

### Python dependency conflicts
**Error**: `pip install fails with dependency conflicts`

**Solution**:
```bash
# Use virtual environment
python3 -m venv venv
source venv/bin/activate
pip install --upgrade pip
pip install -r requirements.txt
```

## Configuration Issues

### API key errors
**Error**: `Invalid or missing ANTHROPIC_API_KEY`

**Solution**:
1. Check .env file exists in python/ or typescript/ directory
2. Verify API key is not the template value
3. Ensure no extra spaces in .env file
4. Check key has correct permissions at console.anthropic.com

### BAML client not generated
**Error**: `ModuleNotFoundError: No module named 'baml_client'`

**Solution**:
```bash
cd /path/to/integrations/baml
baml-cli generate

# Verify files created:
# - python/baml_client/__init__.py
# - typescript/baml_client/index.ts
```

## Runtime Issues

### Type validation errors
**Error**: `BAMLValidationError: Type mismatch`

**Solution**:
- Check BAML function return types match actual API responses
- Regenerate client after modifying types.baml
- Verify API response structure hasn't changed

### Timeout errors
**Error**: `Request timeout after 30 seconds`

**Solution**:
- Increase timeout in client configuration
- Check network connectivity
- Verify API is not rate limiting
- Try simpler/shorter prompts

### Rate limit errors
**Error**: `429: Too Many Requests`

**Solution**:
- Implement exponential backoff (included in utils)
- Reduce request frequency
- Check API quota at console.anthropic.com
- Consider upgrading API plan

## Development Issues

### Hot reload not working
**Issue**: Changes to .baml files not reflected

**Solution**:
```bash
baml-cli generate
# Restart development server
```

### Import errors
**Python**: `ImportError: cannot import name ...`

**Solution**:
- Check virtual environment is activated
- Reinstall dependencies: `pip install -r requirements.txt`
- Verify Python path: `which python`

**TypeScript**: `Cannot find module ...`

**Solution**:
- Run `npm install` again
- Check tsconfig.json paths
- Verify file extensions (.js for imports in ESM)

## Testing Issues

### Integration tests failing
**Error**: Tests fail but examples work

**Solution**:
- Set `RUN_INTEGRATION_TESTS=true` in .env
- Ensure API key is valid
- Check test file paths are correct
- Review test assertions

### Mock tests not working
**Issue**: Mocked responses not being used

**Solution**:
- Verify mock setup in conftest.py (Python) or test setup (TypeScript)
- Check mock is applied before function call
- Ensure not calling real API in unit tests

## Performance Issues

### Slow responses
**Issue**: API calls taking > 10 seconds

**Solution**:
- Simplify prompts
- Reduce document size
- Check network latency
- Consider caching results
- Use streaming for long operations

### High memory usage
**Issue**: Memory consumption increasing over time

**Solution**:
- Process large files in chunks
- Clear caches periodically
- Check for memory leaks
- Use generators/streams for large datasets

## Getting Help

If you can't resolve your issue:

1. Check [BAML Documentation](https://docs.boundaryml.com/)
2. Review [Anthropic API Docs](https://docs.anthropic.com/)
3. Search [Context Foundry Issues](https://github.com/snedea/context-foundry/issues)
4. Create a new issue with:
   - Error message
   - Steps to reproduce
   - Environment details (OS, Python/Node version)
   - Relevant configuration

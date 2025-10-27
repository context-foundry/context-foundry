# Best Practices

Production deployment guidelines for BAML + Anthropic Agent Skills.

## Security

### API Key Management
- **Never commit API keys** to version control
- Use environment variables or secret managers
- Rotate keys regularly
- Use different keys for dev/staging/prod

### Input Validation
- Validate file paths before processing
- Sanitize user-provided prompts
- Set file size limits for document processing

## Performance

### Rate Limiting
- Implement rate limiting for API calls
- Use exponential backoff for retries
- Cache results when appropriate

### Progressive Disclosure
- Load skills only when needed
- Start with lightweight analysis
- Add complexity only if required

### Error Handling
- Use try-catch blocks for all API calls
- Log errors with context
- Provide user-friendly error messages
- Implement circuit breakers for repeated failures

## Type Safety

### BAML Types
- Define clear input/output types in types.baml
- Use BAML's validation features
- Regenerate client after schema changes

### Runtime Validation
- Validate API responses match expected schema
- Use Pydantic (Python) or Zod (TypeScript) for runtime checks

## Monitoring

### Logging
- Log all API calls with timestamps
- Track skill invocations
- Monitor response times
- Log error rates

### Metrics
- Track API usage and costs
- Monitor skill loading efficiency
- Measure confidence scores
- Alert on degraded performance

## Testing

### Test Coverage
- Unit tests with mocked responses
- Integration tests with real API (gated)
- E2E tests for critical workflows

### CI/CD
- Run tests on every commit
- Gate deploys on passing tests
- Use environment-specific configurations

## Cost Optimization

### Token Usage
- Use shorter prompts when possible
- Implement caching for repeated queries
- Choose appropriate model sizes
- Monitor token consumption

### Progressive Disclosure Benefits
- Reduces token usage by 40-60%
- Improves response times
- Lowers API costs
- Simplifies debugging

## Deployment

### Environment Configuration
- Use different API keys per environment
- Configure logging levels appropriately
- Set appropriate timeouts
- Enable monitoring and alerts

### Scaling
- Use connection pooling for concurrent requests
- Implement request queuing
- Consider async/await patterns
- Monitor memory usage

## Maintenance

### Updates
- Keep BAML CLI updated
- Update SDK versions regularly
- Review Anthropic API changelog
- Regenerate clients after updates

### Documentation
- Keep examples up to date
- Document custom skills
- Maintain changelog
- Update troubleshooting guides

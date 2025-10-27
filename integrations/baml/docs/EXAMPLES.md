# Examples

Detailed walkthroughs of BAML + Anthropic Agent Skills examples.

## Document Processing

**Use Case**: Analyze PDFs and DOCX files with structured extraction.

### Python

```python
from examples.document_processing import analyze_document

result = await analyze_document(
    file_path="report.pdf",
    questions=["What are the key findings?", "What's the budget?"]
)

print(f"Summary: {result['summary']}")
print(f"Findings: {result['key_findings']}")
print(f"Confidence: {result['confidence_score']}")
```

### TypeScript

```typescript
import { analyzeDocument } from './examples/documentProcessing';

const result = await analyzeDocument(
  'report.pdf',
  ['What are the key findings?', 'What\'s the budget?']
);

console.log(`Summary: ${result.summary}`);
console.log(`Findings: ${result.key_findings}`);
```

## Data Analysis

**Use Case**: Analyze datasets for trends, anomalies, and insights.

### Python

```python
from examples.data_analysis import analyze_dataset

insights = await analyze_dataset(
    data_source="sales_data.csv",
    analysis_type="trends"
)

print(f"Trends: {insights['trends']}")
print(f"Recommendations: {insights['recommendations']}")
```

## Progressive Skill Loading

**Use Case**: Load skills only when needed (progressive disclosure pattern).

### Python

```python
from examples.custom_skill import progressive_skill_loading

result = await progressive_skill_loading(
    task="Analyze this PDF",
    available_skills=["pdf_reader", "docx_parser", "calculator"]
)

print(f"Loaded: {result['loaded_skills']}")  # Only ['pdf_reader']
print(f"Skipped: {result['skipped_skills']}")  # Others not needed
```

## Error Handling

All functions include retry logic with exponential backoff:

```python
from shared.utils import async_retry

@async_retry(max_retries=3, initial_delay=1.0, backoff_factor=2.0)
async def my_analysis():
    # API call with automatic retries
    pass
```

## Streaming Support

For long-running analysis:

```python
async for chunk in analyze_document_streaming(file_path, questions):
    print(f"Partial result: {chunk}")
```

## Next Steps

- Review [Best Practices](BEST_PRACTICES.md) for production deployment
- Check [Troubleshooting](TROUBLESHOOTING.md) for common issues

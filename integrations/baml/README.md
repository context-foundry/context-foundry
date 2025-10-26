# BAML + Anthropic Agent Skills Integration

Production-ready integration example demonstrating **type-safe prompting** with BAML and **progressive skill disclosure** with Anthropic's Agent Skills system.

![Hero Image](docs/hero.png)

## Overview

This integration showcases how to combine:
- **[BAML](https://github.com/BoundaryML/baml)**: Type-safe prompting framework with compile-time validation
- **[Anthropic Agent Skills](https://www.anthropic.com/engineering/equipping-agents-for-the-real-world-with-agent-skills)**: Progressive disclosure pattern for complex AI capabilities
- **Dual Language Support**: Production-ready Python and TypeScript implementations

## Features

✅ **Type-Safe Prompts**: BAML provides compile-time type checking for LLM inputs/outputs
✅ **Progressive Skill Disclosure**: Skills loaded only when needed
✅ **Production Ready**: Error handling, retry logic, logging, streaming support
✅ **Dual Implementation**: Python and TypeScript with feature parity
✅ **Comprehensive Examples**: Document processing, data analysis, custom skills
✅ **Full Test Coverage**: Unit, integration, and E2E tests

## Quick Start

### Prerequisites

- Python 3.10+ OR Node.js 18+
- Anthropic API key ([get one here](https://console.anthropic.com/))
- BAML CLI: `npm install -g @boundaryml/baml`

### Python Setup (5 minutes)

```bash
cd python/

# Install dependencies
pip install -r requirements.txt

# Configure API key
cp .env.template .env
# Edit .env and add your ANTHROPIC_API_KEY

# Generate BAML client
cd .. && baml-cli generate && cd python/

# Run example
python examples/document_processing.py
```

### TypeScript Setup (5 minutes)

```bash
cd typescript/

# Install dependencies
npm install

# Configure API key
cp .env.template .env
# Edit .env and add your ANTHROPIC_API_KEY

# Generate BAML client
cd .. && baml-cli generate && cd typescript/

# Run example
npm run example:document
```

## Example Usage

### Python: Document Analysis

```python
from examples.document_processing import analyze_document

# Analyze a PDF with type-safe prompts
result = await analyze_document(
    file_path="report.pdf",
    questions=["What are the key findings?", "What's the budget?"]
)

# Type-safe results (validated by BAML)
print(f"Summary: {result.summary}")
print(f"Findings: {result.key_findings}")
print(f"Confidence: {result.confidence_score}")
```

### TypeScript: Data Analysis

```typescript
import { analyzeDataset } from './examples/dataAnalysis';

// Analyze data with progressive skill disclosure
const insights = await analyzeDataset(
  'sales_data.csv',
  'quarterly_trends'
);

// Strongly typed results
console.log(`Trends: ${insights.trends}`);
console.log(`Anomalies: ${insights.anomalies}`);
```

## Project Structure

```
integrations/baml/
├── baml_src/              # BAML configuration (language-agnostic)
│   ├── clients.baml       # Anthropic client setup
│   ├── functions.baml     # Type-safe function definitions
│   └── types.baml         # Custom types
│
├── python/                # Python implementation
│   ├── examples/          # Document processing, data analysis, custom skills
│   ├── shared/            # Config and utilities
│   └── tests/             # Comprehensive test suite
│
├── typescript/            # TypeScript implementation
│   ├── src/examples/      # Document processing, data analysis, custom skills
│   ├── src/shared/        # Config and utilities
│   └── tests/             # Comprehensive test suite
│
├── test_data/             # Sample files for testing
└── docs/                  # Detailed documentation
```

## Documentation

- **[Setup Guide](docs/SETUP.md)**: Detailed installation and configuration
- **[Examples](docs/EXAMPLES.md)**: Walkthrough of all examples
- **[Best Practices](docs/BEST_PRACTICES.md)**: Production deployment tips
- **[Troubleshooting](docs/TROUBLESHOOTING.md)**: Common issues and solutions

## Key Concepts

### Type-Safe Prompts with BAML

BAML provides **compile-time validation** for your prompts and LLM outputs:

```baml
// Define function in BAML
function AnalyzeDocument(file_path: string, questions: string[]) -> DocumentAnalysis {
  client AnthropicClient
  prompt #"Analyze document at {{ file_path }}..."#
}

// Generated client is fully typed
const result: DocumentAnalysis = await b.AnalyzeDocument({...});
```

### Progressive Skill Disclosure

Skills are introduced **only when the task requires them**:

```python
# Agent analyzes task
task_type = await analyze_task_type(user_request)

# Load only necessary skills
if task_type == "document_analysis":
    skills = ["pdf_reader", "docx_parser"]
elif task_type == "data_analysis":
    skills = ["data_processor"]

# Execute with appropriate skills
result = await execute_with_skills(task, skills)
```

## Testing

### Python Tests

```bash
cd python/

# Unit tests (mocked)
pytest tests/ -v

# Integration tests (real API)
export RUN_INTEGRATION_TESTS=true
pytest tests/test_integration.py -v
```

### TypeScript Tests

```bash
cd typescript/

# Unit tests (mocked)
npm test

# Integration tests (real API)
export RUN_INTEGRATION_TESTS=true
npm run test:integration
```

## Integration with Context Foundry

This integration is part of [Context Foundry](../../README.md), an autonomous AI development system. It demonstrates:

- Type-safe agent development patterns
- Production-ready error handling and retry logic
- Dual-language implementation strategies
- Comprehensive testing approaches

## Contributing

See Context Foundry's [Contributing Guide](../../CONTRIBUTING.md) for details.

## License

MIT License - see Context Foundry's [LICENSE](../../LICENSE) file.

## Credits

- **BAML Framework**: [BoundaryML](https://github.com/BoundaryML/baml)
- **Anthropic Agent Skills**: [Anthropic](https://www.anthropic.com/engineering/equipping-agents-for-the-real-world-with-agent-skills)

---

🤖 **Built autonomously by [Context Foundry](https://github.com/snedea/context-foundry)**

Co-Authored-By: Context Foundry <noreply@contextfoundry.dev>

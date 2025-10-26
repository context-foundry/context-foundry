# BAML + Agent Skills Integration (MCP-Only, FREE!)

**The TRUE Context Foundry Way**: Type-safe Agent Skills via Meta-MCP delegation - **NO API costs, NO API keys, UNLIMITED usage!**

![Hero Image](docs/hero.png)

## 🚀 The Meta-MCP Innovation

This integration showcases Context Foundry's **Meta-MCP pattern** applied to BAML + Agent Skills:

Instead of making **paid API calls** to Anthropic or OpenAI, we **spawn Claude instances** via MCP delegation that run on your Claude Code subscription!

## Architecture

```
Traditional Approach (COSTS MONEY):
User → BAML → Direct API Call → Anthropic/OpenAI → Pay per token 💸

Context Foundry Approach (FREE!):
User → BAML Schema → MCP Delegation → Spawn Claude → Agent Skills → $0 🎉
```

## 💰 Cost Comparison

| Approach | Cost | API Keys | Agent Skills | Usage Limit |
|----------|------|----------|--------------|-------------|
| **Direct API** | $3-15/1M tokens | Required | Yes | Pay-per-use |
| **MCP Delegation** | **$0** | **None!** | **Yes** | **Unlimited!** |

**Example Savings:**
- Process 100 PDF documents: **Direct API: $150** → **MCP: $0** = **100% savings!**
- Unlimited document processing on your subscription!

## Features

✅ **FREE & UNLIMITED**: Runs on Claude Code subscription
✅ **NO API KEYS**: Authentication inherited automatically
✅ **AGENT SKILLS**: Full PDF/DOCX/data processing access
✅ **TYPE-SAFE**: BAML schemas for validation (not API calls)
✅ **FRESH CONTEXT**: Each spawn gets 200K token window
✅ **PRODUCTION READY**: Error handling, retry logic, streaming
✅ **TRUE META-MCP**: Uses Context Foundry's core innovation

## Quick Start

### Prerequisites

- **Claude Code subscription** (that's it!)
- Python 3.10+ (for examples)
- **NO API KEYS NEEDED** - authentication inherited from Claude Code

### Python Setup (2 minutes)

```bash
cd python/

# Install dependencies
pip install -r requirements.txt

# NO API KEY CONFIGURATION NEEDED!
# Authentication is inherited from Claude Code

# Run MCP delegation example (FREE, unlimited Agent Skills)
python examples/mcp_delegation.py
```

**That's it!** No API keys to manage, no costs to worry about. Everything runs on your Claude Code subscription.

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

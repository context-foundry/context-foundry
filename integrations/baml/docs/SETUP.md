# Setup Guide

Detailed setup instructions for BAML + Anthropic Agent Skills integration.

## Prerequisites

### Required
- **Python 3.10+** OR **Node.js 18+**
- **Anthropic API Key**: Get one at [console.anthropic.com](https://console.anthropic.com/)
- **BAML CLI**: Install with `npm install -g @boundaryml/baml`

### Optional
- **Git**: For cloning Context Foundry
- **VS Code**: With BAML extension for .baml file editing

## Installation

### Python Setup

```bash
cd python/

# Create virtual environment (recommended)
python3 -m venv venv
source venv/bin/activate  # On Windows: venv\Scripts\activate

# Install dependencies
pip install -r requirements.txt

# Configure environment
cp .env.template .env
# Edit .env and add your ANTHROPIC_API_KEY
```

### TypeScript Setup

```bash
cd typescript/

# Install dependencies
npm install

# Configure environment
cp .env.template .env
# Edit .env and add your ANTHROPIC_API_KEY
```

## BAML Client Generation

**CRITICAL STEP**: Generate the BAML client before running examples.

```bash
# From integrations/baml/ directory
baml-cli generate

# This generates:
# - python/baml_client/__init__.py
# - typescript/baml_client/index.ts
```

## Verification

### Python

```bash
cd python/
python examples/document_processing.py
```

Expected output: Document analysis results (with placeholder data initially).

### TypeScript

```bash
cd typescript/
npm run example:document
```

Expected output: Document analysis results (with placeholder data initially).

## Troubleshooting

### "ANTHROPIC_API_KEY not found"
- Ensure .env file exists in python/ or typescript/ directory
- Verify API key is correctly set (not the template value)

### "baml-cli command not found"
- Install BAML CLI: `npm install -g @boundaryml/baml`
- Check installation: `baml-cli --version`

### "Module not found" errors
- Python: Ensure virtual environment is activated
- TypeScript: Run `npm install` again
- Verify you're in the correct directory

## Next Steps

Once setup is complete:
1. Review [Examples](EXAMPLES.md) for usage patterns
2. Read [Best Practices](BEST_PRACTICES.md) for production tips
3. Run tests to verify everything works

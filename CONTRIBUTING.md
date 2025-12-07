# Contributing to Context Foundry

Thanks for your interest in contributing to Context Foundry!

## Getting Started

### Prerequisites

- Python 3.9+
- Node.js 18+
- Rust (for desktop app)
- Claude Code CLI

### Setup

```bash
# Clone the repo
git clone https://github.com/context-foundry/context-foundry.git
cd context-foundry

# Create Python virtual environment
python3 -m venv .venv
source .venv/bin/activate

# Install Python dependencies
pip install -r requirements.txt

# Install dashboard dependencies
cd tools/dashboard && npm install && cd ../..

# Start the daemon
./tools/cfd start
```

## Development

### Project Structure

```
context-foundry/
├── context_foundry/daemon/  # Python daemon (HTTP API, job management)
├── tools/dashboard/         # React dashboard frontend
├── apps/context-foundry-desktop/  # Tauri desktop app
├── extensions/              # Domain-specific extensions
└── docs/                    # Documentation
```

### Running Tests

```bash
# Python tests
pytest context_foundry/daemon/tests/ -v

# Dashboard type checking
cd tools/dashboard && npx tsc --noEmit
```

### Code Style

- Python: We use `ruff` for linting and formatting
- TypeScript: Standard prettier/eslint config
- Commits: Use conventional commits (feat:, fix:, docs:, etc.)

## Pull Requests

1. Fork the repository
2. Create a feature branch (`git checkout -b feat/my-feature`)
3. Make your changes
4. Run tests to ensure nothing is broken
5. Commit with a descriptive message
6. Push and open a PR

## Reporting Issues

Please use GitHub Issues for bug reports and feature requests. Include:

- Steps to reproduce (for bugs)
- Expected vs actual behavior
- System info (OS, Python version, etc.)

## Code of Conduct

Be respectful and constructive. We're all here to build something useful.

## Questions?

Open a GitHub Discussion or reach out to the maintainers.

# Context Foundry Setup Guide

## Quick Start (3 minutes)

### 1. Install Dependencies

```bash
cd ~/context-foundry
pip3 install -r requirements.txt
```

### 2. Configure API Key (for API/Autonomous modes)

```bash
# Copy example environment file
cp .env.example .env

# Edit .env and add your API key
nano .env  # or use your preferred editor
```

Get your API key from: https://console.anthropic.com/

### 3. Test the Installation

```bash
# Test interactive mode (no API key needed)
python3 prompt_generator.py demo-app "Build a simple calculator"

# Test API integration (requires API key)
python3 ace/claude_integration.py
```

## Usage Modes

### Interactive Mode (Copy/Paste)
No API key required - generates prompts you paste into Claude web interface.

```bash
python3 prompt_generator.py todo-app "Build CLI todo app"
```

**Best for:**
- Learning the workflow
- When you want full control
- Manual review at each step

### API Mode (Semi-Automated)
Uses Claude API with human checkpoints at each phase.

```bash
python3 prompt_generator.py todo-app "Build CLI todo app" --api
```

**Best for:**
- Daily development
- Multiple small features
- When you want speed + control

### Autonomous Mode (Fully Automated)
Runs overnight without human intervention.

```bash
python3 prompt_generator.py todo-app "Build CLI todo app" --autonomous
```

**Best for:**
- Overnight runs
- Large feature implementations
- When you trust the process

## Direct Orchestrator Usage

You can also call the orchestrator directly:

```bash
# With human checkpoints
python3 workflows/autonomous_orchestrator.py my-app "Build REST API"

# Fully autonomous
python3 workflows/autonomous_orchestrator.py my-app "Build REST API" --autonomous
```

## Troubleshooting

### "No module named 'anthropic'"
```bash
pip3 install anthropic
```

### "ANTHROPIC_API_KEY not set"
1. Create `.env` file from `.env.example`
2. Add your API key
3. Or export directly: `export ANTHROPIC_API_KEY=your_key`

### Import errors
Make sure you're in the context-foundry directory when running scripts.

## Next Steps

1. Read the README for philosophy and workflow
2. Try interactive mode first to understand the process
3. Graduate to API mode for daily use
4. Use autonomous mode for overnight feature development

Happy building! 🏭

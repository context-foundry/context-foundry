# Multi-Provider AI Guide

Context Foundry supports **7 AI providers** with complete flexibility to mix and match models across different phases.

## Quick Start

### 1. Configure Your Providers

Edit `.env` to set which provider/model to use for each phase:

```bash
# Use Claude for planning, GPT-4o-mini for coding
SCOUT_PROVIDER=anthropic
SCOUT_MODEL=claude-sonnet-4-20250514

ARCHITECT_PROVIDER=anthropic
ARCHITECT_MODEL=claude-sonnet-4-20250514

BUILDER_PROVIDER=openai
BUILDER_MODEL=gpt-4o-mini

# Add API keys
ANTHROPIC_API_KEY=sk-ant-...
OPENAI_API_KEY=sk-...
```

### 2. Update Pricing

```bash
foundry pricing --update
```

### 3. Estimate Cost

```bash
foundry estimate "Build a todo app"
```

### 4. Build Your Project

```bash
foundry build my-app "Build a todo app"
```

---

## Supported Providers

### 1. Anthropic (Claude)

**Best for**: Reasoning, planning, complex tasks

**Models:**
- `claude-opus-4-20250514` - Most capable ($15/$75 per 1M tokens)
- `claude-sonnet-4-20250514` - Balanced ($3/$15 per 1M tokens) **[Recommended]**
- `claude-haiku-4-20250514` - Fast and cheap ($0.80/$4 per 1M tokens)

**Setup:**
```bash
ANTHROPIC_API_KEY=sk-ant-...
```

Get API key: https://console.anthropic.com/

---

### 2. OpenAI (GPT)

**Best for**: Coding, general tasks, cost optimization

**Models:**
- `gpt-4o` - Flagship model ($2.50/$10 per 1M tokens)
- `gpt-4o-mini` - Affordable and fast ($0.15/$0.60 per 1M tokens) **[Great for Builder]**
- `gpt-4-turbo` - Previous flagship ($10/$30 per 1M tokens)

**Setup:**
```bash
OPENAI_API_KEY=sk-...
pip install openai
```

Get API key: https://platform.openai.com/api-keys

---

### 3. Google (Gemini)

**Best for**: Huge context windows, multimodal tasks

**Models:**
- `gemini-2.0-flash-exp` - Very fast and cheap ($0.075/$0.30 per 1M tokens)
- `gemini-1.5-pro` - 2M context window ($1.25/$5 per 1M tokens)
- `gemini-1.5-flash` - Fast ($0.075/$0.30 per 1M tokens)

**Setup:**
```bash
GOOGLE_API_KEY=...
pip install google-generativeai
```

Get API key: https://ai.google.dev/

---

### 4. Groq

**Best for**: Ultra-fast inference, cost optimization

**Models:**
- `llama-3.1-8b-instant` - Very affordable ($0.05/$0.08 per 1M tokens)
- `llama-3.1-70b-versatile` - More capable ($0.59/$0.79 per 1M tokens)

**Setup:**
```bash
GROQ_API_KEY=...
pip install groq
```

Get API key: https://console.groq.com/

---

### 5. Cloudflare Workers AI

**Best for**: Code generation

**Models:**
- `@cf/qwen/qwen2.5-coder-32b-instruct` - Code specialist ($0.10/$0.10 per 1M tokens)

**Setup:**
```bash
CLOUDFLARE_API_KEY=...
CLOUDFLARE_ACCOUNT_ID=...
```

Get API key: https://dash.cloudflare.com/

---

### 6. Fireworks AI

**Best for**: Code generation

**Models:**
- `accounts/fireworks/models/starcoder2-7b` - Code generation ($0.20/$0.20 per 1M tokens)

**Setup:**
```bash
FIREWORKS_API_KEY=...
```

Get API key: https://fireworks.ai/

---

### 7. Mistral

**Best for**: Code generation, European AI

**Models:**
- `codestral-latest` - Code specialist ($0.20/$0.60 per 1M tokens)
- `mistral-large-latest` - Most capable ($2.00/$6.00 per 1M tokens)

**Setup:**
```bash
MISTRAL_API_KEY=...
pip install mistralai
```

Get API key: https://console.mistral.ai/

---

## Common Configurations

### Cost-Optimized (Recommended)

Use best models for planning, cheapest for coding:

```bash
SCOUT_PROVIDER=anthropic
SCOUT_MODEL=claude-sonnet-4-20250514

ARCHITECT_PROVIDER=anthropic
ARCHITECT_MODEL=claude-sonnet-4-20250514

BUILDER_PROVIDER=openai
BUILDER_MODEL=gpt-4o-mini
```

**Estimated cost:** $4-10 per project

---

### Quality-First

Use premium models for everything:

```bash
SCOUT_PROVIDER=anthropic
SCOUT_MODEL=claude-opus-4-20250514

ARCHITECT_PROVIDER=anthropic
ARCHITECT_MODEL=claude-opus-4-20250514

BUILDER_PROVIDER=anthropic
BUILDER_MODEL=claude-sonnet-4-20250514
```

**Estimated cost:** $15-40 per project

---

### Ultra-Cheap

Use free-tier or cheapest models:

```bash
SCOUT_PROVIDER=gemini
SCOUT_MODEL=gemini-2.0-flash-exp

ARCHITECT_PROVIDER=gemini
ARCHITECT_MODEL=gemini-2.0-flash-exp

BUILDER_PROVIDER=groq
BUILDER_MODEL=llama-3.1-8b-instant
```

**Estimated cost:** $0.50-2 per project

---

### All-Gemini

Use Google Gemini for everything:

```bash
SCOUT_PROVIDER=gemini
SCOUT_MODEL=gemini-1.5-pro

ARCHITECT_PROVIDER=gemini
ARCHITECT_MODEL=gemini-1.5-pro

BUILDER_PROVIDER=gemini
BUILDER_MODEL=gemini-2.0-flash-exp
```

---

## Per-Task Overrides

For fine-grained control, override specific Builder tasks:

```bash
# Use default model for most tasks
BUILDER_PROVIDER=openai
BUILDER_MODEL=gpt-4o-mini

# But use better model for critical tasks
BUILDER_TASK_1_PROVIDER=anthropic
BUILDER_TASK_1_MODEL=claude-sonnet-4-20250514

BUILDER_TASK_5_PROVIDER=gemini
BUILDER_TASK_5_MODEL=gemini-1.5-pro
```

---

## CLI Commands

### List Available Models

```bash
# List all providers
foundry models

# List all models with pricing
foundry models --list

# List models from specific provider
foundry models --list --provider anthropic
```

### Manage Pricing

```bash
# Show pricing status
foundry pricing

# Update pricing from all providers
foundry pricing --update

# Force update (even if not stale)
foundry pricing --update --force

# List current pricing
foundry pricing --list
```

### Estimate Costs

```bash
# Estimate cost for a project
foundry estimate "Build a todo app with React and Node.js"
```

Output:
```
Current Configuration:
============================================================
Scout:     anthropic / claude-sonnet-4-20250514
Architect: anthropic / claude-sonnet-4-20250514
Builder:   openai / gpt-4o-mini

Cost Estimate
============================================================

Scout Phase
  Provider: anthropic
  Model: claude-sonnet-4-20250514
  Est. tokens: 2,000 input, 4,000 output
  Cost: $0.50 - $1.20

Architect Phase
  Provider: anthropic
  Model: claude-sonnet-4-20250514
  Est. tokens: 3,000 input, 7,500 output
  Cost: $1.20 - $2.80

Builder Phase
  Provider: openai
  Model: gpt-4o-mini
  Est. tokens: 10,000 input, 40,000 output
  Cost: $2.00 - $5.00

============================================================
Total Estimated Cost: $3.70 - $9.00
```

---

## Pricing Auto-Update

Context Foundry automatically updates pricing from provider websites:

```bash
# Enable/disable auto-update in .env
PRICING_AUTO_UPDATE=true

# Update interval (days)
PRICING_UPDATE_DAYS=30
```

Pricing is fetched from:
- **Anthropic**: https://docs.claude.com/en/docs/about-claude/pricing
- **OpenAI**: https://openai.com/api/pricing/
- **Gemini**: https://ai.google.dev/gemini-api/docs/pricing
- **Groq**: https://groq.com/pricing
- **Cloudflare**: https://developers.cloudflare.com/workers-ai/
- **Fireworks**: https://fireworks.ai/models/
- **Mistral**: https://mistral.ai/news/

---

## Cost Optimization Tips

### 1. Use Cheap Models for Builder

Builder phase uses the most tokens. Use affordable models:

```bash
BUILDER_PROVIDER=openai
BUILDER_MODEL=gpt-4o-mini  # Only $0.15/$0.60 per 1M tokens
```

### 2. Mix and Match

Use premium models for planning (Scout/Architect), cheap for coding:

```bash
SCOUT_PROVIDER=anthropic
SCOUT_MODEL=claude-sonnet-4-20250514

BUILDER_PROVIDER=groq
BUILDER_MODEL=llama-3.1-8b-instant
```

### 3. Estimate Before Building

Always check estimated cost first:

```bash
foundry estimate "Your project description"
```

### 4. Use Free Tiers

Some providers offer generous free tiers:
- **Gemini**: Large free quota
- **Groq**: Fast free inference

---

## Troubleshooting

### "Provider not found"

Make sure you've installed the provider's SDK:

```bash
pip install openai  # For OpenAI
pip install google-generativeai  # For Gemini
pip install groq  # For Groq
pip install mistralai  # For Mistral
```

### "No pricing found"

Update pricing database:

```bash
foundry pricing --update --force
```

### "API key not configured"

Add the API key to `.env`:

```bash
OPENAI_API_KEY=your_key_here
```

---

## Complete Freedom

**You have complete control.** Use:
- **Same provider for all phases**: `anthropic` everywhere
- **Different providers per phase**: `anthropic` → `openai` → `gemini`
- **Mix any combination**: Your choice!

No restrictions. No assumptions. Configure it however you want.

---

## Examples

### Example 1: Startup (Cost-Conscious)

```bash
SCOUT_PROVIDER=anthropic
SCOUT_MODEL=claude-haiku-4-20250514

ARCHITECT_PROVIDER=anthropic
ARCHITECT_MODEL=claude-haiku-4-20250514

BUILDER_PROVIDER=groq
BUILDER_MODEL=llama-3.1-8b-instant
```

**Estimated cost:** $1-3 per project

---

### Example 2: Enterprise (Quality-First)

```bash
SCOUT_PROVIDER=anthropic
SCOUT_MODEL=claude-opus-4-20250514

ARCHITECT_PROVIDER=anthropic
ARCHITECT_MODEL=claude-opus-4-20250514

BUILDER_PROVIDER=anthropic
BUILDER_MODEL=claude-sonnet-4-20250514
```

**Estimated cost:** $20-50 per project

---

### Example 3: Experimental (All Different)

```bash
SCOUT_PROVIDER=gemini
SCOUT_MODEL=gemini-1.5-pro

ARCHITECT_PROVIDER=anthropic
ARCHITECT_MODEL=claude-sonnet-4-20250514

BUILDER_PROVIDER=openai
BUILDER_MODEL=gpt-4o-mini
```

**Estimated cost:** $5-12 per project

---

## Need Help?

- **Documentation**: See `.env.example` for all options
- **List models**: `foundry models --list`
- **Check pricing**: `foundry pricing`
- **Estimate cost**: `foundry estimate "your task"`

Happy building! 🏭

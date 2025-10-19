# GitHub Models (FREE) Integration Guide

## ✅ Integration Complete!

GitHub Models provider has been successfully added to Context Foundry. You can now use GPT-4o **completely FREE**!

---

## 🚀 Quick Start

### 1. Requirements

- **GitHub Personal Access Token (PAT)** - **NO SUBSCRIPTION NEEDED!**
  - Generate at: https://github.com/settings/tokens
  - Token type: **Classic** (not fine-grained)
  - Required scopes: `repo` or `public_repo`

### 2. Configure Your `.env` File

Add your GitHub PAT to `.env`:

```bash
# GitHub token (used for GitHub Models API + PR creation)
GITHUB_TOKEN=ghp_your_personal_access_token_here
```

### 3. Set Phases to Use GitHub Models

```bash
# Scout Phase - FREE GitHub Models
SCOUT_PROVIDER=github
SCOUT_MODEL=gpt-4o

# Architect Phase - FREE GitHub Models
ARCHITECT_PROVIDER=github
ARCHITECT_MODEL=gpt-4o

# Builder Phase - FREE GitHub Models
BUILDER_PROVIDER=github
BUILDER_MODEL=gpt-4o
```

### 4. Run a Build

```bash
foundry build weather-app "Build a weather app"
```

Context Foundry will:
1. Use your GitHub PAT directly (no token exchange needed)
2. Call GitHub Models API (FREE)
3. Build your project with GPT-4o at **$0 cost**

---

## 💰 Pricing - **100% FREE!**

| Provider | Cost | Rate Limits |
|----------|------|-------------|
| **GitHub Models** | **$0 (FREE)** | **10K requests/day, 10M tokens/day per model** |
| Claude Sonnet | $3/$15 per 1M tokens | Pay per use |
| GPT-4o (OpenAI) | $2.50/$10 per 1M tokens | Pay per use |
| GitHub Copilot | $10/month unlimited | Subscription required |

**Key Benefits**:
- ✅ **Completely FREE** - No credit card required
- ✅ **Generous limits** - 10K requests/day, 10M tokens/day
- ✅ **GPT-4o quality** - Latest GPT-4 model
- ✅ **No subscription** - Just a GitHub PAT

**Rate Limits**:
- 10,000 requests per day per model
- 10,000,000 tokens per day per model
- Resets daily
- More than enough for development!

---

## 📋 Available Models

### gpt-4o (Recommended)
```bash
BUILDER_MODEL=gpt-4o
```
- **Context**: 128,000 tokens
- **Quality**: Best (GPT-4o)
- **Best for**: All coding tasks
- **Cost**: FREE

### gpt-4
```bash
BUILDER_MODEL=gpt-4
```
- **Context**: 8,192 tokens
- **Quality**: Original GPT-4
- **Best for**: Shorter tasks
- **Cost**: FREE

### gpt-3.5-turbo
```bash
BUILDER_MODEL=gpt-3.5-turbo
```
- **Context**: 16,385 tokens
- **Quality**: Fast but lower quality
- **Best for**: Simple tasks
- **Cost**: FREE

---

## 🎯 Recommended Configurations

### All GitHub Models (FREE)
```bash
SCOUT_PROVIDER=github
SCOUT_MODEL=gpt-4o

ARCHITECT_PROVIDER=github
ARCHITECT_MODEL=gpt-4o

BUILDER_PROVIDER=github
BUILDER_MODEL=gpt-4o
```
**Cost**: $0 (completely free!)
**Quality**: Excellent (GPT-4o for everything)

### Mixed Providers (Best Quality)
```bash
SCOUT_PROVIDER=anthropic
SCOUT_MODEL=claude-sonnet-4-5-20250929

ARCHITECT_PROVIDER=anthropic
ARCHITECT_MODEL=claude-sonnet-4-5-20250929

BUILDER_PROVIDER=github
BUILDER_MODEL=gpt-4o
```
**Cost**: ~$0.03 per build (just Scout/Architect)
**Quality**: Excellent (Claude planning + FREE GPT-4o coding)

---

## 🧪 Testing the Integration

Run the test suite:

```bash
python3 tests/test_github_provider.py
```

Expected output:
```
✅ ALL TESTS PASSED
GitHub Models provider successfully integrated!
```

---

## 🔧 How It Works

GitHub Models uses a direct API endpoint (no token exchange):

1. **Your GitHub PAT** → Stored in `.env` as `GITHUB_TOKEN`
2. **Direct API Call** → Uses PAT as Bearer token
3. **GitHub Models Endpoint** → `https://models.inference.ai.azure.com/chat/completions`
4. **FREE Access** → No charges, generous rate limits

**You don't need a Copilot subscription!** Just a GitHub account and PAT.

---

## 🐛 Troubleshooting

### "GitHub token not configured"
- Add `GITHUB_TOKEN=ghp_...` to `.env`
- Generate token at: https://github.com/settings/tokens
- Use **Classic** token type (not fine-grained)

### "GitHub Models API error: HTTP 401"
- Token expired - regenerate at: https://github.com/settings/tokens
- Update `.env` with new token

### "GitHub Models API error: HTTP 429"
- Rate limit reached (10K requests/day or 10M tokens/day)
- Wait for daily reset or switch to another provider temporarily

### "Failed to call GitHub Models API"
- Check internet connection
- Verify token is correct in `.env`
- Try: `curl -H "Authorization: Bearer YOUR_TOKEN" https://models.inference.ai.azure.com/chat/completions`

---

## 📚 Additional Resources

- **GitHub Models**: https://github.com/marketplace/models
- **PAT Generation**: https://github.com/settings/tokens
- **Rate Limits**: 10K req/day, 10M tokens/day per model
- **Supported Models**: GPT-4o, GPT-4, GPT-3.5-turbo, and more

---

## 🎉 Summary

**You now have FREE GPT-4o access via GitHub Models!**

**Benefits**:
1. **$0 cost** - Completely free with generous rate limits
2. **No subscription** - Just a GitHub PAT
3. **GPT-4o quality** - Latest and best GPT-4 model
4. **10M tokens/day** - More than enough for development

**Recommended Setup**:
- Use **GitHub Models (FREE)** for Builder (most tokens)
- Use **Claude or Z.ai** for Scout & Architect (less tokens)
- Total cost: $0 to ~$0.03 per build

**This is the most cost-effective way to use Context Foundry!** 🚀

---

**Integration complete!**

Generate your GitHub PAT, update `.env`, and start building with FREE GPT-4o!

*Date: 2025-10-06*
*Updated: GitHub Models (FREE) replaces Copilot subscription*

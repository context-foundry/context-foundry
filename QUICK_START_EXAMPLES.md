# 🚀 Quick Start: 5 Projects to Build Right Now

Ready to try Context Foundry? Here are **5 ready-to-run examples**. Just copy, paste, and go!

Each takes **15-30 minutes** and costs **$3-12**.

---

## 1. 📝 Todo CLI App

**What:** Command-line todo list with add, complete, remove

**Command:**
```bash
foundry build todo-cli "Build a command-line todo app with add, list, complete, and remove commands. Use JSON for storage and colorful terminal output with the Rich library."
```

**Cost:** $4-8 | **Time:** 15-20 min

**You'll learn:** CLI development, JSON storage, terminal colors

---

## 2. 🔗 URL Shortener

**What:** REST API that shortens URLs (like bit.ly)

**Command:**
```bash
foundry build url-shortener "Create a URL shortener REST API with Flask. Generate short codes, redirect to original URLs, track click counts. Include a basic web UI and SQLite database."
```

**Cost:** $6-12 | **Time:** 20-30 min

**You'll learn:** REST APIs, databases, web development

---

## 3. 💰 Expense Tracker

**What:** Track spending by category, generate reports

**Command:**
```bash
foundry build expense-tracker "Build a CLI expense tracker. Add expenses with amount, category, and description. View spending by category, generate monthly reports, and set budget alerts. Store in SQLite database."
```

**Cost:** $5-10 | **Time:** 20-25 min

**You'll learn:** Database queries, reports, data visualization

---

## 4. 🌤️ Weather CLI

**What:** Beautiful weather forecasts in your terminal

**Command:**
```bash
foundry build weather-cli "Create a command-line weather app that fetches current weather and 5-day forecast from OpenWeatherMap API. Beautiful terminal output with weather icons and color-coded temperatures. Include location search by city name."
```

**Cost:** $3-7 | **Time:** 15-20 min

**You'll learn:** API integration, HTTP requests, data parsing

**Note:** Requires free OpenWeatherMap API key

---

## 5. 📓 Note Manager

**What:** Markdown-based note-taking with search and tags

**Command:**
```bash
foundry build note-manager "Build a CLI note-taking app. Create, edit, search, and tag notes. Store as markdown files in organized folders. Include full-text search, tag management, and export to HTML. Use your default editor for note editing."
```

**Cost:** $5-9 | **Time:** 20-25 min

**You'll learn:** File operations, search, markdown processing

---

## 💡 Before You Start

### 1. Check Your Cost First
```bash
foundry estimate "your project description"
```

### 2. Configure Your Providers

**Default (Recommended):**
Already set in `.env` - no changes needed!

**Ultra-Cheap:**
```bash
BUILDER_PROVIDER=groq
BUILDER_MODEL=llama-3.1-8b-instant
```
Cuts cost by 50-70%!

**Quality-First:**
```bash
BUILDER_PROVIDER=anthropic
BUILDER_MODEL=claude-sonnet-4-5-20250929
```
Best code quality!

### 3. Update Pricing
```bash
foundry pricing --update
```

---

## 📊 Cost Comparison

| Project | Default | Ultra-Cheap | Quality-First |
|---------|---------|-------------|---------------|
| Todo CLI | $4-8 | $1-3 | $10-15 |
| URL Shortener | $6-12 | $2-5 | $15-25 |
| Expense Tracker | $5-10 | $2-4 | $12-20 |
| Weather CLI | $3-7 | $1-3 | $8-12 |
| Note Manager | $5-9 | $2-4 | $12-18 |

---

## 🎯 After Building

### Test It
```bash
cd examples/your-app
python -m pytest
```

### Use It
```bash
# CLI apps
./your-app --help

# Web apps
python app.py
```

### Read the Code
- Check `README.md` in project folder
- Review source files
- Look at tests

---

## 🔥 Pro Tips

1. **Start with Todo CLI** - Simplest, fastest to understand
2. **Review the Plan** - Edit SPEC/PLAN/TASKS before building
3. **Try Different Providers** - Build the same app with Groq, then Claude
4. **Use Autonomous Mode** - Add `--autonomous` for no-review builds
5. **Check Examples** - See `docs/EXAMPLES.md` for detailed guides

---

## 🛟 Need Help?

- **Detailed Examples:** `docs/EXAMPLES.md`
- **Multi-Provider Guide:** `docs/MULTI_PROVIDER_GUIDE.md`
- **List Available Models:** `foundry models --list`
- **Pricing Info:** `foundry pricing`

---

## 🌟 What's Next?

After trying these examples:

1. **Build Your Own Idea** - Use what you learned!
2. **Mix Providers** - Try Gemini for Scout, GPT for Builder
3. **Share Your Project** - Show what you built!
4. **Read the Docs** - Learn advanced features

**Ready? Pick an example and run it!** 🏭

# 🚀 Quick Start Examples

Ready to build something? Here are **5 example projects** you can build right now with Context Foundry. Each takes 15-30 minutes and costs $3-12.

---

## Why These Examples?

- ✅ **Ready to Run** - Just copy and paste the command
- ✅ **Real Projects** - Actual useful apps, not toy examples
- ✅ **Progressive Complexity** - Start simple, get more advanced
- ✅ **Cost Transparent** - Know exactly what you'll spend
- ✅ **Multi-Provider** - Try different AI combinations

---

## Example 1: Todo CLI App

**Perfect for:** First-time users, learning CLI development

### Command

```bash
foundry build todo-cli "Build a command-line todo app with add, list, complete, and remove commands. Use JSON for storage and colorful terminal output with the Rich library."
```

### What You'll Get

- ✅ Full-featured CLI with 5+ commands
- ✅ JSON file-based persistence
- ✅ Colorful terminal output (Rich library)
- ✅ Complete test suite (pytest)
- ✅ README with usage examples

### What You'll Learn

- CLI argument parsing (Click or Typer)
- JSON file operations
- Terminal styling and colors
- Testing CLI applications
- Data persistence

### Configuration

**Default (Recommended):**
```bash
Scout: Claude Sonnet 4.5
Architect: Claude Sonnet 4.5
Builder: GPT-4o-mini
```

**Estimated Cost:** $4-8
**Build Time:** 15-20 minutes

### Try Different Providers

**Ultra-Cheap:**
```bash
BUILDER_PROVIDER=groq BUILDER_MODEL=llama-3.1-8b-instant \
foundry build todo-cli "Build a command-line todo app..."
```
**Cost:** $1-3

**All-Gemini:**
```bash
SCOUT_PROVIDER=gemini SCOUT_MODEL=gemini-1.5-pro \
ARCHITECT_PROVIDER=gemini ARCHITECT_MODEL=gemini-1.5-pro \
BUILDER_PROVIDER=gemini BUILDER_MODEL=gemini-2.0-flash-exp \
foundry build todo-cli "Build a command-line todo app..."
```
**Cost:** $2-5

---

## Example 2: URL Shortener Service

**Perfect for:** Learning web APIs, backend development

### Command

```bash
foundry build url-shortener "Create a URL shortener REST API with Flask. Generate short codes, redirect to original URLs, track click counts. Include a basic web UI and SQLite database."
```

### What You'll Get

- ✅ REST API with endpoints (shorten, redirect, stats)
- ✅ Short code generation (base62 encoding)
- ✅ Click tracking and analytics
- ✅ SQLite database with migrations
- ✅ Simple web UI (HTML/CSS/JS)
- ✅ API documentation

### What You'll Learn

- REST API design
- Flask web framework
- Database modeling (SQLite)
- URL redirects (HTTP 301/302)
- Basic frontend integration
- API testing

### Configuration

**Default:**
```bash
Scout: Claude Sonnet 4.5
Architect: Claude Sonnet 4.5
Builder: GPT-4o-mini
```

**Estimated Cost:** $6-12
**Build Time:** 20-30 minutes

### Try Different Providers

**Quality-First:**
```bash
BUILDER_PROVIDER=anthropic BUILDER_MODEL=claude-sonnet-4-5-20250929 \
foundry build url-shortener "Create a URL shortener REST API..."
```
**Cost:** $10-20 (better code quality)

---

## Example 3: Personal Expense Tracker

**Perfect for:** Learning data management, reports, CLI design

### Command

```bash
foundry build expense-tracker "Build a CLI expense tracker. Add expenses with amount, category, and description. View spending by category, generate monthly reports, and set budget alerts. Store in SQLite database."
```

### What You'll Get

- ✅ Expense management (add, edit, delete)
- ✅ Category-based organization
- ✅ Monthly/yearly reports
- ✅ Budget tracking and alerts
- ✅ Data export (CSV/JSON)
- ✅ Beautiful charts in terminal

### What You'll Learn

- SQLite database operations
- Data aggregation and reporting
- Date/time handling
- Terminal charts (matplotlib or plotext)
- Budget calculations
- Data export formats

### Configuration

**Default:**
```bash
Scout: Claude Sonnet 4.5
Architect: Claude Sonnet 4.5
Builder: GPT-4o-mini
```

**Estimated Cost:** $5-10
**Build Time:** 20-25 minutes

### Try Different Providers

**Balanced:**
```bash
BUILDER_PROVIDER=openai BUILDER_MODEL=gpt-4o \
foundry build expense-tracker "Build a CLI expense tracker..."
```
**Cost:** $8-15 (higher quality GPT-4o)

---

## Example 4: Weather CLI Tool

**Perfect for:** Learning API integration, HTTP requests

### Command

```bash
foundry build weather-cli "Create a command-line weather app that fetches current weather and 5-day forecast from OpenWeatherMap API. Beautiful terminal output with weather icons and color-coded temperatures. Include location search by city name."
```

### What You'll Get

- ✅ Current weather display
- ✅ 5-day forecast
- ✅ Location search (city, zip code)
- ✅ Weather icons in terminal
- ✅ Color-coded temperatures
- ✅ Unit conversion (F/C)

### What You'll Learn

- API integration (OpenWeatherMap)
- HTTP requests (requests library)
- Data parsing (JSON)
- Terminal formatting
- Environment variables (API keys)
- Error handling for APIs

### Configuration

**Default:**
```bash
Scout: Claude Sonnet 4.5
Architect: Claude Sonnet 4.5
Builder: GPT-4o-mini
```

**Estimated Cost:** $3-7
**Build Time:** 15-20 minutes

### Try Different Providers

**Fastest (Groq):**
```bash
BUILDER_PROVIDER=groq BUILDER_MODEL=llama-3.1-70b-versatile \
foundry build weather-cli "Create a command-line weather app..."
```
**Cost:** $4-8 (Groq is very fast)

### Setup Note

You'll need a free OpenWeatherMap API key:
1. Sign up at https://openweathermap.org/api
2. Get free API key
3. Add to generated `.env` file

---

## Example 5: Markdown Note Manager

**Perfect for:** Learning file operations, search, organization

### Command

```bash
foundry build note-manager "Build a CLI note-taking app. Create, edit, search, and tag notes. Store as markdown files in organized folders. Include full-text search, tag management, and export to HTML. Use your default editor for note editing."
```

### What You'll Get

- ✅ Note creation and editing
- ✅ Markdown file storage
- ✅ Tag-based organization
- ✅ Full-text search
- ✅ Export to HTML/PDF
- ✅ Editor integration (vim, nano, etc.)

### What You'll Learn

- File system operations
- Markdown processing
- Search algorithms
- Text indexing
- Process spawning (editor)
- HTML generation

### Configuration

**Default:**
```bash
Scout: Claude Sonnet 4.5
Architect: Claude Sonnet 4.5
Builder: GPT-4o-mini
```

**Estimated Cost:** $5-9
**Build Time:** 20-25 minutes

### Try Different Providers

**Code-Specialist:**
```bash
BUILDER_PROVIDER=mistral BUILDER_MODEL=codestral-latest \
foundry build note-manager "Build a CLI note-taking app..."
```
**Cost:** $4-8 (Mistral Codestral is optimized for code)

---

## Cost Comparison Table

| Example | Default Cost | Ultra-Cheap | Quality-First | Build Time |
|---------|-------------|-------------|---------------|------------|
| Todo CLI | $4-8 | $1-3 | $10-15 | 15-20 min |
| URL Shortener | $6-12 | $2-5 | $15-25 | 20-30 min |
| Expense Tracker | $5-10 | $2-4 | $12-20 | 20-25 min |
| Weather CLI | $3-7 | $1-3 | $8-12 | 15-20 min |
| Note Manager | $5-9 | $2-4 | $12-18 | 20-25 min |

---

## Provider Combinations to Try

### 1. Cost-Optimized (Recommended)
```bash
SCOUT_PROVIDER=anthropic
SCOUT_MODEL=claude-sonnet-4-5-20250929
ARCHITECT_PROVIDER=anthropic
ARCHITECT_MODEL=claude-sonnet-4-5-20250929
BUILDER_PROVIDER=openai
BUILDER_MODEL=gpt-4o-mini
```
**When:** You want best quality/cost ratio

---

### 2. Ultra-Cheap
```bash
SCOUT_PROVIDER=gemini
SCOUT_MODEL=gemini-2.0-flash-exp
ARCHITECT_PROVIDER=gemini
ARCHITECT_MODEL=gemini-2.0-flash-exp
BUILDER_PROVIDER=groq
BUILDER_MODEL=llama-3.1-8b-instant
```
**When:** Experimenting, learning, tight budget

---

### 3. Quality-First
```bash
SCOUT_PROVIDER=anthropic
SCOUT_MODEL=claude-sonnet-4-5-20250929
ARCHITECT_PROVIDER=anthropic
ARCHITECT_MODEL=claude-sonnet-4-5-20250929
BUILDER_PROVIDER=anthropic
BUILDER_MODEL=claude-sonnet-4-5-20250929
```
**When:** Production code, complex projects

---

### 4. All-Gemini
```bash
SCOUT_PROVIDER=gemini
SCOUT_MODEL=gemini-1.5-pro
ARCHITECT_PROVIDER=gemini
ARCHITECT_MODEL=gemini-1.5-pro
BUILDER_PROVIDER=gemini
BUILDER_MODEL=gemini-2.0-flash-exp
```
**When:** Huge context needs, multimodal tasks

---

### 5. Code-Specialist
```bash
SCOUT_PROVIDER=anthropic
SCOUT_MODEL=claude-sonnet-4-5-20250929
ARCHITECT_PROVIDER=anthropic
ARCHITECT_MODEL=claude-sonnet-4-5-20250929
BUILDER_PROVIDER=mistral
BUILDER_MODEL=codestral-latest
```
**When:** Heavy code generation, algorithms

---

## Tips for Success

### 1. Start Small
Begin with **Example 1 (Todo CLI)**. It's simple, fast, and teaches fundamentals.

### 2. Check Estimates First
Always run cost estimate before building:
```bash
foundry estimate "your project description"
```

### 3. Review the Plan
Don't skip the Architect phase review! Edit SPEC/PLAN/TASKS files to get exactly what you want.

### 4. Experiment with Providers
Try the same project with different providers:
- Compare code quality
- Compare costs
- Find your preferred combination

### 5. Use Autonomous Mode Carefully
```bash
foundry build my-app "..." --autonomous
```
Skips all reviews. Good for experimentation, risky for production.

---

## What to Do After Building

### 1. Test the App
```bash
cd examples/your-app
python -m pytest  # Run tests
```

### 2. Try It Out
```bash
# CLI apps
./your-app --help

# Web apps
python app.py
# Visit http://localhost:5000
```

### 3. Read the Code
- Check `README.md` for usage
- Review source files
- Look at tests to understand features

### 4. Extend It
Add features:
```bash
foundry enhance "Add user authentication"
```
*(Coming soon - enhance command)*

### 5. Share It
- Push to GitHub
- Show it to friends
- Use it daily!

---

## Troubleshooting

### Build Failed?

1. **Check API keys:** Make sure they're valid in `.env`
2. **Update pricing:** Run `foundry pricing --update`
3. **Check model names:** Ensure they exist for your provider
4. **Try different model:** Switch to a more reliable model

### Code Not Working?

1. **Read the README:** Generated in project folder
2. **Check dependencies:** Run `pip install -r requirements.txt`
3. **Run tests:** See what's failing
4. **Review the plan:** SPEC/PLAN/TASKS might have misunderstood

### Too Expensive?

1. **Use cheaper models:** Switch to Groq or Gemini
2. **Simplify task:** Break into smaller pieces
3. **Use autonomous mode:** Skip reviews (faster = cheaper)

---

## More Examples

Want more ideas? Try these:

- **Blog Generator** - Static site generator from markdown
- **Password Manager** - Encrypted password storage CLI
- **GitHub Stats** - Analyze your GitHub activity
- **Pomodoro Timer** - Focus timer with notifications
- **API Rate Limiter** - Middleware for rate limiting
- **File Organizer** - Auto-organize downloads by type
- **RSS Reader** - Terminal-based feed reader
- **Docker Manager** - CLI for managing containers
- **Git Helper** - Simplified git workflows
- **CSV Analyzer** - Data analysis and visualization

---

## Need Help?

- **Documentation:** `docs/MULTI_PROVIDER_GUIDE.md`
- **Cost Estimator:** `foundry estimate "your task"`
- **List Models:** `foundry models --list`
- **Check Pricing:** `foundry pricing`

**Happy building!** 🏭

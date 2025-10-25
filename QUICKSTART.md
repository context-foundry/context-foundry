# Context Foundry 2.0 - 5-Minute Quickstart

**Get from zero to deployed app in 5 minutes**

---

## What You'll Do

1. One-time setup (2 minutes)
2. Build your first app (3 minutes of your time, 7-15 min build runs in background)
3. See it deployed on GitHub

**Total active time:** 5 minutes
**Build time:** 7-15 minutes (runs in background while you work - no waiting!)

---

## Step 1: One-Time Setup (2 minutes)

### Install Dependencies

```bash
# Clone Context Foundry
cd ~/homelab  # or your preferred location
git clone https://github.com/snedea/context-foundry.git
cd context-foundry

# Install MCP server (requires Python 3.10+)
pip install -r requirements-mcp.txt
```

### Connect to Claude Code

```bash
# Add MCP server to Claude Code
claude mcp add --transport stdio context-foundry -- \
  python3.10 $(pwd)/tools/mcp_server.py

# Verify connection
claude mcp list
# Should show: ✓ Connected: context-foundry
```

### Authenticate with GitHub

```bash
gh auth login
# Follow prompts to authenticate
```

**Done!** You only do this once.

---

## Step 2: Build Your First App (3 minutes)

### Start Claude Code

```bash
claude
```

### Just Ask Naturally

Inside your Claude Code session, say:

```
Build a simple todo app with the following features:
- Add new todos
- Mark todos as complete
- Delete todos
- Save todos to localStorage
- Clean, modern UI
```

**That's it!** No commands to memorize, no copy/paste needed.

### What Happens Next (Runs in Background!)

Claude Code will automatically start the build **in the background**:

```
🚀 Autonomous build started!

Project: todo-app
Task ID: abc-123-def-456
Location: /tmp/todo-app
Expected duration: 7-15 minutes

You can continue working - the build runs in the background.
```

**You can now:**
- ✅ Continue working on other things
- ✅ Start another build in parallel
- ✅ Close Claude and come back later
- ✅ Check status anytime

**The system autonomously:**
1. **Scout** (1-2 min): Research best practices
2. **Architect** (1-2 min): Design the app
3. **Builder** (2-5 min): Write all code + tests
4. **Test** (1-2 min): Validate everything (auto-fixes failures!)
5. **Document** (1 min): Create README and docs
6. **Deploy** (30 sec): Push to GitHub

**Total time:** 7-15 minutes (runs in background while you work)

### Visual Example: Real Build in Progress

**Here's what a real autonomous build looks like:**

![Build Process - Starting](docs/screenshots/EvolutionQuestBeingBuilt.png)
*Context Foundry begins the autonomous build process after your request*

![Build Process - In Progress](docs/screenshots/BuildStatusUpdate1.png)
*Guided workflow progresses through Scout → Architect → Builder phases automatically*

![Build Process - Testing](docs/screenshots/BuildStatusUpdate2.png)
*Self-healing test loop validates and fixes issues without your intervention*

![Build Process - Complete](docs/screenshots/BuildStatusComplete.png)
*All phases complete with tests passing and documentation generated*

![Final Application](docs/screenshots/App_Ready_to_Play.png)
*Deployed, working application ready to use - from simple request to finished product*

**The entire process runs autonomously** - you can work on other things while it builds!

**Check status:**
```
What's the status of my build?
```

---

## Step 3: Check Your Results

### You'll Get

```
✅ Complete!

GitHub Repository: https://github.com/yourusername/todo-app
Local Files: /tmp/todo-app
Tests: 25/25 passing
Duration: 8.3 minutes

Try it:
cd /tmp/todo-app
npm install
npm start
open http://localhost:8080
```

### What Was Created

- ✅ Full source code (HTML, CSS, JavaScript)
- ✅ Comprehensive tests (Jest)
- ✅ Complete documentation (README, usage guides)
- ✅ Deployed to GitHub
- ✅ All tests passing

---

## More Examples

### Weather App

```
Build a weather app that shows current weather and 5-day forecast
using the OpenWeatherMap API. Include city search and temperature
unit toggle.
```

### REST API

```
Create a REST API with Express.js that has user authentication (JWT),
CRUD operations for blog posts, and PostgreSQL database. Include
comprehensive tests.
```

### Game

```
Build a Snake game in JavaScript with HTML5 Canvas. Include score
tracking, difficulty levels, and game over screen.
```

### Full-Stack App

```
Build a full-stack task management app with:
- Backend: Node.js + Express + PostgreSQL
- Frontend: React with login/register pages
- Features: Create tasks, assign to users, mark complete
- Authentication: JWT tokens
```

---

## Tips for Best Results

### ✅ Do This

**Be specific about features:**
```
Build a calculator app with:
- Basic operations (+, -, *, /)
- Scientific functions (sin, cos, sqrt)
- Memory storage (M+, M-, MR)
- Keyboard support
- Clean UI with button animations
```

**Include technical requirements:**
```
Create a weather API with:
- Express.js framework
- Redis caching (5 min TTL)
- Rate limiting (100 req/hour)
- PostgreSQL for user preferences
- Comprehensive error handling
- Jest tests
```

**Mention deployment needs:**
```
Build a portfolio website that:
- Works on mobile and desktop
- Has dark mode toggle
- Can be deployed to Vercel
- Includes SEO meta tags
```

### ❌ Don't Do This

**Too vague:**
```
Build an app  # What kind of app?
```

**Just questions (won't trigger build):**
```
How do I build a weather app?  # This explains, doesn't build
What's the best way to create an API?  # This discusses, doesn't build
```

**Contradictory requirements:**
```
Build a simple app with 50 features  # Pick one: simple OR feature-rich
```

---

## Common Scenarios

### Scenario 1: Quick Prototype

```
Build a minimal viable product for a recipe sharing app.
Just basic recipe CRUD and search functionality.
Use vanilla JavaScript and localStorage.
```

**Result:** Working prototype in ~7 minutes

### Scenario 2: Production-Ready API

```
Create a production-ready REST API for an e-commerce platform with:
- User authentication and authorization
- Product catalog with categories
- Shopping cart functionality
- Order processing
- Payment integration preparation
- PostgreSQL database
- Comprehensive tests (unit + integration)
- API documentation
- Rate limiting and security headers
```

**Result:** Production-ready API in ~15 minutes

### Scenario 3: Learning Project

```
Build a Pomodoro timer app to help me learn JavaScript.
Include start/stop/reset controls, customizable work/break durations,
and notification sounds. Add detailed code comments explaining
how everything works.
```

**Result:** Educational project with comments in ~8 minutes

---

## What If Something Goes Wrong?

### Build Failed

Check `.context-foundry/test-results-iteration-*.md` for details:

```bash
cd /your/project
cat .context-foundry/test-results-iteration-*.md
```

The system auto-fixes 95% of failures. If it doesn't:
1. Review the error reports
2. Re-run with more iterations: (in Claude Code) "Increase max_test_iterations to 5 and rebuild"

### MCP Tools Not Available

```bash
# Verify MCP connection
claude mcp list

# Should show: ✓ Connected: context-foundry
# If not, re-run setup from Step 1
```

### Timeout

For very complex projects, increase timeout:

```
Build [complex project description]

Use a timeout of 30 minutes for this build.
```

---

## Next Steps

### You Just Built Your First App!

Now try:

1. **Build something useful** - Solve a real problem you have
2. **Experiment** - Try different tech stacks
3. **Learn** - Review the generated code to learn patterns
4. **Share** - Your apps are on GitHub, share them!

### Want to Learn More?

- **README.md** - Full feature overview
- **USER_GUIDE.md** - Detailed usage guide
- **ARCHITECTURE_DECISIONS.md** - How it works under the hood, what's new in 2.0

### Advanced Features

Once comfortable with basics:

- **Parallel builds** - Build multiple components simultaneously
- **Custom workflows** - Edit `orchestrator_prompt.txt`
- **Existing projects** - Enhance or fix existing code
- **Complex systems** - Multi-service architectures

---

## Troubleshooting Quick Reference

| Problem | Solution |
|---------|----------|
| MCP not connected | `claude mcp list` then re-run setup |
| Python version error | Install Python 3.10+: `brew install python@3.10` |
| Build timeout | Add: "Use 30 minute timeout" to request |
| Tests failing | Check `.context-foundry/test-results-*.md` |
| GitHub auth error | Run: `gh auth login` |
| Wrong directory | Specify: "Build in /Users/name/projects/myapp" |

---

## FAQ

**Q: Do I need to know the MCP tool names?**
A: No! Just describe what you want in natural language.

**Q: Can I use this for real projects?**
A: Yes! The code is production-ready with tests and documentation.

**Q: How much does it cost?**
A: Requires Claude Max subscription ($20/month unlimited) or pay-per-use API.

**Q: Can I customize the workflow?**
A: Yes! Edit `tools/orchestrator_prompt.txt` to change phases.

**Q: What if I don't want GitHub deployment?**
A: Say: "Build locally only, skip GitHub deployment"

**Q: Can it work on existing code?**
A: Yes! Say: "Enhance my project at /path/to/project by adding [features]"

**Q: Is the generated code good quality?**
A: Yes - 90%+ test coverage, follows best practices, includes documentation.

**Q: Can I stop a build in progress?**
A: Builds are autonomous but time out after the specified duration (default 90 min).

---

## Summary

**The magic of Context Foundry 2.0:**

1. **You:** "Build [describe your app]"
2. **System:** [Builds autonomously for 7-15 minutes]
3. **You:** Get deployed app with tests and docs

**No commands to memorize. No copy/paste. No supervision needed.**

---

**Ready to build?** → Start Claude Code: `claude`

**Questions?** → See [USER_GUIDE.md](USER_GUIDE.md) for comprehensive help

**Technical details?** → See [ARCHITECTURE_DECISIONS.md](ARCHITECTURE_DECISIONS.md)

---

*Context Foundry 2.0 - Build complete software autonomously*

# JIT Knowledge Injection: Claude Code vs GitHub Copilot

Teaching an LLM domain knowledge not in its training data, at conversation time.

## Quick Comparison

**Discovery**
- Claude Code: Automatically finds and loads `.md` files based on your directory hierarchy. No configuration needed.
- Copilot: You must explicitly list every file in `settings.json`. Nothing is discovered on its own.

**Conditional loading**
- Claude Code: Only loads extension docs when you're working in that domain's directory. Flowise docs stay out of the way when you're doing Roblox work.
- Copilot: Loads every listed file into every session regardless of what you're working on. No automatic filtering.

**Adding a new domain**
- Claude Code: Drop a folder with a `CLAUDE.md` inside it. Immediately discoverable.
- Copilot: Add the file path to `settings.json` and update `copilot-instructions.md`. Two manual steps per extension.

**Knowledge format**
- Both use markdown files. The same `.md` files work in both tools with zero changes.

**Cost of loading**
- Claude Code: Pay per token, so loading unnecessary context costs money. Selective loading matters.
- Copilot: Flat monthly rate. Loading everything every time has no cost penalty, which compensates for the lack of filtering.

**Bottom line**: Both deliver the same knowledge to the model. Claude Code is selective about when to surface what. Copilot loads everything always -- but on a flat rate, that tradeoff is acceptable.

## The Pragmatic Approach

### Step 1: Keep your extension docs as-is

Your `.md` files are already tool-agnostic markdown. No changes needed to:

- `extensions/flowise/CLAUDE.md`
- `extensions/extend/CLAUDE.md`
- `extensions/extend/WORKDAY_EXTEND_DEVELOPER_GUIDE.md`
- Any future extension you create

### Step 2: Create the Copilot entry point

**.github/copilot-instructions.md**

```markdown
# Project Extensions

This project has domain-specific extensions with knowledge
not in your training data. Read the relevant extension docs
before answering questions in that domain.

## Extensions
| Domain | Read first |
|--------|-----------|
| Flowise | extensions/flowise/CLAUDE.md |
| Workday Extend | extensions/extend/CLAUDE.md |
| Roblox | extensions/roblox/CLAUDE.md |
```

### Step 3: Wire up auto-loading

**.vscode/settings.json**

```json
{
  "github.copilot.chat.codeGeneration.instructions": [
    { "file": "extensions/flowise/CLAUDE.md" },
    { "file": "extensions/extend/CLAUDE.md" },
    { "file": "extensions/extend/WORKDAY_EXTEND_DEVELOPER_GUIDE.md" },
    { "file": "extensions/roblox/CLAUDE.md" }
  ]
}
```

This injects all extension knowledge into every Copilot chat session automatically.

### Step 4: Adding a new extension

Same pattern you already follow:

```
extensions/new-domain/
├── CLAUDE.md              <- write your JIT knowledge here
├── patterns/              <- optional
└── docs/                  <- optional deep guides
```

Then add one line to `settings.json`:

```json
{ "file": "extensions/new-domain/CLAUDE.md" }
```

### That's it

Your `.md` files are the teaching material. Claude Code and Copilot are both just delivery mechanisms for getting that material into the context window. Write the knowledge once, point both tools at the same files.

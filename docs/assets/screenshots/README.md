# Mission Control Screenshots

This directory contains screenshots of the Mission Control TUI for documentation.

## Required Screenshots

Add the following screenshots to document Mission Control:

### 1. `mission-control-overview.png`
**Full TUI showing all three tabs**
- Capture with at least 2-3 visible tabs
- Show some activity in each section
- Recommended size: 1200x800px minimum

### 2. `conversation-tab.png`
**Conversation tab with chat interface**
- Show natural language interaction with Claude
- Example conversation: "Build a weather app" → response
- Include markdown rendering (bold, code blocks)
- Show scrollable history

### 3. `builds-tab.png`
**Builds tab with delegation monitoring**
- At least 5-6 rows showing different statuses
- Show variety: Running, Complete, Failed, Timeout
- Highlight the "Daemon" column with different states:
  * Monitoring (green bold)
  * Queued (yellow)
  * Checked (blue)
  * \- (dim)
- Show sortable column headers

### 4. `directory-tab.png`
**Directory tab with file explorer**
- Show 2-3 build tabs
- Expanded file trees showing project structure
- Different project types (e.g., JavaScript, Python)

### 5. `daemon-monitoring.png` (Optional)
**Close-up of daemon monitoring status**
- Zoom in on "Daemon" column
- Show all status types clearly visible

### 6. `build-recovery.png` (Optional)
**Example of recovered delegation**
- Show daemon logs with "Recovered orphaned delegation" message
- Demonstrate recovery on startup

## How to Capture Screenshots

### macOS

**Using built-in screencapture:**
```bash
# Capture specific window
screencapture -w mission-control-overview.png

# Timed capture (5 second delay)
screencapture -T 5 builds-tab.png
```

**Using iTerm2:**
1. Press `Cmd+Shift+S`
2. Select region
3. Save to this directory

### Linux

**Using gnome-screenshot:**
```bash
# Capture window
gnome-screenshot -w -f conversation-tab.png

# Capture specific area
gnome-screenshot -a -f builds-tab.png
```

**Using scrot:**
```bash
scrot -s builds-tab.png
```

### Windows

**Using PowerShell:**
```powershell
# Use Snipping Tool (Win+Shift+S) and save to this directory
```

## Screenshot Guidelines

### Terminal Setup

- **Font:** Monospace, 14-16pt recommended
- **Window size:** 120x40 columns minimum (bigger is better!)
- **Theme:** Dark theme for good contrast
- **Content:** Use real examples with active builds

### What to Show

✅ **Good:**
- Real project names and data
- Multiple builds in different states
- Active monitoring status
- Readable text (not too small)
- Clean terminal (close unnecessary panes)

❌ **Avoid:**
- Sensitive information (API keys, tokens, passwords)
- Cluttered screen with multiple windows
- Tiny text that's hard to read
- Empty/placeholder data

### Before Capturing

1. Start Mission Control: `cf` or `python3 -m tools.cli`
2. Have at least 2-3 active builds running
3. Make sure daemon is running for monitoring status
4. Clean up terminal (close other programs)
5. Set terminal to good size (120x40+)

### Example Session

```bash
# Terminal 1: Start some builds
claude --headless "Build a weather app"
claude --headless "Build a todo list"

# Terminal 2: Start daemon for monitoring
python3 -m tools.evolution.daemon start

# Terminal 3: Launch Mission Control
cf

# Now take screenshots!
```

## File Naming Convention

Use lowercase with hyphens:
- `mission-control-overview.png`
- `conversation-tab.png`
- `builds-tab.png`
- `directory-tab.png`

**NOT:**
- ~~`MissionControl.png`~~
- ~~`Conversation_Tab.png`~~
- ~~`screenshot1.png`~~

## Image Format

- **Format:** PNG (for crisp terminal text)
- **Color:** 24-bit RGB
- **Compression:** Optimize for web (use tools like `optipng` or `pngcrush`)

```bash
# Optimize PNG after capture
optipng -o7 mission-control-overview.png
```

## Contributing Screenshots

1. Capture screenshots following above guidelines
2. Optimize images (< 500KB each preferred)
3. Place in this directory
4. Update MISSION_CONTROL.md if paths change
5. Commit and push:

```bash
git add docs/assets/screenshots/*.png
git commit -m "docs: Add Mission Control screenshots"
git push
```

---

**Need help?** Open an issue on GitHub with questions about screenshots!

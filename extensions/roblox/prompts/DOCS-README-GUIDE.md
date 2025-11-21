# Roblox README Guide (Docs Phase)

**📝 DOCUMENTING ROBLOX GAME PROJECT**

You are documenting a Roblox game project, NOT a web app, mobile app, or traditional software.

## README Structure

Generate `README_ROBLOX.md` with the following sections:

### 1. Project Title & Description

```markdown
# [Game Name]

[Brief description of the game - 1-2 sentences]

**Game Type:** Obby with checkpoints and coin shop
**Platform:** Roblox
**Build System:** Rojo

## Features

- ✓ Checkpoint system with progress saving
- ✓ Coin collection and persistence
- ✓ Shop system with purchasable items
- ✓ DataStore integration for data persistence
- ✓ Server-authoritative architecture
- ✓ Secure RemoteEvent handling
```

### 2. Installation

```markdown
## Installation

### Prerequisites

1. **Rojo** (required) - Project build system
   ```bash
   # macOS/Linux
   curl -sSL https://rojo.space/install.sh | bash

   # Windows
   # Download from https://github.com/rojo-rbx/rojo/releases
   ```
   Version: >= 7.0.0

2. **Roblox Studio** (required) - Game runtime
   - Download from https://www.roblox.com/create
   - Sign in with Roblox account

3. **Optional Tools** (recommended for development)
   ```bash
   # Code formatting
   cargo install stylua

   # Linting
   cargo install selene
   ```

### Setup

1. Clone this repository
   ```bash
   git clone [repository-url]
   cd [project-name]
   ```

2. Verify Rojo installation
   ```bash
   rojo --version
   # Should show 7.x or higher
   ```
```

### 3. Build Instructions

```markdown
## Building

### Build Place File

Generate the `.rbxlx` place file:

```bash
rojo build default.project.json -o dist/Game.rbxlx
```

This creates `dist/Game.rbxlx` which can be opened in Roblox Studio.

### Development Workflow (Optional)

For live syncing during development:

1. Start Rojo server
   ```bash
   rojo serve default.project.json
   ```

2. In Roblox Studio:
   - Install Rojo plugin from https://rojo.space/docs/v7/getting-started/installation/
   - Click "Connect" in Rojo plugin
   - Changes to `.lua` files sync automatically

3. Edit code in your favorite editor
4. Changes appear instantly in Studio
```

### 4. Testing Instructions

```markdown
## Testing

### Static Analysis

Run code quality checks:

```bash
# Format check
stylua --check src/

# Lint check
selene src/

# Type check
luau-analyze src/
```

**Note:** If tools not installed, warnings will be logged but build won't fail.

### Unit Tests

Tests use TestEZ framework and live in `src/ServerScriptService/Tests/`.

To run tests:
1. Install TestEZ plugin in Roblox Studio
   - View → Toolbox → Plugins
   - Search "TestEZ" and install

2. Open `dist/Game.rbxlx` in Roblox Studio

3. Run tests via TestEZ plugin
   - View → TestEZ
   - Click "Run All Tests"

Expected output:
- ✓ CheckpointManager (4/4 tests passed)
- ✓ CoinManager (3/3 tests passed)
- ✓ ShopService (3/3 tests passed)

### Manual Testing

1. Open `dist/Game.rbxlx` in Roblox Studio

2. Enable API Services (for DataStore testing):
   - File → Game Settings → Security
   - Enable "Studio Access to API Services"

3. Press **F5** or click **Play** button

4. Test gameplay:
   - [ ] Player spawns at spawn location
   - [ ] Checkpoints save progress (touch checkpoint, reset, verify respawn)
   - [ ] Coins can be collected
   - [ ] Coin balance persists (stop test, play again)
   - [ ] Shop UI opens
   - [ ] Purchases work correctly

See `docs/MANUAL_TEST_CHECKLIST.md` for full test checklist.
```

### 5. Publishing Instructions

```markdown
## Publishing to Roblox

### First-Time Publishing

1. **Test Thoroughly**
   - Run all tests
   - Verify gameplay in Studio
   - Check for errors in Output window

2. **Open Place File**
   - Open `dist/Game.rbxlx` in Roblox Studio

3. **Publish to Roblox**
   - File → Publish to Roblox → Create New Place
   - Set game name and description
   - Choose visibility (Public/Private)
   - Click "Create"

4. **Configure Game Settings**
   - Home → Game Settings
   - Set genre, max players, etc.
   - Enable permissions (e.g., allow copying if desired)
   - Save settings

5. **Test Live**
   - Click "Play" in the game page
   - Verify everything works in live environment
   - Test with friends for multi-player

### Updating Existing Game

1. Build latest version
   ```bash
   rojo build default.project.json -o dist/Game.rbxlx
   ```

2. Open in Studio and test

3. Publish update
   - File → Publish to Roblox → Update Existing Place
   - Select your place
   - Add update notes
   - Publish

**Note:** V1 does not include automated cloud publishing via Roblox Open Cloud API.
```

### 6. Project Structure

```markdown
## Project Structure

```
/
├── default.project.json           # Rojo project configuration
├── dist/                          # Build output
│   └── Game.rbxlx                 # Generated place file
│
├── src/                           # Source code (Luau)
│   ├── ServerScriptService/       # Server-side logic
│   │   ├── GameSystems/           # Core game systems
│   │   │   ├── CheckpointManager.lua
│   │   │   ├── CoinManager.lua
│   │   │   ├── ShopService.lua
│   │   │   └── PlayerDataManager.lua
│   │   └── Tests/                 # TestEZ unit tests
│   │       ├── CheckpointManager.spec.lua
│   │       └── CoinManager.spec.lua
│   │
│   ├── ReplicatedStorage/         # Shared modules (client + server)
│   │   └── Modules/
│   │       ├── PlayerData.lua      # Data structure definitions
│   │       ├── ShopConfig.lua      # Shop items configuration
│   │       └── GameConfig.lua      # Game settings
│   │
│   ├── StarterPlayer/             # Player initialization
│   │   └── StarterPlayerScripts/  # Client-side scripts
│   │       ├── CoinCollector.lua
│   │       └── CheckpointDetector.lua
│   │
│   ├── StarterGui/                # UI elements
│   │   ├── ShopUI/
│   │   ├── CoinDisplay/
│   │   └── StageCounter/
│   │
│   └── Workspace/                 # Game world objects
│       ├── Checkpoints/           # Checkpoint parts
│       ├── Stages/                # Obby stages
│       └── DeathZones/            # Kill parts
│
├── .luaurc                        # Luau type checker config
├── selene.toml                    # Linter config (if present)
├── stylua.toml                    # Formatter config (if present)
└── README_ROBLOX.md               # This file
```
```

### 7. Architecture & Design

```markdown
## Architecture

### Server-Authoritative Design

This game uses a **server-authoritative architecture** for security:

- **Client:** Handles UI, input, visual effects (exploitable)
- **Server:** Handles all critical logic (trusted)

**Example:**
- ✅ Client: "I touched this checkpoint" → Server: Validates & saves progress
- ❌ Client: "Set my checkpoint to 5" → Server: Trusts value (exploitable)

### Key Systems

#### 1. Checkpoint System
- Saves player progress through stages
- Server validates checkpoint touches
- Progress persists via DataStore
- Respawns player at last checkpoint on death

#### 2. Coin System
- Awards coins for collection
- Server calculates all rewards
- Balance persists via DataStore
- Validates all transactions

#### 3. Shop System
- Processes item purchases
- Validates coin balance before deducting
- Prevents duplicate purchases
- Server-authoritative item granting

#### 4. Player Data Management
- Centralized data storage
- DataStore integration with retry logic
- Memory caching for performance
- Graceful error handling

### Security

All RemoteEvents validate input:
- Type checking
- Range validation
- Business logic validation
- Rate limiting

No client values are trusted for critical operations.
```

### 8. Configuration

```markdown
## Configuration

### Game Settings

Edit `src/ReplicatedStorage/Modules/GameConfig.lua`:

```lua
local GameConfig = {
    -- Checkpoint settings
    checkpoints = {
        count = 50,  -- Total number of checkpoints
        saveDelay = 0.5,  -- Minimum time between saves
    },

    -- Coin settings
    coins = {
        maxBalance = 1000000,  -- Maximum coin balance
        defaultReward = 10,  -- Default coin value
    },

    -- Shop settings
    shop = {
        purchaseCooldown = 1,  -- Seconds between purchases
    },
}

return table.freeze(GameConfig)
```

### Shop Items

Edit `src/ReplicatedStorage/Modules/ShopConfig.lua`:

```lua
local ShopConfig = {
    items = {
        ["speed_boost"] = {
            name = "Speed Boost",
            description = "Run 2x faster",
            cost = 100,
            category = "powerup",
        },
        -- Add more items here
    }
}

return table.freeze(ShopConfig)
```
```

### 9. Troubleshooting

```markdown
## Troubleshooting

### Build Issues

**Error: "Rojo not found"**
- Install Rojo: https://rojo.space
- Verify installation: `rojo --version`

**Error: "Invalid project.json"**
- Validate JSON syntax
- Check Rojo documentation for schema

### Studio Issues

**Error: "DataStore request was rejected"**
- Enable Studio Access to API Services
- File → Game Settings → Security → Enable API Services

**Players not spawning**
- Verify spawn location in Workspace
- Check for errors in Output window

### Testing Issues

**Tests won't run**
- Install TestEZ plugin
- Verify tests are in ServerScriptService/Tests/
- Check for syntax errors in test files

**DataStore not persisting**
- Enable API Services in Studio
- In live game: Verify game is published (not just saved locally)

### Performance Issues

**Low FPS in Studio**
- Reduce part count in Workspace
- Optimize scripts (check for tight loops)
- Profile with MicroProfiler

**Server lag with multiple players**
- Check server CPU usage in Developer Console
- Optimize DataStore calls (cache in memory)
- Review event connections (disconnect when not needed)
```

### 10. Contributing & License

```markdown
## Contributing

This project was generated by Context Foundry with the Roblox extension.

To modify:
1. Edit `.lua` files in `src/`
2. Rebuild: `rojo build default.project.json -o dist/Game.rbxlx`
3. Test in Studio
4. Run static analysis: `stylua --check src/ && selene src/`
5. Commit changes

## Credits

- **Generated by:** [Context Foundry](https://github.com/anthropics/context-foundry) Roblox Extension
- **Build System:** [Rojo](https://rojo.space)
- **Testing:** [TestEZ](https://github.com/Roblox/testez)

## License

[Specify license - e.g., MIT, Apache 2.0, etc.]
```

## Additional Documentation Files

### Manual Test Checklist

Create `docs/MANUAL_TEST_CHECKLIST.md`:

```markdown
# Manual Test Checklist

Use this checklist when testing the game manually.

## Spawn & Initialization
- [ ] Player spawns at spawn location (not in mid-air or stuck)
- [ ] Player data loads within 3 seconds
- [ ] Coin UI displays with correct starting balance (usually 0)
- [ ] Stage counter UI displays (shows "Stage 0" or "Stage 1")
- [ ] No errors in Output window on join

## Checkpoint System
- [ ] Player can touch checkpoint (visual feedback recommended)
- [ ] Touching checkpoint saves progress (verify in Output or UI)
- [ ] Resetting character respawns at last checkpoint
- [ ] Death respawns at last checkpoint (not spawn)
- [ ] Checkpoints persist across server joins:
  - Touch checkpoint 3
  - Leave game
  - Rejoin
  - Verify spawn at checkpoint 3
- [ ] Cannot skip checkpoints (if sequential design)

## Coin System
- [ ] Coins are visible in world
- [ ] Touching coin collects it
- [ ] Coin UI updates immediately
- [ ] Collected coins disappear (can't re-collect)
- [ ] Coin balance persists across sessions:
  - Collect 10 coins
  - Leave and rejoin
  - Verify still have 10 coins

## Shop System
- [ ] Shop UI can be opened (button or proximity prompt)
- [ ] Available items display with names, descriptions, prices
- [ ] Can purchase item with sufficient coins
- [ ] Purchase deducts correct coin amount
- [ ] Purchased item appears in inventory or is equipped
- [ ] Cannot purchase with insufficient coins
- [ ] Cannot purchase same item twice (if one-time purchase)

## Data Persistence
- [ ] Progress saves periodically (check Output for save messages)
- [ ] Leaving game triggers save
- [ ] Rejoining restores all data:
  - Checkpoint progress
  - Coin balance
  - Owned items
  - Statistics (if applicable)

## Multi-Player
- [ ] Two players can join simultaneously
- [ ] Each player has independent progress
- [ ] Collecting coin doesn't affect other player
- [ ] Checkpoints work independently per player
- [ ] No data leakage (Player A can't see Player B's data)

## Security & Anti-Cheat
- [ ] Cannot collect coins from far away (test teleporting away)
- [ ] Cannot award self coins via exploits
- [ ] Cannot purchase items without sufficient funds
- [ ] Cannot teleport to unreached checkpoints
- [ ] Rate limiting prevents spam (rapid checkpoint touching)

## Performance
- [ ] Game runs at stable 60 FPS in Studio
- [ ] No lag spikes during gameplay
- [ ] Server performance < 5% CPU (Developer Console)
- [ ] Memory usage stable (no gradual increase)
- [ ] Test with 10+ players (if possible)

## Error Handling
- [ ] DataStore failures don't crash game (check by disabling API Services)
- [ ] Missing data loads with defaults
- [ ] Invalid RemoteEvent payloads don't crash server
- [ ] Corrupted data handled gracefully

## Edge Cases
- [ ] Player leaving mid-save doesn't corrupt data
- [ ] Rapid checkpoint touching doesn't cause issues
- [ ] Purchasing while low on coins doesn't cause negative balance
- [ ] Destroying coin while another player collects it
```

## Docs Phase Checklist

Before completing documentation:

### README Completeness
- [ ] Title and description clear
- [ ] Installation instructions complete
- [ ] Build instructions work
- [ ] Testing instructions accurate
- [ ] Publishing instructions detailed
- [ ] Project structure documented
- [ ] Troubleshooting section helpful

### Additional Docs
- [ ] Manual test checklist created
- [ ] Configuration guide included
- [ ] Architecture explained
- [ ] Security model documented

### Accuracy
- [ ] All commands tested and working
- [ ] All paths correct
- [ ] Version numbers accurate
- [ ] Links not broken

### Clarity
- [ ] Language is clear and concise
- [ ] Steps are numbered and sequential
- [ ] Examples provided where helpful
- [ ] Assumes user is new to Roblox development

---

**Remember:** Users need to understand this is a Roblox game built with Rojo, NOT a web app or traditional software project. Documentation should be Roblox-specific and assume some familiarity with Roblox Studio.

# Roblox Extension Artifact Contract

**Extension:** Roblox
**Version:** 1.0.0
**Context Foundry:** 2.3.0+
**Last Updated:** 2025-11-17

## Primary Artifact

**Type:** Roblox Place File (`.rbxlx`)
**Format:** XML-based Roblox Studio-compatible place file
**Output Location:** `dist/Game.rbxlx`

## Project Structure (Rojo-based)

```
/
├── default.project.json           # Rojo project configuration
├── dist/                          # Build output directory
│   └── Game.rbxlx                 # Generated place file
│
├── src/                           # Source code (Luau)
│   ├── ServerScriptService/       # Server-side logic
│   │   ├── GameSystems/           # Core game systems
│   │   │   ├── CheckpointManager.lua
│   │   │   ├── CoinManager.lua
│   │   │   └── ShopService.lua
│   │   └── Tests/                 # TestEZ unit tests
│   │       ├── CheckpointManager.spec.lua
│   │       └── CoinManager.spec.lua
│   │
│   ├── ReplicatedStorage/         # Shared modules (client + server)
│   │   ├── Modules/
│   │   │   ├── PlayerData.lua
│   │   │   └── ShopConfig.lua
│   │   └── Assets/                # Shared assets
│   │
│   ├── StarterPlayer/             # Player initialization
│   │   ├── StarterPlayerScripts/  # Client-side scripts
│   │   └── StarterCharacterScripts/  # Character scripts
│   │
│   ├── StarterGui/                # UI elements
│   │   └── ShopUI/
│   │       └── ShopFrame.lua
│   │
│   └── Workspace/                 # Game world objects
│       ├── Checkpoints/           # Checkpoint parts
│       └── Stages/                # Obby stages
│
├── README_ROBLOX.md               # Build & test instructions
└── .luaurc                        # Luau type checking configuration
```

## How to Run Locally

### Prerequisites

1. **Install Rojo** (Roblox project management tool)
   ```bash
   # macOS/Linux
   curl -sSL https://rojo.space/install.sh | bash

   # Windows
   # Download from https://github.com/rojo-rbx/rojo/releases
   ```

2. **Install Roblox Studio**
   - Download from https://www.roblox.com/create
   - Sign in with Roblox account

### Build Steps

1. **Build the place file:**
   ```bash
   rojo build default.project.json -o dist/Game.rbxlx
   ```

2. **Open in Roblox Studio:**
   - Double-click `dist/Game.rbxlx` OR
   - Open Roblox Studio → File → Open → Select `dist/Game.rbxlx`

3. **Test the game:**
   - Press **F5** or click the **Play** button
   - Test gameplay mechanics
   - Verify checkpoints, coins, shop functionality

### Development Workflow (Optional)

For live syncing during development:

```bash
# Start Rojo server
rojo serve default.project.json

# In Roblox Studio:
# 1. Install Rojo plugin from https://rojo.space/docs/v7/getting-started/installation/
# 2. Click "Connect" in Rojo plugin
# 3. Changes to .lua files sync automatically
```

## Minimum Toolchain

### Required

| Tool | Version | Purpose | Installation |
|------|---------|---------|--------------|
| **Rojo** | ≥ 7.x (tested with 7.4.0) | Project build system | https://rojo.space |
| **Roblox Studio** | Latest | Testing & publishing | https://www.roblox.com/create |

### Optional (Recommended)

| Tool | Version | Purpose | Installation |
|------|---------|---------|--------------|
| **Stylua** | ≥ 0.20.0 | Code formatting | `cargo install stylua` |
| **Selene** | ≥ 0.27.1 | Linting | `cargo install selene` |
| **luau-analyze** | Latest | Type checking | Included with Roblox Studio |

### Toolchain Version Check

```bash
# Verify Rojo
rojo --version  # Should show 7.x or higher

# Verify optional tools
stylua --version  # 0.20.0 or higher
selene --version  # 0.27.1 or higher
```

## Build Command

**Standard build:**
```bash
rojo build default.project.json -o dist/Game.rbxlx
```

**Watch mode (development):**
```bash
rojo serve default.project.json
# Connect via Rojo plugin in Studio
```

## Test Strategy (V1)

### Static Analysis (Automated)

Run these checks before committing:

```bash
# Format check
stylua --check src/

# Lint check
selene src/

# Type check
luau-analyze src/
```

**Graceful Degradation:** If tools are not installed, warnings are logged but build doesn't fail.

### Unit Tests (Manual - V1)

Tests are written using TestEZ framework and live in `src/ServerScriptService/Tests/`.

**To run tests:**
1. Install [TestEZ plugin](https://github.com/Roblox/testez) in Roblox Studio
2. Open `dist/Game.rbxlx` in Studio
3. Navigate to ServerScriptService → Tests
4. Run tests via TestEZ plugin interface

**Test Coverage Requirements:**
- [ ] CheckpointManager: Save/load checkpoint progress
- [ ] CoinManager: Award coins, deduct coins, persist balance
- [ ] ShopService: Process purchases, validate coin balance

### Manual Test Checklist

After building and opening in Studio, verify:

- [ ] Player spawns at correct location
- [ ] Checkpoints save progress (touch checkpoint, reset, respawn at checkpoint)
- [ ] Death zones reset player to last checkpoint
- [ ] Coins can be collected
- [ ] Coin count displays correctly in UI
- [ ] Shop UI opens and displays items
- [ ] Purchases deduct correct coin amount
- [ ] Purchased items grant correctly
- [ ] DataStore persists data across sessions (in Studio testing mode)

### Future (V2): Automated Runtime Testing

- Headless test runner integration
- Automated gameplay testing
- CI/CD integration

## Deploy Phase (V1)

### What CF Produces

1. **Source code:** Complete Rojo project structure
2. **Build artifact:** `dist/Game.rbxlx` place file
3. **Documentation:** `README_ROBLOX.md` with instructions

### Publishing to Roblox (Manual)

**V1 does NOT automate publishing.** Follow these steps manually:

1. **Open place file:**
   - Open `dist/Game.rbxlx` in Roblox Studio

2. **Test thoroughly:**
   - Use Studio's Test mode (F5) to verify functionality

3. **Publish to Roblox:**
   - File → Publish to Roblox
   - Choose "Create new game" or "Update existing game"
   - Set game name, description, and visibility
   - Configure place settings (max players, genre, etc.)

4. **Post-publishing:**
   - Test in live environment
   - Configure monetization (if applicable)
   - Set up game passes/developer products in Creator Dashboard

### Future (V2): Cloud Publishing

- Roblox Open Cloud API integration
- Automated place upload
- Asset upload automation
- Configuration deployment

## DataStore Expectations (V1)

### What's Implemented

Code implements DataStore layer for data persistence:

```lua
-- Example: CoinManager uses DataStore
local DataStoreService = game:GetService("DataStoreService")
local CoinStore = DataStoreService:GetDataStore("PlayerCoins")

function CoinManager:SaveCoins(player, amount)
    local success, err = pcall(function()
        CoinStore:SetAsync(player.UserId, amount)
    end)
    return success
end
```

### Testing in Studio

DataStore works in Studio **Test Mode** with limitations:

- **Enable Studio Access:**
  - File → Game Settings → Security → Enable Studio Access to API Services

- **Limitations:**
  - Data only persists within same Studio session
  - Throttling limits apply
  - Use `DataStoreService:GetDataStore()` (not `GetGlobalDataStore()`)

### Production DataStore

For live games, DataStore automatically persists to Roblox cloud:

- Data persists across server shutdowns
- Automatic scaling and redundancy
- Rate limits apply (see: https://create.roblox.com/docs/cloud-services/data-stores)

**Best Practices (Implemented):**
- ✅ Use `UpdateAsync` for atomic operations
- ✅ Validate all data before saving
- ✅ Handle errors gracefully (pcall)
- ✅ Implement retry logic for transient failures
- ✅ Never trust client-supplied data

### V1 Scope

- DataStore implementation: **YES**
- Studio testing support: **YES**
- Production cloud setup: **Automatic** (no manual config needed)
- External database integration: **NO** (not in V1)

## Output File Locations

| File | Location | Description |
|------|----------|-------------|
| **Source code** | `src/**/*.lua` | All Luau scripts |
| **Rojo config** | `default.project.json` | Project structure definition |
| **Built place** | `dist/Game.rbxlx` | Playable place file |
| **Documentation** | `README_ROBLOX.md` | How to build, test, publish |
| **Type config** | `.luaurc` | Luau analyzer settings |

## Build Artifacts (Example)

After running `rojo build`:

```
dist/
└── Game.rbxlx              # 500KB - 5MB (depends on assets)
```

**Note:** `.rbxlx` files are XML-based and can be version controlled, but they're generated artifacts. Only commit source code (`src/`) and Rojo config.

## Project Type Variants

The Roblox extension supports these project types:

| Project Type | Description | Detection |
|--------------|-------------|-----------|
| **roblox-game** | Full Roblox game | `default.project.json` + game structure |
| **roblox-plugin** | Roblox Studio plugin | `plugin.lua` in root |
| **roblox-library** | Shared module/library | ModuleScript structure |

**V1 Focus:** `roblox-game` with Rojo workflow

## Constraints & Limitations

### V1 Constraints

- **Must use Rojo:** Projects must be Rojo-based (not raw `.rbxl` files)
- **Must support offline play:** Game logic works in Studio Test mode
- **Server-authoritative:** All critical logic (coins, purchases, checkpoints) runs on server
- **Luau only:** No Roblox-TS support in V1 (TypeScript transpiled to Luau)

### V1 Out of Scope

- ❌ Roblox Open Cloud API (publishing, asset upload)
- ❌ Roblox-TS projects (TypeScript support)
- ❌ Wally dependency management
- ❌ Automated headless testing
- ❌ External database integration
- ❌ Asset pipeline automation

### Future Versions

V2+ may include:
- Roblox-TS support
- Wally package management
- Automated cloud publishing
- Advanced testing frameworks
- Asset management workflows

## Compatibility

### Roblox Studio Versions

Tested with:
- Roblox Studio (Windows/macOS): Latest production release

### Rojo Compatibility

- Rojo 7.x: **Full support**
- Rojo 6.x: **May work** (not tested)
- Rojo 0.5.x: **Not supported** (legacy version)

### Luau Language

- Type annotations: **Recommended**
- Strict mode: **Enabled** (via `.luaurc`)
- Modern syntax: **Yes** (for loops, continue, etc.)

## Example README (Generated)

Every generated project includes `README_ROBLOX.md`:

```markdown
# [Game Name]

Roblox obby game with checkpoints and coin shop.

## Installation

1. Install Rojo: https://rojo.space
2. Clone this repository

## Build

```bash
rojo build default.project.json -o dist/Game.rbxlx
```

## Open & Test

1. Open `dist/Game.rbxlx` in Roblox Studio
2. Press Play (F5) to test

## Run Tests

1. Install TestEZ plugin in Studio
2. Open Tests folder in ServerScriptService
3. Run via TestEZ plugin

## Publish to Roblox

1. File → Publish to Roblox
2. Create new place OR update existing
3. Configure settings and publish
```

## Contract Checklist Summary

✅ **Primary artifact:** `.rbxlx` place file
✅ **Run locally:** Open in Roblox Studio, press F5
✅ **Minimum toolchain:** Rojo ≥7.x, Roblox Studio (latest)
✅ **Deploy phase:** Build to `dist/`, document manual publishing
✅ **Output location:** `dist/Game.rbxlx`
✅ **DataStore:** Implemented with Studio testing support
✅ **Test strategy:** Static analysis + manual TestEZ tests
✅ **Constraints:** Rojo-based, server-authoritative, Luau only

---

**Questions or issues?** See `/extensions/roblox/README.md` or file an issue.

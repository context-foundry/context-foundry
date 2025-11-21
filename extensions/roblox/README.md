# Roblox Extension for Context Foundry

**Version:** 1.0.0
**Context Foundry:** 2.3.0+

Enables Context Foundry to build Roblox games with Rojo workflow support, security-focused patterns, and server-authoritative architecture.

## Features

- 🎮 **Roblox Project Detection** - Automatically detects Rojo-based and placefile projects
- 🏗️ **Server-Authoritative Architecture** - Enforces secure, server-side game logic
- 🔒 **Security-Focused** - RemoteEvent validation, anti-cheat patterns, exploit prevention
- 📦 **Obby Pattern Library** - Ready-to-use checkpoint, coin, and shop systems
- 🧪 **Test Integration** - TestEZ framework, static analysis (Stylua, Selene, Luau)
- 📝 **Roblox-Specific Docs** - Generates README with Rojo build instructions

## Quick Start

### 1. Install Extension

The extension is already included with Context Foundry 2.3.0+. No additional installation needed.

### 2. Bootstrap Patterns

Import Roblox patterns into the global codex:

```bash
python scripts/bootstrap_roblox_patterns.py
```

### 3. Verify Installation

Run the smoke test:

```bash
python tools/run_extension_smoke_test.py --extension roblox
```

Expected output: ✅ Smoke test PASSED

### 4. Create a Roblox Game

```bash
cd /path/to/new/game
echo '{"name": "MyObby"}' > default.project.json
mkdir -p src/ServerScriptService

cf build "Create an obby game with 10 stages, checkpoints, coins, and a shop"
```

## What Gets Generated

Context Foundry with the Roblox extension generates:

- **Rojo Project Structure** - Complete `src/` directory layout
- **Server-Side Systems:**
  - `CheckpointManager.lua` - Checkpoint saving and respawning
  - `CoinManager.lua` - Coin awards, balance, persistence
  - `ShopService.lua` - Purchase validation and item granting
  - `PlayerDataManager.lua` - DataStore integration with retry logic
- **Client Scripts** - Coin collection, UI controllers
- **Configuration** - `ShopConfig.lua`, `GameConfig.lua`
- **Build Artifact** - `dist/Game.rbxlx` (Roblox Studio place file)
- **Tests** - TestEZ unit tests for all systems
- **Documentation** - `README_ROBLOX.md` with build/test/publish instructions

## Project Detection

The extension automatically detects Roblox projects by checking for:

1. **Primary:** Rojo configuration (`default.project.json` or `*.project.json`)
2. **Secondary:** Placefile (`.rbxl` or `.rbxlx` in root)

When detected, Context Foundry:
- Activates Roblox-specific prompts in all phases
- Uses Luau coding standards (not JavaScript/Python)
- Enforces server-authoritative architecture
- Applies security validation patterns
- Generates Rojo-compatible project structure

## Extension Architecture

### Pattern Library

Located in `patterns/roblox-expertise.json`:

- **obby-checkpoints-coin-shop** - Complete obby game pattern
- **roblox-module-structure** - ModuleScript organization
- **roblox-datastore-best-practices** - DataStore patterns
- **roblox-remote-events-security** - Security validation

### Phase-Specific Prompts

Located in `prompts/`:

- `SCOUT-PROJECT-ASSESSMENT.md` - Project analysis with security checks
- `ARCHITECT-GAME-SYSTEMS.md` - Server-authoritative design
- `BUILDER-LUAU-BEST-PRACTICES.md` - Luau coding standards + security
- `TESTER-TEST-STRATEGY.md` - Static analysis + TestEZ + manual testing
- `DOCS-README-GUIDE.md` - Roblox-specific documentation

### Template Project

Located in `templates/basic-obby/`:

Complete reference implementation of an obby game with:
- Checkpoint system
- Coin collection
- Shop with purchases
- DataStore persistence
- Security validation

## Security Features

The Roblox extension enforces critical security patterns:

### 1. RemoteEvent Validation

All RemoteEvent handlers validate:
- **Type** - Is the data the expected type?
- **Range** - Is the value within acceptable bounds?
- **Business Logic** - Does the request make sense?
- **Rate Limiting** - Is the client spamming?

### 2. Server Authority

- Client sends INTENT ("I touched this checkpoint")
- Server validates and calculates state changes
- Client NEVER directly sets critical values (coins, checkpoints, items)

### 3. Anti-Cheat

- Distance validation for coin collection
- Checkpoint position verification
- Balance checks before purchases
- Suspicious activity logging

## Testing

### Unit Tests

Run extension tests:

```bash
cd extensions/roblox
pytest tests/
```

### Smoke Test

Quick validation:

```bash
python tools/run_extension_smoke_test.py --extension roblox
```

### Generated Project Tests

Generated games include:
- Static analysis (Stylua, Selene, Luau-analyze)
- TestEZ unit tests
- Manual test checklist

## Configuration

### Shop Items

Edit `src/ReplicatedStorage/Modules/ShopConfig.lua` in generated projects:

```lua
local ShopConfig = {
    items = {
        ["speed_boost"] = {
            name = "Speed Boost",
            description = "Run 2x faster",
            cost = 100,
            category = "powerup",
        },
        -- Add more items
    }
}
```

### Game Settings

Edit `src/ReplicatedStorage/Modules/GameConfig.lua`:

```lua
local GameConfig = {
    checkpoints = {
        count = 50,
        saveDelay = 0.5,
    },
    coins = {
        maxBalance = 1000000,
        defaultReward = 10,
    },
}
```

## Building & Publishing

### Build

```bash
rojo build default.project.json -o dist/Game.rbxlx
```

### Test in Studio

1. Open `dist/Game.rbxlx` in Roblox Studio
2. Enable API Services: File → Game Settings → Security → Enable Studio Access to API Services
3. Press Play (F5) to test

### Publish

1. File → Publish to Roblox
2. Create new place or update existing
3. Configure game settings
4. Publish

## Troubleshooting

### Extension Not Detected

```bash
# Verify extension exists
ls extensions/roblox/detector.py

# Run smoke test
python tools/run_extension_smoke_test.py --extension roblox
```

### Detection Not Working

```bash
# Verify Rojo config exists
ls default.project.json

# Test detection manually
python -c "
from pathlib import Path
import sys
sys.path.insert(0, 'extensions')
from roblox.detector import detect_roblox_project
result = detect_roblox_project(Path('.'))
print(result)
"
```

### Build Errors

- **"Rojo not found"** - Install Rojo: https://rojo.space
- **"DataStore request rejected"** - Enable API Services in Studio settings
- **"Tests failing"** - Check TestEZ plugin installed, verify test files exist

## Advanced Usage

### Custom Patterns

Add new patterns to `patterns/roblox-expertise.json` and re-run bootstrap:

```bash
python scripts/bootstrap_roblox_patterns.py
```

### Development Workflow

1. Create Rojo project
2. Start Rojo server: `rojo serve default.project.json`
3. Connect Rojo plugin in Studio
4. Edit `.lua` files - changes sync automatically
5. Test in Studio

### Extending the Extension

See `docs/EXTENSION_DEVELOPMENT_GUIDE.md` for creating additional extensions.

## Version Compatibility

| Component | Version | Required |
|-----------|---------|----------|
| Context Foundry | ≥ 2.3.0 | ✅ Yes |
| Rojo | ≥ 7.0.0 | ✅ Yes |
| Roblox Studio | Latest | ✅ Yes |
| Stylua | ≥ 0.20.0 | ⚠️ Optional |
| Selene | ≥ 0.27.0 | ⚠️ Optional |
| luau-analyze | Latest | ⚠️ Optional |

## Contributing

### Adding Patterns

1. Edit `patterns/roblox-expertise.json`
2. Run `python scripts/bootstrap_roblox_patterns.py`
3. Test with smoke test
4. Submit PR

### Reporting Issues

File issues at: https://github.com/anthropics/context-foundry/issues

Tag with `extension:roblox`

## Resources

- **Rojo Documentation:** https://rojo.space/docs
- **Roblox Creator Docs:** https://create.roblox.com/docs
- **TestEZ:** https://github.com/Roblox/testez
- **Luau:** https://luau-lang.org/
- **Context Foundry Docs:** https://code.claude.com/docs

## License

Same as Context Foundry (see main repository LICENSE)

## Credits

- **Built with:** Context Foundry 2.3.0
- **Rojo:** Roblox project management
- **TestEZ:** Roblox unit testing framework
- **Pattern Library:** Community-contributed best practices

---

**Generated with ❤️ by the Context Foundry team**

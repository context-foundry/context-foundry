# Basic Obby Template

A production-ready Roblox obby (obstacle course) game template with checkpoint system, coin collection, and shop functionality.

## Features

- **Checkpoint System**: Server-authoritative checkpoint saving with respawn handling
- **Coin Economy**: Secure coin collection with distance validation (anti-cheat)
- **Shop System**: Purchase powerups and items with rate limiting and validation
- **Data Persistence**: DataStore integration with retry logic and auto-save
- **UI Components**: Coin display, stage counter, and shop interface
- **Test Suite**: Comprehensive TestEZ unit tests for all game systems
- **Security-First**: Server-authoritative architecture, RemoteEvent validation

## Prerequisites

- [Rojo](https://rojo.space/) >= 7.0.0
- [TestEZ](https://github.com/Roblox/testez) (for running tests in Studio)
- [Stylua](https://github.com/JohnnyMorganz/StyLua) (optional, for code formatting)
- [Selene](https://kampfkarren.github.io/selene/) (optional, for linting)

## Quick Start

### 1. Install Rojo

```bash
# Using Foreman (recommended)
foreman install

# Or download from https://github.com/roblox/rojo/releases
```

### 2. Build the Project

```bash
# Build to a place file
rojo build default.project.json -o dist/Game.rbxlx

# Or serve for live sync during development
rojo serve default.project.json
```

### 3. Open in Roblox Studio

1. Open Roblox Studio
2. File > Open from File > Select `dist/Game.rbxlx`
3. Play test to verify everything works

## Project Structure

```
basic-obby/
├── default.project.json          # Rojo project file
├── README_ROBLOX.md             # This file
├── .luaurc                       # Luau type checking config
│
├── src/
│   ├── ServerScriptService/
│   │   ├── GameSystems/
│   │   │   ├── PlayerDataManager.lua    # DataStore management
│   │   │   ├── CheckpointManager.lua    # Checkpoint system
│   │   │   ├── CoinManager.lua          # Coin economy
│   │   │   └── ShopService.lua          # Shop purchases
│   │   │
│   │   └── Tests/
│   │       ├── CheckpointManager.spec.lua
│   │       ├── CoinManager.spec.lua
│   │       └── ShopService.spec.lua
│   │
│   ├── ReplicatedStorage/
│   │   └── Modules/
│   │       ├── PlayerData.lua      # Type definitions
│   │       ├── ShopConfig.lua      # Shop items config
│   │       └── GameConfig.lua      # Game settings
│   │
│   ├── StarterPlayer/
│   │   └── StarterPlayerScripts/
│   │       └── CoinCollector.lua   # Client coin detection
│   │
│   ├── StarterGui/
│   │   ├── CoinDisplay/
│   │   │   └── CoinLabel.lua       # Coin UI
│   │   ├── StageCounter/
│   │   │   └── StageLabel.lua      # Stage UI
│   │   └── ShopUI/
│   │       └── ShopFrame.lua       # Shop UI
│   │
│   └── Workspace/
│       └── (Place your obby parts here)
```

## Development Workflow

### Live Sync with Rojo

For real-time code syncing during development:

```bash
# Terminal 1: Start Rojo server
rojo serve default.project.json

# Terminal 2 (or Roblox Studio):
# 1. Open Roblox Studio
# 2. Install Rojo plugin from https://rojo.space/docs/installation/
# 3. Click "Connect" in the Rojo plugin
# 4. Make code changes in your editor - they'll sync to Studio automatically
```

### Running Tests

#### In Roblox Studio (Recommended)

1. Install [TestEZ plugin](https://github.com/Roblox/testez)
2. Open the project in Studio
3. Click **"Run Tests"** in the TestEZ plugin
4. View test results in the Output window

#### Command Line (Static Analysis)

```bash
# Type checking
luau-analyze src/

# Linting
selene src/

# Code formatting
stylua src/ --check
```

### Adding New Features

1. **Create Lua files** in appropriate directories
2. **Update default.project.json** if adding new RemoteEvents or Workspace objects
3. **Add tests** in `src/ServerScriptService/Tests/`
4. **Run tests** before committing

### Security Best Practices

This template follows server-authoritative architecture:

- **NEVER trust client input** - Always validate RemoteEvent payloads
- **Server calculates rewards** - Client only reports events (e.g., coin touch)
- **Validate distances** - Check player proximity for coin collection
- **Rate limiting** - Prevent spam requests (e.g., shop purchases)
- **Type checking** - Use Luau type annotations for safety

## Configuration

### Game Settings

Edit `src/ReplicatedStorage/Modules/GameConfig.lua`:

```lua
{
    MAX_CHECKPOINTS = 10,
    AUTO_SAVE_INTERVAL = 300,  -- Seconds
    -- Add your settings here
}
```

### Shop Items

Edit `src/ReplicatedStorage/Modules/ShopConfig.lua`:

```lua
items = {
    ["item_id"] = {
        name = "Item Name",
        description = "What it does",
        cost = 100,
        category = "powerup",
    }
}
```

## Building the Obby Course

1. **Create checkpoint parts** in Workspace
2. **Add IntValue named "CheckpointNumber"** to each checkpoint
3. **Set values** 1, 2, 3... for checkpoint order
4. **Add TouchEnded event** in a script:

```lua
local CheckpointManager = require(game.ServerScriptService.GameSystems.CheckpointManager)

checkpointPart.Touched:Connect(function(hit)
    local player = game.Players:GetPlayerFromCharacter(hit.Parent)
    if player then
        local checkpointNum = checkpointPart.CheckpointNumber.Value
        CheckpointManager:SaveCheckpoint(player, checkpointNum)
    end
end)
```

## Publishing to Roblox

### Option 1: Manual Upload

1. Build: `rojo build default.project.json -o dist/Game.rbxlx`
2. Open `dist/Game.rbxlx` in Roblox Studio
3. File > Publish to Roblox
4. Select existing place or create new

### Option 2: Rojo Deploy (for updates)

If you have an existing published game:

```bash
# Configure authentication
rojo upload default.project.json --place_id YOUR_PLACE_ID --cookie .roblosecurity
```

**Security Warning**: Never commit `.roblosecurity` file to version control!

## Troubleshooting

### "Module not found" errors

- Ensure Rojo built correctly: `rojo build default.project.json -o dist/Game.rbxlx`
- Check `default.project.json` has correct `$path` entries
- Verify module hierarchy matches `require()` paths

### Tests failing

- Check that PlayerDataManager is initialized before other systems
- Ensure mock player objects have required fields (Name, UserId)
- Verify RemoteEvents exist in ReplicatedStorage.Remotes

### Data not saving

- Enable Studio API Services: Game Settings > Security > Enable Studio Access to API Services
- Check Output window for DataStore errors
- Verify DataStore name doesn't conflict with existing data

### UI not appearing

- Check ScreenGui ResetOnSpawn is false (or you'll lose UI on respawn)
- Verify LocalScripts are running (check Output for errors)
- Ensure RemoteEvents are properly connected

## Resources

- [Rojo Documentation](https://rojo.space/docs/)
- [Luau Documentation](https://luau-lang.org/)
- [TestEZ Documentation](https://roblox.github.io/testez/)
- [Roblox DevHub](https://create.roblox.com/docs)
- [DataStore Best Practices](https://create.roblox.com/docs/cloud-services/data-stores)

## Support

For issues with the template:
1. Check this README and troubleshooting section
2. Review test files for usage examples
3. Consult Roblox DevHub documentation

For Context Foundry Roblox extension issues:
- See `extensions/roblox/README.md` in the Context Foundry repository

## License

This template is provided as part of the Context Foundry Roblox extension.
Modify and use as needed for your own Roblox games.

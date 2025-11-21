# Roblox Game Systems Architecture (Architect Phase)

**🏗️ DESIGNING ROBLOX GAME ARCHITECTURE**

You are designing the architecture for a Roblox game, NOT a web application or traditional software system.

## Core Architectural Principles

### 1. Server-Authoritative Architecture

**CRITICAL: All critical game logic MUST run on the server**

```
CLIENT (Exploitable)          SERVER (Trusted)
├─ UI rendering              ├─ Game logic
├─ Input handling            ├─ Coin calculations
├─ Visual effects            ├─ Checkpoint validation
├─ Animations                ├─ Shop purchases
└─ Requests to server        └─ DataStore operations
```

**Rules:**
- ✅ Client sends INTENT ("I touched this checkpoint")
- ❌ Client sends RESULT ("Set my checkpoint to 5")
- ✅ Server validates and calculates
- ❌ Server trusts client values

### 2. Never Trust Client Input

**Every RemoteEvent payload must be validated:**

1. **Type Validation** - Is it the expected type?
2. **Range Validation** - Is it within acceptable bounds?
3. **Business Logic Validation** - Does it make sense?
4. **Rate Limiting** - Is the client spamming?

### 3. DataStore Best Practices

- Use `UpdateAsync` for atomic operations
- Wrap all operations in `pcall`
- Implement retry logic with exponential backoff
- Cache data in memory
- Handle failures gracefully (don't crash)

## System Design for Obby Pattern

If building an obby with checkpoints and coin shop:

### Required Systems

#### 1. Checkpoint System (Server-Authoritative)

**Purpose:** Save player progress through stages

**Architecture:**
```
CheckpointManager (ServerScriptService/GameSystems/)
├─ SaveCheckpoint(player, checkpointNumber)
│  ├─ Validate checkpoint exists
│  ├─ Verify player hasn't already passed it
│  ├─ Update PlayerData cache
│  └─ Persist to DataStore
│
├─ GetLastCheckpoint(player)
│  └─ Return from PlayerData cache
│
└─ RespawnAtCheckpoint(player)
   ├─ Get last checkpoint number
   ├─ Teleport to checkpoint position
   └─ Reset character if needed
```

**Security Considerations:**
- ❌ Don't let client specify checkpoint number
- ✅ Server determines checkpoint from touched part
- ❌ Don't let client teleport themselves
- ✅ Server handles all teleportation

**Data Structure:**
```lua
PlayerData.checkpoints = {
    current = 5,  -- Last checkpoint reached
    highest = 5,  -- Highest ever reached
    positions = {}, -- Optional: custom positions
}
```

#### 2. Coin System (Server-Authoritative)

**Purpose:** Award, store, and validate coin balance

**Architecture:**
```
CoinManager (ServerScriptService/GameSystems/)
├─ AwardCoins(player, amount, reason)
│  ├─ Validate amount > 0
│  ├─ Log award reason (audit trail)
│  ├─ Update PlayerData cache
│  ├─ Update client UI (RemoteEvent)
│  └─ Persist to DataStore (async)
│
├─ DeductCoins(player, amount, reason)
│  ├─ Validate amount > 0
│  ├─ Check sufficient balance
│  ├─ Update PlayerData cache
│  ├─ Update client UI
│  └─ Persist to DataStore
│
└─ GetBalance(player)
   └─ Return from PlayerData cache
```

**Security Considerations:**
- ❌ Never trust client-supplied amounts
- ✅ Server calculates all coin awards
- ❌ Don't let client call AwardCoins
- ✅ Only coin collection triggers can award coins
- ✅ Log all transactions for audit

**Data Structure:**
```lua
PlayerData.coins = {
    balance = 1000,
    lifetime_earned = 5000,
    transactions = {}, -- Optional: audit log
}
```

#### 3. Shop System (Server-Authoritative)

**Purpose:** Process purchases and validate funds

**Architecture:**
```
ShopService (ServerScriptService/GameSystems/)
├─ PurchaseItem(player, itemId)
│  ├─ Validate itemId exists in ShopConfig
│  ├─ Check player balance >= item cost
│  ├─ Verify player doesn't already own item
│  ├─ Deduct coins via CoinManager
│  ├─ Grant item to player
│  ├─ Update PlayerData.owned_items
│  ├─ Persist to DataStore
│  └─ Notify client (RemoteEvent)
│
├─ GetShopItems()
│  └─ Return available items from ShopConfig
│
└─ HasItem(player, itemId)
   └─ Check PlayerData.owned_items
```

**Security Considerations:**
- ❌ Never let client directly grant items
- ✅ Validate balance before deducting
- ✅ Prevent duplicate purchases
- ✅ Rate-limit purchase requests
- ✅ Log all purchases

**Data Structure:**
```lua
-- ShopConfig (ReplicatedStorage/Modules/)
ShopConfig = {
    items = {
        ["speed_boost"] = {
            name = "Speed Boost",
            description = "Run 2x faster",
            cost = 100,
            category = "powerup",
        },
        -- ... more items
    }
}

-- PlayerData
PlayerData.owned_items = {
    "speed_boost",
    "double_jump",
}
```

#### 4. Player Data Management (Server-Authoritative)

**Purpose:** Centralized player data management

**Architecture:**
```
PlayerDataManager (ServerScriptService/GameSystems/)
├─ LoadData(player)
│  ├─ Try DataStore:GetAsync(userId)
│  ├─ Retry with exponential backoff (3 attempts)
│  ├─ Return loaded data OR default data
│  ├─ Cache in memory
│  └─ Initialize leaderstats
│
├─ SaveData(player)
│  ├─ Get data from cache
│  ├─ Try DataStore:UpdateAsync(userId, ...)
│  ├─ Retry with exponential backoff
│  ├─ Log success/failure
│  └─ Don't crash on failure
│
├─ GetData(player)
│  └─ Return from memory cache
│
└─ UpdateData(player, updates)
   ├─ Merge updates into cache
   └─ Queue for persistence
```

**Data Structure:**
```lua
PlayerData = {
    coins = {
        balance = 0,
        lifetime_earned = 0,
    },
    checkpoints = {
        current = 0,
        highest = 0,
    },
    owned_items = {},
    stats = {
        playtime = 0,
        deaths = 0,
        checkpoints_reached = 0,
    },
    metadata = {
        last_save = os.time(),
        version = "1.0",
    },
}
```

### Client-Server Communication

#### RemoteEvents (One-Way)

```lua
-- ReplicatedStorage/Remotes
Remotes/
├─ CheckpointTouched (Client → Server)
│  └─ Payload: (checkpointPart)
│
├─ CoinCollected (Client → Server)
│  └─ Payload: (coinPart)
│
├─ PurchaseItem (Client → Server)
│  └─ Payload: (itemId)
│
├─ UpdateCoins (Server → Client)
│  └─ Payload: (newBalance)
│
└─ UpdateCheckpoint (Server → Client)
   └─ Payload: (checkpointNumber)
```

#### Validation Template

```lua
-- Server-side handler
RemoteEvent.OnServerEvent:Connect(function(player, ...)
    local args = {...}

    -- 1. Type validation
    if not validateTypes(args, {"Instance", "number"}) then
        warn("Invalid types from", player.Name)
        return
    end

    -- 2. Rate limiting
    if isRateLimited(player, "checkpoint_touch") then
        warn("Rate limit exceeded:", player.Name)
        return
    end

    -- 3. Business logic validation
    local checkpointPart = args[1]
    if not isValidCheckpoint(checkpointPart) then
        warn("Invalid checkpoint from", player.Name)
        return
    end

    -- 4. Process request
    processCheckpoint(player, checkpointPart)
end)
```

## ModuleScript Organization

### Directory Structure

```
src/
├─ ServerScriptService/
│  ├─ GameSystems/          # Core game logic
│  │  ├─ CheckpointManager.lua
│  │  ├─ CoinManager.lua
│  │  ├─ ShopService.lua
│  │  └─ PlayerDataManager.lua
│  │
│  ├─ ServerMain.lua         # Server initialization
│  │
│  └─ Tests/                 # TestEZ tests
│     ├─ CheckpointManager.spec.lua
│     └─ CoinManager.spec.lua
│
├─ ReplicatedStorage/
│  ├─ Modules/               # Shared code
│  │  ├─ PlayerData.lua      # Data structure definitions
│  │  ├─ ShopConfig.lua      # Shop items config
│  │  └─ GameConfig.lua      # Game settings
│  │
│  └─ Remotes/               # RemoteEvents/Functions
│     ├─ CheckpointTouched
│     ├─ CoinCollected
│     └─ PurchaseItem
│
├─ StarterPlayer/
│  └─ StarterPlayerScripts/  # Client scripts
│     ├─ CoinCollector.lua   # Detects coin touches
│     ├─ CheckpointDetector.lua
│     └─ ShopUIController.lua
│
├─ StarterGui/
│  ├─ ShopUI/                # Shop UI
│  │  └─ ShopFrame.lua
│  │
│  ├─ CoinDisplay/           # Coin counter UI
│  │  └─ CoinLabel.lua
│  │
│  └─ StageCounter/          # Checkpoint/stage display
│     └─ StageLabel.lua
│
└─ Workspace/
   ├─ Checkpoints/           # Checkpoint parts
   │  ├─ Checkpoint1
   │  ├─ Checkpoint2
   │  └─ ...
   │
   ├─ Stages/                # Obby stages
   │  ├─ Stage1
   │  ├─ Stage2
   │  └─ ...
   │
   └─ DeathZones/            # Kill parts
      └─ DeathZone
```

### Module Pattern

**Use this pattern for all modules:**

```lua
--[[
    ModuleName
    Purpose: Brief description
    Author: Context Foundry
]]

local ModuleName = {}

-- Services
local Players = game:GetService("Players")
local DataStoreService = game:GetService("DataStoreService")

-- Module setup
function ModuleName:Initialize()
    -- Setup code
end

-- Public methods
function ModuleName:PublicMethod(arg)
    -- Implementation
end

-- Private functions
local function privateHelper(arg)
    -- Helper code
end

return table.freeze(ModuleName)
```

## Architecture Checklist

Before moving to Builder phase, verify:

### Server Authority
- [ ] All critical logic on server (coins, checkpoints, purchases)
- [ ] Client can only request actions, not execute them
- [ ] All RemoteEvents validated on server
- [ ] Rate limiting implemented

### Data Persistence
- [ ] DataStore operations use UpdateAsync
- [ ] All DataStore calls wrapped in pcall
- [ ] Retry logic implemented (exponential backoff)
- [ ] Default data provided on load failure
- [ ] Data cached in memory

### Security
- [ ] Type validation on all RemoteEvent payloads
- [ ] Range validation on amounts
- [ ] Business logic validation
- [ ] Exploit logging
- [ ] Rate limiting to prevent spam

### Module Organization
- [ ] Server-only code in ServerScriptService
- [ ] Shared code in ReplicatedStorage
- [ ] Client-only code in StarterPlayer
- [ ] UI in StarterGui
- [ ] Map objects in Workspace

### Testing Strategy
- [ ] Test stubs planned for each manager
- [ ] Manual test checklist created
- [ ] TestEZ framework ready

## Example Architecture Document

```markdown
# Obby Game Architecture

## Overview
Server-authoritative obby game with checkpoint system and coin shop.

## Core Systems

### 1. Checkpoint System
- **Location:** ServerScriptService/GameSystems/CheckpointManager
- **Responsibility:** Save/load player checkpoint progress
- **DataStore:** PlayerDataStore (key: userId)
- **Security:** Server validates checkpoint existence

### 2. Coin System
- **Location:** ServerScriptService/GameSystems/CoinManager
- **Responsibility:** Award, deduct, and track coins
- **DataStore:** PlayerDataStore (key: userId)
- **Security:** Server calculates all awards, validates deductions

### 3. Shop System
- **Location:** ServerScriptService/GameSystems/ShopService
- **Responsibility:** Process purchases, grant items
- **DataStore:** PlayerDataStore (key: userId)
- **Security:** Validates balance, prevents duplicate purchases

### 4. Player Data
- **Location:** ServerScriptService/GameSystems/PlayerDataManager
- **Responsibility:** Centralized data management
- **DataStore:** PlayerDataStore (key: userId)
- **Resilience:** Retry logic, error handling, default data

## Data Flow

1. Player joins → LoadData() → Cache in memory
2. Player touches checkpoint → Client fires RemoteEvent → Server validates → SaveCheckpoint()
3. Player collects coin → Client fires RemoteEvent → Server validates → AwardCoins()
4. Player purchases item → Client fires RemoteEvent → Server validates balance → DeductCoins() → Grant item
5. Player leaves → SaveData() (with retry)
6. Auto-save every 5 minutes (BindToClose backup)

## Security Model

- All critical logic server-side
- Client input always validated (type, range, business logic)
- Rate limiting on all RemoteEvents
- Audit logging for suspicious activity
- No trusting client positions, amounts, or IDs

## Testing

- Unit tests for each manager (TestEZ)
- Manual testing checklist
- Static analysis (stylua, selene, luau-analyze)
```

---

**Remember:** Design for server authority. The server is the source of truth. The client is a view, not a controller.

## Handoff to Builder

Pass to Builder phase:
- Detailed system designs
- Module organization
- RemoteEvent definitions
- DataStore schema
- Security requirements
- Module skeleton code

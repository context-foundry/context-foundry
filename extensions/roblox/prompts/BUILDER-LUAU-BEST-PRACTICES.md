# Luau Best Practices (Builder Phase)

**⚡ BUILDING ROBLOX GAME CODE**

You are writing Luau code for Roblox, NOT JavaScript, Python, TypeScript, or other languages.

## Language: Luau (Typed Lua)

- File extension: `.lua`
- Syntax: Lua 5.1 with Roblox extensions
- Type system: Gradual typing with type annotations
- Runtime: Roblox engine (NOT Node.js, browser, or Python runtime)

## Critical Security Rules

### 1. ALWAYS Validate RemoteEvent Payloads

**Every RemoteEvent handler MUST validate input:**

```lua
-- ❌ BAD: Trusts client input
CoinRemote.OnServerEvent:Connect(function(player, amount)
    player.leaderstats.Coins.Value = amount
end)

-- ✅ GOOD: Validates input
CoinRemote.OnServerEvent:Connect(function(player, amount)
    -- Type validation
    if type(amount) ~= "number" then
        warn(player.Name, "sent invalid coin amount type")
        return
    end

    -- Range validation
    if amount < 0 or amount > 1000000 then
        warn(player.Name, "sent suspicious coin amount:", amount)
        return
    end

    -- Business logic validation
    local currentBalance = CoinManager:GetBalance(player)
    if amount <= currentBalance then
        CoinManager:SetBalance(player, amount)
    else
        warn(player.Name, "tried to set coins higher than current balance")
    end
end)
```

**Validation Template:**

```lua
local function validateRemoteInput(player, expectedTypes, ...)
    local args = {...}

    -- Check argument count
    if #args ~= #expectedTypes then
        warn(player.Name, "wrong number of arguments")
        return false
    end

    -- Check each type
    for i, expectedType in ipairs(expectedTypes) do
        local actualType = typeof(args[i])
        if actualType ~= expectedType then
            warn(player.Name, "argument", i, "expected", expectedType, "got", actualType)
            return false
        end
    end

    return true
end

-- Usage
PurchaseRemote.OnServerEvent:Connect(function(player, itemId, quantity)
    if not validateRemoteInput(player, {"string", "number"}, itemId, quantity) then
        return
    end

    -- Process purchase
    ShopService:Purchase(player, itemId, quantity)
end)
```

### 2. Server-Authoritative Logic

**Server calculates, client observes:**

```lua
-- ❌ BAD: Client tells server the result
-- Client: CoinRemote:FireServer(100) -- "Give me 100 coins"

-- ✅ GOOD: Client sends intent, server calculates
-- Client: CoinCollectedRemote:FireServer(coinPart)
-- Server validates and calculates reward

-- Server:
CoinCollectedRemote.OnServerEvent:Connect(function(player, coinPart)
    -- Validate it's actually a coin
    if not coinPart or not coinPart:IsA("BasePart") then
        return
    end

    if not coinPart:FindFirstChild("CoinValue") then
        return
    end

    -- Validate player is close enough (anti-cheat)
    local character = player.Character
    if not character then return end

    local distance = (character:GetPivot().Position - coinPart.Position).Magnitude
    if distance > 20 then  -- Max collect distance
        warn(player.Name, "tried to collect coin from too far away")
        return
    end

    -- Server determines reward
    local coinValue = coinPart.CoinValue.Value
    CoinManager:AwardCoins(player, coinValue, "coin_collection")

    -- Destroy coin so others can't collect it
    coinPart:Destroy()
end)
```

### 3. Never Trust Client Positions/Teleportation

```lua
-- ❌ BAD: Client can teleport themselves
TeleportRemote.OnServerEvent:Connect(function(player, position)
    player.Character:PivotTo(CFrame.new(position))
end)

-- ✅ GOOD: Server controls teleportation
local function respawnAtCheckpoint(player, checkpointNumber)
    -- Server validates checkpoint exists
    local checkpoint = workspace.Checkpoints:FindFirstChild("Checkpoint" .. checkpointNumber)
    if not checkpoint then
        warn("Invalid checkpoint:", checkpointNumber)
        return
    end

    -- Server validates player has reached this checkpoint
    local playerData = PlayerDataManager:GetData(player)
    if checkpointNumber > playerData.checkpoints.current then
        warn(player.Name, "tried to teleport to unreached checkpoint")
        return
    end

    -- Server performs teleportation
    local character = player.Character
    if character then
        character:PivotTo(checkpoint.CFrame + Vector3.new(0, 5, 0))
    end
end
```

## Luau Coding Standards

### Type Annotations

**Use type annotations for better IDE support and type checking:**

```lua
-- Simple types
local coins: number = 100
local playerName: string = "Player1"
local isActive: boolean = true

-- Function signatures
local function calculateReward(baseAmount: number, multiplier: number): number
    return baseAmount * multiplier
end

-- Complex types
type PlayerData = {
    coins: {
        balance: number,
        lifetime_earned: number,
    },
    checkpoints: {
        current: number,
        highest: number,
    },
    owned_items: {string},
}

local function loadPlayerData(userId: number): PlayerData
    -- Implementation
end

-- Optional types
local function findPlayer(name: string): Player?
    return Players:FindFirstChild(name)
end
```

### Module Pattern

**All modules should follow this pattern:**

```lua
--[[
    CheckpointManager
    Manages player checkpoint progress

    Methods:
        SaveCheckpoint(player: Player, checkpointNumber: number): boolean
        GetLastCheckpoint(player: Player): number
        RespawnAtCheckpoint(player: Player): ()

    Author: Context Foundry
    Version: 1.0.0
]]

local CheckpointManager = {}

-- Services (cached at module level)
local Players = game:GetService("Players")
local RunService = game:GetService("RunService")

-- Dependencies
local PlayerDataManager = require(script.Parent.PlayerDataManager)

-- Constants
local MAX_CHECKPOINTS = 50
local CHECKPOINT_SAVE_DELAY = 0.5

-- Private state
local lastCheckpointTime = {}

-- Public methods
function CheckpointManager:SaveCheckpoint(player: Player, checkpointNumber: number): boolean
    assert(typeof(player) == "Instance" and player:IsA("Player"), "Invalid player")
    assert(type(checkpointNumber) == "number", "Invalid checkpoint number")

    -- Validate checkpoint range
    if checkpointNumber < 1 or checkpointNumber > MAX_CHECKPOINTS then
        warn("Checkpoint number out of range:", checkpointNumber)
        return false
    end

    -- Rate limiting
    local lastTime = lastCheckpointTime[player.UserId] or 0
    if tick() - lastTime < CHECKPOINT_SAVE_DELAY then
        return false -- Too soon
    end
    lastCheckpointTime[player.UserId] = tick()

    -- Update player data
    local data = PlayerDataManager:GetData(player)
    if checkpointNumber > data.checkpoints.current then
        data.checkpoints.current = checkpointNumber
        data.checkpoints.highest = math.max(data.checkpoints.highest, checkpointNumber)

        -- Notify client
        local updateEvent = game.ReplicatedStorage.Remotes.UpdateCheckpoint
        updateEvent:FireClient(player, checkpointNumber)

        return true
    end

    return false
end

function CheckpointManager:GetLastCheckpoint(player: Player): number
    local data = PlayerDataManager:GetData(player)
    return data.checkpoints.current
end

function CheckpointManager:RespawnAtCheckpoint(player: Player): ()
    local checkpointNumber = self:GetLastCheckpoint(player)
    local checkpoint = workspace.Checkpoints:FindFirstChild("Checkpoint" .. checkpointNumber)

    if checkpoint and player.Character then
        player.Character:PivotTo(checkpoint.CFrame + Vector3.new(0, 5, 0))
    end
end

-- Private helper functions
local function validateCheckpointExists(checkpointNumber: number): boolean
    return workspace.Checkpoints:FindFirstChild("Checkpoint" .. checkpointNumber) ~= nil
end

-- Return frozen table
return table.freeze(CheckpointManager)
```

### DataStore Pattern

**Always use pcall and retry logic:**

```lua
local DataStoreService = game:GetService("DataStoreService")
local PlayerDataStore = DataStoreService:GetDataStore("PlayerData")

local MAX_RETRIES = 3
local RETRY_DELAY = 2

local function loadPlayerData(userId: number): PlayerData
    for attempt = 1, MAX_RETRIES do
        local success, result = pcall(function()
            return PlayerDataStore:GetAsync(tostring(userId))
        end)

        if success then
            -- Return data or default
            return result or getDefaultPlayerData()
        else
            warn("DataStore error (attempt", attempt, "):", result)
            if attempt < MAX_RETRIES then
                task.wait(RETRY_DELAY * attempt) -- Exponential backoff
            end
        end
    end

    -- All retries failed - return default data
    warn("Failed to load data for", userId, "- using defaults")
    return getDefaultPlayerData()
end

local function savePlayerData(userId: number, data: PlayerData): boolean
    for attempt = 1, MAX_RETRIES do
        local success, result = pcall(function()
            PlayerDataStore:UpdateAsync(tostring(userId), function(oldData)
                -- Merge with existing data to prevent overwrites
                return data
            end)
        end)

        if success then
            return true
        else
            warn("DataStore save error (attempt", attempt, "):", result)
            if attempt < MAX_RETRIES then
                task.wait(RETRY_DELAY * attempt)
            end
        end
    end

    warn("Failed to save data for", userId)
    return false
end

-- Save on player leaving (with BindToClose backup)
Players.PlayerRemoving:Connect(function(player)
    savePlayerData(player.UserId, PlayerDataManager:GetData(player))
end)

game:BindToClose(function()
    -- Save all player data on server shutdown
    for _, player in ipairs(Players:GetPlayers()) do
        savePlayerData(player.UserId, PlayerDataManager:GetData(player))
    end
end)
```

### Error Handling

**Use pcall for operations that can fail:**

```lua
-- ❌ BAD: Crash on error
local data = DataStore:GetAsync(userId)

-- ✅ GOOD: Handle errors gracefully
local success, data = pcall(function()
    return DataStore:GetAsync(userId)
end)

if success then
    print("Loaded data:", data)
else
    warn("Failed to load data:", data) -- 'data' is the error message
    -- Use default data
    data = getDefaultData()
end
```

### Performance Best Practices

```lua
-- ❌ BAD: Calls GetChildren in loop
while true do
    for _, player in pairs(game.Players:GetPlayers()) do
        for _, part in pairs(workspace:GetChildren()) do
            -- Expensive
        end
    end
    task.wait(1)
end

-- ✅ GOOD: Caches results
local workspaceParts = workspace:GetChildren()

workspace.ChildAdded:Connect(function(child)
    table.insert(workspaceParts, child)
end)

workspace.ChildRemoved:Connect(function(child)
    local index = table.find(workspaceParts, child)
    if index then
        table.remove(workspaceParts, index)
    end
end)

-- Now use cached array
while true do
    for _, part in ipairs(workspaceParts) do
        -- Much faster
    end
    task.wait(1)
end
```

```lua
-- ❌ BAD: Tight loop in Heartbeat
RunService.Heartbeat:Connect(function()
    for i = 1, 1000 do
        -- Heavy computation
    end
end)

-- ✅ GOOD: Async work with task.spawn
RunService.Heartbeat:Connect(function()
    task.spawn(function()
        for i = 1, 1000 do
            -- Heavy computation (doesn't block)
        end
    end)
end)
```

### Memory Management

**Disconnect events when done:**

```lua
-- ❌ BAD: Never disconnects
local connection = part.Touched:Connect(function(hit)
    -- Handle touch
end)

-- ✅ GOOD: Disconnects after use
local connection
connection = part.Touched:Connect(function(hit)
    -- Handle touch
    connection:Disconnect()
end)

-- ✅ BETTER: Cleanup pattern (Maid/Janitor)
local connections = {}

table.insert(connections, part.Touched:Connect(function() end))
table.insert(connections, workspace.ChildAdded:Connect(function() end))

-- On cleanup
for _, conn in ipairs(connections) do
    conn:Disconnect()
end
connections = {}
```

## Builder Phase Checklist

Before considering implementation complete:

### Code Quality
- [ ] Type annotations on all public functions
- [ ] Strict mode enabled (`.luaurc`)
- [ ] Modules return frozen tables
- [ ] No circular dependencies
- [ ] Services cached at module level

### Security
- [ ] All RemoteEvent handlers validate input (type, range, business logic)
- [ ] Server-authoritative for all critical logic
- [ ] No trusting client positions/amounts/IDs
- [ ] Rate limiting implemented
- [ ] Suspicious activity logged

### Error Handling
- [ ] DataStore operations wrapped in pcall
- [ ] Retry logic implemented (exponential backoff)
- [ ] Default data provided on failures
- [ ] Graceful degradation (no crashes)

### Performance
- [ ] :GetChildren() results cached
- [ ] :GetService() used instead of game.Service
- [ ] Heavy work in task.spawn() / coroutines
- [ ] No tight loops in Heartbeat
- [ ] Events disconnected when done

### Testing
- [ ] Test stubs created (TestEZ)
- [ ] Manual test cases documented
- [ ] Example usage in comments

## Example Complete Module

```lua
--[[
    CoinManager
    Manages player coin balance and transactions

    Dependencies:
        - PlayerDataManager

    Public Methods:
        AwardCoins(player, amount, reason) -> boolean
        DeductCoins(player, amount, reason) -> boolean
        GetBalance(player) -> number

    Author: Context Foundry
    Version: 1.0.0
]]

local CoinManager = {}

-- Services
local Players = game:GetService("Players")
local ReplicatedStorage = game:GetService("ReplicatedStorage")

-- Dependencies
local PlayerDataManager = require(script.Parent.PlayerDataManager)

-- Remotes
local UpdateCoinsEvent = ReplicatedStorage.Remotes.UpdateCoins

-- Constants
local MAX_COIN_BALANCE = 1000000
local MIN_TRANSACTION = 1

-- Public API
function CoinManager:AwardCoins(player: Player, amount: number, reason: string): boolean
    assert(typeof(player) == "Instance", "Invalid player")
    assert(type(amount) == "number", "Invalid amount")

    -- Validate amount
    if amount < MIN_TRANSACTION then
        warn("Coin amount too small:", amount)
        return false
    end

    -- Get player data
    local data = PlayerDataManager:GetData(player)
    if not data then
        warn("No data for player:", player.Name)
        return false
    end

    -- Update balance
    local newBalance = math.min(data.coins.balance + amount, MAX_COIN_BALANCE)
    local actualAwarded = newBalance - data.coins.balance

    data.coins.balance = newBalance
    data.coins.lifetime_earned += actualAwarded

    -- Log transaction
    print(player.Name, "awarded", actualAwarded, "coins. Reason:", reason)

    -- Notify client
    UpdateCoinsEvent:FireClient(player, newBalance)

    return true
end

function CoinManager:DeductCoins(player: Player, amount: number, reason: string): boolean
    assert(typeof(player) == "Instance", "Invalid player")
    assert(type(amount) == "number", "Invalid amount")

    -- Validate amount
    if amount < MIN_TRANSACTION then
        warn("Coin amount too small:", amount)
        return false
    end

    -- Get player data
    local data = PlayerDataManager:GetData(player)
    if not data then
        warn("No data for player:", player.Name)
        return false
    end

    -- Check balance
    if data.coins.balance < amount then
        warn(player.Name, "insufficient coins. Has:", data.coins.balance, "Needs:", amount)
        return false
    end

    -- Deduct coins
    data.coins.balance -= amount

    -- Log transaction
    print(player.Name, "spent", amount, "coins. Reason:", reason)

    -- Notify client
    UpdateCoinsEvent:FireClient(player, data.coins.balance)

    return true
end

function CoinManager:GetBalance(player: Player): number
    local data = PlayerDataManager:GetData(player)
    return data and data.coins.balance or 0
end

-- Private helpers
local function validateCoinAmount(amount: number): boolean
    return type(amount) == "number"
        and amount >= MIN_TRANSACTION
        and amount <= MAX_COIN_BALANCE
end

return table.freeze(CoinManager)
```

---

## Beginner-Friendly Patterns

**If building for beginners or teaching Roblox development**, reference the `roblox-beginner-foundations` pattern for:

### Common Beginner Patterns

**Kill Brick Template:**
```lua
local killBrick = script.Parent

killBrick.Touched:Connect(function(hit)
    local humanoid = hit.Parent:FindFirstChild("Humanoid")
    if humanoid then
        humanoid.Health = 0
    end
end)
```

**Checkpoint System (Simple):**
```lua
local Players = game:GetService("Players")
local checkpoint = script.Parent
local checkpointNumber = tonumber(checkpoint.Name)

checkpoint.Touched:Connect(function(hit)
    local player = Players:GetPlayerFromCharacter(hit.Parent)
    if player and checkpointNumber then
        local stageValue = player.leaderstats.Stage
        if checkpointNumber > stageValue.Value then
            stageValue.Value = checkpointNumber
        end
    end
end)
```

**Leaderstats Setup:**
```lua
local Players = game:GetService("Players")

Players.PlayerAdded:Connect(function(player)
    local leaderstats = Instance.new("Folder")
    leaderstats.Name = "leaderstats"
    leaderstats.Parent = player

    local stage = Instance.new("IntValue")
    stage.Name = "Stage"
    stage.Value = 0
    stage.Parent = leaderstats
end)
```

### Teaching Progression

1. **Variable Binding:** `local part = script.Parent`
2. **Instance Creation:** `Instance.new("Part")` + `.Parent = workspace`
3. **Properties & Conditionals:** `if part.Anchored == true then ... end`
4. **Events:** `.Touched:Connect(function(hit) ... end)`
5. **Loops:** `for i = 1, 10 do ... task.wait() end`
6. **Randomness:** `math.random(1, 10)`, `Vector3.new(math.random(-50, 50), 10, math.random(-50, 50))`
7. **Cleanup:** `Debris:AddItem(part, 5)`
8. **Reusability:** Iterate over folders instead of per-part scripts

### Critical Warnings for Beginners

- **ALWAYS use `task.wait()` in loops** - omitting causes server timeout
- **Check for `nil` before accessing** - use `FindFirstChild()` and validate
- **Use `:GetService()` for services** - not `game.Players`
- **Prefer centralized scripts** - avoid duplicate scripts on each object

---

**Remember:** Write secure, server-authoritative Luau code. Never trust the client. Validate everything.

## Handoff to Tester

Pass to Tester phase:
- Completed Luau modules
- RemoteEvent handlers
- DataStore integration
- Security validation points
- Performance optimizations
- Test stubs

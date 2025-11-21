# Roblox Test Strategy (Tester Phase)

**🧪 TESTING ROBLOX GAME CODE**

You are testing a Roblox game, NOT a web application, mobile app, or traditional software.

## Testing Philosophy

Roblox games require a **hybrid testing approach**:

1. **Static Analysis** (Automated) - Format, lint, type check
2. **Unit Tests** (TestEZ) - Test individual modules
3. **Manual Testing** (Studio) - Test gameplay in Roblox Studio
4. **Integration Testing** (Manual V1) - Test full game flow

## V1 Test Strategy

### 1. Static Analysis (Automated)

Run these checks automatically:

```bash
# Format check
stylua --check src/

# Lint check
selene src/

# Type check
luau-analyze src/
```

**Graceful Degradation:**
- If tool not installed → Log warning, continue
- Don't fail build if tools missing (V1 policy)
- Document installation in README

**Implementation:**

```lua
-- Test runner script
local function runStaticAnalysis()
    local results = {
        stylua = {success = false, output = ""},
        selene = {success = false, output = ""},
        luau = {success = false, output = ""},
    }

    -- Check Stylua
    local styluaInstalled = isCommandAvailable("stylua")
    if styluaInstalled then
        local success, output = runCommand("stylua --check src/")
        results.stylua = {success = success, output = output}
    else
        print("⚠️  Stylua not found - skipping format checks")
        print("   Install: cargo install stylua")
    end

    -- Check Selene
    local seleneInstalled = isCommandAvailable("selene")
    if seleneInstalled then
        local success, output = runCommand("selene src/")
        results.selene = {success = success, output = output}
    else
        print("⚠️  Selene not found - skipping lint checks")
        print("   Install: cargo install selene")
    end

    -- Check Luau
    local luauInstalled = isCommandAvailable("luau-analyze")
    if luauInstalled then
        local success, output = runCommand("luau-analyze src/")
        results.luau = {success = success, output = output}
    else
        print("⚠️  luau-analyze not found - skipping type checks")
        print("   Included with Roblox Studio")
    end

    return results
end
```

### 2. Unit Tests (TestEZ Framework)

**Location:** `src/ServerScriptService/Tests/`

**Framework:** TestEZ (Roblox's unit testing framework)

**Test Structure:**

```lua
-- CheckpointManager.spec.lua

return function()
    local CheckpointManager = require(script.Parent.Parent.GameSystems.CheckpointManager)
    local PlayerDataManager = require(script.Parent.Parent.GameSystems.PlayerDataManager)

    describe("CheckpointManager", function()
        describe("SaveCheckpoint", function()
            it("should save valid checkpoint", function()
                local mockPlayer = createMockPlayer()
                local result = CheckpointManager:SaveCheckpoint(mockPlayer, 1)

                expect(result).to.equal(true)

                local data = PlayerDataManager:GetData(mockPlayer)
                expect(data.checkpoints.current).to.equal(1)
            end)

            it("should reject invalid checkpoint number", function()
                local mockPlayer = createMockPlayer()
                local result = CheckpointManager:SaveCheckpoint(mockPlayer, -1)

                expect(result).to.equal(false)
            end)

            it("should update highest checkpoint", function()
                local mockPlayer = createMockPlayer()

                CheckpointManager:SaveCheckpoint(mockPlayer, 5)
                local data = PlayerDataManager:GetData(mockPlayer)

                expect(data.checkpoints.highest).to.equal(5)
            end)

            it("should not decrease checkpoint progress", function()
                local mockPlayer = createMockPlayer()

                CheckpointManager:SaveCheckpoint(mockPlayer, 5)
                CheckpointManager:SaveCheckpoint(mockPlayer, 3)

                local data = PlayerDataManager:GetData(mockPlayer)
                expect(data.checkpoints.current).to.equal(5)
            end)
        end)

        describe("GetLastCheckpoint", function()
            it("should return current checkpoint", function()
                local mockPlayer = createMockPlayer()

                CheckpointManager:SaveCheckpoint(mockPlayer, 3)
                local checkpoint = CheckpointManager:GetLastCheckpoint(mockPlayer)

                expect(checkpoint).to.equal(3)
            end)

            it("should return 0 for new player", function()
                local mockPlayer = createMockPlayer()
                local checkpoint = CheckpointManager:GetLastCheckpoint(mockPlayer)

                expect(checkpoint).to.equal(0)
            end)
        end)
    end)

    -- Helper: Create mock player for testing
    local function createMockPlayer()
        local mockPlayer = {
            Name = "TestPlayer",
            UserId = math.random(1, 1000000),
        }

        -- Initialize player data
        PlayerDataManager:InitializeData(mockPlayer)

        return mockPlayer
    end
end
```

**Test Coverage Requirements:**

Generate tests for:
- [ ] CheckpointManager
  - SaveCheckpoint (valid, invalid, edge cases)
  - GetLastCheckpoint
  - RespawnAtCheckpoint
- [ ] CoinManager
  - AwardCoins (valid, invalid amounts, max balance)
  - DeductCoins (valid, insufficient funds)
  - GetBalance
- [ ] ShopService
  - PurchaseItem (valid, insufficient funds, invalid item)
  - HasItem
  - GetShopItems
- [ ] PlayerDataManager
  - LoadData (success, failure, default data)
  - SaveData (success, retry, failure)
  - GetData

**Running TestEZ Tests (Manual - V1):**

1. Install TestEZ plugin in Roblox Studio
2. Open `dist/Game.rbxlx` in Studio
3. Navigate to ServerScriptService → Tests
4. Click "Run Tests" in TestEZ plugin
5. Verify all tests pass

**Documentation for Users:**

```markdown
## Running Tests

### Install TestEZ Plugin

1. Open Roblox Studio
2. View → Toolbox → Plugins
3. Search for "TestEZ"
4. Install the TestEZ plugin

### Run Tests

1. Open `dist/Game.rbxlx` in Roblox Studio
2. View → Explorer → ServerScriptService → Tests
3. Click the TestEZ plugin button
4. Click "Run All Tests"
5. Review test results

### Expected Output

All tests should pass:
- ✓ CheckpointManager (4/4 tests passed)
- ✓ CoinManager (3/3 tests passed)
- ✓ ShopService (3/3 tests passed)
```

### 3. Manual Testing Checklist

**Core Gameplay Tests:**

#### Spawn & Initialization
- [ ] Player spawns at correct location
- [ ] Player data loads correctly
- [ ] UI displays (coin counter, stage counter)
- [ ] No console errors on join

#### Checkpoint System
- [ ] Player can touch checkpoints
- [ ] Checkpoint saves progress
- [ ] Death teleports to last checkpoint
- [ ] Checkpoints persist across server joins
- [ ] Can't skip checkpoints (if sequential)

#### Coin System
- [ ] Coins can be collected
- [ ] Coin UI updates immediately
- [ ] Coin balance persists across sessions
- [ ] Can't collect same coin twice
- [ ] Coin amounts are correct

#### Shop System
- [ ] Shop UI opens and displays items
- [ ] Item prices shown correctly
- [ ] Can purchase items with sufficient coins
- [ ] Purchase deducts correct amount
- [ ] Insufficient coins prevents purchase
- [ ] Items appear in inventory after purchase
- [ ] Can't purchase same item twice

#### Death Zones
- [ ] Touching death zone kills player
- [ ] Player respawns at last checkpoint
- [ ] Death doesn't reset coins or progress

#### Data Persistence
- [ ] Progress saves periodically
- [ ] Leaving and rejoining restores progress
- [ ] Coins persist across sessions
- [ ] Owned items persist

#### Multi-Player
- [ ] Multiple players don't interfere
- [ ] Each player has independent progress
- [ ] Coin collection is player-specific
- [ ] No data leakage between players

**Security Tests (Anti-Cheat):**

- [ ] Can't collect coins from far away
- [ ] Can't teleport to unreached checkpoints
- [ ] Can't purchase items without funds
- [ ] Can't award self coins via client
- [ ] Rate limiting prevents spam

**Performance Tests:**

- [ ] Game runs smoothly (60 FPS)
- [ ] No lag with 10+ players
- [ ] Server performance < 5% CPU
- [ ] Memory usage stable (no leaks)

### 4. Integration Testing (V1: Manual)

**Test Full Game Flow:**

1. **New Player Flow**
   - [ ] Join game as new player
   - [ ] Verify starts at spawn
   - [ ] Verify default coin balance (0)
   - [ ] Complete stage 1
   - [ ] Checkpoint saves
   - [ ] Collect coins
   - [ ] Verify balance updates

2. **Purchase Flow**
   - [ ] Collect enough coins
   - [ ] Open shop UI
   - [ ] Purchase item
   - [ ] Verify deduction
   - [ ] Verify item granted
   - [ ] Try to purchase again (should fail)

3. **Death & Respawn Flow**
   - [ ] Reach checkpoint 3
   - [ ] Die in death zone
   - [ ] Verify respawn at checkpoint 3
   - [ ] Verify coins unchanged
   - [ ] Continue playing

4. **Save & Load Flow**
   - [ ] Reach checkpoint 5
   - [ ] Collect 100 coins
   - [ ] Leave game
   - [ ] Rejoin
   - [ ] Verify checkpoint 5
   - [ ] Verify 100 coins
   - [ ] Verify owned items

## Test Automation (V2 Future)

**Future enhancements:**

- Headless test runner for CI/CD
- Automated gameplay testing
- Load testing framework
- Performance profiling
- Automated security scanning

## Test Documentation

**Generate README section:**

```markdown
## Testing

### Static Analysis

Run formatting, linting, and type checking:

```bash
# Format check
stylua --check src/

# Lint check
selene src/

# Type check
luau-analyze src/
```

Install tools:
```bash
cargo install stylua selene
```

### Unit Tests

Tests use TestEZ framework and live in `src/ServerScriptService/Tests/`.

To run tests:
1. Install TestEZ plugin in Roblox Studio
2. Open `dist/Game.rbxlx`
3. Run tests via TestEZ plugin

### Manual Testing

Follow the manual test checklist:

#### Basic Gameplay
- [ ] Player spawns correctly
- [ ] Checkpoints save progress
- [ ] Coins can be collected
- [ ] Shop purchases work
- [ ] Data persists across sessions

#### Security
- [ ] Can't exploit RemoteEvents
- [ ] Can't collect coins from far away
- [ ] Can't purchase without funds

#### Performance
- [ ] Runs at 60 FPS
- [ ] No lag with multiple players
- [ ] Memory usage stable

See `docs/MANUAL_TEST_CHECKLIST.md` for full checklist.
```

## Test Results Format

**Output test results in this format:**

```
=== Roblox Game Test Results ===

STATIC ANALYSIS:
  ✓ Stylua: All files formatted correctly
  ✓ Selene: No linting errors
  ✓ Luau-analyze: No type errors

UNIT TESTS:
  ✓ CheckpointManager: 4/4 tests passed
  ✓ CoinManager: 3/3 tests passed
  ✓ ShopService: 3/3 tests passed
  Total: 10/10 tests passed

MANUAL TESTING:
  ✓ Spawn & Initialization (4/4 checks passed)
  ✓ Checkpoint System (6/6 checks passed)
  ✓ Coin System (5/5 checks passed)
  ✓ Shop System (7/7 checks passed)
  ✓ Data Persistence (4/4 checks passed)
  ✓ Multi-Player (4/4 checks passed)
  ✓ Security (5/5 checks passed)
  ⚠️  Performance (3/4 checks passed - minor FPS drops with 15+ players)

OVERALL: PASS ✓

Recommendations:
  - Optimize coin collection loop for better performance
  - Add index to DataStore queries
```

## Tester Phase Checklist

Before declaring testing complete:

### Static Analysis
- [ ] Stylua check passes (or tool not installed)
- [ ] Selene check passes (or tool not installed)
- [ ] Luau-analyze check passes (or tool not installed)
- [ ] Warnings logged for missing tools

### Unit Tests
- [ ] Tests created for all managers
- [ ] All tests pass
- [ ] Test coverage > 80%
- [ ] Edge cases tested

### Manual Tests
- [ ] All checklist items verified
- [ ] No critical bugs found
- [ ] Security tests pass
- [ ] Performance acceptable

### Documentation
- [ ] Test instructions in README
- [ ] Manual test checklist documented
- [ ] Test results formatted
- [ ] Known issues documented

---

**Remember:** V1 focuses on static analysis + manual testing. Full automation comes in V2.

## Handoff to Docs

Pass to Docs phase:
- Test results
- Known issues
- Performance notes
- Installation requirements
- Testing instructions

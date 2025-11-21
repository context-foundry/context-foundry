# Roblox Project Assessment (Scout Phase)

**🎮 ROBLOX GAME PROJECT DETECTED**

This is a Roblox game project, NOT a web application, mobile app, or traditional software project.

## Project Details

- **Project Type:** {roblox_project_type}
- **Subtype:** {project_subtype} (rojo or placefile)
- **Complexity:** {complexity}
- **Has Tests:** {has_tests}

## Critical Understanding

### This is Roblox Development

You are working with:
- **Luau** (typed Lua variant), NOT JavaScript, Python, or other languages
- **Rojo** build system (NOT webpack, vite, or traditional build tools)
- **Roblox Studio** as the runtime environment
- **Roblox services** (DataStoreService, Players, Workspace, etc.)
- **Client-server architecture** (Studio acts as both client and server)

### DO NOT Research

❌ **Web frameworks** (React, Vue, Angular, Svelte)
❌ **Backend frameworks** (Express, FastAPI, Django, Flask)
❌ **Databases** (PostgreSQL, MongoDB, Redis)
❌ **HTTP/REST APIs** (unless for external integrations)
❌ **Package managers** (npm, pip, cargo) - use Rojo, not package managers
❌ **Deployment platforms** (Vercel, Netlify, AWS) - Roblox handles hosting

### DO Research

✅ **Roblox DataStore** patterns and best practices
✅ **RemoteEvent/RemoteFunction** security and usage
✅ **ModuleScript** organization (ReplicatedStorage, ServerScriptService)
✅ **Rojo workflow** and project structure
✅ **Luau type annotations** and strict mode
✅ **Roblox services** (Players, Workspace, TweenService, etc.)
✅ **Server-authoritative** architecture patterns
✅ **Checkpoint systems** for obby games
✅ **Coin/currency systems** with persistence
✅ **Shop systems** with validation

## Detection & Assessment Checklist

### 1. Project Structure Analysis

Check for key indicators:

- [ ] **Rojo Configuration**
  - `default.project.json` or `*.project.json` present?
  - Configured for which Roblox project structure?

- [ ] **Source Directory** (`src/`)
  - `ServerScriptService/` - Server-side logic
  - `ReplicatedStorage/` - Shared modules
  - `StarterPlayer/` - Client scripts
  - `StarterGui/` - UI elements
  - `Workspace/` - Game world objects

- [ ] **Tests Directory**
  - `src/ServerScriptService/Tests/` exists?
  - Uses TestEZ framework?
  - Test coverage percentage?

- [ ] **Configuration Files**
  - `.luaurc` - Luau type checker config
  - `selene.toml` - Linter config
  - `stylua.toml` - Formatter config

### 2. Game Systems Detection

Scan for existing game systems:

- [ ] **Checkpoint System**
  - CheckpointManager or similar?
  - How are checkpoints stored?
  - Server-authoritative or client-side?

- [ ] **Currency System**
  - CoinManager, MoneyManager, or similar?
  - Uses DataStore for persistence?
  - Validated on server?

- [ ] **Shop System**
  - ShopService or similar?
  - Validates purchases server-side?
  - Prevents insufficient funds purchases?

- [ ] **Player Data Management**
  - PlayerDataManager or similar?
  - Caches data in memory?
  - Handles DataStore failures gracefully?

- [ ] **Remote Communication**
  - RemoteEvents/RemoteFunctions defined?
  - Input validation present?
  - Rate limiting implemented?

### 3. Security Assessment

**CRITICAL: Check for security vulnerabilities**

- [ ] **RemoteEvent Validation**
  - Are client inputs validated on server?
  - Type checking present?
  - Range validation for amounts?
  - Business logic validation?

- [ ] **Server Authority**
  - Critical logic (coins, checkpoints, purchases) on server?
  - Client can only send intent, not results?
  - No trusting client-supplied positions/amounts?

- [ ] **DataStore Security**
  - Uses UpdateAsync for atomic operations?
  - Validates data before saving?
  - Handles corrupted data gracefully?

- [ ] **Exploit Prevention**
  - Rate limiting on RemoteEvents?
  - Logs suspicious activity?
  - Validates item ownership before granting benefits?

### 4. Code Quality Assessment

- [ ] **Type Annotations**
  - Uses Luau type annotations?
  - Strict mode enabled in `.luaurc`?

- [ ] **Module Pattern**
  - Modules return frozen tables?
  - Avoids circular dependencies?
  - Proper separation of concerns?

- [ ] **Error Handling**
  - DataStore calls wrapped in pcall?
  - Retry logic implemented?
  - Graceful degradation on failures?

- [ ] **Performance**
  - Caches :GetChildren() results?
  - Avoids tight loops in Heartbeat?
  - Uses task.spawn() for async work?

### 5. Pattern Matching

Query Context Codex for applicable patterns:

```
Search codex by:
- category="roblox"
- project_types includes "{roblox_project_type}"
- tags matching: ["checkpoint", "coins", "shop", "obby"]
```

Expected patterns to find:
- `obby-checkpoints-coin-shop` - Main game pattern
- `roblox-module-structure` - Code organization
- `roblox-datastore-best-practices` - Persistence
- `roblox-remote-events-security` - Security

### 6. Common Issues to Check

Search codex for known issues:

- `roblox-remote-security-001` - Input validation vulnerabilities
- `roblox-datastore-failure-001` - DataStore error handling
- `roblox-performance-001` - Performance bottlenecks
- `roblox-memory-leak-001` - Event cleanup issues

### 7. Toolchain Verification

Check which tools are available:

```bash
# Required
rojo --version  # Should be ≥7.0.0

# Optional but recommended
stylua --version
selene --version
luau-analyze --version
```

**Graceful Degradation:**
- If tools missing, log warning
- Don't fail build (V1 policy)
- Document installation in README

## Scout Output Requirements

Generate a comprehensive assessment including:

### Project Summary
- Project type and subtype
- Complexity level
- Existing game systems
- Test coverage status

### Security Findings
- List all security concerns found
- Prioritize by severity (HIGH/MEDIUM/LOW)
- Reference applicable security patterns from codex

### Architecture Notes
- Current code organization
- Module structure
- Client-server architecture
- DataStore usage patterns

### Applicable Patterns
- List patterns from codex that apply
- Explain why each pattern is relevant
- Note any patterns currently violated

### Recommended Actions
- Security fixes needed
- Architecture improvements
- Testing gaps to fill
- Documentation to add

### Toolchain Status
- Which tools are available
- Which are missing
- Installation instructions for missing tools

## Example Assessment Output

```
# Roblox Obby Game Assessment

## Project Overview
- Type: roblox-game (Rojo-based)
- Complexity: Moderate
- Has Tests: Yes (TestEZ framework)
- Game Systems: Checkpoints, Coins, Shop

## Security Findings

### HIGH PRIORITY
- ❌ CoinManager accepts client-supplied amounts (roblox-remote-security-001)
  - Fix: Validate amounts on server
  - Pattern: roblox-remote-events-security

### MEDIUM PRIORITY
- ⚠️  DataStore calls not wrapped in pcall (roblox-datastore-failure-001)
  - Fix: Add error handling and retry logic
  - Pattern: roblox-datastore-best-practices

## Architecture
- Server-authoritative design: Partial
- Module organization: Good (follows roblox-module-structure)
- DataStore usage: Present but needs error handling

## Applicable Patterns
1. obby-checkpoints-coin-shop (primary pattern)
2. roblox-remote-events-security (security)
3. roblox-datastore-best-practices (persistence)
4. roblox-module-structure (organization)

## Recommendations
1. Add RemoteEvent input validation (HIGH)
2. Implement DataStore error handling (MEDIUM)
3. Add rate limiting to prevent spam (MEDIUM)
4. Increase test coverage to 80%+ (LOW)
5. Add type annotations to all modules (LOW)

## Toolchain
- ✅ Rojo 7.4.0 installed
- ✅ Stylua 0.20.0 installed
- ❌ Selene not found - install with: cargo install selene
- ✅ luau-analyze available (Roblox Studio)
```

## Beginner-Focused Projects

**If this project is for teaching or beginner developers**, reference the `roblox-beginner-foundations` pattern which includes:

### Foundational Concepts to Check
- [ ] Variable binding with `local part = script.Parent`
- [ ] Instance creation with `Instance.new()`
- [ ] Event handling with `.Touched:Connect()`
- [ ] Player detection with `GetPlayerFromCharacter()`
- [ ] Leaderstats setup in `Players.PlayerAdded`
- [ ] Checkpoint system with simple number-based progression
- [ ] Proper use of `task.wait()` in loops
- [ ] Cleanup patterns with `Debris:AddItem()`

### Common Beginner Patterns to Look For
1. **Kill Bricks** - Parts that damage/kill on touch
2. **Checkpoints** - Save player progress with leaderstats
3. **Teleport on Spawn** - Respawn at last checkpoint
4. **Simple Loops** - for loops with proper wait() calls
5. **Object Iteration** - Using `pairs()` to handle multiple objects
6. **Reusable Scripts** - One script managing multiple similar objects

### Teaching Red Flags to Check
- ❌ Missing `task.wait()` in `while true do` loops (will crash!)
- ❌ Not checking if Humanoid exists before accessing (nil errors)
- ❌ Using `game.Players` instead of `game:GetService("Players")`
- ❌ Separate script per object instead of centralized iteration
- ❌ Client-authoritative logic (checkpoints set by client)
- ❌ No validation on RemoteEvent handlers

### Beginner-Friendly Recommendations
If project needs teaching patterns:
1. Include commented code examples in modules
2. Add simple checkpoint + leaderstats system
3. Provide kill brick template
4. Show proper event handling patterns
5. Demonstrate loop + wait() patterns
6. Include Debris cleanup examples

**Pattern Reference:** Query `roblox-beginner-foundations` for complete code examples.

## Next Phase Handoff

Pass to Architect phase:
- Security vulnerabilities list
- Applicable patterns
- Existing architecture assessment
- Recommended improvements
- Game systems to implement/fix

---

**Remember:** This is a Roblox game. All advice, patterns, and recommendations must be Roblox-specific. Do NOT suggest web frameworks, databases, or non-Roblox technologies.

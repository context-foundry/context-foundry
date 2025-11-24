--[[
	PlayerManager
	Simple player management for test project

	Demonstrates:
	- Player join/leave handling
	- RemoteEvent usage
	- Server-authoritative patterns
	- Luau type annotations

	Author: Context Foundry Roblox Extension - Test Project
]]

local PlayerManager = {}

-- Services
local Players = game:GetService("Players")
local ReplicatedStorage = game:GetService("ReplicatedStorage")

-- Shared configuration
local TestConfig = require(ReplicatedStorage.TestConfig)

-- Remotes
local Remotes = ReplicatedStorage:WaitForChild("Remotes")
local TestEvent = Remotes:WaitForChild("TestEvent")

-- Player data storage
local playerData: {[number]: {joined: number, name: string}} = {}

-- Log game info on startup
print(string.format("[PlayerManager] Starting %s v%s", TestConfig.GAME_NAME, TestConfig.VERSION))
print(string.format("[PlayerManager] Max players: %d", TestConfig.MAX_PLAYERS))

-- Public API
function PlayerManager:GetPlayerData(player: Player)
	return playerData[player.UserId]
end

function PlayerManager:GetAllPlayers(): {Player}
	return Players:GetPlayers()
end

-- Initialize player on join
local function onPlayerAdded(player: Player)
	print(string.format("[PlayerManager] %s joined (UserId: %d)", player.Name, player.UserId))

	-- Store player data
	playerData[player.UserId] = {
		joined = os.time(),
		name = player.Name,
	}

	-- Create leaderstats
	local leaderstats = Instance.new("Folder")
	leaderstats.Name = "leaderstats"
	leaderstats.Parent = player

	local sessionTime = Instance.new("IntValue")
	sessionTime.Name = "SessionTime"
	sessionTime.Value = 0
	sessionTime.Parent = leaderstats
end

-- Cleanup on player leave
local function onPlayerRemoving(player: Player)
	print(string.format("[PlayerManager] %s left", player.Name))

	-- Clean up player data
	playerData[player.UserId] = nil
end

-- Handle test event (demonstrates RemoteEvent validation)
TestEvent.OnServerEvent:Connect(function(player: Player, message: any)
	-- Validate input (security best practice)
	if type(message) ~= "string" then
		warn(string.format("[PlayerManager] %s sent invalid message type", player.Name))
		return
	end

	-- Validate length
	if #message > 100 then
		warn(string.format("[PlayerManager] %s sent message too long", player.Name))
		return
	end

	print(string.format("[PlayerManager] %s says: %s", player.Name, message))
end)

-- Connect events
Players.PlayerAdded:Connect(onPlayerAdded)
Players.PlayerRemoving:Connect(onPlayerRemoving)

-- Handle players who joined before script ran
for _, player in ipairs(Players:GetPlayers()) do
	task.spawn(onPlayerAdded, player)
end

return table.freeze(PlayerManager)

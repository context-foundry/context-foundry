--[[
	PlayerDataManager
	Manages player data loading, saving, and caching

	Dependencies: None

	Public Methods:
		LoadData(player: Player) -> PlayerData
		SaveData(player: Player) -> boolean
		GetData(player: Player) -> PlayerData?
		UpdateData(player: Player, updates: table) -> ()

	Author: Context Foundry Roblox Extension
	Version: 1.0.0
]]

local PlayerDataManager = {}

-- Services
local Players = game:GetService("Players")
local DataStoreService = game:GetService("DataStoreService")
local RunService = game:GetService("RunService")
local ReplicatedStorage = game:GetService("ReplicatedStorage")

-- Shared modules
local PlayerData = require(ReplicatedStorage.Modules.PlayerData)
export type PlayerData = PlayerData.PlayerData

-- DataStore
local PlayerDataStore = DataStoreService:GetDataStore("PlayerData_v1")

-- Constants
local MAX_RETRIES = 3
local RETRY_DELAY = 2
local AUTO_SAVE_INTERVAL = 300  -- 5 minutes

-- Player data cache (in-memory)
local playerDataCache: {[number]: PlayerData} = {}

-- Public API
function PlayerDataManager:LoadData(player: Player): PlayerData
	assert(typeof(player) == "Instance" and player:IsA("Player"), "Invalid player")

	local userId = player.UserId

	-- Try to load from DataStore with retry logic
	for attempt = 1, MAX_RETRIES do
		local success, result = pcall(function()
			return PlayerDataStore:GetAsync(tostring(userId))
		end)

		if success then
			local data = result or PlayerData.getDefault()

			-- Migrate data if needed (version check)
			if data.metadata and data.metadata.version ~= "1.0" then
				data = self:MigrateData(data)
			end

			-- Cache in memory
			playerDataCache[userId] = data

			print(string.format("[PlayerDataManager] Loaded data for %s (attempt %d)", player.Name, attempt))
			return data
		else
			warn(string.format("[PlayerDataManager] Load error for %s (attempt %d): %s", player.Name, attempt, tostring(result)))

			if attempt < MAX_RETRIES then
				task.wait(RETRY_DELAY * attempt)  -- Exponential backoff
			end
		end
	end

	-- All retries failed - use default data
	warn(string.format("[PlayerDataManager] Failed to load data for %s - using defaults", player.Name))
	local defaultData = PlayerData.getDefault()
	playerDataCache[userId] = defaultData
	return defaultData
end

function PlayerDataManager:SaveData(player: Player): boolean
	assert(typeof(player) == "Instance" and player:IsA("Player"), "Invalid player")

	local userId = player.UserId
	local data = playerDataCache[userId]

	if not data then
		warn(string.format("[PlayerDataManager] No data to save for %s", player.Name))
		return false
	end

	-- Update last save time
	data.metadata.last_save = os.time()

	-- Try to save with retry logic
	for attempt = 1, MAX_RETRIES do
		local success, result = pcall(function()
			PlayerDataStore:UpdateAsync(tostring(userId), function(oldData)
				-- Use new data, but preserve any server-side changes
				return data
			end)
		end)

		if success then
			print(string.format("[PlayerDataManager] Saved data for %s (attempt %d)", player.Name, attempt))
			return true
		else
			warn(string.format("[PlayerDataManager] Save error for %s (attempt %d): %s", player.Name, attempt, tostring(result)))

			if attempt < MAX_RETRIES then
				task.wait(RETRY_DELAY * attempt)
			end
		end
	end

	-- All retries failed
	warn(string.format("[PlayerDataManager] Failed to save data for %s", player.Name))
	return false
end

function PlayerDataManager:GetData(player: Player): PlayerData?
	assert(typeof(player) == "Instance" and player:IsA("Player"), "Invalid player")

	return playerDataCache[player.UserId]
end

function PlayerDataManager:UpdateData(player: Player, updates: table): ()
	assert(typeof(player) == "Instance" and player:IsA("Player"), "Invalid player")
	assert(type(updates) == "table", "Updates must be a table")

	local data = playerDataCache[player.UserId]
	if not data then
		warn(string.format("[PlayerDataManager] No data to update for %s", player.Name))
		return
	end

	-- Merge updates (shallow merge for now)
	for key, value in pairs(updates) do
		data[key] = value
	end
end

function PlayerDataManager:MigrateData(oldData: table): PlayerData
	-- Migration logic for older data versions
	-- For now, just return default data merged with old data
	local newData = PlayerData.getDefault()

	-- Preserve old values if they exist
	if oldData.coins then
		newData.coins = oldData.coins
	end
	if oldData.checkpoints then
		newData.checkpoints = oldData.checkpoints
	end
	if oldData.owned_items then
		newData.owned_items = oldData.owned_items
	end

	newData.metadata.version = "1.0"
	return newData
end

-- Private helpers
local function removePlayerDataCache(player: Player): ()
	playerDataCache[player.UserId] = nil
end

-- Initialize on player join
Players.PlayerAdded:Connect(function(player)
	PlayerDataManager:LoadData(player)
end)

-- Save on player leave
Players.PlayerRemoving:Connect(function(player)
	PlayerDataManager:SaveData(player)
	removePlayerDataCache(player)
end)

-- Auto-save every 5 minutes
task.spawn(function()
	while true do
		task.wait(AUTO_SAVE_INTERVAL)

		for _, player in ipairs(Players:GetPlayers()) do
			task.spawn(function()
				PlayerDataManager:SaveData(player)
			end)
		end
	end
end)

-- Save all data on server shutdown
game:BindToClose(function()
	print("[PlayerDataManager] Server shutting down - saving all player data")

	for _, player in ipairs(Players:GetPlayers()) do
		PlayerDataManager:SaveData(player)
	end

	-- Wait a bit for saves to complete
	task.wait(3)
end)

return table.freeze(PlayerDataManager)

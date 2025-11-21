--[[
	CoinManager
	Manages player coin balance and transactions

	Dependencies:
		- PlayerDataManager

	Public Methods:
		AwardCoins(player: Player, amount: number, reason: string) -> boolean
		DeductCoins(player: Player, amount: number, reason: string) -> boolean
		GetBalance(player: Player) -> number

	Author: Context Foundry Roblox Extension
	Version: 1.0.0
]]

local CoinManager = {}

-- Services
local Players = game:GetService("Players")
local ReplicatedStorage = game:GetService("ReplicatedStorage")

-- Dependencies
local PlayerDataManager = require(script.Parent.PlayerDataManager)

-- Remotes
local Remotes = ReplicatedStorage:WaitForChild("Remotes")
local UpdateCoinsEvent = Remotes:WaitForChild("UpdateCoins")
local CoinCollectedEvent = Remotes:WaitForChild("CoinCollected")

-- Constants
local MAX_COIN_BALANCE = 1000000
local MIN_TRANSACTION = 1
local COIN_COLLECT_RANGE = 20  -- Maximum distance to collect coin

-- Track leaderstats IntValues for each player
local playerLeaderstats: {[Player]: IntValue} = {}

-- Public API
function CoinManager:AwardCoins(player: Player, amount: number, reason: string): boolean
	assert(typeof(player) == "Instance" and player:IsA("Player"), "Invalid player")
	assert(type(amount) == "number", "Invalid amount")

	-- Validate amount
	if amount < MIN_TRANSACTION then
		warn(string.format("[CoinManager] Coin amount too small: %d", amount))
		return false
	end

	-- Get player data
	local data = PlayerDataManager:GetData(player)
	if not data then
		warn(string.format("[CoinManager] No data for player: %s", player.Name))
		return false
	end

	-- Update balance (capped at max)
	local newBalance = math.min(data.coins.balance + amount, MAX_COIN_BALANCE)
	local actualAwarded = newBalance - data.coins.balance

	data.coins.balance = newBalance
	data.coins.lifetime_earned += actualAwarded

	-- Log transaction
	print(string.format("[CoinManager] %s awarded %d coins. Reason: %s", player.Name, actualAwarded, reason or "unknown"))

	-- Update leaderstats display
	local leaderstatValue = playerLeaderstats[player]
	if leaderstatValue then
		leaderstatValue.Value = newBalance
	end

	-- Notify client
	UpdateCoinsEvent:FireClient(player, newBalance)

	return true
end

function CoinManager:DeductCoins(player: Player, amount: number, reason: string): boolean
	assert(typeof(player) == "Instance" and player:IsA("Player"), "Invalid player")
	assert(type(amount) == "number", "Invalid amount")

	-- Validate amount
	if amount < MIN_TRANSACTION then
		warn(string.format("[CoinManager] Coin amount too small: %d", amount))
		return false
	end

	-- Get player data
	local data = PlayerDataManager:GetData(player)
	if not data then
		warn(string.format("[CoinManager] No data for player: %s", player.Name))
		return false
	end

	-- Check balance
	if data.coins.balance < amount then
		warn(string.format("[CoinManager] %s has insufficient coins. Has: %d, Needs: %d", player.Name, data.coins.balance, amount))
		return false
	end

	-- Deduct coins
	data.coins.balance -= amount

	-- Log transaction
	print(string.format("[CoinManager] %s spent %d coins. Reason: %s", player.Name, amount, reason or "unknown"))

	-- Update leaderstats display
	local leaderstatValue = playerLeaderstats[player]
	if leaderstatValue then
		leaderstatValue.Value = data.coins.balance
	end

	-- Notify client
	UpdateCoinsEvent:FireClient(player, data.coins.balance)

	return true
end

function CoinManager:GetBalance(player: Player): number
	assert(typeof(player) == "Instance" and player:IsA("Player"), "Invalid player")

	local data = PlayerDataManager:GetData(player)
	return data and data.coins.balance or 0
end

-- Handle coin collection (server-side validation)
CoinCollectedEvent.OnServerEvent:Connect(function(player, coinPart)
	-- Validate coin part
	if not coinPart or not coinPart:IsA("BasePart") then
		warn(string.format("[CoinManager] %s sent invalid coin part", player.Name))
		return
	end

	-- Check if it has a CoinValue
	local coinValue = coinPart:FindFirstChild("CoinValue")
	if not coinValue or not coinValue:IsA("NumberValue") then
		warn(string.format("[CoinManager] Coin part missing CoinValue: %s", coinPart:GetFullName()))
		return
	end

	-- Validate player distance (anti-cheat)
	local character = player.Character
	if not character then return end

	local humanoidRootPart = character:FindFirstChild("HumanoidRootPart")
	if not humanoidRootPart then return end

	local distance = (humanoidRootPart.Position - coinPart.Position).Magnitude
	if distance > COIN_COLLECT_RANGE then
		warn(string.format("[CoinManager] %s tried to collect coin from too far away (distance: %.1f)", player.Name, distance))
		return
	end

	-- Award coins (server calculates reward)
	local amount = coinValue.Value
	local success = CoinManager:AwardCoins(player, amount, "coin_collection")

	if success then
		-- Destroy coin so others can't collect it
		coinPart:Destroy()

		print(string.format("[CoinManager] %s collected coin worth %d", player.Name, amount))
	end
end)

-- Setup leaderstats on player join
Players.PlayerAdded:Connect(function(player)
	-- Wait for data to load
	task.wait(0.5)

	local data = PlayerDataManager:GetData(player)
	if not data then
		warn(string.format("[CoinManager] No data for player on join: %s", player.Name))
		return
	end

	-- Create leaderstats
	local leaderstats = Instance.new("Folder")
	leaderstats.Name = "leaderstats"
	leaderstats.Parent = player

	local coinsValue = Instance.new("IntValue")
	coinsValue.Name = "Coins"
	coinsValue.Value = data.coins.balance
	coinsValue.Parent = leaderstats

	-- Store reference so we can update it when coins change
	playerLeaderstats[player] = coinsValue
end)

-- Clean up leaderstats reference on player leave
Players.PlayerRemoving:Connect(function(player)
	playerLeaderstats[player] = nil
end)

return table.freeze(CoinManager)

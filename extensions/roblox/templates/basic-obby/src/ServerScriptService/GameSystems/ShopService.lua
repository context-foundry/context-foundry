--[[
	ShopService
	Manages shop purchases and item ownership

	Dependencies:
		- PlayerDataManager
		- CoinManager

	Public Methods:
		PurchaseItem(player: Player, itemId: string) -> boolean
		HasItem(player: Player, itemId: string) -> boolean

	Author: Context Foundry Roblox Extension
	Version: 1.0.0
]]

local ShopService = {}

-- Services
local ReplicatedStorage = game:GetService("ReplicatedStorage")

-- Dependencies
local PlayerDataManager = require(script.Parent.PlayerDataManager)
local CoinManager = require(script.Parent.CoinManager)

-- Configuration
local ShopConfig = require(ReplicatedStorage.Modules.ShopConfig)

-- Remotes
local Remotes = ReplicatedStorage:WaitForChild("Remotes")
local PurchaseItemEvent = Remotes:WaitForChild("PurchaseItem")

-- Constants
local PURCHASE_COOLDOWN = 1  -- Seconds between purchases

-- Rate limiting
local lastPurchaseTime: {[number]: number} = {}

-- Public API
function ShopService:PurchaseItem(player: Player, itemId: string): boolean
	assert(typeof(player) == "Instance" and player:IsA("Player"), "Invalid player")
	assert(type(itemId) == "string", "Invalid itemId")

	-- Rate limiting
	local userId = player.UserId
	local lastTime = lastPurchaseTime[userId] or 0
	local currentTime = tick()

	if currentTime - lastTime < PURCHASE_COOLDOWN then
		warn(string.format("[ShopService] %s is purchasing too fast", player.Name))
		return false
	end

	-- Validate item exists
	local item = ShopConfig.items[itemId]
	if not item then
		warn(string.format("[ShopService] Invalid item ID: %s", itemId))
		return false
	end

	-- Get player data
	local data = PlayerDataManager:GetData(player)
	if not data then
		warn(string.format("[ShopService] No data for player: %s", player.Name))
		return false
	end

	-- Check if player already owns item
	if self:HasItem(player, itemId) then
		warn(string.format("[ShopService] %s already owns %s", player.Name, itemId))
		return false
	end

	-- Check balance
	local balance = CoinManager:GetBalance(player)
	if balance < item.cost then
		warn(string.format("[ShopService] %s has insufficient coins for %s. Has: %d, Needs: %d",
			player.Name, itemId, balance, item.cost))
		return false
	end

	-- Deduct coins
	local success = CoinManager:DeductCoins(player, item.cost, "shop_purchase:" .. itemId)
	if not success then
		return false
	end

	-- Grant item
	table.insert(data.owned_items, itemId)

	-- Update rate limit
	lastPurchaseTime[userId] = currentTime

	print(string.format("[ShopService] %s purchased %s for %d coins", player.Name, item.name, item.cost))
	return true
end

function ShopService:HasItem(player: Player, itemId: string): boolean
	assert(typeof(player) == "Instance" and player:IsA("Player"), "Invalid player")
	assert(type(itemId) == "string", "Invalid itemId")

	local data = PlayerDataManager:GetData(player)
	if not data then
		return false
	end

	return table.find(data.owned_items, itemId) ~= nil
end

-- Handle purchase requests
PurchaseItemEvent.OnServerEvent:Connect(function(player, itemId)
	-- Validate input
	if type(itemId) ~= "string" then
		warn(string.format("[ShopService] %s sent invalid itemId type", player.Name))
		return
	end

	-- Process purchase
	local success = ShopService:PurchaseItem(player, itemId)

	if success then
		-- Notify client of successful purchase
		-- (You can fire a success event here if needed)
	end
end)

return table.freeze(ShopService)

--[[
	ShopService Tests
	TestEZ unit tests for ShopService

	To run: Install TestEZ plugin in Studio, click "Run Tests"
]]

return function()
	local ShopService = require(script.Parent.Parent.GameSystems.ShopService)
	local PlayerDataManager = require(script.Parent.Parent.GameSystems.PlayerDataManager)
	local CoinManager = require(script.Parent.Parent.GameSystems.CoinManager)

	-- Mock player for testing
	local function createMockPlayer()
		return {
			Name = "TestPlayer",
			UserId = math.random(1, 1000000),
			Character = nil,
		}
	end

	describe("ShopService", function()
		describe("PurchaseItem", function()
			it("should purchase valid item with sufficient balance", function()
				local player = createMockPlayer()
				PlayerDataManager:LoadData(player)

				-- Give player enough coins
				local data = PlayerDataManager:GetData(player)
				data.coins.balance = 1000

				-- Purchase speed_boost (costs 100 per ShopConfig)
				local result = ShopService:PurchaseItem(player, "speed_boost")

				expect(result).to.equal(true)
				expect(ShopService:HasItem(player, "speed_boost")).to.equal(true)
			end)

			it("should reject purchase with invalid item ID", function()
				local player = createMockPlayer()
				PlayerDataManager:LoadData(player)

				local data = PlayerDataManager:GetData(player)
				data.coins.balance = 1000

				local result = ShopService:PurchaseItem(player, "invalid_item")

				expect(result).to.equal(false)
			end)

			it("should reject purchase when player already owns item", function()
				local player = createMockPlayer()
				PlayerDataManager:LoadData(player)

				local data = PlayerDataManager:GetData(player)
				data.coins.balance = 1000

				-- Purchase once
				ShopService:PurchaseItem(player, "speed_boost")

				-- Give more coins and try to purchase again
				data.coins.balance = 1000

				local result = ShopService:PurchaseItem(player, "speed_boost")

				expect(result).to.equal(false)
			end)

			it("should reject purchase with insufficient balance", function()
				local player = createMockPlayer()
				PlayerDataManager:LoadData(player)

				local data = PlayerDataManager:GetData(player)
				data.coins.balance = 50  -- Not enough for speed_boost (100 coins)

				local result = ShopService:PurchaseItem(player, "speed_boost")

				expect(result).to.equal(false)
				expect(data.coins.balance).to.equal(50)  -- Balance unchanged
			end)

			it("should deduct correct coin amount on purchase", function()
				local player = createMockPlayer()
				PlayerDataManager:LoadData(player)

				local data = PlayerDataManager:GetData(player)
				data.coins.balance = 500

				ShopService:PurchaseItem(player, "speed_boost")  -- costs 100

				-- Balance should be reduced by item cost
				local newBalance = CoinManager:GetBalance(player)
				expect(newBalance).to.equal(400)
			end)
		end)

		describe("HasItem", function()
			it("should return true when player owns item", function()
				local player = createMockPlayer()
				PlayerDataManager:LoadData(player)

				local data = PlayerDataManager:GetData(player)
				data.coins.balance = 1000
				ShopService:PurchaseItem(player, "speed_boost")

				local hasItem = ShopService:HasItem(player, "speed_boost")

				expect(hasItem).to.equal(true)
			end)

			it("should return false when player does not own item", function()
				local player = createMockPlayer()
				PlayerDataManager:LoadData(player)

				local hasItem = ShopService:HasItem(player, "speed_boost")

				expect(hasItem).to.equal(false)
			end)

			it("should return false for player with no data", function()
				local player = createMockPlayer()
				-- Don't load data

				local hasItem = ShopService:HasItem(player, "speed_boost")

				expect(hasItem).to.equal(false)
			end)
		end)

		describe("Rate Limiting", function()
			it("should reject rapid purchases", function()
				local player = createMockPlayer()
				PlayerDataManager:LoadData(player)

				local data = PlayerDataManager:GetData(player)
				data.coins.balance = 10000

				-- First purchase should succeed
				local result1 = ShopService:PurchaseItem(player, "speed_boost")
				expect(result1).to.equal(true)

				-- Give more coins for second purchase
				data.coins.balance = 10000

				-- Immediate second purchase should fail due to cooldown
				local result2 = ShopService:PurchaseItem(player, "double_jump")
				expect(result2).to.equal(false)

				-- Wait for cooldown
				task.wait(1.1)

				-- Third purchase should succeed after cooldown
				local result3 = ShopService:PurchaseItem(player, "double_jump")
				expect(result3).to.equal(true)
			end)
		end)
	end)
end

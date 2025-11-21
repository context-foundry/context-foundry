--[[
	CoinManager Tests
	TestEZ unit tests for CoinManager

	To run: Install TestEZ plugin in Studio, click "Run Tests"
]]

return function()
	local CoinManager = require(script.Parent.Parent.GameSystems.CoinManager)
	local PlayerDataManager = require(script.Parent.Parent.GameSystems.PlayerDataManager)

	-- Mock player for testing
	local function createMockPlayer()
		return {
			Name = "TestPlayer",
			UserId = math.random(1, 1000000),
			Character = nil,
		}
	end

	describe("CoinManager", function()
		describe("AwardCoins", function()
			it("should award valid amount of coins", function()
				local player = createMockPlayer()
				PlayerDataManager:LoadData(player)

				local result = CoinManager:AwardCoins(player, 100, "test")

				expect(result).to.equal(true)

				local data = PlayerDataManager:GetData(player)
				expect(data.coins.balance).to.equal(100)
				expect(data.coins.lifetime_earned).to.equal(100)
			end)

			it("should reject coin amounts below minimum", function()
				local player = createMockPlayer()
				PlayerDataManager:LoadData(player)

				local result = CoinManager:AwardCoins(player, 0, "test")

				expect(result).to.equal(false)
			end)

			it("should cap coins at maximum balance", function()
				local player = createMockPlayer()
				PlayerDataManager:LoadData(player)

				-- Set balance near max
				local data = PlayerDataManager:GetData(player)
				data.coins.balance = 999999

				-- Try to award more than cap allows
				CoinManager:AwardCoins(player, 1000, "test")

				expect(data.coins.balance).to.equal(1000000)  -- Capped at MAX
			end)

			it("should accumulate lifetime earned correctly", function()
				local player = createMockPlayer()
				PlayerDataManager:LoadData(player)

				CoinManager:AwardCoins(player, 50, "test1")
				CoinManager:AwardCoins(player, 75, "test2")

				local data = PlayerDataManager:GetData(player)
				expect(data.coins.lifetime_earned).to.equal(125)
			end)
		end)

		describe("DeductCoins", function()
			it("should deduct valid amount of coins", function()
				local player = createMockPlayer()
				PlayerDataManager:LoadData(player)

				-- Give player some coins first
				local data = PlayerDataManager:GetData(player)
				data.coins.balance = 100

				local result = CoinManager:DeductCoins(player, 30, "test")

				expect(result).to.equal(true)
				expect(data.coins.balance).to.equal(70)
			end)

			it("should reject deduction with insufficient balance", function()
				local player = createMockPlayer()
				PlayerDataManager:LoadData(player)

				local data = PlayerDataManager:GetData(player)
				data.coins.balance = 50

				local result = CoinManager:DeductCoins(player, 100, "test")

				expect(result).to.equal(false)
				expect(data.coins.balance).to.equal(50)  -- Unchanged
			end)

			it("should reject deduction amounts below minimum", function()
				local player = createMockPlayer()
				PlayerDataManager:LoadData(player)

				local data = PlayerDataManager:GetData(player)
				data.coins.balance = 100

				local result = CoinManager:DeductCoins(player, 0, "test")

				expect(result).to.equal(false)
				expect(data.coins.balance).to.equal(100)  -- Unchanged
			end)
		end)

		describe("GetBalance", function()
			it("should return correct balance", function()
				local player = createMockPlayer()
				PlayerDataManager:LoadData(player)

				local data = PlayerDataManager:GetData(player)
				data.coins.balance = 250

				local balance = CoinManager:GetBalance(player)

				expect(balance).to.equal(250)
			end)

			it("should return 0 for player with no data", function()
				local player = createMockPlayer()
				-- Don't load data

				local balance = CoinManager:GetBalance(player)

				expect(balance).to.equal(0)
			end)
		end)
	end)
end

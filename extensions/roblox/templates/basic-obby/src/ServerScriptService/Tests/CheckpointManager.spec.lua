--[[
	CheckpointManager Tests
	TestEZ unit tests for CheckpointManager

	To run: Install TestEZ plugin in Studio, click "Run Tests"
]]

return function()
	local CheckpointManager = require(script.Parent.Parent.GameSystems.CheckpointManager)
	local PlayerDataManager = require(script.Parent.Parent.GameSystems.PlayerDataManager)

	-- Mock player for testing
	local function createMockPlayer()
		return {
			Name = "TestPlayer",
			UserId = math.random(1, 1000000),
			Character = nil,
		}
	end

	describe("CheckpointManager", function()
		describe("SaveCheckpoint", function()
			it("should save valid checkpoint", function()
				local player = createMockPlayer()
				PlayerDataManager:LoadData(player)

				local result = CheckpointManager:SaveCheckpoint(player, 1)

				expect(result).to.equal(true)

				local data = PlayerDataManager:GetData(player)
				expect(data.checkpoints.current).to.equal(1)
			end)

			it("should reject negative checkpoint numbers", function()
				local player = createMockPlayer()
				PlayerDataManager:LoadData(player)

				local result = CheckpointManager:SaveCheckpoint(player, -1)

				expect(result).to.equal(false)
			end)

			it("should reject checkpoint numbers > MAX", function()
				local player = createMockPlayer()
				PlayerDataManager:LoadData(player)

				local result = CheckpointManager:SaveCheckpoint(player, 999)

				expect(result).to.equal(false)
			end)

			it("should update highest checkpoint", function()
				local player = createMockPlayer()
				PlayerDataManager:LoadData(player)

				CheckpointManager:SaveCheckpoint(player, 5)

				local data = PlayerDataManager:GetData(player)
				expect(data.checkpoints.highest).to.equal(5)
			end)

			it("should not decrease checkpoint progress", function()
				local player = createMockPlayer()
				PlayerDataManager:LoadData(player)

				CheckpointManager:SaveCheckpoint(player, 5)
				CheckpointManager:SaveCheckpoint(player, 3)

				local data = PlayerDataManager:GetData(player)
				expect(data.checkpoints.current).to.equal(5)
			end)
		end)

		describe("GetLastCheckpoint", function()
			it("should return current checkpoint", function()
				local player = createMockPlayer()
				PlayerDataManager:LoadData(player)

				CheckpointManager:SaveCheckpoint(player, 3)
				local checkpoint = CheckpointManager:GetLastCheckpoint(player)

				expect(checkpoint).to.equal(3)
			end)

			it("should return 0 for new player", function()
				local player = createMockPlayer()
				PlayerDataManager:LoadData(player)

				local checkpoint = CheckpointManager:GetLastCheckpoint(player)

				expect(checkpoint).to.equal(0)
			end)
		end)
	end)
end

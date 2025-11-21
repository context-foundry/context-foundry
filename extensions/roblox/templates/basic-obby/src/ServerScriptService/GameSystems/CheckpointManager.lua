--[[
	CheckpointManager
	Manages player checkpoint progress and respawning

	Dependencies:
		- PlayerDataManager

	Public Methods:
		SaveCheckpoint(player: Player, checkpointNumber: number) -> boolean
		GetLastCheckpoint(player: Player) -> number
		RespawnAtCheckpoint(player: Player) -> ()

	Author: Context Foundry Roblox Extension
	Version: 1.0.0
]]

local CheckpointManager = {}

-- Services
local Players = game:GetService("Players")
local ReplicatedStorage = game:GetService("ReplicatedStorage")

-- Dependencies
local PlayerDataManager = require(script.Parent.PlayerDataManager)

-- Remotes
local Remotes = ReplicatedStorage:WaitForChild("Remotes")
local UpdateCheckpointEvent = Remotes:WaitForChild("UpdateCheckpoint")

-- Constants
local MAX_CHECKPOINTS = 50
local CHECKPOINT_SAVE_DELAY = 0.5  -- Minimum time between checkpoint saves

-- Rate limiting
local lastCheckpointTime: {[number]: number} = {}

-- Public API
function CheckpointManager:SaveCheckpoint(player: Player, checkpointNumber: number): boolean
	assert(typeof(player) == "Instance" and player:IsA("Player"), "Invalid player")
	assert(type(checkpointNumber) == "number", "Invalid checkpoint number")

	-- Validate checkpoint range
	if checkpointNumber < 1 or checkpointNumber > MAX_CHECKPOINTS then
		warn(string.format("[CheckpointManager] Checkpoint number out of range: %d", checkpointNumber))
		return false
	end

	-- Rate limiting
	local userId = player.UserId
	local lastTime = lastCheckpointTime[userId] or 0
	local currentTime = tick()

	if currentTime - lastTime < CHECKPOINT_SAVE_DELAY then
		return false  -- Too soon
	end

	lastCheckpointTime[userId] = currentTime

	-- Get player data
	local data = PlayerDataManager:GetData(player)
	if not data then
		warn(string.format("[CheckpointManager] No data for player: %s", player.Name))
		return false
	end

	-- Update checkpoint (only if progressing forward)
	if checkpointNumber > data.checkpoints.current then
		data.checkpoints.current = checkpointNumber
		data.checkpoints.highest = math.max(data.checkpoints.highest, checkpointNumber)
		data.stats.checkpoints_reached += 1

		-- Notify client
		UpdateCheckpointEvent:FireClient(player, checkpointNumber)

		print(string.format("[CheckpointManager] %s reached checkpoint %d", player.Name, checkpointNumber))
		return true
	end

	return false
end

function CheckpointManager:GetLastCheckpoint(player: Player): number
	assert(typeof(player) == "Instance" and player:IsA("Player"), "Invalid player")

	local data = PlayerDataManager:GetData(player)
	return data and data.checkpoints.current or 0
end

function CheckpointManager:RespawnAtCheckpoint(player: Player): ()
	assert(typeof(player) == "Instance" and player:IsA("Player"), "Invalid player")

	local checkpointNumber = self:GetLastCheckpoint(player)

	-- Find checkpoint in workspace
	local checkpointName = "Checkpoint" .. checkpointNumber
	local checkpointsFolder = workspace:FindFirstChild("Checkpoints")

	if not checkpointsFolder then
		warn("[CheckpointManager] Checkpoints folder not found in Workspace")
		return
	end

	local checkpoint = checkpointsFolder:FindFirstChild(checkpointName)

	if checkpoint and player.Character then
		local character = player.Character
		local humanoidRootPart = character:FindFirstChild("HumanoidRootPart")

		if humanoidRootPart then
			-- Teleport to checkpoint (with offset above)
			local spawnCFrame = checkpoint.CFrame + Vector3.new(0, 5, 0)
			character:PivotTo(spawnCFrame)

			print(string.format("[CheckpointManager] Respawned %s at checkpoint %d", player.Name, checkpointNumber))
		end
	else
		-- Checkpoint not found, respawn at spawn location
		warn(string.format("[CheckpointManager] Checkpoint %d not found for %s", checkpointNumber, player.Name))
	end
end

-- Handle player death
Players.PlayerAdded:Connect(function(player)
	player.CharacterAdded:Connect(function(character)
		local humanoid = character:WaitForChild("Humanoid")

		humanoid.Died:Connect(function()
			-- Update death stats
			local data = PlayerDataManager:GetData(player)
			if data then
				data.stats.deaths += 1
			end

			-- Wait for respawn, then teleport to checkpoint
			task.wait(Players.RespawnTime)

			if player.Parent then  -- Player still in game
				CheckpointManager:RespawnAtCheckpoint(player)
			end
		end)
	end)
end)

-- Handle checkpoint touches (server-side validation)
local function setupCheckpointTouch(checkpoint: BasePart, checkpointNumber: number)
	checkpoint.Touched:Connect(function(hit)
		local character = hit.Parent
		if not character then return end

		local humanoid = character:FindFirstChild("Humanoid")
		if not humanoid then return end

		local player = Players:GetPlayerFromCharacter(character)
		if not player then return end

		-- Save checkpoint
		CheckpointManager:SaveCheckpoint(player, checkpointNumber)
	end)
end

-- Initialize checkpoints in workspace
task.spawn(function()
	local checkpointsFolder = workspace:WaitForChild("Checkpoints", 10)

	if checkpointsFolder then
		for _, checkpoint in ipairs(checkpointsFolder:GetChildren()) do
			if checkpoint:IsA("BasePart") then
				-- Extract checkpoint number from name (e.g., "Checkpoint5" -> 5)
				local checkpointNumber = tonumber(checkpoint.Name:match("%d+"))

				if checkpointNumber then
					setupCheckpointTouch(checkpoint, checkpointNumber)
				end
			end
		end

		-- Listen for new checkpoints
		checkpointsFolder.ChildAdded:Connect(function(checkpoint)
			if checkpoint:IsA("BasePart") then
				local checkpointNumber = tonumber(checkpoint.Name:match("%d+"))

				if checkpointNumber then
					setupCheckpointTouch(checkpoint, checkpointNumber)
				end
			end
		end)
	else
		warn("[CheckpointManager] Checkpoints folder not found in Workspace")
	end
end)

return table.freeze(CheckpointManager)

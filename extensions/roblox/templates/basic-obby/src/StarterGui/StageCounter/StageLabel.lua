--[[
	StageLabel
	Client-side UI script for displaying player's current checkpoint/stage

	Listens to UpdateCheckpoint RemoteEvent and updates the UI

	Author: Context Foundry Roblox Extension
	Version: 1.0.0
]]

local ReplicatedStorage = game:GetService("ReplicatedStorage")
local Players = game:GetService("Players")

local player = Players.LocalPlayer

-- Get UI elements
local screenGui = script.Parent.Parent
local stageLabel = screenGui:WaitForChild("StageCounter"):WaitForChild("StageLabel")

-- Get RemoteEvent
local Remotes = ReplicatedStorage:WaitForChild("Remotes")
local UpdateCheckpointEvent = Remotes:WaitForChild("UpdateCheckpoint")

-- Get game config for max checkpoints
local GameConfig = require(ReplicatedStorage.Modules.GameConfig)
local MAX_CHECKPOINTS = GameConfig.MAX_CHECKPOINTS or 10

-- Initialize display
local function updateStageDisplay(checkpoint: number)
	stageLabel.Text = string.format("📍 Stage: %d/%d", checkpoint, MAX_CHECKPOINTS)
end

-- Listen for checkpoint updates from server
UpdateCheckpointEvent.OnClientEvent:Connect(function(newCheckpoint)
	updateStageDisplay(newCheckpoint)
end)

-- Initialize with starting value
updateStageDisplay(0)

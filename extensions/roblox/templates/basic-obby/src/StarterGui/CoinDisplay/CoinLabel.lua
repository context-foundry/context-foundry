--[[
	CoinLabel
	Client-side UI script for displaying player's coin balance

	Listens to UpdateCoins RemoteEvent and updates the UI

	Author: Context Foundry Roblox Extension
	Version: 1.0.0
]]

local ReplicatedStorage = game:GetService("ReplicatedStorage")
local Players = game:GetService("Players")

local player = Players.LocalPlayer

-- Get UI elements
local screenGui = script.Parent.Parent
local coinLabel = screenGui:WaitForChild("CoinDisplay"):WaitForChild("CoinLabel")

-- Get RemoteEvent
local Remotes = ReplicatedStorage:WaitForChild("Remotes")
local UpdateCoinsEvent = Remotes:WaitForChild("UpdateCoins")

-- Initialize display
local function updateCoinDisplay(balance: number)
	coinLabel.Text = "💰 Coins: " .. tostring(balance)
end

-- Listen for coin updates from server
UpdateCoinsEvent.OnClientEvent:Connect(function(newBalance)
	updateCoinDisplay(newBalance)
end)

-- Initialize from leaderstats
player:WaitForChild("leaderstats")
local coinsValue = player.leaderstats:WaitForChild("Coins")

-- Update when leaderstats changes
updateCoinDisplay(coinsValue.Value)

coinsValue:GetPropertyChangedSignal("Value"):Connect(function()
	updateCoinDisplay(coinsValue.Value)
end)

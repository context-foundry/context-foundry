--[[
	CoinCollector (Client)
	Detects coin touches and requests collection from server

	Author: Context Foundry Roblox Extension
]]

local Players = game:GetService("Players")
local ReplicatedStorage = game:GetService("ReplicatedStorage")

local player = Players.LocalPlayer
local character = player.Character or player.CharacterAdded:Wait()
local humanoid = character:WaitForChild("Humanoid")

-- Remotes
local Remotes = ReplicatedStorage:WaitForChild("Remotes")
local CoinCollectedEvent = Remotes:WaitForChild("CoinCollected")

-- Track collected coins to prevent double-collection
local collectedCoins = {}

-- Find coins folder
local coinsFolder = workspace:WaitForChild("Coins", 10)

if coinsFolder then
	-- Listen for coin touches
	for _, coin in ipairs(coinsFolder:GetChildren()) do
		if coin:IsA("BasePart") then
			coin.Touched:Connect(function(hit)
				if hit.Parent == character and not collectedCoins[coin] then
					collectedCoins[coin] = true

					-- Request collection from server
					CoinCollectedEvent:FireServer(coin)
				end
			end)
		end
	end
end

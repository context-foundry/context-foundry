--[[
	ShopFrame
	Client-side UI script for the shop interface

	Displays available items and handles purchase requests
	Communicates with server via PurchaseItem RemoteEvent

	Author: Context Foundry Roblox Extension
	Version: 1.0.0
]]

local ReplicatedStorage = game:GetService("ReplicatedStorage")
local Players = game:GetService("Players")

local player = Players.LocalPlayer

-- Get UI elements
local screenGui = script.Parent.Parent
local shopFrame = screenGui:WaitForChild("ShopUI"):WaitForChild("ShopFrame")
local itemContainer = shopFrame:WaitForChild("ItemContainer")
local toggleButton = screenGui:WaitForChild("ShopUI"):WaitForChild("ToggleButton")

-- Get RemoteEvents and Config
local Remotes = ReplicatedStorage:WaitForChild("Remotes")
local PurchaseItemEvent = Remotes:WaitForChild("PurchaseItem")
local ShopConfig = require(ReplicatedStorage.Modules.ShopConfig)

-- Shop state
local isShopOpen = false

-- Toggle shop visibility
local function toggleShop()
	isShopOpen = not isShopOpen
	shopFrame.Visible = isShopOpen
	toggleButton.Text = isShopOpen and "Close Shop" or "🛒 Shop"
end

-- Create item button
local function createItemButton(itemId: string, itemData: table)
	local button = Instance.new("TextButton")
	button.Name = itemId
	button.Size = UDim2.new(1, -20, 0, 80)
	button.BackgroundColor3 = Color3.fromRGB(50, 50, 50)
	button.BorderSizePixel = 2
	button.BorderColor3 = Color3.fromRGB(100, 100, 100)
	button.Font = Enum.Font.GothamBold
	button.TextColor3 = Color3.fromRGB(255, 255, 255)
	button.TextSize = 16
	button.Text = string.format(
		"%s\n%s\n💰 %d coins",
		itemData.name,
		itemData.description,
		itemData.cost
	)
	button.TextYAlignment = Enum.TextYAlignment.Center
	button.Parent = itemContainer

	-- Handle purchase click
	button.MouseButton1Click:Connect(function()
		-- Request purchase from server
		PurchaseItemEvent:FireServer(itemId)

		-- Provide visual feedback
		button.BackgroundColor3 = Color3.fromRGB(100, 100, 100)
		button.Text = "Processing..."

		-- Reset button after delay
		task.wait(0.5)
		button.BackgroundColor3 = Color3.fromRGB(50, 50, 50)
		button.Text = string.format(
			"%s\n%s\n💰 %d coins",
			itemData.name,
			itemData.description,
			itemData.cost
		)
	end)

	return button
end

-- Populate shop items
local function populateShop()
	-- Clear existing items
	for _, child in ipairs(itemContainer:GetChildren()) do
		if child:IsA("TextButton") then
			child:Destroy()
		end
	end

	-- Create button for each item
	for itemId, itemData in pairs(ShopConfig.items) do
		createItemButton(itemId, itemData)
	end

	-- Add UIListLayout if not present
	if not itemContainer:FindFirstChildOfClass("UIListLayout") then
		local layout = Instance.new("UIListLayout")
		layout.Padding = UDim.new(0, 10)
		layout.SortOrder = Enum.SortOrder.LayoutOrder
		layout.Parent = itemContainer
	end
end

-- Initialize shop
shopFrame.Visible = false
toggleButton.MouseButton1Click:Connect(toggleShop)

-- Populate items when config is ready
populateShop()

-- Keyboard shortcut to toggle shop (B key)
local UserInputService = game:GetService("UserInputService")
UserInputService.InputBegan:Connect(function(input, gameProcessedEvent)
	if gameProcessedEvent then return end

	if input.KeyCode == Enum.KeyCode.B then
		toggleShop()
	end
end)

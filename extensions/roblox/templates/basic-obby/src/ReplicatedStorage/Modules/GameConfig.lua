--[[
	GameConfig
	Global game configuration

	Modify these settings to customize your obby game.

	Author: Context Foundry Roblox Extension
]]

local GameConfig = {
	-- Maximum number of checkpoints in the game
	MAX_CHECKPOINTS = 10,

	-- Auto-save interval in seconds
	AUTO_SAVE_INTERVAL = 300,

	-- Coin system settings
	MAX_COIN_BALANCE = 1000000,
	DEFAULT_COIN_REWARD = 10,
	COIN_COLLECT_RANGE = 20,

	-- Shop system settings
	SHOP_PURCHASE_COOLDOWN = 1,
}

return table.freeze(GameConfig)

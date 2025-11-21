--[[
	ShopConfig
	Configuration for shop items

	Author: Context Foundry Roblox Extension
]]

local ShopConfig = {
	items = {
		["speed_boost"] = {
			name = "Speed Boost",
			description = "Run 2x faster",
			cost = 100,
			category = "powerup",
		},
		["double_jump"] = {
			name = "Double Jump",
			description = "Jump twice in mid-air",
			cost = 250,
			category = "powerup",
		},
		["extra_life"] = {
			name = "Extra Life",
			description = "Respawn at last checkpoint on death",
			cost = 500,
			category = "utility",
		},
	}
}

return table.freeze(ShopConfig)

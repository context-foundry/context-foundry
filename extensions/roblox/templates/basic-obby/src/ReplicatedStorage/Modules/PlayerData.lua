--[[
	PlayerData
	Type definitions and default data structure for player data

	Author: Context Foundry Roblox Extension
]]

export type PlayerData = {
	coins: {
		balance: number,
		lifetime_earned: number,
	},
	checkpoints: {
		current: number,
		highest: number,
	},
	owned_items: {string},
	stats: {
		playtime: number,
		deaths: number,
		checkpoints_reached: number,
	},
	metadata: {
		last_save: number,
		version: string,
	},
}

local PlayerData = {}

function PlayerData.getDefault(): PlayerData
	return {
		coins = {
			balance = 0,
			lifetime_earned = 0,
		},
		checkpoints = {
			current = 0,
			highest = 0,
		},
		owned_items = {},
		stats = {
			playtime = 0,
			deaths = 0,
			checkpoints_reached = 0,
		},
		metadata = {
			last_save = os.time(),
			version = "1.0",
		},
	}
end

return table.freeze(PlayerData)

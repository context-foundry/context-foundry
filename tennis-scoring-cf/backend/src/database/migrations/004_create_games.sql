-- Migration: Create games table
-- Description: Stores game information within sets

CREATE TABLE IF NOT EXISTS games (
  id SERIAL PRIMARY KEY,
  set_id INTEGER NOT NULL REFERENCES sets(id) ON DELETE CASCADE,
  game_number INTEGER NOT NULL,
  server INTEGER NOT NULL,
  player1_points INTEGER DEFAULT 0,
  player2_points INTEGER DEFAULT 0,
  winner INTEGER,
  completed_at TIMESTAMP,

  CONSTRAINT chk_server CHECK (server IN (1, 2)),
  CONSTRAINT chk_game_winner CHECK (winner IN (1, 2)),
  UNIQUE(set_id, game_number)
);

-- Index for performance
CREATE INDEX idx_games_set_id ON games(set_id);

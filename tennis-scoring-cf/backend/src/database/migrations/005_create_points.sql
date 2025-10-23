-- Migration: Create points table
-- Description: Stores individual point history

CREATE TABLE IF NOT EXISTS points (
  id SERIAL PRIMARY KEY,
  game_id INTEGER NOT NULL REFERENCES games(id) ON DELETE CASCADE,
  point_number INTEGER NOT NULL,
  winner INTEGER NOT NULL,
  score_after VARCHAR(20),
  created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,

  CONSTRAINT chk_point_winner CHECK (winner IN (1, 2))
);

-- Index for performance
CREATE INDEX idx_points_game_id ON points(game_id);

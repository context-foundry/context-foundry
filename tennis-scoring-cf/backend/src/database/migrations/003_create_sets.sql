-- Migration: Create sets table
-- Description: Stores set information for matches

CREATE TABLE IF NOT EXISTS sets (
  id SERIAL PRIMARY KEY,
  match_id INTEGER NOT NULL REFERENCES matches(id) ON DELETE CASCADE,
  set_number INTEGER NOT NULL,
  player1_games INTEGER DEFAULT 0,
  player2_games INTEGER DEFAULT 0,
  tiebreak_score JSONB,
  winner INTEGER,
  completed_at TIMESTAMP,

  CONSTRAINT chk_set_winner CHECK (winner IN (1, 2)),
  UNIQUE(match_id, set_number)
);

-- Index for performance
CREATE INDEX idx_sets_match_id ON sets(match_id);

-- Migration: Create matches table
-- Description: Stores tennis match information

CREATE TABLE IF NOT EXISTS matches (
  id SERIAL PRIMARY KEY,
  created_by INTEGER NOT NULL REFERENCES users(id) ON DELETE CASCADE,
  player1_name VARCHAR(255) NOT NULL,
  player2_name VARCHAR(255) NOT NULL,
  player3_name VARCHAR(255),
  player4_name VARCHAR(255),
  match_type VARCHAR(20) NOT NULL DEFAULT 'singles',
  format VARCHAR(20) NOT NULL DEFAULT 'best_of_3',
  status VARCHAR(20) NOT NULL DEFAULT 'scheduled',
  winner INTEGER,
  location VARCHAR(255),
  scheduled_at TIMESTAMP,
  started_at TIMESTAMP,
  completed_at TIMESTAMP,
  metadata JSONB,
  created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
  updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,

  CONSTRAINT chk_match_type CHECK (match_type IN ('singles', 'doubles')),
  CONSTRAINT chk_format CHECK (format IN ('best_of_3', 'best_of_5')),
  CONSTRAINT chk_status CHECK (status IN ('scheduled', 'in_progress', 'completed', 'cancelled')),
  CONSTRAINT chk_winner CHECK (winner IN (1, 2))
);

-- Indexes for performance
CREATE INDEX idx_matches_status ON matches(status);
CREATE INDEX idx_matches_created_by ON matches(created_by);
CREATE INDEX idx_matches_scheduled_at ON matches(scheduled_at);
CREATE INDEX idx_matches_status_date ON matches(status, scheduled_at);

-- Trigger to update updated_at timestamp
CREATE TRIGGER update_matches_updated_at
BEFORE UPDATE ON matches
FOR EACH ROW
EXECUTE FUNCTION update_updated_at_column();

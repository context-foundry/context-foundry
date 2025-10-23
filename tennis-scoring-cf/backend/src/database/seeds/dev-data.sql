-- Seed data for development and testing
-- This file provides sample data to test the application

-- Insert sample users (passwords are 'Password123!')
INSERT INTO users (email, password_hash, role, first_name, last_name, school_name) VALUES
  ('coach@test.com', '$2b$12$LQv3c1yqBWVHxkd0LHAkCOYz6TtxMQJqhN8/LewY5gyV3uVDvU2C2', 'coach', 'John', 'Smith', 'Lincoln High School'),
  ('coach2@test.com', '$2b$12$LQv3c1yqBWVHxkd0LHAkCOYz6TtxMQJqhN8/LewY5gyV3uVDvU2C2', 'coach', 'Sarah', 'Johnson', 'Washington High School'),
  ('viewer@test.com', '$2b$12$LQv3c1yqBWVHxkd0LHAkCOYz6TtxMQJqhN8/LewY5gyV3uVDvU2C2', 'viewer', 'Mike', 'Davis', NULL)
ON CONFLICT (email) DO NOTHING;

-- Insert sample matches
INSERT INTO matches (created_by, player1_name, player2_name, match_type, format, status, location, scheduled_at) VALUES
  (1, 'Roger Federer', 'Rafael Nadal', 'singles', 'best_of_3', 'completed', 'Court 1', NOW() - INTERVAL '2 days'),
  (1, 'Novak Djokovic', 'Andy Murray', 'singles', 'best_of_3', 'completed', 'Court 2', NOW() - INTERVAL '1 day'),
  (2, 'Serena Williams', 'Venus Williams', 'singles', 'best_of_3', 'scheduled', 'Court 1', NOW() + INTERVAL '1 day')
ON CONFLICT DO NOTHING;

-- Note: For completed matches, you would also insert sets, games, and points data
-- This is left as an exercise or can be added when needed for more comprehensive testing

COMMIT;

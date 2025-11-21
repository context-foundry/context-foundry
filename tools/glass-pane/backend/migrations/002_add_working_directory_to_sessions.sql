-- Migration: Add working_directory to chat_sessions
-- Created: 2025-11-16
-- Description: Enables per-session working directory configuration for Claude CLI execution

-- Add working_directory column to chat_sessions table
ALTER TABLE chat_sessions ADD COLUMN working_directory TEXT;

-- Create index for faster lookups by working directory
CREATE INDEX IF NOT EXISTS idx_chat_sessions_working_directory
ON chat_sessions(working_directory);

-- Add comment explaining the column
-- Note: NULL working_directory means use backend's current working directory
-- Non-null values must be absolute paths to existing directories

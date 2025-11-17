-- Migration: Add chat sessions and messages tables for Forge chat interface
-- Created: 2025-11-16
-- Description: Adds persistent chat storage with sessions and message history

-- Chat Sessions table
CREATE TABLE IF NOT EXISTS chat_sessions (
    id TEXT PRIMARY KEY,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    last_activity TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    model TEXT DEFAULT 'sonnet',  -- sonnet, opus, haiku
    plan_mode BOOLEAN DEFAULT 0,
    bypass_permissions BOOLEAN DEFAULT 0,
    title TEXT,  -- User-defined session title
    message_count INTEGER DEFAULT 0
);

-- Chat Messages table
CREATE TABLE IF NOT EXISTS chat_messages (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    session_id TEXT NOT NULL,
    role TEXT NOT NULL,  -- 'user' | 'assistant' | 'system'
    content TEXT NOT NULL,
    timestamp TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    tokens_used INTEGER,  -- Track token usage per message
    FOREIGN KEY (session_id) REFERENCES chat_sessions(id) ON DELETE CASCADE
);

-- Create indices for performance
CREATE INDEX IF NOT EXISTS idx_chat_messages_session ON chat_messages(session_id);
CREATE INDEX IF NOT EXISTS idx_chat_messages_timestamp ON chat_messages(timestamp DESC);
CREATE INDEX IF NOT EXISTS idx_chat_sessions_last_activity ON chat_sessions(last_activity DESC);

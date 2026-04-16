-- Migration 004: Add offline-first exam monitoring tables
-- Creates exam_sessions table and adds browser_history table

-- Exam sessions table (replaces the old session concept)
CREATE TABLE IF NOT EXISTS exam_sessions (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    roll_no TEXT NOT NULL,
    lab_no TEXT NOT NULL,
    start_time DOUBLE PRECISION NOT NULL,
    end_time DOUBLE PRECISION,
    secret_key_verified INTEGER DEFAULT 0,
    synced INTEGER DEFAULT 0,
    created_at TIMESTAMPTZ DEFAULT NOW()
);

-- Index for fast lookups
CREATE INDEX IF NOT EXISTS idx_exam_sessions_roll ON exam_sessions(roll_no);
CREATE INDEX IF NOT EXISTS idx_exam_sessions_active ON exam_sessions(end_time) WHERE end_time IS NULL;

-- Browser history table (was only in local SQLite before)
CREATE TABLE IF NOT EXISTS browser_history (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    session_id UUID NOT NULL REFERENCES exam_sessions(id) ON DELETE CASCADE,
    student_id UUID,
    url TEXT NOT NULL,
    title TEXT,
    visit_count INTEGER DEFAULT 1,
    last_visited TIMESTAMPTZ NOT NULL,
    browser TEXT,
    created_at TIMESTAMPTZ DEFAULT NOW(),
    UNIQUE(session_id, student_id, url)
);

-- Index for browser history queries
CREATE INDEX IF NOT EXISTS idx_browser_history_session ON browser_history(session_id);
CREATE INDEX IF NOT EXISTS idx_browser_history_last_visited ON browser_history(last_visited DESC);

-- Add missing columns to existing tables if they don't exist
-- For live_processes
ALTER TABLE live_processes ADD COLUMN IF NOT EXISTS risk_level TEXT DEFAULT 'normal';
ALTER TABLE live_processes ADD COLUMN IF NOT EXISTS category TEXT;
ALTER TABLE live_processes ADD COLUMN IF NOT EXISTS label TEXT;
ALTER TABLE live_processes ADD COLUMN IF NOT EXISTS is_incognito BOOLEAN DEFAULT FALSE;

-- For connected_devices
ALTER TABLE connected_devices ADD COLUMN IF NOT EXISTS readable_name TEXT;
ALTER TABLE connected_devices ADD COLUMN IF NOT EXISTS risk_level TEXT DEFAULT 'normal';
ALTER TABLE connected_devices ADD COLUMN IF NOT EXISTS message TEXT;

-- For terminal_events
ALTER TABLE terminal_events ADD COLUMN IF NOT EXISTS full_command TEXT;

-- Note: We're keeping all existing tables and data for backward compatibility

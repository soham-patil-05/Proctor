-- 004_add_browser_history.sql
-- Adds browser history storage and additive timestamp columns used by telemetry queries.

CREATE TABLE IF NOT EXISTS browser_history (
  id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
  session_id UUID NOT NULL REFERENCES sessions(id) ON DELETE CASCADE,
  student_id UUID NOT NULL REFERENCES students(id) ON DELETE CASCADE,
  url TEXT,
  title TEXT,
  visit_count INT DEFAULT 1,
  last_visit TEXT,
  synced BOOLEAN DEFAULT false,
  created_at timestamptz NOT NULL DEFAULT now(),
  recorded_at timestamptz NOT NULL DEFAULT now()
);

CREATE INDEX IF NOT EXISTS idx_browser_history_student
  ON browser_history (session_id, student_id, created_at DESC);

ALTER TABLE live_processes
  ADD COLUMN IF NOT EXISTS recorded_at timestamptz DEFAULT now();

ALTER TABLE connected_devices
  ADD COLUMN IF NOT EXISTS recorded_at timestamptz DEFAULT now();

ALTER TABLE network_info
  ADD COLUMN IF NOT EXISTS recorded_at timestamptz DEFAULT now();

ALTER TABLE domain_activity
  ADD COLUMN IF NOT EXISTS recorded_at timestamptz DEFAULT now();

ALTER TABLE terminal_events
  ADD COLUMN IF NOT EXISTS recorded_at timestamptz DEFAULT now();

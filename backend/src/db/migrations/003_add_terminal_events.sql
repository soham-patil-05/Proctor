-- 003_add_terminal_events.sql
-- Adds the terminal_events table to persist terminal_request and
-- terminal_command events sent by the network monitor's ss / auditd layers.
-- Safe to run multiple times (idempotent).

CREATE TABLE IF NOT EXISTS terminal_events (
  id            UUID        PRIMARY KEY DEFAULT uuid_generate_v4(),
  session_id    UUID        NOT NULL REFERENCES sessions(id) ON DELETE CASCADE,
  student_id    UUID        NOT NULL REFERENCES students(id) ON DELETE CASCADE,
  event_type    TEXT        NOT NULL CHECK (event_type IN ('terminal_request', 'terminal_command')),
  tool          TEXT        NOT NULL,
  remote_ip     TEXT,                          -- Layer 1 (ss) only
  remote_host   TEXT,                          -- Layer 1 (ss) only
  remote_port   INT,                           -- Layer 1 (ss) only
  pid           INT,                           -- Layer 1 (ss) only
  full_command  TEXT,                          -- Layer 2 (auditd) only
  risk_level    TEXT        NOT NULL DEFAULT 'medium',
  message       TEXT,
  detected_at   timestamptz NOT NULL DEFAULT now()
);

CREATE INDEX IF NOT EXISTS idx_terminal_events_student
  ON terminal_events (student_id, session_id, detected_at DESC);

CREATE INDEX IF NOT EXISTS idx_terminal_events_risk
  ON terminal_events (session_id, risk_level);

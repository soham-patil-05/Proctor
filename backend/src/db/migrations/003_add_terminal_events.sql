-- 003_add_terminal_events.sql
-- FIX: Removed CHECK (event_type IN ('terminal_request', 'terminal_command'))
--      The client can send other event_type values. The strict CHECK caused every
--      insert that didn't match exactly to fail with a 500.
-- FIX: Made tool nullable — client doesn't always send a tool field.
-- FIX: Made risk_level nullable with default — not always present in payload.
-- Safe to run multiple times (idempotent).

CREATE TABLE IF NOT EXISTS terminal_events (
  id            UUID        PRIMARY KEY DEFAULT uuid_generate_v4(),
  session_id    UUID        NOT NULL REFERENCES sessions(id) ON DELETE CASCADE,
  student_id    UUID        NOT NULL REFERENCES students(id) ON DELETE CASCADE,
  event_type    TEXT        NOT NULL,
  tool          TEXT,
  remote_ip     TEXT,
  remote_host   TEXT,
  remote_port   INT,
  pid           INT,
  full_command  TEXT,
  risk_level    TEXT        NOT NULL DEFAULT 'medium',
  message       TEXT,
  detected_at   timestamptz NOT NULL DEFAULT now()
);

CREATE INDEX IF NOT EXISTS idx_terminal_events_student
  ON terminal_events (student_id, session_id, detected_at DESC);

CREATE INDEX IF NOT EXISTS idx_terminal_events_risk
  ON terminal_events (session_id, risk_level);

-- 002_add_insights_columns.sql
-- Non-destructive migration: adds enrichment columns for examiner-friendly insights.
-- Safe to run multiple times (uses IF NOT EXISTS / ADD COLUMN IF NOT EXISTS for PG 9.6+).

-- connected_devices: new enrichment columns
DO $$
BEGIN
  IF NOT EXISTS (SELECT 1 FROM information_schema.columns WHERE table_name='connected_devices' AND column_name='readable_name') THEN
    ALTER TABLE connected_devices ADD COLUMN readable_name TEXT;
  END IF;
  IF NOT EXISTS (SELECT 1 FROM information_schema.columns WHERE table_name='connected_devices' AND column_name='risk_level') THEN
    ALTER TABLE connected_devices ADD COLUMN risk_level TEXT;
  END IF;
  IF NOT EXISTS (SELECT 1 FROM information_schema.columns WHERE table_name='connected_devices' AND column_name='message') THEN
    ALTER TABLE connected_devices ADD COLUMN message TEXT;
  END IF;
END $$;

-- live_processes: new enrichment columns
DO $$
BEGIN
  IF NOT EXISTS (SELECT 1 FROM information_schema.columns WHERE table_name='live_processes' AND column_name='risk_level') THEN
    ALTER TABLE live_processes ADD COLUMN risk_level TEXT;
  END IF;
  IF NOT EXISTS (SELECT 1 FROM information_schema.columns WHERE table_name='live_processes' AND column_name='category') THEN
    ALTER TABLE live_processes ADD COLUMN category TEXT;
  END IF;
END $$;

-- domain_activity: new table
CREATE TABLE IF NOT EXISTS domain_activity (
  id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
  session_id UUID NOT NULL REFERENCES sessions(id) ON DELETE CASCADE,
  student_id UUID NOT NULL REFERENCES students(id) ON DELETE CASCADE,
  domain TEXT NOT NULL,
  request_count INT DEFAULT 0,
  risk_level TEXT DEFAULT 'normal',
  last_accessed timestamptz DEFAULT now(),
  UNIQUE(session_id, student_id, domain)
);

CREATE INDEX IF NOT EXISTS idx_domain_activity_student ON domain_activity(student_id, session_id);

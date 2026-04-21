-- 005_fix_constraints.sql
-- Fixes all constraints that cause 500 errors on ingest without dropping any tables or data.
-- Safe to run multiple times.

-- 1. Add UNIQUE(teacher_id, name) to subjects if missing
--    Required for ON CONFLICT (teacher_id, name) in ensureSubject() to work.
DO $$
BEGIN
  IF NOT EXISTS (
    SELECT 1 FROM pg_constraint
    WHERE conname = 'subjects_teacher_id_name_key'
      AND conrelid = 'subjects'::regclass
  ) THEN
    ALTER TABLE subjects ADD CONSTRAINT subjects_teacher_id_name_key UNIQUE (teacher_id, name);
  END IF;
END $$;

-- 2. Drop the strict device_type CHECK on connected_devices (client sends varied types)
DO $$
BEGIN
  IF EXISTS (
    SELECT 1 FROM pg_constraint
    WHERE contype = 'c'
      AND conrelid = 'connected_devices'::regclass
      AND conname LIKE '%device_type%'
  ) THEN
    ALTER TABLE connected_devices DROP CONSTRAINT IF EXISTS connected_devices_device_type_check;
  END IF;
END $$;

-- 3. Drop the strict status CHECK on live_processes (client sends 'sleeping', 'zombie', etc.)
DO $$
BEGIN
  IF EXISTS (
    SELECT 1 FROM pg_constraint
    WHERE contype = 'c'
      AND conrelid = 'live_processes'::regclass
      AND conname LIKE '%status%'
  ) THEN
    ALTER TABLE live_processes DROP CONSTRAINT IF EXISTS live_processes_status_check;
  END IF;
END $$;

-- 4. Drop the strict event_type CHECK on terminal_events (client sends varied event types)
DO $$
BEGIN
  IF EXISTS (
    SELECT 1 FROM pg_constraint
    WHERE contype = 'c'
      AND conrelid = 'terminal_events'::regclass
      AND conname LIKE '%event_type%'
  ) THEN
    ALTER TABLE terminal_events DROP CONSTRAINT IF EXISTS terminal_events_event_type_check;
  END IF;
END $$;

-- 5. Make terminal_events.tool nullable (client doesn't always send it)
DO $$
BEGIN
  IF EXISTS (
    SELECT 1 FROM information_schema.columns
    WHERE table_name = 'terminal_events'
      AND column_name = 'tool'
      AND is_nullable = 'NO'
  ) THEN
    ALTER TABLE terminal_events ALTER COLUMN tool DROP NOT NULL;
  END IF;
END $$;

-- 6. Set default for connected_devices.device_id so NULLs don't break unique index
DO $$
BEGIN
  IF EXISTS (
    SELECT 1 FROM information_schema.columns
    WHERE table_name = 'connected_devices' AND column_name = 'device_id'
  ) THEN
    ALTER TABLE connected_devices ALTER COLUMN device_id SET DEFAULT 'unknown';
  END IF;
END $$;

-- 7. Set default for live_processes.process_name to avoid NOT NULL violations
DO $$
BEGIN
  IF EXISTS (
    SELECT 1 FROM information_schema.columns
    WHERE table_name = 'live_processes' AND column_name = 'process_name'
  ) THEN
    ALTER TABLE live_processes ALTER COLUMN process_name SET DEFAULT 'unknown';
  END IF;
END $$;

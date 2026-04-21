-- Enable extensions
CREATE EXTENSION IF NOT EXISTS "uuid-ossp";
CREATE EXTENSION IF NOT EXISTS "pgcrypto";

-- teachers
CREATE TABLE IF NOT EXISTS teachers (
  id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
  email TEXT UNIQUE NOT NULL,
  name TEXT NOT NULL,
  password_hash TEXT NOT NULL,
  role TEXT NOT NULL DEFAULT 'teacher',
  created_at timestamptz NOT NULL DEFAULT now()
);

-- students
CREATE TABLE IF NOT EXISTS students (
  id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
  roll_no TEXT UNIQUE NOT NULL,
  name TEXT NOT NULL,
  email TEXT,
  department TEXT,
  year int,
  created_at timestamptz NOT NULL DEFAULT now()
);

-- subjects
-- FIX: Added UNIQUE(teacher_id, name) so ensureSubject ON CONFLICT works correctly.
-- Without this constraint the ON CONFLICT clause in the controller has no target and throws.
CREATE TABLE IF NOT EXISTS subjects (
  id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
  teacher_id UUID NOT NULL REFERENCES teachers(id) ON DELETE CASCADE,
  name TEXT NOT NULL,
  department TEXT,
  year int,
  created_at timestamptz NOT NULL DEFAULT now(),
  UNIQUE(teacher_id, name)
);

-- sessions
CREATE TABLE IF NOT EXISTS sessions (
  id UUID PRIMARY KEY,
  subject_id UUID NOT NULL REFERENCES subjects(id) ON DELETE CASCADE,
  batch TEXT NOT NULL,
  lab_name TEXT NOT NULL,
  date date NOT NULL,
  start_time time NOT NULL,
  end_time timestamptz,
  is_live boolean NOT NULL DEFAULT false,
  password TEXT,
  created_by UUID NOT NULL REFERENCES teachers(id),
  created_at timestamptz NOT NULL DEFAULT now()
);

-- session_students
CREATE TABLE IF NOT EXISTS session_students (
  id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
  session_id UUID NOT NULL REFERENCES sessions(id) ON DELETE CASCADE,
  student_id UUID NOT NULL REFERENCES students(id) ON DELETE CASCADE,
  last_seen_at timestamptz,
  current_status TEXT DEFAULT 'normal',
  joined_at timestamptz DEFAULT now(),
  UNIQUE(session_id, student_id)
);

-- connected_devices
-- FIX: Removed CHECK (device_type IN ('usb','external')) — client may send other device
--      types (e.g. 'bluetooth', 'hid'). A strict CHECK caused every such insert to fail.
-- FIX: device_id defaults to a generated value when NULL so the UNIQUE constraint
--      (session_id, student_id, device_id) never collides on NULL vs NULL comparisons.
CREATE TABLE IF NOT EXISTS connected_devices (
  id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
  session_id UUID NOT NULL REFERENCES sessions(id) ON DELETE CASCADE,
  student_id UUID NOT NULL REFERENCES students(id) ON DELETE CASCADE,
  device_id TEXT NOT NULL DEFAULT 'unknown',
  device_name TEXT NOT NULL,
  device_type TEXT NOT NULL DEFAULT 'usb',
  connected_at timestamptz NOT NULL DEFAULT now(),
  disconnected_at timestamptz,
  metadata jsonb,
  readable_name TEXT,
  risk_level TEXT,
  message TEXT,
  UNIQUE(session_id, student_id, device_id)
);

-- network_info
CREATE TABLE IF NOT EXISTS network_info (
  id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
  session_id UUID NOT NULL REFERENCES sessions(id) ON DELETE CASCADE,
  student_id UUID NOT NULL REFERENCES students(id) ON DELETE CASCADE,
  ip_address TEXT,
  gateway TEXT,
  dns jsonb,
  active_connections int,
  updated_at timestamptz NOT NULL DEFAULT now(),
  UNIQUE(session_id, student_id)
);

-- live_processes
-- FIX: Removed CHECK (status IN ('running','ended')) — client sends other statuses
--      (e.g. 'sleeping', 'zombie', 'disk-sleep'). Strict CHECK caused every such row to fail.
CREATE TABLE IF NOT EXISTS live_processes (
  id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
  session_id UUID NOT NULL REFERENCES sessions(id) ON DELETE CASCADE,
  student_id UUID NOT NULL REFERENCES students(id) ON DELETE CASCADE,
  pid int NOT NULL,
  process_name TEXT NOT NULL DEFAULT 'unknown',
  cpu_percent NUMERIC(5,2) DEFAULT 0,
  memory_mb NUMERIC(10,2) DEFAULT 0,
  status TEXT NOT NULL DEFAULT 'running',
  updated_at timestamptz NOT NULL DEFAULT now(),
  risk_level TEXT,
  category TEXT,
  UNIQUE(session_id, student_id, pid)
);

-- optional process_history (not strictly required)
CREATE TABLE IF NOT EXISTS process_history (
  id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
  session_id UUID,
  student_id UUID,
  pid int,
  process_name TEXT,
  cpu_percent NUMERIC(5,2),
  memory_mb NUMERIC(10,2),
  status TEXT,
  recorded_at timestamptz DEFAULT now()
);

-- domain_activity
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

CREATE INDEX IF NOT EXISTS idx_students_roll_no ON students(roll_no);
CREATE INDEX IF NOT EXISTS idx_sessions_is_live ON sessions(is_live);
CREATE INDEX IF NOT EXISTS idx_session_students_status ON session_students(session_id, current_status);
CREATE INDEX IF NOT EXISTS idx_live_processes_student ON live_processes(student_id, session_id);
CREATE INDEX IF NOT EXISTS idx_domain_activity_student ON domain_activity(student_id, session_id);

import { v5 as uuidv5, validate as uuidValidate } from 'uuid';
import { query } from '../db/index.js';

const SESSION_NAMESPACE = '2ffce69a-b3c9-4d84-a6f7-a67dd6a958cc';

function normalizeSessionId(sessionId) {
  if (!sessionId) return null;
  const s = String(sessionId).trim();
  return uuidValidate(s) ? s : uuidv5(s, SESSION_NAMESPACE);
}

async function ensureTeacherAndSubject() {
  const teacherRes = await query(
    `INSERT INTO teachers (email, name, password_hash, role)
     VALUES ($1, $2, $3, 'teacher')
     ON CONFLICT (email) DO UPDATE SET name = EXCLUDED.name
     RETURNING id`,
    ['system@labguardian.local', 'LabGuardian System', 'disabled']
  );
  const teacherId = teacherRes.rows[0].id;

  const subjectRes = await query(
    `INSERT INTO subjects (teacher_id, name, department, year)
     VALUES ($1, 'Telemetry Subject', 'SYSTEM', 0)
     RETURNING id`,
    [teacherId]
  );

  return { teacherId, subjectId: subjectRes.rows[0].id };
}

async function ensureSession(sessionId, labNo) {
  const normalized = normalizeSessionId(sessionId);
  const existing = await query('SELECT id FROM sessions WHERE id = $1', [normalized]);
  if (existing.rows.length > 0) return normalized;

  const { teacherId, subjectId } = await ensureTeacherAndSubject();
  await query(
    `INSERT INTO sessions (id, subject_id, batch, lab_name, date, start_time, is_live, created_by)
     VALUES ($1, $2, 'N/A', $3, CURRENT_DATE, CURRENT_TIME, false, $4)
     ON CONFLICT (id) DO NOTHING`,
    [normalized, subjectId, labNo || 'N/A', teacherId]
  );

  return normalized;
}

async function ensureStudent(rollNo, name) {
  const result = await query(
    `INSERT INTO students (roll_no, name)
     VALUES ($1, $2)
     ON CONFLICT (roll_no) DO UPDATE SET name = COALESCE(EXCLUDED.name, students.name)
     RETURNING id`,
    [rollNo, name || rollNo]
  );
  return result.rows[0].id;
}

async function ensureSessionStudent(sessionId, studentId) {
  await query(
    `INSERT INTO session_students (session_id, student_id, current_status, last_seen_at)
     VALUES ($1, $2, 'normal', now())
     ON CONFLICT (session_id, student_id)
     DO UPDATE SET last_seen_at = now()`,
    [sessionId, studentId]
  );
}

export async function ingestTelemetry(req, res) {
  const {
    sessionId,
    rollNo,
    labNo,
    name,
    devices = [],
    browserHistory = [],
    processes = [],
    terminalEvents = [],
  } = req.body || {};

  if (!sessionId || !rollNo) {
    return res.status(400).json({ error: 'Missing required fields' });
  }

  try {
    const resolvedSessionId = await ensureSession(sessionId, labNo);
    const studentId = await ensureStudent(rollNo, name);
    await ensureSessionStudent(resolvedSessionId, studentId);

    for (const device of devices) {
      const metadata = typeof device?.metadata === 'string'
        ? device.metadata
        : JSON.stringify(device?.metadata || {});

      await query(
        `INSERT INTO connected_devices
           (id, session_id, student_id, device_id, device_name, device_type, connected_at, metadata, readable_name, risk_level, message)
         VALUES (uuid_generate_v4(), $1, $2, $3, $4, $5, now(), $6::jsonb, $7, $8, $9)`,
        [
          resolvedSessionId,
          studentId,
          device?.id ?? null,
          device?.name ?? device?.readable_name ?? 'USB Storage Device',
          device?.device_type ?? 'usb',
          metadata,
          device?.readable_name ?? null,
          device?.risk_level ?? null,
          device?.message ?? null,
        ]
      );
    }

    for (const history of browserHistory) {
      await query(
        `INSERT INTO browser_history
           (session_id, roll_no, url, title, visit_count, last_visited, browser)
         VALUES ($1, $2, $3, $4, $5, $6, $7)`,
        [
          String(resolvedSessionId),
          String(rollNo),
          history?.url ?? null,
          history?.title ?? null,
          history?.visit_count ?? 1,
          history?.last_visited ?? null,
          history?.browser ?? null,
        ]
      );
    }

    for (const process of processes) {
      await query(
        `INSERT INTO live_processes
           (id, session_id, student_id, pid, process_name, cpu_percent, memory_mb, status, risk_level, category, updated_at)
         VALUES (uuid_generate_v4(), $1, $2, $3, $4, $5, $6, $7, $8, $9, now())`,
        [
          resolvedSessionId,
          studentId,
          process?.pid ?? null,
          process?.name ?? process?.label ?? null,
          process?.cpu ?? null,
          process?.memory ?? null,
          process?.status ?? 'running',
          process?.risk_level ?? null,
          process?.category ?? null,
        ]
      );
    }

    for (const event of terminalEvents) {
      await query(
        `INSERT INTO terminal_events
           (id, session_id, student_id, event_type, tool, remote_ip, remote_host, remote_port, pid, full_command, risk_level, message, detected_at)
         VALUES (uuid_generate_v4(), $1, $2, $3, $4, $5, $6, $7, $8, $9, $10, $11, COALESCE($12::timestamptz, now()))`,
        [
          resolvedSessionId,
          studentId,
          event?.event_type ?? null,
          event?.tool ?? null,
          event?.remote_ip ?? null,
          event?.remote_host ?? null,
          event?.remote_port ?? null,
          event?.pid ?? null,
          event?.full_command ?? null,
          event?.risk_level ?? null,
          event?.message ?? null,
          event?.detected_at ?? null,
        ]
      );
    }

    return res.json({ success: true });
  } catch (_err) {
    return res.status(500).json({ error: 'Ingest failed' });
  }
}

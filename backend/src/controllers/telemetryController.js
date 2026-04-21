import { v5 as uuidv5, validate as uuidValidate } from 'uuid';
import { query } from '../db/index.js';

const SESSION_NAMESPACE = '2ffce69a-b3c9-4d84-a6f7-a67dd6a958cc';

function normalizeSessionId(sessionId) {
  if (!sessionId) return null;
  const s = String(sessionId).trim();
  return uuidValidate(s) ? s : uuidv5(s, SESSION_NAMESPACE);
}

// UUID v4 generated in JS — no uuid-ossp extension needed at runtime
function generateUuid() {
  return 'xxxxxxxx-xxxx-4xxx-yxxx-xxxxxxxxxxxx'.replace(/[xy]/g, (c) => {
    const r = (Math.random() * 16) | 0;
    return (c === 'x' ? r : (r & 0x3) | 0x8).toString(16);
  });
}

// Always returns a valid JSON string — never throws
function safeJsonString(value) {
  if (value == null) return '{}';
  if (typeof value === 'string') {
    try { JSON.parse(value); return value; } catch { return JSON.stringify({ raw: value }); }
  }
  try { return JSON.stringify(value); } catch { return '{}'; }
}

// Normalise process status to one of the two values the old schema accepted.
// After running migration 005 this guard is no longer strictly needed,
// but it prevents any future constraint issues.
function normalizeStatus(status) {
  if (!status) return 'running';
  const s = String(status).toLowerCase();
  // Map common psutil / platform statuses to our two canonical values
  const ended = ['ended', 'zombie', 'dead', 'stopped', 'exit'];
  return ended.includes(s) ? 'ended' : 'running';
}

// Normalise device_type to one of the two values the old schema accepted.
// After running migration 005 this guard is no longer strictly needed.
function normalizeDeviceType(type) {
  if (!type) return 'usb';
  const t = String(type).toLowerCase();
  return t === 'external' ? 'external' : 'usb';
}

// Normalise event_type for terminal_events.
// After running migration 005 this guard is no longer strictly needed.
function normalizeEventType(type) {
  if (!type) return 'terminal_command';
  const t = String(type).toLowerCase();
  if (t.includes('request')) return 'terminal_request';
  if (t.includes('command')) return 'terminal_command';
  // Accept any value — migration 005 drops the CHECK constraint
  return t;
}

async function ensureTeacher() {
  const result = await query(
    `INSERT INTO teachers (email, name, password_hash, role)
     VALUES ($1, $2, $3, 'teacher')
     ON CONFLICT (email) DO UPDATE SET name = EXCLUDED.name
     RETURNING id`,
    ['system@labguardian.local', 'LabGuardian System', 'disabled']
  );
  return result.rows[0].id;
}

// Requires UNIQUE(teacher_id, name) on subjects — added by migration 005_fix_constraints.sql
async function ensureSubject(teacherId) {
  const result = await query(
    `INSERT INTO subjects (teacher_id, name, department, year)
     VALUES ($1, 'Telemetry Subject', 'SYSTEM', 0)
     ON CONFLICT (teacher_id, name) DO UPDATE SET name = EXCLUDED.name
     RETURNING id`,
    [teacherId]
  );
  return result.rows[0].id;
}

async function ensureSession(sessionId, labNo) {
  const normalized = normalizeSessionId(sessionId);

  const existing = await query('SELECT id FROM sessions WHERE id = $1', [normalized]);
  if (existing.rows.length > 0) return normalized;

  const teacherId = await ensureTeacher();
  const subjectId = await ensureSubject(teacherId);

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
    // ── 1. Identity resolution ──────────────────────────────────────────────
    let resolvedSessionId;
    try {
      resolvedSessionId = await ensureSession(sessionId, labNo);
    } catch (err) {
      console.error('[Telemetry] ensureSession failed:', err.message);
      throw err;
    }

    let studentId;
    try {
      studentId = await ensureStudent(rollNo, name);
    } catch (err) {
      console.error('[Telemetry] ensureStudent failed:', err.message);
      throw err;
    }

    try {
      await ensureSessionStudent(resolvedSessionId, studentId);
    } catch (err) {
      console.error('[Telemetry] ensureSessionStudent failed:', err.message);
      throw err;
    }

    // ── 2. Devices ──────────────────────────────────────────────────────────
    for (const device of devices) {
      const metadata = safeJsonString(device?.metadata);
      // FIX: device_id fallback to generateUuid() when null/undefined so the
      //      UNIQUE(session_id, student_id, device_id) constraint never sees NULL
      const deviceId = device?.id ? String(device.id) : generateUuid();
      // FIX: normalizeDeviceType guards the old CHECK (device_type IN ('usb','external'))
      const deviceType = normalizeDeviceType(device?.device_type);

      try {
        await query(
          `INSERT INTO connected_devices
             (id, session_id, student_id, device_id, device_name, device_type,
              connected_at, metadata, readable_name, risk_level, message)
           VALUES ($1, $2, $3, $4, $5, $6, now(), $7::jsonb, $8, $9, $10)
           ON CONFLICT (session_id, student_id, device_id)
           DO UPDATE SET
             device_name   = EXCLUDED.device_name,
             device_type   = EXCLUDED.device_type,
             connected_at  = now(),
             metadata      = EXCLUDED.metadata,
             readable_name = EXCLUDED.readable_name,
             risk_level    = EXCLUDED.risk_level,
             message       = EXCLUDED.message`,
          [
            generateUuid(),
            resolvedSessionId,
            studentId,
            deviceId,
            device?.name ?? device?.readable_name ?? 'USB Storage Device',
            deviceType,
            metadata,
            device?.readable_name ?? null,
            device?.risk_level ?? null,
            device?.message ?? null,
          ]
        );
      } catch (err) {
        console.error('[Telemetry] device insert failed:', err.message, device);
        throw err;
      }
    }

    // ── 3. Browser history ──────────────────────────────────────────────────
    for (const history of browserHistory) {
      // FIX: skip rows with no url — url is NOT NULL in the schema
      if (!history?.url) continue;

      try {
        await query(
          `INSERT INTO browser_history
             (session_id, roll_no, url, title, visit_count, last_visited, browser)
           VALUES ($1, $2, $3, $4, $5, $6, $7)
           ON CONFLICT (session_id, roll_no, url)
           DO UPDATE SET
             title        = EXCLUDED.title,
             visit_count  = GREATEST(browser_history.visit_count, EXCLUDED.visit_count),
             last_visited = EXCLUDED.last_visited,
             browser      = EXCLUDED.browser,
             created_at   = now()`,
          [
            String(resolvedSessionId),
            String(rollNo),
            history.url,
            history?.title ?? null,
            history?.visit_count ?? 1,
            history?.last_visited ?? null,
            history?.browser ?? null,
          ]
        );
      } catch (err) {
        console.error('[Telemetry] browser_history insert failed:', err.message, history?.url);
        throw err;
      }
    }

    // ── 4. Processes ────────────────────────────────────────────────────────
    for (const proc of processes) {
      // FIX: pid must be an integer — skip entirely if null/NaN
      const pid = proc?.pid != null ? parseInt(proc.pid, 10) : null;
      if (pid == null || Number.isNaN(pid)) continue;

      // FIX: normalizeStatus guards the old CHECK (status IN ('running','ended'))
      const status = normalizeStatus(proc?.status);
      // FIX: process_name must not be null (NOT NULL column)
      const processName = proc?.name ?? proc?.label ?? 'unknown';

      try {
        await query(
          `INSERT INTO live_processes
             (id, session_id, student_id, pid, process_name, cpu_percent,
              memory_mb, status, risk_level, category, updated_at)
           VALUES ($1, $2, $3, $4, $5, $6, $7, $8, $9, $10, now())
           ON CONFLICT (session_id, student_id, pid)
           DO UPDATE SET
             process_name = EXCLUDED.process_name,
             cpu_percent  = EXCLUDED.cpu_percent,
             memory_mb    = EXCLUDED.memory_mb,
             status       = EXCLUDED.status,
             risk_level   = EXCLUDED.risk_level,
             category     = EXCLUDED.category,
             updated_at   = now()`,
          [
            generateUuid(),
            resolvedSessionId,
            studentId,
            pid,
            processName,
            proc?.cpu ?? 0,
            proc?.memory ?? 0,
            status,
            proc?.risk_level ?? null,
            proc?.category ?? null,
          ]
        );
      } catch (err) {
        console.error('[Telemetry] live_processes insert failed:', err.message, pid);
        throw err;
      }
    }

    // ── 5. Terminal events ──────────────────────────────────────────────────
    for (const event of terminalEvents) {
      // FIX: normalizeEventType guards the old CHECK constraint
      const eventType = normalizeEventType(event?.event_type);
      // FIX: risk_level has NOT NULL DEFAULT 'medium' in schema but send a safe value anyway
      const riskLevel = event?.risk_level ?? 'medium';

      try {
        await query(
          `INSERT INTO terminal_events
             (id, session_id, student_id, event_type, tool, remote_ip, remote_host,
              remote_port, pid, full_command, risk_level, message, detected_at)
           VALUES ($1, $2, $3, $4, $5, $6, $7, $8, $9, $10, $11, $12,
                   COALESCE($13::timestamptz, now()))`,
          [
            generateUuid(),
            resolvedSessionId,
            studentId,
            eventType,
            event?.tool ?? null,
            event?.remote_ip ?? null,
            event?.remote_host ?? null,
            event?.remote_port ?? null,
            event?.pid ?? null,
            event?.full_command ?? null,
            riskLevel,
            event?.message ?? null,
            event?.detected_at ?? null,
          ]
        );
      } catch (err) {
        console.error('[Telemetry] terminal_events insert failed:', err.message, event?.event_type);
        throw err;
      }
    }

    return res.json({ success: true });
  } catch (err) {
    console.error('[Telemetry] ingest failed:', err.message);
    return res.status(500).json({ error: 'Ingest failed' });
  }
}

export async function getTelemetryQuery(req, res) {
  const {
    sessionId,
    labNo,
    rollNoStart,
    rollNoEnd,
    startTime,
    endTime,
  } = req.query || {};

  if (!sessionId) {
    return res.status(400).json({ error: 'sessionId is required' });
  }

  const normalizedSessionId = normalizeSessionId(sessionId);
  const params = [normalizedSessionId];
  const filters = ['s.id = $1'];

  if (labNo) {
    params.push(String(labNo));
    filters.push(`s.lab_name = $${params.length}`);
  }
  if (rollNoStart) {
    params.push(String(rollNoStart));
    filters.push(`st.roll_no >= $${params.length}`);
  }
  if (rollNoEnd) {
    params.push(String(rollNoEnd));
    filters.push(`st.roll_no <= $${params.length}`);
  }
  if (startTime) {
    params.push(startTime);
    filters.push(`COALESCE(last_seen.last_recorded_at, ss.last_seen_at) >= $${params.length}::timestamptz`);
  }
  if (endTime) {
    params.push(endTime);
    filters.push(`COALESCE(last_seen.last_recorded_at, ss.last_seen_at) <= $${params.length}::timestamptz`);
  }

  const sql = `
    SELECT
      s.id AS session_id,
      st.roll_no,
      st.name,
      s.lab_name AS lab_no,
      COALESCE(last_seen.last_recorded_at, ss.last_seen_at) AS last_recorded_at
    FROM session_students ss
    JOIN sessions s ON s.id = ss.session_id
    JOIN students st ON st.id = ss.student_id
    LEFT JOIN LATERAL (
      SELECT MAX(observed_at) AS last_recorded_at
      FROM (
        SELECT MAX(cd.connected_at) AS observed_at
          FROM connected_devices cd
         WHERE cd.session_id = ss.session_id AND cd.student_id = ss.student_id
        UNION ALL
        SELECT MAX(lp.updated_at)
          FROM live_processes lp
         WHERE lp.session_id = ss.session_id AND lp.student_id = ss.student_id
        UNION ALL
        SELECT MAX(te.detected_at)
          FROM terminal_events te
         WHERE te.session_id = ss.session_id AND te.student_id = ss.student_id
        UNION ALL
        SELECT MAX(bh.created_at)
          FROM browser_history bh
         WHERE bh.session_id = s.id::text AND bh.roll_no = st.roll_no
      ) telemetry_points
    ) last_seen ON TRUE
    WHERE ${filters.join(' AND ')}
    ORDER BY st.roll_no ASC
  `;

  const result = await query(sql, params);
  return res.json({
    data: result.rows.map((row) => ({
      sessionId: row.session_id,
      rollNo: row.roll_no,
      name: row.name,
      labNo: row.lab_no,
      lastRecordedAt: row.last_recorded_at,
    })),
  });
}

export async function getStudentTelemetry(req, res) {
  const { rollNo } = req.params;
  const { sessionId } = req.query || {};

  if (!sessionId) {
    return res.status(400).json({ error: 'sessionId is required' });
  }

  const normalizedSessionId = normalizeSessionId(sessionId);

  const studentRes = await query('SELECT id FROM students WHERE roll_no = $1', [rollNo]);
  if (studentRes.rows.length === 0) {
    return res.json({ devices: [], browserHistory: [], processes: [], terminalEvents: [] });
  }

  const studentId = studentRes.rows[0].id;

  const [devicesRes, browserHistoryRes, processesRes, terminalEventsRes] = await Promise.all([
    query(
      `SELECT device_id, device_name, device_type, connected_at, disconnected_at,
              metadata, readable_name, risk_level, message
       FROM connected_devices
       WHERE session_id = $1 AND student_id = $2
       ORDER BY connected_at DESC`,
      [normalizedSessionId, studentId]
    ),
    query(
      `SELECT url, title, visit_count, last_visited, browser, created_at
       FROM browser_history
       WHERE session_id = $1::text AND roll_no = $2
       ORDER BY created_at DESC`,
      [normalizedSessionId, rollNo]
    ),
    query(
      `SELECT pid, process_name, cpu_percent, memory_mb, status, risk_level, category, updated_at
       FROM live_processes
       WHERE session_id = $1 AND student_id = $2
       ORDER BY updated_at DESC`,
      [normalizedSessionId, studentId]
    ),
    query(
      `SELECT event_type, tool, remote_ip, remote_host, remote_port, pid,
              full_command, risk_level, message, detected_at
       FROM terminal_events
       WHERE session_id = $1 AND student_id = $2
       ORDER BY detected_at DESC`,
      [normalizedSessionId, studentId]
    ),
  ]);

  return res.json({
    devices: devicesRes.rows.map((row) => ({
      id: row.device_id,
      name: row.device_name,
      device_type: row.device_type,
      connectedAt: row.connected_at,
      disconnectedAt: row.disconnected_at,
      metadata: row.metadata,
      readableName: row.readable_name,
      riskLevel: row.risk_level,
      message: row.message,
    })),
    browserHistory: browserHistoryRes.rows.map((row) => ({
      url: row.url,
      title: row.title,
      visit_count: row.visit_count,
      last_visited: row.last_visited,
      browser: row.browser,
      createdAt: row.created_at,
    })),
    processes: processesRes.rows.map((row) => ({
      pid: row.pid,
      name: row.process_name,
      cpu: row.cpu_percent,
      memory: row.memory_mb,
      status: row.status,
      riskLevel: row.risk_level,
      category: row.category,
      updatedAt: row.updated_at,
    })),
    terminalEvents: terminalEventsRes.rows.map((row) => ({
      eventType: row.event_type,
      tool: row.tool,
      remoteIp: row.remote_ip,
      remoteHost: row.remote_host,
      remotePort: row.remote_port,
      pid: row.pid,
      fullCommand: row.full_command,
      riskLevel: row.risk_level,
      message: row.message,
      detectedAt: row.detected_at,
    })),
  });
}

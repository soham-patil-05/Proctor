import { v5 as uuidv5, validate as uuidValidate } from 'uuid';
import { query } from '../db/index.js';

const SESSION_NAMESPACE = '2ffce69a-b3c9-4d84-a6f7-a67dd6a958cc';

function normalizeSessionId(sessionId) {
  if (!sessionId) return null;
  const s = String(sessionId).trim();
  return uuidValidate(s) ? s : uuidv5(s, SESSION_NAMESPACE);
}

function toIsoOrNow(value) {
  if (!value) return new Date().toISOString();
  const d = new Date(value);
  return Number.isNaN(d.getTime()) ? new Date().toISOString() : d.toISOString();
}

function toFloat(value, fallback = null) {
  const n = Number(value);
  return Number.isFinite(n) ? n : fallback;
}

function toInt(value, fallback = null) {
  const n = Number(value);
  return Number.isFinite(n) ? Math.trunc(n) : fallback;
}

function normalizeRisk(value) {
  const risk = String(value || 'normal').toLowerCase();
  if (['high', 'medium', 'low', 'normal'].includes(risk)) return risk;
  return 'normal';
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
    return res.status(400).json({ error: 'sessionId and rollNo are required' });
  }

  try {
    const resolvedSessionId = await ensureSession(sessionId, labNo);
    const studentId = await ensureStudent(rollNo, name);
    await ensureSessionStudent(resolvedSessionId, studentId);

    if (Array.isArray(devices)) {
      for (const device of devices) {
        const metadata = device?.metadata;
        const metadataJson =
          typeof metadata === 'string' ? metadata : JSON.stringify(metadata && typeof metadata === 'object' ? metadata : {});

        await query(
          `INSERT INTO connected_devices
           (session_id, student_id, device_id, device_name, device_type, connected_at, readable_name, risk_level, message, metadata)
           VALUES ($1, $2, $3, $4, 'usb', now(), $5, $6, $7, $8::jsonb)
           ON CONFLICT (session_id, student_id, device_id)
           DO UPDATE SET
             device_name = EXCLUDED.device_name,
             device_type = 'usb',
             readable_name = EXCLUDED.readable_name,
             risk_level = EXCLUDED.risk_level,
             message = EXCLUDED.message,
             metadata = EXCLUDED.metadata`,
          [
            resolvedSessionId,
            studentId,
            device?.id ?? null,
            device?.readable_name ?? device?.device_name ?? 'USB Storage Device',
            device?.readable_name ?? null,
            normalizeRisk(device?.risk_level),
            device?.message ?? null,
            metadataJson,
          ]
        );
      }
    }

    if (Array.isArray(browserHistory)) {
      for (const entry of browserHistory) {
        if (!entry?.url) continue;
        await query(
          `INSERT INTO browser_history (session_id, roll_no, url, title, visit_count, last_visited, browser)
           VALUES ($1, $2, $3, $4, $5, $6, $7)
           ON CONFLICT (session_id, roll_no, url)
           DO UPDATE SET
             title = COALESCE(EXCLUDED.title, browser_history.title),
             visit_count = GREATEST(browser_history.visit_count, EXCLUDED.visit_count),
             last_visited = GREATEST(COALESCE(browser_history.last_visited, 0), COALESCE(EXCLUDED.last_visited, 0)),
             browser = COALESCE(EXCLUDED.browser, browser_history.browser)`,
          [
            String(resolvedSessionId),
            String(rollNo),
            entry?.url ?? null,
            entry?.title ?? null,
            toInt(entry?.visit_count, 1),
            toFloat(entry?.last_visited, null),
            entry?.browser ?? null,
          ]
        );
      }
    }

    if (Array.isArray(processes)) {
      for (const process of processes) {
        await query(
          `INSERT INTO live_processes
           (session_id, student_id, pid, process_name, cpu_percent, memory_mb, status, risk_level, updated_at)
           VALUES ($1, $2, $3, $4, $5, $6, $7, $8, now())
           ON CONFLICT (session_id, student_id, pid)
           DO UPDATE SET
             process_name = EXCLUDED.process_name,
             cpu_percent = EXCLUDED.cpu_percent,
             memory_mb = EXCLUDED.memory_mb,
             status = EXCLUDED.status,
             risk_level = EXCLUDED.risk_level,
             updated_at = now()`,
          [
            resolvedSessionId,
            studentId,
            toInt(process?.pid, null),
            process?.label || process?.name || process?.process_name || null,
            toFloat(process?.cpu, 0),
            toFloat(process?.memory, 0),
            process?.status || 'running',
            process?.risk_level || null,
          ]
        );
      }
    }

    if (Array.isArray(terminalEvents)) {
      for (const event of terminalEvents) {
        await query(
          `INSERT INTO terminal_events
           (id, session_id, student_id, event_type, tool, detected_at, pid, full_command, remote_ip, remote_port, remote_host, message, risk_level)
           VALUES (COALESCE($1::uuid, uuid_generate_v4()), $2, $3, $4, $5, $6, $7, $8, $9, $10, $11, $12, $13)`,
          [
            event?.id && uuidValidate(String(event.id)) ? event.id : null,
            resolvedSessionId,
            studentId,
            event?.event_type || null,
            event?.tool || null,
            toIsoOrNow(event?.detected_at),
            toInt(event?.pid, null),
            event?.full_command ?? null,
            event?.remote_ip ?? null,
            event?.remote_port ?? null,
            event?.remote_host ?? null,
            event?.message ?? null,
            normalizeRisk(event?.risk_level),
          ]
        );
      }
    }

    return res.json({ success: true });
  } catch (err) {
    return res.status(500).json({ error: 'Storage failure', detail: err.message });
  }
}

export async function queryTelemetry(req, res, next) {
  try {
    const { sessionId, startTime, endTime, labNo, rollNoStart, rollNoEnd } = req.query;

    if (!sessionId) {
      return res.status(400).json({ error: 'sessionId is required' });
    }

    const resolvedSessionId = normalizeSessionId(sessionId);

    const { rows } = await query(
      `SELECT st.roll_no,
              st.name,
              se.id AS session_id,
              se.lab_name AS lab_no,
              GREATEST(
                COALESCE(MAX(lp.updated_at), to_timestamp(0)),
                COALESCE(MAX(cd.connected_at), to_timestamp(0)),
                COALESCE(MAX(te.detected_at), to_timestamp(0)),
                COALESCE(MAX(bh.created_at), to_timestamp(0))
              ) AS last_recorded_at
       FROM session_students ss
       JOIN students st ON st.id = ss.student_id
       JOIN sessions se ON se.id = ss.session_id
       LEFT JOIN live_processes lp ON lp.session_id = se.id AND lp.student_id = st.id
       LEFT JOIN connected_devices cd ON cd.session_id = se.id AND cd.student_id = st.id
       LEFT JOIN terminal_events te ON te.session_id = se.id AND te.student_id = st.id
      LEFT JOIN browser_history bh ON bh.session_id = se.id::text AND bh.roll_no = st.roll_no
       WHERE se.id = $1
       GROUP BY st.roll_no, st.name, se.id, se.lab_name
       ORDER BY st.roll_no ASC`,
      [resolvedSessionId]
    );

    let filtered = rows.map((r) => ({
      rollNo: r.roll_no,
      name: r.name,
      sessionId: r.session_id,
      labNo: r.lab_no,
      lastRecordedAt: r.last_recorded_at,
    }));

    if (labNo) {
      filtered = filtered.filter((r) => r.labNo === labNo);
    }

    if (startTime) {
      const start = new Date(startTime).getTime();
      filtered = filtered.filter((r) => new Date(r.lastRecordedAt).getTime() >= start);
    }

    if (endTime) {
      const end = new Date(endTime).getTime();
      filtered = filtered.filter((r) => new Date(r.lastRecordedAt).getTime() <= end);
    }

    const bothNumeric =
      rollNoStart !== undefined &&
      rollNoEnd !== undefined &&
      rollNoStart !== '' &&
      rollNoEnd !== '' &&
      /^\d+$/.test(String(rollNoStart)) &&
      /^\d+$/.test(String(rollNoEnd));

    if (rollNoStart || rollNoEnd) {
      filtered = filtered.filter((r) => {
        const value = String(r.rollNo);
        if (bothNumeric && /^\d+$/.test(value)) {
          const n = Number(value);
          if (rollNoStart && n < Number(rollNoStart)) return false;
          if (rollNoEnd && n > Number(rollNoEnd)) return false;
          return true;
        }
        if (rollNoStart && value < String(rollNoStart)) return false;
        if (rollNoEnd && value > String(rollNoEnd)) return false;
        return true;
      });
    }

    return res.json(filtered);
  } catch (err) {
    return next(err);
  }
}

export async function getStudentDetail(req, res, next) {
  try {
    const { rollNo } = req.params;
    const { sessionId } = req.query;

    if (!sessionId) {
      return res.status(400).json({ error: 'sessionId is required' });
    }

    const resolvedSessionId = normalizeSessionId(sessionId);
    const studentRes = await query('SELECT id FROM students WHERE roll_no = $1', [rollNo]);

    if (studentRes.rows.length === 0) {
      return res.json({
        devices: [],
        browserHistory: [],
        processes: [],
        terminalEvents: [],
      });
    }

    const studentId = studentRes.rows[0].id;

    const [deviceRows, browserRows, processRows, terminalRows] = await Promise.all([
      query(
        `SELECT device_id, readable_name, message, risk_level, metadata
         FROM connected_devices
         WHERE session_id = $1 AND student_id = $2 AND COALESCE(device_type, 'usb') = 'usb'
         ORDER BY connected_at DESC`,
        [resolvedSessionId, studentId]
      ),
      query(
        `SELECT url, title, visit_count, last_visited, browser
         FROM browser_history
         WHERE session_id = $1::text AND roll_no = $2`,
        [String(resolvedSessionId), String(rollNo)]
      ),
      query(
        `SELECT pid, process_name, cpu_percent, memory_mb, status, risk_level
         FROM live_processes
         WHERE session_id = $1
           AND student_id = $2
           AND risk_level IS NOT NULL
           AND status <> 'ended'
         ORDER BY updated_at DESC`,
        [resolvedSessionId, studentId]
      ),
      query(
        `SELECT id, event_type, tool, detected_at, pid, full_command, remote_ip, remote_port, remote_host, message, risk_level
         FROM terminal_events
         WHERE session_id = $1 AND student_id = $2`,
        [resolvedSessionId, studentId]
      ),
    ]);

    const devices = deviceRows.rows.map((row) => {
      let metadata = row.metadata;
      if (typeof metadata === 'string') {
        try {
          metadata = JSON.parse(metadata);
        } catch {
          metadata = {};
        }
      }
      if (!metadata || typeof metadata !== 'object') metadata = {};

      return {
        id: row.device_id,
        readableName: row.readable_name,
        message: row.message,
        riskLevel: row.risk_level,
        metadata: {
          mountpoint: metadata.mountpoint ?? null,
          totalGb: metadata.totalGb ?? metadata.total_gb ?? null,
        },
      };
    });

    const browserHistory = browserRows.rows
      .map((row) => ({
        url: row.url,
        title: row.title,
        visitCount: toInt(row.visit_count, 1),
        lastVisited: toFloat(row.last_visited, 0),
        browser: row.browser,
      }))
      .sort((a, b) => (b.lastVisited || 0) - (a.lastVisited || 0));

    const processes = processRows.rows.map((row) => ({
      pid: row.pid,
      name: row.process_name,
      label: row.process_name,
      cpu: toFloat(row.cpu_percent, 0),
      memory: toFloat(row.memory_mb, 0),
      status: row.status,
      riskLevel: row.risk_level,
    }));

    const terminalEvents = terminalRows.rows
      .map((row) => ({
        id: row.id,
        eventType: row.event_type,
        tool: row.tool,
        detectedAt: row.detected_at,
        pid: row.pid,
        fullCommand: row.full_command,
        remoteIp: row.remote_ip,
        remotePort: row.remote_port,
        remoteHost: row.remote_host,
        message: row.message,
        riskLevel: row.risk_level,
      }))
      .sort((a, b) => new Date(b.detectedAt || 0).getTime() - new Date(a.detectedAt || 0).getTime());

    return res.json({
      devices,
      browserHistory,
      processes,
      terminalEvents,
    });
  } catch (err) {
    return next(err);
  }
}

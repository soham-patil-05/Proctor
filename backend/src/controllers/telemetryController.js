import { v5 as uuidv5, validate as uuidValidate } from 'uuid';
import { query } from '../db/index.js';
import { toCamel } from '../utils/helpers.js';

const SESSION_NAMESPACE = '2ffce69a-b3c9-4d84-a6f7-a67dd6a958cc';

function normalizeSessionId(sessionId) {
  if (!sessionId) return null;
  const s = String(sessionId).trim();
  return uuidValidate(s) ? s : uuidv5(s, SESSION_NAMESPACE);
}

function toIsoOrNull(value) {
  if (!value) return null;
  const d = new Date(value);
  return Number.isNaN(d.getTime()) ? null : d.toISOString();
}

function parseMaybeJsonArray(value) {
  if (Array.isArray(value)) return value;
  if (typeof value !== 'string') return [];
  try {
    const parsed = JSON.parse(value);
    return Array.isArray(parsed) ? parsed : [];
  } catch {
    return [];
  }
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

/**
 * EXPORT_PAYLOAD_SCHEMA:
 * {
 *   "sessionId": string,
 *   "rollNo": string,
 *   "labNo": string,
 *   "name": string,
 *   "processes": [ { pid, process_name, cpu_percent, memory_mb, status, risk_level, category } ],
 *   "devices": [ { device_id, device_name, device_type, connected_at, disconnected_at, readable_name, risk_level, message } ],
 *   "network": { ip_address, gateway, dns, active_connections: [...] },
 *   "domainActivity": [ { domain, request_count, risk_level, last_accessed } ],
 *   "terminalEvents": [ { event_type, tool, remote_ip, remote_host, remote_port, pid, full_command, risk_level, message, detected_at } ],
 *   "browserHistory": [ { url, title, visit_count, last_visit } ]
 * }
 */
export async function ingestTelemetry(req, res) {
  const {
    sessionId,
    rollNo,
    labNo,
    name,
    processes = [],
    devices = [],
    network = null,
    domainActivity = [],
    terminalEvents = [],
    browserHistory = [],
  } = req.body || {};

  if (!sessionId || !rollNo) {
    return res.status(400).json({ error: 'sessionId and rollNo are required' });
  }

  const stored = {
    processes: 0,
    devices: 0,
    network: 0,
    domainActivity: 0,
    terminalEvents: 0,
    browserHistory: 0,
  };
  const errors = [];

  try {
    const resolvedSessionId = await ensureSession(sessionId, labNo);
    const studentId = await ensureStudent(rollNo, name);
    await ensureSessionStudent(resolvedSessionId, studentId);

    try {
      if (Array.isArray(processes)) {
        await query(
          `UPDATE live_processes
           SET status = 'ended', updated_at = now()
           WHERE session_id = $1 AND student_id = $2`,
          [resolvedSessionId, studentId]
        );

        for (const p of processes) {
          await query(
            `INSERT INTO live_processes
             (session_id, student_id, pid, process_name, cpu_percent, memory_mb, status, risk_level, category, updated_at)
             VALUES ($1, $2, $3, $4, $5, $6, $7, $8, $9, now())
             ON CONFLICT (session_id, student_id, pid)
             DO UPDATE SET
               process_name = EXCLUDED.process_name,
               cpu_percent = EXCLUDED.cpu_percent,
               memory_mb = EXCLUDED.memory_mb,
               status = EXCLUDED.status,
               risk_level = EXCLUDED.risk_level,
               category = EXCLUDED.category,
               updated_at = now()`,
            [
              resolvedSessionId,
              studentId,
              p.pid,
              p.process_name,
              p.cpu_percent ?? 0,
              p.memory_mb ?? 0,
              p.status ?? 'running',
              p.risk_level ?? null,
              p.category ?? null,
            ]
          );
          stored.processes += 1;
        }
      }
    } catch (err) {
      console.error('[ingest/processes]', err);
      errors.push(`processes: ${err.message}`);
    }

    try {
      if (Array.isArray(devices)) {
        for (const d of devices) {
          await query(
            `INSERT INTO connected_devices
             (session_id, student_id, device_id, device_name, device_type, connected_at, disconnected_at, readable_name, risk_level, message)
             VALUES ($1, $2, $3, $4, $5, $6, $7, $8, $9, $10)
             ON CONFLICT (session_id, student_id, device_id)
             DO UPDATE SET
               device_name = EXCLUDED.device_name,
               device_type = EXCLUDED.device_type,
               connected_at = COALESCE(EXCLUDED.connected_at, connected_devices.connected_at),
               disconnected_at = EXCLUDED.disconnected_at,
               readable_name = EXCLUDED.readable_name,
               risk_level = EXCLUDED.risk_level,
               message = EXCLUDED.message`,
            [
              resolvedSessionId,
              studentId,
              d.device_id,
              d.device_name,
              d.device_type,
              toIsoOrNull(d.connected_at) ?? new Date().toISOString(),
              toIsoOrNull(d.disconnected_at),
              d.readable_name ?? null,
              d.risk_level ?? null,
              d.message ?? null,
            ]
          );
          stored.devices += 1;
        }
      }
    } catch (err) {
      console.error('[ingest/devices]', err);
      errors.push(`devices: ${err.message}`);
    }

    try {
      if (network && typeof network === 'object') {
        await query(
          `INSERT INTO network_info
           (session_id, student_id, ip_address, gateway, dns, active_connections, updated_at)
           VALUES ($1, $2, $3, $4, $5, $6, now())
           ON CONFLICT (session_id, student_id)
           DO UPDATE SET
             ip_address = EXCLUDED.ip_address,
             gateway = EXCLUDED.gateway,
             dns = EXCLUDED.dns,
             active_connections = EXCLUDED.active_connections,
             updated_at = now()`,
          [
            resolvedSessionId,
            studentId,
            network.ip_address ?? null,
            network.gateway ?? null,
            JSON.stringify(Array.isArray(network.dns) ? network.dns : []),
            JSON.stringify(Array.isArray(network.active_connections) ? network.active_connections : []),
          ]
        );
        stored.network += 1;
      }
    } catch (err) {
      console.error('[ingest/network]', err);
      errors.push(`network: ${err.message}`);
    }

    try {
      if (Array.isArray(domainActivity)) {
        for (const d of domainActivity) {
          await query(
            `INSERT INTO domain_activity
             (id, session_id, student_id, domain, request_count, risk_level, last_accessed)
             VALUES (uuid_generate_v4(), $1, $2, $3, $4, $5, $6)
             ON CONFLICT (session_id, student_id, domain)
             DO UPDATE SET
               request_count = domain_activity.request_count + EXCLUDED.request_count,
               risk_level = EXCLUDED.risk_level,
               last_accessed = EXCLUDED.last_accessed`,
            [
              resolvedSessionId,
              studentId,
              d.domain,
              d.request_count ?? 1,
              d.risk_level ?? null,
              toIsoOrNull(d.last_accessed) ?? new Date().toISOString(),
            ]
          );
          stored.domainActivity += 1;
        }
      }
    } catch (err) {
      console.error('[ingest/domainActivity]', err);
      errors.push(`domainActivity: ${err.message}`);
    }

    try {
      if (Array.isArray(terminalEvents)) {
        for (const t of terminalEvents) {
          await query(
            `INSERT INTO terminal_events
             (id, session_id, student_id, event_type, tool, remote_ip, remote_host, remote_port, pid, full_command, risk_level, message, detected_at)
             VALUES (uuid_generate_v4(), $1, $2, $3, $4, $5, $6, $7, $8, $9, $10, $11, $12)`,
            [
              resolvedSessionId,
              studentId,
              t.event_type,
              t.tool ?? null,
              t.remote_ip ?? null,
              t.remote_host ?? null,
              t.remote_port ?? null,
              t.pid ?? null,
              t.full_command ?? null,
              t.risk_level ?? null,
              t.message ?? null,
              toIsoOrNull(t.detected_at) ?? new Date().toISOString(),
            ]
          );
          stored.terminalEvents += 1;
        }
      }
    } catch (err) {
      console.error('[ingest/terminalEvents]', err);
      errors.push(`terminalEvents: ${err.message}`);
    }

    try {
      if (Array.isArray(browserHistory)) {
        for (const b of browserHistory) {
          await query(
            `INSERT INTO browser_history
             (session_id, student_id, url, title, visit_count, last_visit, synced, created_at, recorded_at)
             VALUES ($1, $2, $3, $4, $5, $6, true, now(), now())`,
            [
              resolvedSessionId,
              studentId,
              b.url ?? null,
              b.title ?? null,
              b.visit_count ?? 1,
              toIsoOrNull(b.last_visit) ?? new Date().toISOString(),
            ]
          );
          stored.browserHistory += 1;
        }
      }
    } catch (err) {
      console.error('[ingest/browserHistory]', err);
      errors.push(`browserHistory: ${err.message}`);
    }

    if (errors.length > 0) {
      return res.status(500).json({
        error: 'Storage failure',
        detail: errors.join(' | '),
        stored,
      });
    }

    return res.json({ success: true, stored });
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
                COALESCE(MAX(ni.updated_at), to_timestamp(0)),
                COALESCE(MAX(da.last_accessed), to_timestamp(0)),
                COALESCE(MAX(te.detected_at), to_timestamp(0)),
                COALESCE(MAX(bh.created_at), to_timestamp(0))
              ) AS last_recorded_at
       FROM session_students ss
       JOIN students st ON st.id = ss.student_id
       JOIN sessions se ON se.id = ss.session_id
       LEFT JOIN live_processes lp ON lp.session_id = se.id AND lp.student_id = st.id
       LEFT JOIN connected_devices cd ON cd.session_id = se.id AND cd.student_id = st.id
       LEFT JOIN network_info ni ON ni.session_id = se.id AND ni.student_id = st.id
       LEFT JOIN domain_activity da ON da.session_id = se.id AND da.student_id = st.id
       LEFT JOIN terminal_events te ON te.session_id = se.id AND te.student_id = st.id
       LEFT JOIN browser_history bh ON bh.session_id = se.id AND bh.student_id = st.id
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

    res.json(filtered);
  } catch (err) {
    next(err);
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
        rollNo,
        sessionId: resolvedSessionId,
        processes: [],
        devices: { usb: [], external: [] },
        network: null,
        domainActivity: [],
        terminalEvents: [],
        browserHistory: [],
      });
    }

    const studentId = studentRes.rows[0].id;

    const [processRows, deviceRows, networkRows, domainRows, terminalRows, browserRows] = await Promise.all([
      query(
        `SELECT pid, process_name, cpu_percent, memory_mb, status, risk_level, category
         FROM live_processes
         WHERE session_id = $1 AND student_id = $2
         ORDER BY updated_at DESC`,
        [resolvedSessionId, studentId]
      ),
      query(
        `SELECT device_id, device_name, device_type, connected_at, disconnected_at, readable_name, risk_level, message
         FROM connected_devices
         WHERE session_id = $1 AND student_id = $2
         ORDER BY connected_at DESC`,
        [resolvedSessionId, studentId]
      ),
      query(
        `SELECT ip_address, gateway, dns, active_connections
         FROM network_info
         WHERE session_id = $1 AND student_id = $2
         ORDER BY updated_at DESC
         LIMIT 1`,
        [resolvedSessionId, studentId]
      ),
      query(
        `SELECT domain, request_count, risk_level, last_accessed
         FROM domain_activity
         WHERE session_id = $1 AND student_id = $2
         ORDER BY request_count DESC`,
        [resolvedSessionId, studentId]
      ),
      query(
        `SELECT event_type, tool, remote_ip, remote_host, remote_port, pid, full_command, risk_level, message, detected_at
         FROM terminal_events
         WHERE session_id = $1 AND student_id = $2
         ORDER BY detected_at DESC
         LIMIT 200`,
        [resolvedSessionId, studentId]
      ),
      query(
        `SELECT url, title, visit_count, last_visit
         FROM browser_history
         WHERE session_id = $1 AND student_id = $2
         ORDER BY last_visit DESC
         LIMIT 500`,
        [resolvedSessionId, studentId]
      ),
    ]);

    const processes = processRows.rows.map((r) => {
      const c = toCamel(r);
      return {
        pid: c.pid,
        processName: c.processName,
        cpuPercent: Number(c.cpuPercent ?? 0),
        memoryMb: Number(c.memoryMb ?? 0),
        status: c.status,
        riskLevel: c.riskLevel ?? null,
        category: c.category ?? null,
      };
    });

    const allDevices = deviceRows.rows.map((r) => {
      const c = toCamel(r);
      return {
        deviceId: c.deviceId,
        deviceName: c.deviceName,
        deviceType: c.deviceType,
        connectedAt: c.connectedAt,
        disconnectedAt: c.disconnectedAt,
        readableName: c.readableName,
        riskLevel: c.riskLevel,
        message: c.message,
      };
    });

    const network = networkRows.rows[0]
      ? (() => {
          const c = toCamel(networkRows.rows[0]);
          const dns = parseMaybeJsonArray(c.dns);
          const active = parseMaybeJsonArray(c.activeConnections).map((row) => {
            const rc = toCamel(row);
            return {
              remoteIp: rc.remoteIp,
              remoteHost: rc.remoteHost,
              remotePort: rc.remotePort,
              pid: rc.pid,
              process: rc.process,
            };
          });
          return {
            ipAddress: c.ipAddress,
            gateway: c.gateway,
            dns,
            activeConnections: active,
          };
        })()
      : null;

    const domainActivity = domainRows.rows.map((r) => {
      const c = toCamel(r);
      return {
        domain: c.domain,
        requestCount: c.requestCount,
        riskLevel: c.riskLevel,
        lastAccessed: c.lastAccessed,
      };
    });

    const terminalEvents = terminalRows.rows.map((r) => {
      const c = toCamel(r);
      return {
        eventType: c.eventType,
        tool: c.tool,
        remoteIp: c.remoteIp,
        remoteHost: c.remoteHost,
        remotePort: c.remotePort,
        pid: c.pid,
        fullCommand: c.fullCommand,
        riskLevel: c.riskLevel,
        message: c.message,
        detectedAt: c.detectedAt,
      };
    });

    const browserHistory = browserRows.rows.map((r) => {
      const c = toCamel(r);
      return {
        url: c.url,
        title: c.title,
        visitCount: c.visitCount,
        lastVisit: c.lastVisit,
      };
    });

    res.json({
      rollNo,
      sessionId: resolvedSessionId,
      processes,
      devices: {
        usb: allDevices.filter((d) => (d.deviceType || '').toLowerCase() === 'usb'),
        external: allDevices.filter((d) => (d.deviceType || '').toLowerCase() !== 'usb'),
      },
      network,
      domainActivity,
      terminalEvents,
      browserHistory,
    });
  } catch (err) {
    next(err);
  }
}

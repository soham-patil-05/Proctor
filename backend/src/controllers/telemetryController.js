import { v5 as uuidv5, validate as uuidValidate } from 'uuid';
import { query } from '../db/index.js';
import { upsertProcessSnapshot } from '../services/processService.js';
import { upsertDevicesSnapshot, upsertNetworkInfo, getDevices, getNetworkInfo } from '../services/deviceService.js';
import { upsertDomainActivity, insertTerminalEvent, getDomainActivity, getTerminalEvents } from '../services/networkService.js';
import { getProcesses } from '../services/processService.js';

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

/**
 * Ingest contract:
 * {
 *   sessionId, rollNo, labNo, name, recordedAt,
 *   processes: [], devices: { usb: [], external: [] }, network: {},
 *   domainActivity: [], terminalEvents: [], browserHistory: []
 * }
 */
export async function ingestTelemetry(req, res, next) {
  try {
    const {
      sessionId,
      rollNo,
      labNo,
      name,
      processes = [],
      devices = { usb: [], external: [] },
      network = null,
      domainActivity = [],
      terminalEvents = [],
      browserHistory = [],
    } = req.body || {};

    if (!sessionId || !rollNo) {
      return res.status(400).json({ error: 'sessionId and rollNo are required' });
    }

    const resolvedSessionId = await ensureSession(sessionId, labNo);
    const studentId = await ensureStudent(rollNo, name);
    await ensureSessionStudent(resolvedSessionId, studentId);

    if (Array.isArray(processes) && processes.length > 0) {
      const normalizedProcesses = processes.map((p) => ({
        pid: p.pid,
        name: p.name ?? p.processName,
        cpu: p.cpu ?? p.cpuPercent,
        memory: p.memory ?? p.memoryMb,
        status: p.status,
        risk_level: p.risk_level ?? p.riskLevel,
        category: p.category,
      }));
      await upsertProcessSnapshot(resolvedSessionId, studentId, normalizedProcesses);
    }

    if (devices && (Array.isArray(devices.usb) || Array.isArray(devices.external))) {
      const normalizedDevices = {
        usb: (devices.usb || []).map((d) => ({
          id: d.id ?? d.deviceId,
          name: d.name ?? d.deviceName,
          metadata: d.metadata ?? null,
          readable_name: d.readable_name ?? d.readableName,
          risk_level: d.risk_level ?? d.riskLevel,
          message: d.message ?? null,
        })),
        external: (devices.external || []).map((d) => ({
          id: d.id ?? d.deviceId,
          name: d.name ?? d.deviceName,
          metadata: d.metadata ?? null,
          readable_name: d.readable_name ?? d.readableName,
          risk_level: d.risk_level ?? d.riskLevel,
          message: d.message ?? null,
        })),
      };
      await upsertDevicesSnapshot(resolvedSessionId, studentId, normalizedDevices);
    }

    if (network && typeof network === 'object') {
      await upsertNetworkInfo(resolvedSessionId, studentId, {
        ip: network.ip ?? network.ipAddress,
        gateway: network.gateway,
        dns: network.dns,
        activeConnections: network.activeConnections,
      });
    }

    if (Array.isArray(domainActivity) && domainActivity.length > 0) {
      const normalizedDomains = domainActivity.map((d) => ({
        domain: d.domain,
        count: d.count ?? d.requestCount,
        risk_level: d.risk_level ?? d.riskLevel,
      }));
      await upsertDomainActivity(resolvedSessionId, studentId, normalizedDomains);
    }

    if (Array.isArray(terminalEvents)) {
      for (const event of terminalEvents) {
        const eventType = event.eventType ?? event.event_type ?? 'terminal_command';
        await insertTerminalEvent(
          resolvedSessionId,
          studentId,
          {
            tool: event.tool,
            remote_ip: event.remoteIp ?? event.remote_ip,
            remote_host: event.remoteHost ?? event.remote_host,
            remote_port: event.remotePort ?? event.remote_port,
            pid: event.pid,
            full_command: event.fullCommand ?? event.full_command,
          },
          eventType,
          event.riskLevel ?? event.risk_level ?? 'medium',
          event.message ?? null
        );
      }
    }

    if (Array.isArray(browserHistory)) {
      for (const row of browserHistory) {
        await query(
          `INSERT INTO browser_history
           (session_id, student_id, url, title, visit_count, last_visit, synced, created_at, recorded_at)
           VALUES ($1, $2, $3, $4, $5, $6, 1, now(), now())`,
          [
            resolvedSessionId,
            studentId,
            row.url ?? null,
            row.title ?? null,
            row.visitCount ?? row.visit_count ?? 1,
            row.lastVisit ?? row.last_visited ?? null,
          ]
        );
      }
    }

    res.json({ success: true });
  } catch (err) {
    next(err);
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

    // If both bounds are purely numeric we compare numerically, otherwise lexicographically.
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

    const [processes, devices, network, domainActivity, terminalEvents, browserRows] = await Promise.all([
      getProcesses(resolvedSessionId, studentId),
      getDevices(resolvedSessionId, studentId),
      getNetworkInfo(resolvedSessionId, studentId),
      getDomainActivity(resolvedSessionId, studentId),
      getTerminalEvents(resolvedSessionId, studentId),
      query(
        `SELECT url, title, visit_count, last_visit
         FROM browser_history
         WHERE session_id = $1 AND student_id = $2
         ORDER BY created_at DESC
         LIMIT 500`,
        [resolvedSessionId, studentId]
      ),
    ]);

    res.json({
      rollNo,
      sessionId: resolvedSessionId,
      processes: processes.map((p) => ({
        pid: p.pid,
        processName: p.name,
        cpuPercent: Number(p.cpu ?? 0),
        memoryMb: Number(p.memory ?? 0),
        status: p.status,
        riskLevel: p.risk_level ?? null,
        category: p.category ?? null,
      })),
      devices: {
        usb: (devices.usb || []).map((d) => ({
          deviceId: d.id,
          deviceName: d.name,
          readableName: d.readable_name ?? null,
          riskLevel: d.risk_level ?? null,
          message: d.message ?? null,
          metadata: d.metadata ?? null,
        })),
        external: (devices.external || []).map((d) => ({
          deviceId: d.id,
          deviceName: d.name,
          readableName: d.readable_name ?? null,
          riskLevel: d.risk_level ?? null,
          message: d.message ?? null,
          metadata: d.metadata ?? null,
        })),
      },
      network: network
        ? {
            ipAddress: network.ip,
            gateway: network.gateway,
            dns: network.dns,
            activeConnections: network.activeConnections,
          }
        : null,
      domainActivity: domainActivity.map((d) => ({
        domain: d.domain,
        requestCount: d.request_count,
        riskLevel: d.risk_level,
        lastAccessed: d.last_accessed,
      })),
      terminalEvents: terminalEvents.map((t) => ({
        eventType: t.event_type,
        tool: t.tool,
        fullCommand: t.full_command,
        remoteIp: t.remote_ip,
        remoteHost: t.remote_host,
        remotePort: t.remote_port,
        pid: t.pid,
        riskLevel: t.risk_level,
        message: t.message,
        detectedAt: t.detected_at,
      })),
      browserHistory: browserRows.rows.map((b) => ({
        url: b.url,
        title: b.title,
        visitCount: b.visit_count,
        lastVisit: b.last_visit,
      })),
    });
  } catch (err) {
    next(err);
  }
}

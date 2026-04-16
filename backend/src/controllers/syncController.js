// controllers/syncController.js - Handles log receiving and dashboard data

import { query } from '../db/index.js';
import { asyncHandler } from '../utils/helpers.js';

/**
 * POST /api/logs/receive
 * Receive batch of logs from student agent
 * No authentication required
 */
export const receiveLogs = asyncHandler(async (req, res) => {
    const {
        session_id,
        timestamp,
        processes,
        devices,
        terminal_events,
        browser_history
    } = req.body;

    if (!session_id) {
        return res.status(400).json({ error: 'session_id is required' });
    }

    let totalRecords = 0;

    // Insert processes
    if (processes && processes.length > 0) {
        for (const proc of processes) {
            await query(`
                INSERT INTO live_processes 
                (session_id, student_id, pid, process_name, cpu_percent, memory_mb, status,
                 risk_level, category, label, is_incognito, updated_at)
                VALUES ($1, $2, $3, $4, $5, $6, $7, $8, $9, $10, $11, NOW())
                ON CONFLICT (session_id, student_id, pid) DO UPDATE SET
                    cpu_percent = EXCLUDED.cpu_percent,
                    memory_mb = EXCLUDED.memory_mb,
                    status = EXCLUDED.status,
                    updated_at = NOW()
            `, [
                session_id,
                proc.roll_no || session_id, // Use session_id as student_id for now
                proc.pid,
                proc.process_name,
                proc.cpu_percent,
                proc.memory_mb,
                proc.status || 'running',
                proc.risk_level || 'normal',
                proc.category,
                proc.label,
                proc.is_incognito ? true : false
            ]);
            totalRecords++;
        }
    }

    // Insert devices
    if (devices && devices.length > 0) {
        for (const device of devices) {
            await query(`
                INSERT INTO connected_devices
                (session_id, student_id, device_id, device_name, device_type, readable_name,
                 risk_level, message, metadata, connected_at, disconnected_at)
                VALUES ($1, $2, $3, $4, $5, $6, $7, $8, $9, to_timestamp($10), 
                        CASE WHEN $11 THEN to_timestamp($11) ELSE NULL END)
                ON CONFLICT (session_id, student_id, device_id) DO UPDATE SET
                    disconnected_at = CASE WHEN $11 THEN to_timestamp($11) ELSE EXCLUDED.disconnected_at END
            `, [
                session_id,
                device.roll_no || session_id,
                device.device_id,
                device.device_name,
                device.device_type,
                device.readable_name,
                device.risk_level || 'normal',
                device.message,
                device.metadata,
                device.connected_at,
                device.disconnected_at || null
            ]);
            totalRecords++;
        }
    }

    // Insert terminal events
    if (terminal_events && terminal_events.length > 0) {
        for (const event of terminal_events) {
            await query(`
                INSERT INTO terminal_events
                (session_id, student_id, tool, remote_ip, remote_host, remote_port, pid,
                 event_type, full_command, risk_level, message, detected_at)
                VALUES ($1, $2, $3, $4, $5, $6, $7, $8, $9, $10, $11, to_timestamp($12))
            `, [
                session_id,
                event.roll_no || session_id,
                event.tool,
                event.remote_ip,
                event.remote_host,
                event.remote_port,
                event.pid,
                event.event_type,
                event.full_command,
                event.risk_level || 'medium',
                event.message,
                event.detected_at
            ]);
            totalRecords++;
        }
    }

    // Insert browser history
    if (browser_history && browser_history.length > 0) {
        for (const entry of browser_history) {
            await query(`
                INSERT INTO browser_history
                (session_id, student_id, url, title, visit_count, last_visited, browser)
                VALUES ($1, $2, $3, $4, $5, to_timestamp($6), $7)
                ON CONFLICT (session_id, student_id, url) DO UPDATE SET
                    visit_count = GREATEST(browser_history.visit_count, EXCLUDED.visit_count),
                    last_visited = GREATEST(browser_history.last_visited, EXCLUDED.last_visited)
            `, [
                session_id,
                entry.roll_no || session_id,
                entry.url,
                entry.title || '',
                entry.visit_count || 1,
                entry.last_visited,
                entry.browser || 'Unknown'
            ]);
            totalRecords++;
        }
    }

    res.json({
        message: 'Logs received successfully',
        totalRecords,
        session_id
    });
});

/**
 * GET /api/dashboard/students
 * Get all students grouped by start time, with filters
 * No authentication required
 */
export const getDashboardStudents = asyncHandler(async (req, res) => {
    const { lab_no, time_from, time_to, status } = req.query;

    let whereClause = 'WHERE es.end_time IS NULL'; // Only active sessions
    let params = [];
    let paramCount = 1;

    if (lab_no) {
        whereClause += ` AND es.lab_no = $${paramCount}`;
        params.push(lab_no);
        paramCount++;
    }

    if (time_from) {
        whereClause += ` AND es.start_time >= $${paramCount}`;
        params.push(time_from);
        paramCount++;
    }

    if (time_to) {
        whereClause += ` AND es.start_time <= $${paramCount}`;
        params.push(time_to);
        paramCount++;
    }

    const query_sql = `
        SELECT 
            es.id as session_id,
            es.roll_no,
            es.lab_no,
            es.start_time,
            es.end_time,
            COUNT(DISTINCT lp.pid) as process_count,
            COUNT(DISTINCT cd.device_id) as device_count,
            COUNT(DISTINCT te.id) as terminal_event_count,
            COUNT(DISTINCT bh.id) as browser_history_count
        FROM exam_sessions es
        LEFT JOIN live_processes lp ON es.id = lp.session_id
        LEFT JOIN connected_devices cd ON es.id = cd.session_id
        LEFT JOIN terminal_events te ON es.id = te.session_id
        LEFT JOIN browser_history bh ON es.id = bh.session_id
        ${whereClause}
        GROUP BY es.id
        ORDER BY es.start_time DESC
    `;

    const result = await query(query_sql, params);

    // Group by start time (rounded to nearest minute)
    const groupedStudents = {};
    for (const row of result.rows) {
        const startTime = new Date(row.start_time * 1000);
        const timeKey = startTime.toISOString();

        if (!groupedStudents[timeKey]) {
            groupedStudents[timeKey] = {
                start_time: timeKey,
                students: []
            };
        }

        groupedStudents[timeKey].students.push({
            session_id: row.session_id,
            roll_no: row.roll_no,
            lab_no: row.lab_no,
            start_time: row.start_time,
            process_count: parseInt(row.process_count),
            device_count: parseInt(row.device_count),
            terminal_event_count: parseInt(row.terminal_event_count),
            browser_history_count: parseInt(row.browser_history_count)
        });
    }

    res.json({
        total: result.rows.length,
        grouped: Object.values(groupedStudents)
    });
});

/**
 * GET /api/dashboard/student/:sessionId
 * Get detailed activity for a specific student
 * No authentication required
 */
export const getStudentDetails = asyncHandler(async (req, res) => {
    const { sessionId } = req.params;

    // Get session info
    const sessionResult = await query(`
        SELECT * FROM exam_sessions WHERE id = $1
    `, [sessionId]);

    if (sessionResult.rows.length === 0) {
        return res.status(404).json({ error: 'Session not found' });
    }

    const session = sessionResult.rows[0];

    // Get processes
    const processesResult = await query(`
        SELECT * FROM live_processes 
        WHERE session_id = $1 
        ORDER BY updated_at DESC
        LIMIT 100
    `, [sessionId]);

    // Get devices
    const devicesResult = await query(`
        SELECT * FROM connected_devices 
        WHERE session_id = $1 
        ORDER BY connected_at DESC
    `, [sessionId]);

    // Get terminal events
    const terminalResult = await query(`
        SELECT * FROM terminal_events 
        WHERE session_id = $1 
        ORDER BY detected_at DESC
        LIMIT 100
    `, [sessionId]);

    // Get browser history
    const browserResult = await query(`
        SELECT * FROM browser_history 
        WHERE session_id = $1 
        ORDER BY last_visited DESC
        LIMIT 100
    `, [sessionId]);

    res.json({
        session,
        processes: processesResult.rows,
        devices: devicesResult.rows,
        terminal_events: terminalResult.rows,
        browser_history: browserResult.rows
    });
});

/**
 * POST /api/exam/end-all
 * End all active exam sessions with secret key verification
 * No authentication required
 */
export const endAllSessions = asyncHandler(async (req, res) => {
    const { secret_key } = req.body;

    if (secret_key !== '80085') {
        return res.status(403).json({ error: 'Invalid secret key' });
    }

    const result = await query(`
        UPDATE exam_sessions 
        SET end_time = EXTRACT(EPOCH FROM NOW()),
            secret_key_verified = 1
        WHERE end_time IS NULL
        RETURNING id, roll_no, lab_no
    `);

    res.json({
        message: 'All sessions ended',
        ended_count: result.rows.length,
        sessions: result.rows
    });
});

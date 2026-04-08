// src/controllers/studentsController.js
import jwt from 'jsonwebtoken';
import { query } from '../db/index.js';
import { config } from '../config/index.js';
import { httpError, rowsToCamel, toCamel } from '../utils/helpers.js';
import { cached } from '../utils/cache.js';
import {
    upsertStudent,
    ensureSessionStudent,
    getSessionById,
} from '../services/studentService.js';

/**
 * POST /api/students/join-session
 * Body: { rollNo, sessionId, password? }
 * Returns: { token, studentId, sessionId, expiresIn }
 */
export async function joinSession(req, res, next) {
    try {
        const { rollNo, sessionId, password } = req.body;

        if (!rollNo || !sessionId) {
            throw httpError(400, 'rollNo and sessionId are required');
        }

        // 1. Validate session exists and is live
        const session = await getSessionById(sessionId);
        if (!session) throw httpError(404, 'Session not found');
        if (!session.is_live) throw httpError(400, 'Session is not live');

        // 2. Verify password if session has one
        if (session.password && session.password !== (password || '')) {
            throw httpError(403, 'Invalid session password');
        }

        // 3. Upsert student
        const studentId = await upsertStudent(rollNo);

        // 4. Ensure session_students row and touch last_seen_at
        await ensureSessionStudent(sessionId, studentId);

        // 5. Issue short-lived student JWT (1 hour)
        const expiresIn = 3600;
        const token = jwt.sign(
            { studentId, rollNo, sessionId, role: 'student' },
            config.jwtSecret,
            { expiresIn }
        );

        res.json({ token, studentId, sessionId, expiresIn });
    } catch (err) {
        next(err);
    }
}

/**
 * GET /api/teacher/sessions/:sessionId/students
 * Returns list with { rollNo, name, status, lastSeen }.
 */
export async function getSessionStudents(req, res, next) {
    try {
        const teacherId = req.user.userId;
        const { sessionId } = req.params;

        // verify teacher owns session
        const check = await query(
            'SELECT id FROM sessions WHERE id = $1 AND created_by = $2',
            [sessionId, teacherId]
        );
        if (check.rows.length === 0) throw httpError(404, 'Session not found');

        const { rows } = await query(
            `SELECT
         st.roll_no, st.name,
         ss.current_status AS status,
         ss.last_seen_at   AS last_seen
       FROM session_students ss
       JOIN students st ON st.id = ss.student_id
       WHERE ss.session_id = $1
       ORDER BY st.roll_no`,
            [sessionId]
        );

        res.json(rowsToCamel(rows));
    } catch (err) {
        next(err);
    }
}

/**
 * GET /api/teacher/students/:rollNo
 * Returns student profile and enrolled subjects.
 */
export async function getStudentProfile(req, res, next) {
    try {
        const { rollNo } = req.params;

        const stuResult = await query(
            'SELECT * FROM students WHERE roll_no = $1',
            [rollNo]
        );
        if (stuResult.rows.length === 0) throw httpError(404, 'Student not found');

        const student = toCamel(stuResult.rows[0]);

        // get subjects via session_students → sessions → subjects
        const { rows: subjects } = await query(
            `SELECT DISTINCT su.id, su.name, su.department, su.year
       FROM session_students ss
       JOIN sessions se ON se.id = ss.session_id
       JOIN subjects su ON su.id = se.subject_id
       WHERE ss.student_id = $1`,
            [student.id]
        );

        res.json({ ...student, enrolledSubjects: rowsToCamel(subjects) });
    } catch (err) {
        next(err);
    }
}

/**
 * GET /api/teacher/students/:rollNo/devices?sessionId=...
 * Returns { usb: [...], external: [...] } with disconnected_at IS NULL.
 */
export async function getStudentDevices(req, res, next) {
    try {
        const { rollNo } = req.params;
        const { sessionId } = req.query;

        if (!sessionId) throw httpError(400, 'sessionId query param is required');

        const stuResult = await query('SELECT id FROM students WHERE roll_no = $1', [rollNo]);
        if (stuResult.rows.length === 0) throw httpError(404, 'Student not found');
        const studentId = stuResult.rows[0].id;

        const result = await cached(`devices:${sessionId}:${studentId}`, 2000, async () => {
            const { rows } = await query(
                `SELECT device_id, device_name, device_type, connected_at, metadata,
                        readable_name, risk_level, message
           FROM connected_devices
           WHERE session_id = $1 AND student_id = $2 AND disconnected_at IS NULL`,
                [sessionId, studentId]
            );
            const usb = rows.filter((r) => r.device_type === 'usb').map(toCamel);
            const external = rows.filter((r) => r.device_type === 'external').map(toCamel);
            return { usb, external };
        });

        res.json(result);
    } catch (err) {
        next(err);
    }
}

/**
 * GET /api/teacher/students/:rollNo/network?sessionId=...
 * Returns latest network_info record.
 */
export async function getStudentNetwork(req, res, next) {
    try {
        const { rollNo } = req.params;
        const { sessionId } = req.query;

        if (!sessionId) throw httpError(400, 'sessionId query param is required');

        const stuResult = await query('SELECT id FROM students WHERE roll_no = $1', [rollNo]);
        if (stuResult.rows.length === 0) throw httpError(404, 'Student not found');
        const studentId = stuResult.rows[0].id;

        const result = await cached(`network:${sessionId}:${studentId}`, 2000, async () => {
            const { rows } = await query(
                `SELECT ip_address, gateway, dns, active_connections, updated_at
           FROM network_info
           WHERE session_id = $1 AND student_id = $2
           ORDER BY updated_at DESC
           LIMIT 1`,
                [sessionId, studentId]
            );
            return rows.length ? toCamel(rows[0]) : null;
        });

        res.json(result);
    } catch (err) {
        next(err);
    }
}

/**
 * GET /api/teacher/sessions/:sessionId/students/:rollNo/processes
 * Returns snapshot of live_processes for student/session.
 */
export async function getStudentProcesses(req, res, next) {
    try {
        const { sessionId, rollNo } = req.params;

        const stuResult = await query('SELECT id FROM students WHERE roll_no = $1', [rollNo]);
        if (stuResult.rows.length === 0) throw httpError(404, 'Student not found');
        const studentId = stuResult.rows[0].id;

        const result = await cached(`procs:${sessionId}:${studentId}`, 2000, async () => {
            const { rows } = await query(
                `SELECT pid, process_name, cpu_percent, memory_mb, status, updated_at,
                        risk_level, category
           FROM live_processes
           WHERE session_id = $1 AND student_id = $2
           ORDER BY updated_at DESC`,
                [sessionId, studentId]
            );
            return rowsToCamel(rows);
        });

        res.json(result);
    } catch (err) {
        next(err);
    }
}

/**
 * GET /api/teacher/students/:rollNo/domain-activity?sessionId=...
 * Returns aggregated domain activity for the student in the given session.
 */
export async function getStudentDomainActivity(req, res, next) {
    try {
        const { rollNo } = req.params;
        const { sessionId } = req.query;

        if (!sessionId) throw httpError(400, 'sessionId query param is required');

        const stuResult = await query('SELECT id FROM students WHERE roll_no = $1', [rollNo]);
        if (stuResult.rows.length === 0) throw httpError(404, 'Student not found');
        const studentId = stuResult.rows[0].id;

        const result = await cached(`domains:${sessionId}:${studentId}`, 2000, async () => {
            const { rows } = await query(
                `SELECT domain, request_count, risk_level, last_accessed
           FROM domain_activity
           WHERE session_id = $1 AND student_id = $2
           ORDER BY request_count DESC
           LIMIT 50`,
                [sessionId, studentId]
            );
            return rowsToCamel(rows);
        });

        res.json(result);
    } catch (err) {
        next(err);
    }
}

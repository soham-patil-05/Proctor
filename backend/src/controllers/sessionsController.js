// src/controllers/sessionsController.js
import { query } from '../db/index.js';
import { httpError, rowsToCamel, toCamel } from '../utils/helpers.js';

/**
 * POST /api/teacher/sessions
 * Body: { subjectId, batch, lab, date, startTime, password? }
 */
export async function createSession(req, res, next) {
    try {
        const teacherId = req.user.userId;
        const { subjectId, batch, lab, date, startTime, password } = req.body;

        if (!subjectId || !batch || !lab || !date || !startTime) {
            throw httpError(400, 'subjectId, batch, lab, date, and startTime are required');
        }

        // verify teacher owns the subject
        const subCheck = await query(
            'SELECT id FROM subjects WHERE id = $1 AND teacher_id = $2',
            [subjectId, teacherId]
        );
        if (subCheck.rows.length === 0) {
            throw httpError(403, 'Subject not found or not owned by you');
        }

        const { rows } = await query(
            `INSERT INTO sessions (subject_id, batch, lab_name, date, start_time, is_live, password, created_by)
       VALUES ($1, $2, $3, $4, $5, true, $6, $7)
       RETURNING id, is_live`,
            [subjectId, batch, lab, date, startTime, password || null, teacherId]
        );

        const session = rows[0];
        res.status(201).json({
            sessionId: session.id,
            isLive: session.is_live,
            joinUrl: `/ws/agents/sessions/${session.id}/students/:studentId`,
        });
    } catch (err) {
        next(err);
    }
}

/**
 * GET /api/teacher/sessions?status=all|live|ended
 */
export async function getSessions(req, res, next) {
    try {
        const teacherId = req.user.userId;
        const status = req.query.status || 'all';

        let filter = '';
        if (status === 'live') filter = 'AND se.is_live = true';
        if (status === 'ended') filter = 'AND se.is_live = false';

        const { rows } = await query(
            `SELECT
         se.id AS session_id, se.batch, se.lab_name, se.date, se.start_time, se.end_time,
         se.is_live, se.created_at,
         su.name AS subject_name
       FROM sessions se
       JOIN subjects su ON su.id = se.subject_id
       WHERE se.created_by = $1 ${filter}
       ORDER BY se.created_at DESC`,
            [teacherId]
        );

        res.json(rowsToCamel(rows));
    } catch (err) {
        next(err);
    }
}

/**
 * GET /api/teacher/sessions/:sessionId
 */
export async function getSession(req, res, next) {
    try {
        const teacherId = req.user.userId;
        const { sessionId } = req.params;

        const { rows } = await query(
            `SELECT
         se.id AS session_id, se.subject_id, se.batch, se.lab_name, se.date,
         se.start_time, se.end_time, se.is_live, se.password, se.created_by,
         se.created_at,
         su.name AS subject_name,
         (SELECT COUNT(*)::int FROM session_students ss WHERE ss.session_id = se.id) AS student_count
       FROM sessions se
       JOIN subjects su ON su.id = se.subject_id
       WHERE se.id = $1 AND se.created_by = $2`,
            [sessionId, teacherId]
        );

        if (rows.length === 0) throw httpError(404, 'Session not found');

        res.json(toCamel(rows[0]));
    } catch (err) {
        next(err);
    }
}

/**
 * POST /api/teacher/sessions/:sessionId/end
 */
export async function endSession(req, res, next) {
    try {
        const teacherId = req.user.userId;
        const { sessionId } = req.params;

        const { rows } = await query(
            `UPDATE sessions
       SET is_live = false, end_time = now()
       WHERE id = $1 AND created_by = $2
       RETURNING end_time`,
            [sessionId, teacherId]
        );

        if (rows.length === 0) throw httpError(404, 'Session not found');

        res.json({ status: 'ended', endedAt: rows[0].end_time });
    } catch (err) {
        next(err);
    }
}

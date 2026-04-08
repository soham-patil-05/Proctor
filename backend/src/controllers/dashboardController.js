// src/controllers/dashboardController.js
import { query } from '../db/index.js';
import { toCamel } from '../utils/helpers.js';

/**
 * GET /api/teacher/dashboard
 * Returns { totalSubjects, activeSession, totalSessions }.
 */
export async function getDashboard(req, res, next) {
    try {
        const teacherId = req.user.userId;

        const { rows } = await query(
            `SELECT
         (SELECT COUNT(*)::int FROM subjects WHERE teacher_id = $1) AS total_subjects,
         (SELECT COUNT(*)::int FROM sessions WHERE created_by = $1 AND is_live = true) AS active_session,
         (SELECT COUNT(*)::int FROM sessions WHERE created_by = $1) AS total_sessions`,
            [teacherId]
        );

        res.json(toCamel(rows[0]));
    } catch (err) {
        next(err);
    }
}

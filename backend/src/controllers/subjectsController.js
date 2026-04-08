// src/controllers/subjectsController.js
import { query } from '../db/index.js';
import { httpError, rowsToCamel } from '../utils/helpers.js';

/**
 * GET /api/teacher/subjects
 * Returns subjects for the authenticated teacher with totalSessions and active flag.
 */
export async function getSubjects(req, res, next) {
    try {
        const teacherId = req.user.userId;

        const { rows } = await query(
            `SELECT
         s.id, s.name, s.department, s.year, s.created_at,
         COUNT(se.id)::int                          AS total_sessions,
         BOOL_OR(se.is_live) IS TRUE                AS active
       FROM subjects s
       LEFT JOIN sessions se ON se.subject_id = s.id
       WHERE s.teacher_id = $1
       GROUP BY s.id
       ORDER BY s.created_at DESC`,
            [teacherId]
        );

        res.json(rowsToCamel(rows));
    } catch (err) {
        next(err);
    }
}

/**
 * POST /api/teacher/subjects
 * Body: { name, department, year }
 */
export async function createSubject(req, res, next) {
    try {
        const teacherId = req.user.userId;
        const { name, department, year } = req.body;

        if (!name) throw httpError(400, 'Subject name is required');

        const { rows } = await query(
            `INSERT INTO subjects (teacher_id, name, department, year)
       VALUES ($1, $2, $3, $4)
       RETURNING *`,
            [teacherId, name, department || null, year || null]
        );

        res.status(201).json(rowsToCamel(rows)[0]);
    } catch (err) {
        next(err);
    }
}

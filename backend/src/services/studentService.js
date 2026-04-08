// src/services/studentService.js — student upsert & session-join helpers
import { query } from '../db/index.js';

/**
 * Upsert a student row by roll_no.
 * Creates the student if not exists, updates name if provided.
 * @returns {string} student UUID
 */
export async function upsertStudent(rollNo, name) {
    const { rows } = await query(
        `INSERT INTO students (roll_no, name)
     VALUES ($1, $2)
     ON CONFLICT (roll_no) DO UPDATE SET name = EXCLUDED.name
     RETURNING id`,
        [rollNo, name || rollNo]
    );
    return rows[0].id;
}

/**
 * Ensure a session_students row exists and touch last_seen_at.
 */
export async function ensureSessionStudent(sessionId, studentId) {
    await query(
        `INSERT INTO session_students (session_id, student_id, current_status, last_seen_at)
     VALUES ($1, $2, 'normal', now())
     ON CONFLICT (session_id, student_id)
     DO UPDATE SET last_seen_at = now()`,
        [sessionId, studentId]
    );
}

/**
 * Get a session by id (regardless of live status).
 */
export async function getSessionById(sessionId) {
    const { rows } = await query(
        'SELECT id, subject_id, is_live, password, created_by FROM sessions WHERE id = $1',
        [sessionId]
    );
    return rows[0] || null;
}

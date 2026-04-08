// src/services/sessionService.js — session-related DB operations used by WS server
import { query } from '../db/index.js';

/**
 * Verify that a session exists and is live.
 * @returns {object|null} session row
 */
export async function getLiveSession(sessionId) {
    const { rows } = await query(
        'SELECT id, subject_id, created_by, is_live FROM sessions WHERE id = $1',
        [sessionId]
    );
    return rows[0] || null;
}

/**
 * Upsert a session_student record and update last_seen_at.
 */
export async function upsertSessionStudent(sessionId, studentId, status = 'normal') {
    await query(
        `INSERT INTO session_students (session_id, student_id, current_status, last_seen_at)
     VALUES ($1, $2, $3, now())
     ON CONFLICT (session_id, student_id)
     DO UPDATE SET last_seen_at = now(), current_status = EXCLUDED.current_status`,
        [sessionId, studentId, status]
    );
}

/**
 * Touch last_seen_at for a session student.
 */
export async function touchLastSeen(sessionId, studentId) {
    await query(
        `UPDATE session_students SET last_seen_at = now() WHERE session_id = $1 AND student_id = $2`,
        [sessionId, studentId]
    );
}

/**
 * Look up a student by id.
 */
export async function getStudentById(studentId) {
    const { rows } = await query('SELECT * FROM students WHERE id = $1', [studentId]);
    return rows[0] || null;
}

/**
 * Verify teacher owns the session.
 */
export async function teacherOwnsSession(teacherId, sessionId) {
    const { rows } = await query(
        'SELECT id FROM sessions WHERE id = $1 AND created_by = $2',
        [sessionId, teacherId]
    );
    return rows.length > 0;
}

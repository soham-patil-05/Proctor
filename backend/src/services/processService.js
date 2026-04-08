// src/services/processService.js — live_processes DB operations
import { query } from '../db/index.js';

/**
 * Upsert a single process row (INSERT … ON CONFLICT) with enrichment fields.
 */
export async function upsertProcess(sessionId, studentId, proc) {
    await query(
        `INSERT INTO live_processes (session_id, student_id, pid, process_name, cpu_percent, memory_mb, status, risk_level, category, updated_at)
     VALUES ($1, $2, $3, $4, $5, $6, 'running', $7, $8, now())
     ON CONFLICT (session_id, student_id, pid)
     DO UPDATE SET process_name = EXCLUDED.process_name,
                   cpu_percent  = EXCLUDED.cpu_percent,
                   memory_mb    = EXCLUDED.memory_mb,
                   status       = EXCLUDED.status,
                   risk_level   = COALESCE(EXCLUDED.risk_level, live_processes.risk_level),
                   category     = COALESCE(EXCLUDED.category, live_processes.category),
                   updated_at   = now()`,
        [
            sessionId,
            studentId,
            proc.pid,
            proc.name,
            proc.cpu ?? 0,
            proc.memory ?? 0,
            proc.risk_level ?? null,
            proc.category ?? null,
        ]
    );
}

/**
 * Bulk upsert from a process_snapshot.
 */
export async function upsertProcessSnapshot(sessionId, studentId, processes) {
    for (const p of processes) {
        await upsertProcess(sessionId, studentId, p);
    }
}

/**
 * Update an existing process row (cpu, memory, status, risk_level, category).
 */
export async function updateProcess(sessionId, studentId, proc) {
    await query(
        `UPDATE live_processes
     SET cpu_percent = $4, memory_mb = $5, status = $6,
         risk_level = COALESCE($7, risk_level),
         category   = COALESCE($8, category),
         updated_at = now()
     WHERE session_id = $1 AND student_id = $2 AND pid = $3`,
        [
            sessionId,
            studentId,
            proc.pid,
            proc.cpu ?? 0,
            proc.memory ?? 0,
            proc.status ?? 'running',
            proc.risk_level ?? null,
            proc.category ?? null,
        ]
    );
}

/**
 * Mark a process as ended.
 */
export async function endProcess(sessionId, studentId, pid) {
    await query(
        `UPDATE live_processes SET status = 'ended', updated_at = now()
     WHERE session_id = $1 AND student_id = $2 AND pid = $3`,
        [sessionId, studentId, pid]
    );
}

/**
 * Get all live processes for a student/session (with enrichment fields).
 */
export async function getProcesses(sessionId, studentId) {
    const { rows } = await query(
        `SELECT pid, process_name AS name, cpu_percent AS cpu, memory_mb AS memory,
                status, risk_level, category
     FROM live_processes
     WHERE session_id = $1 AND student_id = $2
     ORDER BY updated_at DESC`,
        [sessionId, studentId]
    );
    return rows;
}

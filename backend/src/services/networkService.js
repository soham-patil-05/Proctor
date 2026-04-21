// src/services/networkService.js — domain_activity & terminal_events DB operations
import { query } from '../db/index.js';

// FIX: uuid_generate_v4() requires the uuid-ossp extension which may not be
// enabled on all hosted DB providers. Generate UUIDs in JS instead.
function generateUuid() {
  return 'xxxxxxxx-xxxx-4xxx-yxxx-xxxxxxxxxxxx'.replace(/[xy]/g, (c) => {
    const r = (Math.random() * 16) | 0;
    return (c === 'x' ? r : (r & 0x3) | 0x8).toString(16);
  });
}

/**
 * Upsert domain activity: increment request_count for each domain entry.
 */
export async function upsertDomainActivity(sessionId, studentId, domainEntries) {
  for (const entry of domainEntries) {
    await query(
      `INSERT INTO domain_activity
         (id, session_id, student_id, domain, request_count, risk_level, last_accessed)
       VALUES ($1, $2, $3, $4, $5, $6, now())
       ON CONFLICT (session_id, student_id, domain)
       DO UPDATE SET request_count = domain_activity.request_count + EXCLUDED.request_count,
                     risk_level    = COALESCE(EXCLUDED.risk_level, domain_activity.risk_level),
                     last_accessed = now()`,
      [
        generateUuid(),
        sessionId,
        studentId,
        entry.domain,
        entry.count ?? 1,
        entry.risk_level ?? 'normal',
      ]
    );
  }
}

/**
 * Get aggregated domain activity for a student/session, ordered by request_count desc.
 */
export async function getDomainActivity(sessionId, studentId) {
  const { rows } = await query(
    `SELECT domain, request_count, risk_level, last_accessed
     FROM domain_activity
     WHERE session_id = $1 AND student_id = $2
     ORDER BY request_count DESC
     LIMIT 50`,
    [sessionId, studentId]
  );
  return rows;
}

/**
 * Persist a single terminal_request or terminal_command event.
 */
export async function insertTerminalEvent(
  sessionId, studentId, data, eventType, riskLevel, message
) {
  await query(
    `INSERT INTO terminal_events
       (id, session_id, student_id, event_type,
        tool, remote_ip, remote_host, remote_port, pid,
        full_command, risk_level, message, detected_at)
     VALUES
       ($1, $2, $3, $4,
        $5, $6, $7, $8, $9,
        $10, $11, $12, now())`,
    [
      generateUuid(),
      sessionId,
      studentId,
      eventType,
      data.tool ?? null,
      data.remote_ip ?? null,
      data.remote_host ?? null,
      data.remote_port ?? null,
      data.pid ?? null,
      data.full_command ?? null,
      riskLevel,
      message ?? null,
    ]
  );
}

/**
 * Fetch the most recent terminal events for a student in a session.
 */
export async function getTerminalEvents(sessionId, studentId) {
  const { rows } = await query(
    `SELECT id, event_type, tool, remote_ip, remote_host, remote_port,
            pid, full_command, risk_level, message, detected_at
     FROM terminal_events
     WHERE session_id = $1 AND student_id = $2
     ORDER BY detected_at DESC
     LIMIT 100`,
    [sessionId, studentId]
  );
  return rows;
}

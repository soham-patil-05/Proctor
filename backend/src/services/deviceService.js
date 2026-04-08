// src/services/deviceService.js — connected_devices & network_info DB operations
import { query } from '../db/index.js';

/* ─── connected_devices ─────────────────────────────────────────── */

/**
 * Upsert a single device (with new enrichment fields).
 */
export async function upsertDevice(sessionId, studentId, device, deviceType) {
    await query(
        `INSERT INTO connected_devices
       (session_id, student_id, device_id, device_name, device_type, connected_at, metadata,
        readable_name, risk_level, message)
     VALUES ($1, $2, $3, $4, $5, now(), $6, $7, $8, $9)
     ON CONFLICT (session_id, student_id, device_id)
     DO UPDATE SET disconnected_at = NULL,
                   device_name     = EXCLUDED.device_name,
                   readable_name   = COALESCE(EXCLUDED.readable_name, connected_devices.readable_name),
                   risk_level      = COALESCE(EXCLUDED.risk_level, connected_devices.risk_level),
                   message         = COALESCE(EXCLUDED.message, connected_devices.message)`,
        [
            sessionId,
            studentId,
            device.id,
            device.name,
            deviceType,
            device.metadata ?? null,
            device.readable_name ?? null,
            device.risk_level ?? null,
            device.message ?? null,
        ]
    );
}

/**
 * Process a devices_snapshot — upsert all USB & external devices.
 */
export async function upsertDevicesSnapshot(sessionId, studentId, data) {
    for (const d of data.usb || []) {
        await upsertDevice(sessionId, studentId, d, 'usb');
    }
    for (const d of data.external || []) {
        await upsertDevice(sessionId, studentId, d, 'external');
    }
}

/**
 * Mark a device as disconnected.
 */
export async function disconnectDevice(sessionId, studentId, deviceId) {
    await query(
        `UPDATE connected_devices
     SET disconnected_at = now()
     WHERE session_id = $1 AND student_id = $2 AND device_id = $3`,
        [sessionId, studentId, deviceId]
    );
}

/**
 * Get currently-connected devices for student/session (with enrichment fields).
 */
export async function getDevices(sessionId, studentId) {
    const { rows } = await query(
        `SELECT device_id AS id, device_name AS name, device_type,
                readable_name, risk_level, message, metadata
     FROM connected_devices
     WHERE session_id = $1 AND student_id = $2 AND disconnected_at IS NULL`,
        [sessionId, studentId]
    );
    return {
        usb: rows.filter((r) => r.device_type === 'usb'),
        external: rows.filter((r) => r.device_type === 'external'),
    };
}

/* ─── network_info ──────────────────────────────────────────────── */

/**
 * Upsert network info.
 */
export async function upsertNetworkInfo(sessionId, studentId, net) {
    await query(
        `INSERT INTO network_info
       (session_id, student_id, ip_address, gateway, dns, active_connections, updated_at)
     VALUES ($1, $2, $3, $4, $5, $6, now())
     ON CONFLICT (session_id, student_id)
     DO UPDATE SET ip_address        = EXCLUDED.ip_address,
                   gateway           = EXCLUDED.gateway,
                   dns               = EXCLUDED.dns,
                   active_connections = EXCLUDED.active_connections,
                   updated_at        = now()`,
        [
            sessionId,
            studentId,
            net.ip ?? null,
            net.gateway ?? null,
            JSON.stringify(net.dns ?? []),
            net.activeConnections ?? 0,
        ]
    );
}

/**
 * Get latest network info.
 */
export async function getNetworkInfo(sessionId, studentId) {
    const { rows } = await query(
        `SELECT ip_address AS ip, gateway, dns, active_connections AS "activeConnections"
     FROM network_info
     WHERE session_id = $1 AND student_id = $2
     ORDER BY updated_at DESC LIMIT 1`,
        [sessionId, studentId]
    );
    return rows[0] || null;
}

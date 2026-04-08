// src/ws-server.js — standalone WebSocket server process
//
// Runs on WS_PORT (default 8001).
// Two connection roles:
//   agent  → /ws/agents/sessions/:sessionId/students/:studentId
//   teacher → /ws/teachers/sessions/:sessionId/students/:rollNo/processes
//
// Authenticates via JWT (Authorization header OR ?token= query param).
// Agent tokens must have role=student; teacher tokens must have role=teacher.

import 'dotenv/config';
import http from 'node:http';
import { URL } from 'node:url';
import { WebSocketServer, WebSocket } from 'ws';
import { config, getRedis } from './config/index.js';
import { verifyToken } from './middleware/auth.js';
import { pool, query } from './db/index.js';
import {
    upsertProcess,
    upsertProcessSnapshot,
    updateProcess,
    endProcess,
    getProcesses,
} from './services/processService.js';
import {
    upsertDevice,
    upsertDevicesSnapshot,
    disconnectDevice,
    getDevices,
    upsertNetworkInfo,
    getNetworkInfo,
} from './services/deviceService.js';
import {
    upsertDomainActivity,
    getDomainActivity,
    insertTerminalEvent,
    getTerminalEvents,
} from './services/networkService.js';
import {
    getLiveSession,
    upsertSessionStudent,
    touchLastSeen,
    getStudentById,
    teacherOwnsSession,
} from './services/sessionService.js';
import {
    subscribe,
    unsubscribe,
    unsubscribeAll,
    publish,
} from './services/wsPublisher.js';

/* ─── Configurable log level ─────────────────────────────────────── */
const LOG_LEVEL = (process.env.LOG_LEVEL || 'info').toLowerCase();
const LOG_LEVELS = { debug: 0, info: 1, warn: 2, error: 3 };

function log(level, ...args) {
    if ((LOG_LEVELS[level] ?? 1) >= (LOG_LEVELS[LOG_LEVEL] ?? 1)) {
        const fn = level === 'error' ? console.error : level === 'warn' ? console.warn : console.log;
        fn(`[WS][${level.toUpperCase()}]`, new Date().toISOString(), ...args);
    }
}

/* ================================================================
   Helpers
   ================================================================ */

/**
 * Parse the URL path into { role, sessionId, studentId?, rollNo? }.
 */
function parsePath(pathname) {
    const agentMatch = pathname.match(
        /^\/ws\/agents\/sessions\/([0-9a-f-]+)\/students\/([0-9a-f-]+)$/i
    );
    if (agentMatch) {
        return { role: 'agent', sessionId: agentMatch[1], studentId: agentMatch[2] };
    }

    const teacherMatch = pathname.match(
        /^\/ws\/teachers\/sessions\/([0-9a-f-]+)\/students\/([^/]+)\/processes$/i
    );
    if (teacherMatch) {
        return { role: 'teacher', sessionId: teacherMatch[1], rollNo: teacherMatch[2] };
    }

    return null;
}

/**
 * Extract JWT from the upgrade request.
 */
function extractToken(req) {
    const auth = req.headers.authorization;
    if (auth?.startsWith('Bearer ')) return auth.slice(7);
    const url = new URL(req.url, `http://${req.headers.host}`);
    return url.searchParams.get('token');
}

/* ─── Message validators ─────────────────────────────────────────── */
const VALID_TYPES = new Set([
    'process_snapshot', 'process_new', 'process_update', 'process_end',
    'devices_snapshot', 'device_connected', 'device_disconnected',
    'network_snapshot', 'network_update', 'domain_activity',
    'terminal_request', 'terminal_command',
    'heartbeat',
]);

function validateAgentMsg(msg) {
    if (!msg || typeof msg !== 'object') return 'Message must be a JSON object';
    if (!VALID_TYPES.has(msg.type)) return `Unknown type: ${msg.type}`;
    if (msg.type !== 'heartbeat' && msg.data === undefined) return 'Missing data field';
    return null;
}

/**
 * Sanitize strings in metadata to prevent injection; limit to 4 KB.
 */
function sanitizeMetadata(meta) {
    if (meta == null) return null;
    const str = typeof meta === 'string' ? meta : JSON.stringify(meta);
    if (str.length > 4096) return null;
    return typeof meta === 'string' ? meta : JSON.parse(str);
}

/* ================================================================
   In-memory agent tracking (for heartbeat / liveness)
   ================================================================ */

const agentSockets = new Map();
const HEARTBEAT_TIMEOUT_MS = 15_000; // 15s timeout per spec

function agentKey(sessionId, studentId) {
    return `${sessionId}:${studentId}`;
}

function resetHeartbeatTimer(sessionId, studentId) {
    const key = agentKey(sessionId, studentId);
    const entry = agentSockets.get(key);
    if (!entry) return;

    if (entry.timer) clearTimeout(entry.timer);

    entry.lastSeen = Date.now();
    entry.timer = setTimeout(() => {
        const offlineMsg = {
            type: 'agent_offline',
            data: { studentId, lastSeen: new Date(entry.lastSeen).toISOString() },
        };
        publish(sessionId, studentId, offlineMsg);
        log('warn', `Agent offline (heartbeat timeout): session=${sessionId} student=${studentId}`);
    }, HEARTBEAT_TIMEOUT_MS);
}

/* ─── Rate limiter (per student — 2 updates/sec for process events) ── */
const rateBuckets = new Map(); // key → { count, resetAt }

function isRateLimited(sessionId, studentId) {
    const key = agentKey(sessionId, studentId);
    const now = Date.now();
    let bucket = rateBuckets.get(key);
    if (!bucket || now >= bucket.resetAt) {
        bucket = { count: 0, resetAt: now + 1000 };
        rateBuckets.set(key, bucket);
    }
    bucket.count++;
    return bucket.count > 2;
}

/* ================================================================
   Redis event buffer (optional — last 100 events per student)
   ================================================================ */

let redis = null;

async function bufferEvent(sessionId, studentId, event) {
    if (!redis) return;
    try {
        const key = `events:${sessionId}:${studentId}`;
        await redis.lPush(key, JSON.stringify(event));
        await redis.lTrim(key, 0, 99);
        await redis.expire(key, 3600);
    } catch { /* ignore Redis failures */ }
}

async function getBufferedEvents(sessionId, studentId) {
    if (!redis) return [];
    try {
        const key = `events:${sessionId}:${studentId}`;
        const items = await redis.lRange(key, 0, 99);
        return items.map((i) => JSON.parse(i)).reverse();
    } catch {
        return [];
    }
}

/* ================================================================
   WebSocket server setup (with permessage-deflate)
   ================================================================ */

const httpServer = http.createServer((_req, res) => {
    res.writeHead(426, { 'Content-Type': 'text/plain' });
    res.end('Upgrade required');
});

const wss = new WebSocketServer({
    noServer: true,
    perMessageDeflate: {
        zlibDeflateOptions: { chunkSize: 1024, memLevel: 7, level: 3 },
        zlibInflateOptions: { chunkSize: 10 * 1024 },
        threshold: 256,
    },
});

httpServer.on('upgrade', (req, socket, head) => {
    try {
        const token = extractToken(req);
        if (!token) {
            socket.write('HTTP/1.1 401 Unauthorized\r\n\r\n');
            socket.destroy();
            return;
        }

        const user = verifyToken(token); // throws on bad/expired token
        req._user = user;

        wss.handleUpgrade(req, socket, head, (ws) => {
            wss.emit('connection', ws, req);
        });
    } catch (err) {
        log('error', 'Auth failed:', err.message);
        socket.write('HTTP/1.1 401 Unauthorized\r\n\r\n');
        socket.destroy();
    }
});

/* ================================================================
   Connection handler
   ================================================================ */

wss.on('connection', async (ws, req) => {
    const url = new URL(req.url, `http://${req.headers.host}`);
    const parsed = parsePath(url.pathname);
    const user = req._user;

    if (!parsed) {
        ws.close(4000, 'Invalid path');
        return;
    }

    const { role, sessionId } = parsed;

    /* ── Agent connection ──────────────────────────────────────── */
    if (role === 'agent') {
        const { studentId } = parsed;

        // Role check — agent must have student JWT
        if (user.role !== 'student') {
            ws.close(4005, 'Agent endpoint requires student token');
            return;
        }

        // Token session/student must match URL
        if (user.sessionId !== sessionId || user.studentId !== studentId) {
            ws.close(4006, 'Token does not match path');
            return;
        }

        // Verify session is live
        const session = await getLiveSession(sessionId);
        if (!session || !session.is_live) {
            ws.close(4001, 'Session not live');
            return;
        }

        // Verify student exists
        const student = await getStudentById(studentId);
        if (!student) {
            ws.close(4002, 'Student not found');
            return;
        }

        // Register / upsert the student into the session
        await upsertSessionStudent(sessionId, studentId);

        // Track the agent socket
        const key = agentKey(sessionId, studentId);
        const prev = agentSockets.get(key);
        if (prev?.timer) clearTimeout(prev.timer);

        agentSockets.set(key, { ws, lastSeen: Date.now(), timer: null });
        resetHeartbeatTimer(sessionId, studentId);

        log('info', `Agent connected: session=${sessionId} student=${studentId}`);

        // Send ack + config to agent
        ws.send(JSON.stringify({
            type: 'ack',
            data: {
                message: 'Connected to session',
                config: {
                    snapshotIntervalSec: 30,
                    deltaIntervalSec: 3,
                    heartbeatIntervalSec: 5,
                },
            },
        }));

        ws.on('message', async (raw) => {
            try {
                const msg = JSON.parse(raw.toString());

                // Validate message shape
                const err = validateAgentMsg(msg);
                if (err) {
                    log('warn', `Invalid agent msg: ${err}`);
                    return;
                }

                resetHeartbeatTimer(sessionId, studentId);
                await touchLastSeen(sessionId, studentId);

                // Rate-limit process update events
                const isProcessUpdate = ['process_new', 'process_update'].includes(msg.type);
                if (isProcessUpdate && isRateLimited(sessionId, studentId)) {
                    return; // silently drop
                }

                // Sanitize device metadata
                if (msg.type === 'device_connected' && msg.data?.metadata) {
                    msg.data.metadata = sanitizeMetadata(msg.data.metadata);
                }
                if (msg.type === 'devices_snapshot' && msg.data) {
                    for (const d of (msg.data.usb || [])) { d.metadata = sanitizeMetadata(d.metadata); }
                    for (const d of (msg.data.external || [])) { d.metadata = sanitizeMetadata(d.metadata); }
                }

                switch (msg.type) {
                    case 'process_snapshot':
                        await upsertProcessSnapshot(sessionId, studentId, msg.data);
                        break;
                    case 'process_new':
                        await upsertProcess(sessionId, studentId, msg.data);
                        break;
                    case 'process_update':
                        await updateProcess(sessionId, studentId, msg.data);
                        break;
                    case 'process_end':
                        await endProcess(sessionId, studentId, msg.data.pid);
                        break;
                    case 'devices_snapshot':
                        await upsertDevicesSnapshot(sessionId, studentId, msg.data);
                        break;
                    case 'device_connected':
                        await upsertDevice(sessionId, studentId, msg.data, msg.data.type || 'usb');
                        break;
                    case 'device_disconnected':
                        await disconnectDevice(sessionId, studentId, msg.data.id);
                        break;
                    case 'network_snapshot':
                        await upsertNetworkInfo(sessionId, studentId, msg.data);
                        break;
                    case 'network_update':
                        await upsertNetworkInfo(sessionId, studentId, msg.data);
                        break;
                    case 'domain_activity':
                        await upsertDomainActivity(sessionId, studentId, msg.data);
                        break;
                    case 'terminal_request':
                    case 'terminal_command':
                        msg.data.event_type = msg.type;
                        msg.data.risk_level = msg.meta?.risk_level ?? 'medium';
                        msg.data.message = msg.meta?.message ?? null;
                        msg.data.detected_at = new Date().toISOString();
                        
                        await insertTerminalEvent(
                            sessionId,
                            studentId,
                            msg.data,
                            msg.type,
                            msg.data.risk_level,
                            msg.data.message
                        );
                        break;
                    case 'heartbeat':
                        break;
                    default:
                        log('warn', `Unknown agent message type: ${msg.type}`);
                }

                // Buffer event in Redis and publish to teachers
                await bufferEvent(sessionId, studentId, msg);
                publish(sessionId, studentId, msg);
            } catch (err) {
                log('error', 'Agent message error:', err.message);
            }
        });

        ws.on('close', () => {
            const entry = agentSockets.get(key);
            if (entry?.timer) clearTimeout(entry.timer);
            agentSockets.delete(key);
            log('info', `Agent disconnected: session=${sessionId} student=${studentId}`);

            publish(sessionId, studentId, {
                type: 'agent_offline',
                data: { studentId, lastSeen: new Date().toISOString() },
            });
        });

        return;
    }

    /* ── Teacher connection ────────────────────────────────────── */
    if (role === 'teacher') {
        const { rollNo } = parsed;

        // Role check — teacher endpoint requires teacher JWT
        if (user.role !== 'teacher') {
            ws.close(4005, 'Teacher endpoint requires teacher token');
            return;
        }

        // Verify ownership
        const owns = await teacherOwnsSession(user.userId, sessionId);
        if (!owns) {
            ws.close(4003, 'No permission for this session');
            return;
        }

        // Resolve student id from rollNo
        const stuResult = await query('SELECT id FROM students WHERE roll_no = $1', [rollNo]);
        if (stuResult.rows.length === 0) {
            ws.close(4004, 'Student not found');
            return;
        }
        const studentId = stuResult.rows[0].id;

        // Subscribe this teacher to events
        subscribe(sessionId, studentId, ws);
        log('info', `Teacher subscribed: session=${sessionId} student=${rollNo}`);

        // Send initial snapshots
        try {
            const [processes, devices, network, domains, terminalEvents] = await Promise.all([
                getProcesses(sessionId, studentId),
                getDevices(sessionId, studentId),
                getNetworkInfo(sessionId, studentId),
                getDomainActivity(sessionId, studentId),
                getTerminalEvents(sessionId, studentId),
            ]);

            ws.send(JSON.stringify({ type: 'process_snapshot', data: processes }));
            ws.send(JSON.stringify({ type: 'devices_snapshot', data: devices }));
            if (network) {
                ws.send(JSON.stringify({ type: 'network_snapshot', data: network }));
            }
            if (domains && domains.length > 0) {
                ws.send(JSON.stringify({ type: 'domain_activity', data: domains }));
            }
            if (terminalEvents && terminalEvents.length > 0) {
                ws.send(JSON.stringify({ type: 'terminal_events_snapshot', data: terminalEvents }));
            }

            // Replay buffered events from Redis (if available)
            const buffered = await getBufferedEvents(sessionId, studentId);
            for (const evt of buffered) {
                ws.send(JSON.stringify(evt));
            }
        } catch (err) {
            log('error', 'Error sending initial snapshots:', err.message);
        }

        ws.on('close', () => {
            unsubscribe(sessionId, studentId, ws);
            log('info', `Teacher unsubscribed: session=${sessionId} student=${rollNo}`);
        });

        return;
    }
});

/* ================================================================
   Exported lifecycle — called from server.js
   ================================================================ */

export async function startWsServer() {
    redis = await getRedis();

    httpServer.listen(config.wsPort, () => {
        log('info', `WebSocket server listening on port ${config.wsPort}`);
    });
}

export async function stopWsServer() {
    wss.close();
    httpServer.close();
    if (redis) await redis.quit();
}

// src/services/wsPublisher.js — manages teacher WebSocket subscriptions and broadcasting
// This module is imported by ws-server.js and maintains a registry of connected teacher sockets.

/**
 * Registry structure:
 *   subscriptions: Map<sessionId, Map<studentId, Set<ws>>>
 * Each teacher socket is added to the sets matching the (sessionId, studentId) pairs it subscribes to.
 */
const subscriptions = new Map();

/**
 * Subscribe a teacher WebSocket to events for a specific session/student pair.
 */
export function subscribe(sessionId, studentId, ws) {
    if (!subscriptions.has(sessionId)) {
        subscriptions.set(sessionId, new Map());
    }
    const sessionMap = subscriptions.get(sessionId);
    if (!sessionMap.has(studentId)) {
        sessionMap.set(studentId, new Set());
    }
    sessionMap.get(studentId).add(ws);
}

/**
 * Unsubscribe a teacher socket from a specific session/student pair.
 */
export function unsubscribe(sessionId, studentId, ws) {
    const sessionMap = subscriptions.get(sessionId);
    if (!sessionMap) return;
    const studentSet = sessionMap.get(studentId);
    if (!studentSet) return;
    studentSet.delete(ws);
    if (studentSet.size === 0) sessionMap.delete(studentId);
    if (sessionMap.size === 0) subscriptions.delete(sessionId);
}

/**
 * Remove a teacher socket from ALL subscriptions (e.g. on disconnect).
 */
export function unsubscribeAll(ws) {
    for (const [sessionId, sessionMap] of subscriptions) {
        for (const [studentId, studentSet] of sessionMap) {
            studentSet.delete(ws);
            if (studentSet.size === 0) sessionMap.delete(studentId);
        }
        if (sessionMap.size === 0) subscriptions.delete(sessionId);
    }
}

/**
 * Broadcast a JSON message to all teacher sockets watching a given session/student.
 */
export function publish(sessionId, studentId, message) {
    const sessionMap = subscriptions.get(sessionId);
    if (!sessionMap) return;
    const studentSet = sessionMap.get(studentId);
    if (!studentSet) return;

    const payload = typeof message === 'string' ? message : JSON.stringify(message);

    for (const ws of studentSet) {
        if (ws.readyState === 1 /* WebSocket.OPEN */) {
            ws.send(payload);
        }
    }
}

/**
 * Broadcast to all teachers watching ANY student in a given session.
 */
export function publishToSession(sessionId, message) {
    const sessionMap = subscriptions.get(sessionId);
    if (!sessionMap) return;

    const payload = typeof message === 'string' ? message : JSON.stringify(message);
    const sent = new Set(); // avoid duplicate sends

    for (const studentSet of sessionMap.values()) {
        for (const ws of studentSet) {
            if (!sent.has(ws) && ws.readyState === 1) {
                ws.send(payload);
                sent.add(ws);
            }
        }
    }
}

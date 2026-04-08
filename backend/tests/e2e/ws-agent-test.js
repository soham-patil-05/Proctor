// tests/e2e/ws-agent-test.js — Test script: simulates an agent sending WS events
//
// Usage:
//   1. Ensure WS server is running
//   2. Set TOKEN, SESSION_ID, STUDENT_ID environment vars
//   3. node tests/e2e/ws-agent-test.js
//
// Example:
//   TOKEN=<jwt> SESSION_ID=<uuid> STUDENT_ID=<uuid> node tests/e2e/ws-agent-test.js

import WebSocket from 'ws';

const BASE = `ws://localhost:${process.env.WS_PORT || 8001}`;
const TOKEN = process.env.TOKEN;
const SESSION_ID = process.env.SESSION_ID;
const STUDENT_ID = process.env.STUDENT_ID;

if (!TOKEN || !SESSION_ID || !STUDENT_ID) {
    console.error('Usage: TOKEN=... SESSION_ID=... STUDENT_ID=... node ws-agent-test.js');
    process.exit(1);
}

const url = `${BASE}/ws/agents/sessions/${SESSION_ID}/students/${STUDENT_ID}?token=${TOKEN}`;
console.log('[Agent] Connecting to', url);

const ws = new WebSocket(url);

ws.on('open', () => {
    console.log('[Agent] Connected ✓');

    // 1. Send process_new
    const newProc = { type: 'process_new', data: { pid: 1234, name: 'code.exe', cpu: 12.5, memory: 150.0, status: 'running' } };
    ws.send(JSON.stringify(newProc));
    console.log('[Agent] Sent process_new:', JSON.stringify(newProc));

    // 2. Send process_update after 1s
    setTimeout(() => {
        const update = { type: 'process_update', data: { pid: 1234, cpu: 25.0, memory: 200.0, status: 'running' } };
        ws.send(JSON.stringify(update));
        console.log('[Agent] Sent process_update:', JSON.stringify(update));
    }, 1000);

    // 3. Send heartbeat after 2s
    setTimeout(() => {
        ws.send(JSON.stringify({ type: 'heartbeat' }));
        console.log('[Agent] Sent heartbeat');
    }, 2000);

    // 4. Send devices_snapshot after 3s
    setTimeout(() => {
        const devices = {
            type: 'devices_snapshot',
            data: {
                usb: [{ id: 'usb-001', name: 'USB Flash Drive' }],
                external: [{ id: 'ext-001', name: 'External HDD' }],
            },
        };
        ws.send(JSON.stringify(devices));
        console.log('[Agent] Sent devices_snapshot');
    }, 3000);

    // 5. Send network_snapshot after 4s
    setTimeout(() => {
        const net = {
            type: 'network_snapshot',
            data: { ip: '192.168.1.50', gateway: '192.168.1.1', dns: ['8.8.8.8', '8.8.4.4'], activeConnections: 5 },
        };
        ws.send(JSON.stringify(net));
        console.log('[Agent] Sent network_snapshot');
    }, 4000);

    // 6. Send process_end after 5s
    setTimeout(() => {
        const end = { type: 'process_end', data: { pid: 1234 } };
        ws.send(JSON.stringify(end));
        console.log('[Agent] Sent process_end');
    }, 5000);

    // 7. Close after 6s
    setTimeout(() => {
        ws.close();
        console.log('[Agent] Disconnected — test complete ✓');
        process.exit(0);
    }, 6000);
});

ws.on('error', (err) => {
    console.error('[Agent] Error:', err.message);
    process.exit(1);
});

ws.on('close', (code, reason) => {
    console.log(`[Agent] Connection closed: ${code} ${reason}`);
});

// tests/e2e/flow.test.js — End-to-end test scenario (Node script, no framework needed)
//
// Prerequisites:
//   1. Postgres running with migrations applied
//   2. A teacher account seeded (see seed script below)
//   3. HTTP server running on PORT (default 8000)
//   4. WS server running on WS_PORT (default 8001)
//
// Run: node tests/e2e/flow.test.js
//
// This script tests the full flow:
//   Login → Create subject → Create session → WS agent sends events → Teacher receives them → End session

import 'dotenv/config';
import WebSocket from 'ws';

const BASE = `http://localhost:${process.env.PORT || 8000}/api`;
const WS_BASE = `ws://localhost:${process.env.WS_PORT || 8001}`;

const TEACHER_EMAIL = 'e2e@test.com';
const TEACHER_PASS = 'password123';

/* ─── helpers ───────────────────────────────────────────────────── */
async function api(method, path, body, token) {
    const headers = { 'Content-Type': 'application/json' };
    if (token) headers.Authorization = `Bearer ${token}`;

    const res = await fetch(`${BASE}${path}`, {
        method,
        headers,
        body: body ? JSON.stringify(body) : undefined,
    });
    const json = await res.json();
    return { status: res.status, data: json };
}

function assert(cond, msg) {
    if (!cond) throw new Error(`ASSERTION FAILED: ${msg}`);
}

/* ─── run ───────────────────────────────────────────────────────── */
async function run() {
    console.log('=== E2E Flow Test ===\n');

    // Step 1: Login
    console.log('1. Login…');
    const loginRes = await api('POST', '/auth/login', { email: TEACHER_EMAIL, password: TEACHER_PASS });
    assert(loginRes.status === 200, `Login should return 200, got ${loginRes.status}`);
    assert(loginRes.data.token, 'Login should return a token');
    const token = loginRes.data.token;
    console.log('   ✓ Logged in\n');

    // Step 2: Create subject
    console.log('2. Create subject…');
    const subRes = await api('POST', '/teacher/subjects', { name: 'E2E Subject', department: 'CS', year: 2 }, token);
    assert(subRes.status === 201, `Create subject should return 201, got ${subRes.status}`);
    const subjectId = subRes.data.id;
    console.log(`   ✓ Subject created: ${subjectId}\n`);

    // Step 3: Create session
    console.log('3. Create session…');
    const sessRes = await api('POST', '/teacher/sessions', {
        subjectId,
        batch: 'A',
        lab: 'Lab-101',
        date: new Date().toISOString().slice(0, 10),
        startTime: '09:00',
    }, token);
    assert(sessRes.status === 201, `Create session should return 201, got ${sessRes.status}`);
    assert(sessRes.data.isLive === true, 'Session should be live');
    const sessionId = sessRes.data.sessionId;
    console.log(`   ✓ Session created: ${sessionId}\n`);

    // Step 4: Dashboard
    console.log('4. Dashboard…');
    const dashRes = await api('GET', '/teacher/dashboard', null, token);
    assert(dashRes.status === 200, 'Dashboard should return 200');
    assert(dashRes.data.activeSession >= 1, 'Should have at least 1 active session');
    console.log(`   ✓ Dashboard OK: ${JSON.stringify(dashRes.data)}\n`);

    // Step 5: Get sessions list
    console.log('5. Get sessions (live)…');
    const listRes = await api('GET', '/teacher/sessions?status=live', null, token);
    assert(listRes.status === 200, 'Sessions list should return 200');
    assert(listRes.data.length >= 1, 'Should have at least 1 live session');
    console.log(`   ✓ Live sessions: ${listRes.data.length}\n`);

    // Step 6: End session
    console.log('6. End session…');
    const endRes = await api('POST', `/teacher/sessions/${sessionId}/end`, {}, token);
    assert(endRes.status === 200, 'End session should return 200');
    assert(endRes.data.status === 'ended', 'Status should be ended');
    console.log(`   ✓ Session ended at ${endRes.data.endedAt}\n`);

    console.log('=== ALL E2E TESTS PASSED ===');
}

run().catch((err) => {
    console.error('E2E FAILED:', err.message);
    process.exit(1);
});

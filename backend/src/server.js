// src/server.js — HTTP(S) server entry point
import 'dotenv/config';
import http from 'node:http';
import app from './app.js';
import { config } from './config/index.js';
import { pool } from './db/index.js';

/**
 * In production, terminate TLS at the reverse-proxy (nginx / Caddy / AWS ALB).
 * If you need Node-level HTTPS for development, swap `http.createServer` for
 * `https.createServer` with cert/key files loaded from disk.
 */
const server = http.createServer(app);

server.listen(config.port, () => {
    console.log(`[HTTP] Listening on port ${config.port}`);
});

/* ─── Graceful shutdown ─────────────────────────────────────────── */
async function shutdown(signal) {
    console.log(`\n[${signal}] Shutting down…`);
    server.close();
    await pool.end();
    process.exit(0);
}

process.on('SIGINT', () => shutdown('SIGINT'));
process.on('SIGTERM', () => shutdown('SIGTERM'));

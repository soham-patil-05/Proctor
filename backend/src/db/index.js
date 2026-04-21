// src/db/index.js — Postgres pool + query helper
import pg from 'pg';
import { config } from '../config/index.js';

const { Pool } = pg;

export const pool = new Pool({
    connectionString: config.databaseUrl,
    ssl: { rejectUnauthorized: false },
    max: 20,
    idleTimeoutMillis: 30_000,
    connectionTimeoutMillis: 5_000,
});

pool.on('error', (err) => {
    console.error('[Postgres] Unexpected pool error:', err.message);
});

/**
 * Execute a parameterised query.
 * @param {string} text  SQL statement with $1,$2… placeholders
 * @param {any[]}  params  values
 * @returns {Promise<pg.QueryResult>}
 */
export async function query(text, params) {
    const start = Date.now();
    const result = await pool.query(text, params);
    const duration = Date.now() - start;
    if (duration > 500) {
        console.warn(`[DB] Slow query (${duration}ms):`, text.slice(0, 80));
    }
    return result;
}

/**
 * Grab a client for transactional work.
 */
export async function getClient() {
    const client = await pool.connect();
    return client;
}

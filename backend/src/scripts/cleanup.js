// src/scripts/cleanup.js — Delete monitoring rows older than 7 days (cron-friendly)
import 'dotenv/config';
import pg from 'pg';

const RETENTION_DAYS = 7;

async function cleanup() {
    const client = new pg.Client({ connectionString: process.env.DATABASE_URL });
    await client.connect();

    const cutoff = `now() - interval '${RETENTION_DAYS} days'`;

    const tables = [
        { table: 'live_processes', col: 'updated_at' },
        { table: 'connected_devices', col: 'connected_at' },
        { table: 'network_info', col: 'updated_at' },
        { table: 'terminal_events', col: 'detected_at' },
        { table: 'browser_history', col: 'last_visited' },
    ];

    for (const { table, col } of tables) {
        const sql = `DELETE FROM ${table} WHERE ${col} < ${cutoff}`;
        const result = await client.query(sql);
        console.log(`[Cleanup] ${table}: deleted ${result.rowCount} rows`);
    }

    // Clean up ended exam sessions older than retention
    const endedResult = await client.query(
        `DELETE FROM exam_sessions WHERE end_time IS NOT NULL AND end_time < EXTRACT(EPOCH FROM ${cutoff})`
    );
    console.log(`[Cleanup] exam_sessions (ended): deleted ${endedResult.rowCount} rows`);

    await client.end();
    console.log('[Cleanup] Done.');
}

cleanup().catch((err) => {
    console.error('[Cleanup] FAILED:', err);
    process.exit(1);
});

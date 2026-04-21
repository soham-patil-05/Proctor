// src/scripts/migrate.js — Run SQL migrations against the database (idempotent)
// Also cleans up duplicate and orphaned data before applying migrations.

import dotenv from 'dotenv';
import fs from 'node:fs';
import path from 'node:path';
import { fileURLToPath } from 'node:url';
import pg from 'pg';

const __dirname = path.dirname(fileURLToPath(import.meta.url));

dotenv.config({
  path: path.join(__dirname, '../../.env'),
});

if (!process.env.DATABASE_URL) {
  console.error('[Migrate] ERROR: DATABASE_URL is not defined.');
  process.exit(1);
}

// ---------------------------------------------------------------------------
// Helpers
// ---------------------------------------------------------------------------

// Returns true if a table exists in the public schema
async function tableExists(client, tableName) {
  const { rows } = await client.query(
    `SELECT 1 FROM information_schema.tables
     WHERE table_schema = 'public' AND table_name = $1`,
    [tableName]
  );
  return rows.length > 0;
}

// Returns the count of rows matching a query
async function rowCount(client, sql) {
  const { rows } = await client.query(sql);
  return parseInt(rows[0].cnt, 10);
}

// ---------------------------------------------------------------------------
// Cleanup — removes duplicates and orphaned rows that would block migrations.
// Every step is guarded so it is safe on a brand-new empty database.
// ---------------------------------------------------------------------------
async function cleanup(client) {
  console.log('[Cleanup] Starting data cleanup…');

  // ── 1. Duplicate subjects ───────────────────────────────────────────────
  // Old controller inserted a new subject row on every ingest with no
  // ON CONFLICT guard, leaving many (teacher_id, name) duplicates.
  // Keep only the oldest row per (teacher_id, name), delete the rest.
  if (await tableExists(client, 'subjects')) {
    const cnt = await rowCount(client, `
      SELECT COUNT(*) AS cnt FROM (
        SELECT teacher_id, name FROM subjects
        GROUP BY teacher_id, name HAVING COUNT(*) > 1
      ) t
    `);
    if (cnt > 0) {
      await client.query(`
        DELETE FROM subjects
        WHERE id NOT IN (
          SELECT DISTINCT ON (teacher_id, name) id
          FROM subjects
          ORDER BY teacher_id, name, created_at ASC
        )
      `);
      console.log(`[Cleanup] ✓ Removed ${cnt} duplicate subject group(s)`);
    } else {
      console.log('[Cleanup] No duplicate subjects found');
    }
  }

  // ── 2. Orphaned sessions ────────────────────────────────────────────────
  if (await tableExists(client, 'sessions') && await tableExists(client, 'subjects')) {
    const cnt = await rowCount(client, `
      SELECT COUNT(*) AS cnt FROM sessions s
      WHERE NOT EXISTS (SELECT 1 FROM subjects sub WHERE sub.id = s.subject_id)
    `);
    if (cnt > 0) {
      await client.query(`DELETE FROM sessions WHERE subject_id NOT IN (SELECT id FROM subjects)`);
      console.log(`[Cleanup] ✓ Removed ${cnt} orphaned session(s)`);
    } else {
      console.log('[Cleanup] No orphaned sessions found');
    }
  }

  // ── 3. Orphaned session_students ────────────────────────────────────────
  if (await tableExists(client, 'session_students')) {
    const cnt = await rowCount(client, `
      SELECT COUNT(*) AS cnt FROM session_students ss
      WHERE NOT EXISTS (SELECT 1 FROM sessions s WHERE s.id = ss.session_id)
         OR NOT EXISTS (SELECT 1 FROM students st WHERE st.id = ss.student_id)
    `);
    if (cnt > 0) {
      await client.query(`
        DELETE FROM session_students
        WHERE session_id NOT IN (SELECT id FROM sessions)
           OR student_id NOT IN (SELECT id FROM students)
      `);
      console.log(`[Cleanup] ✓ Removed ${cnt} orphaned session_students row(s)`);
    } else {
      console.log('[Cleanup] No orphaned session_students found');
    }
  }

  // ── 4. Orphaned connected_devices ──────────────────────────────────────
  if (await tableExists(client, 'connected_devices')) {
    const cnt = await rowCount(client, `
      SELECT COUNT(*) AS cnt FROM connected_devices cd
      WHERE NOT EXISTS (SELECT 1 FROM sessions s WHERE s.id = cd.session_id)
         OR NOT EXISTS (SELECT 1 FROM students st WHERE st.id = cd.student_id)
    `);
    if (cnt > 0) {
      await client.query(`
        DELETE FROM connected_devices
        WHERE session_id NOT IN (SELECT id FROM sessions)
           OR student_id NOT IN (SELECT id FROM students)
      `);
      console.log(`[Cleanup] ✓ Removed ${cnt} orphaned connected_devices row(s)`);
    } else {
      console.log('[Cleanup] No orphaned connected_devices found');
    }
  }

  // ── 5. Orphaned live_processes ──────────────────────────────────────────
  if (await tableExists(client, 'live_processes')) {
    const cnt = await rowCount(client, `
      SELECT COUNT(*) AS cnt FROM live_processes lp
      WHERE NOT EXISTS (SELECT 1 FROM sessions s WHERE s.id = lp.session_id)
         OR NOT EXISTS (SELECT 1 FROM students st WHERE st.id = lp.student_id)
    `);
    if (cnt > 0) {
      await client.query(`
        DELETE FROM live_processes
        WHERE session_id NOT IN (SELECT id FROM sessions)
           OR student_id NOT IN (SELECT id FROM students)
      `);
      console.log(`[Cleanup] ✓ Removed ${cnt} orphaned live_processes row(s)`);
    } else {
      console.log('[Cleanup] No orphaned live_processes found');
    }
  }

  // ── 6. Orphaned terminal_events ─────────────────────────────────────────
  if (await tableExists(client, 'terminal_events')) {
    const cnt = await rowCount(client, `
      SELECT COUNT(*) AS cnt FROM terminal_events te
      WHERE NOT EXISTS (SELECT 1 FROM sessions s WHERE s.id = te.session_id)
         OR NOT EXISTS (SELECT 1 FROM students st WHERE st.id = te.student_id)
    `);
    if (cnt > 0) {
      await client.query(`
        DELETE FROM terminal_events
        WHERE session_id NOT IN (SELECT id FROM sessions)
           OR student_id NOT IN (SELECT id FROM students)
      `);
      console.log(`[Cleanup] ✓ Removed ${cnt} orphaned terminal_events row(s)`);
    } else {
      console.log('[Cleanup] No orphaned terminal_events found');
    }
  }

  // ── 7. Orphaned browser_history (session_id stored as TEXT) ────────────
  if (await tableExists(client, 'browser_history')) {
    const cnt = await rowCount(client, `
      SELECT COUNT(*) AS cnt FROM browser_history bh
      WHERE NOT EXISTS (
        SELECT 1 FROM sessions s WHERE s.id::text = bh.session_id
      )
    `);
    if (cnt > 0) {
      await client.query(`
        DELETE FROM browser_history
        WHERE session_id NOT IN (SELECT id::text FROM sessions)
      `);
      console.log(`[Cleanup] ✓ Removed ${cnt} orphaned browser_history row(s)`);
    } else {
      console.log('[Cleanup] No orphaned browser_history found');
    }
  }

  // ── 8. Orphaned domain_activity ─────────────────────────────────────────
  if (await tableExists(client, 'domain_activity')) {
    const cnt = await rowCount(client, `
      SELECT COUNT(*) AS cnt FROM domain_activity da
      WHERE NOT EXISTS (SELECT 1 FROM sessions s WHERE s.id = da.session_id)
         OR NOT EXISTS (SELECT 1 FROM students st WHERE st.id = da.student_id)
    `);
    if (cnt > 0) {
      await client.query(`
        DELETE FROM domain_activity
        WHERE session_id NOT IN (SELECT id FROM sessions)
           OR student_id NOT IN (SELECT id FROM students)
      `);
      console.log(`[Cleanup] ✓ Removed ${cnt} orphaned domain_activity row(s)`);
    } else {
      console.log('[Cleanup] No orphaned domain_activity found');
    }
  }

  // ── 9. Orphaned network_info ────────────────────────────────────────────
  if (await tableExists(client, 'network_info')) {
    const cnt = await rowCount(client, `
      SELECT COUNT(*) AS cnt FROM network_info ni
      WHERE NOT EXISTS (SELECT 1 FROM sessions s WHERE s.id = ni.session_id)
         OR NOT EXISTS (SELECT 1 FROM students st WHERE st.id = ni.student_id)
    `);
    if (cnt > 0) {
      await client.query(`
        DELETE FROM network_info
        WHERE session_id NOT IN (SELECT id FROM sessions)
           OR student_id NOT IN (SELECT id FROM students)
      `);
      console.log(`[Cleanup] ✓ Removed ${cnt} orphaned network_info row(s)`);
    } else {
      console.log('[Cleanup] No orphaned network_info found');
    }
  }

  console.log('[Cleanup] Done.\n');
}

// ---------------------------------------------------------------------------
// Migration runner
// ---------------------------------------------------------------------------
async function migrate() {
  console.log('[Migrate] Starting migration run.');

  const client = new pg.Client({
    connectionString: process.env.DATABASE_URL,
    ssl: { rejectUnauthorized: false },
  });

  await client.connect();
  console.log('[Migrate] Connected to database.\n');

  // Cleanup before migrations so constraint additions never fail on dirty data
  await cleanup(client);

  // Create a tracking table so each SQL file is only ever run once
  await client.query(`
    CREATE TABLE IF NOT EXISTS _migrations (
      filename   TEXT PRIMARY KEY,
      applied_at TIMESTAMPTZ NOT NULL DEFAULT now()
    )
  `);

  const migrationsDir = path.join(__dirname, '..', 'db', 'migrations');

  const files = fs
    .readdirSync(migrationsDir)
    .filter((f) => f.endsWith('.sql'))
    .sort();

  for (const file of files) {
    const { rows } = await client.query(
      'SELECT filename FROM _migrations WHERE filename = $1',
      [file]
    );

    if (rows.length > 0) {
      console.log(`[Migrate] Skipping ${file} (already applied)`);
      continue;
    }

    const filePath = path.join(migrationsDir, file);
    const sql = fs.readFileSync(filePath, 'utf-8');

    console.log(`[Migrate] Running ${file}…`);
    await client.query(sql);

    await client.query('INSERT INTO _migrations (filename) VALUES ($1)', [file]);
    console.log(`[Migrate] ✓ ${file}`);
  }

  await client.end();
  console.log('\n[Migrate] All done.');
}

migrate().catch((err) => {
  console.error('[Migrate] FAILED:', err.message);
  process.exit(1);
});
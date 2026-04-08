// src/scripts/migrate.js — Run SQL migrations against the database

import dotenv from 'dotenv';
import fs from 'node:fs';
import path from 'node:path';
import { fileURLToPath } from 'node:url';
import pg from 'pg';

const __dirname = path.dirname(fileURLToPath(import.meta.url));

// Explicitly load .env from backend root (2 levels up from src/scripts)
dotenv.config({
  path: path.join(__dirname, '../../.env'),
});

// Fail fast if DATABASE_URL is missing
if (!process.env.DATABASE_URL) {
  console.error('[Migrate] ERROR: DATABASE_URL is not defined.');
  process.exit(1);
}

async function migrate() {
  console.log('[Migrate] Using DB:', process.env.DATABASE_URL);

  const client = new pg.Client({
    connectionString: process.env.DATABASE_URL,
  });

  await client.connect();
  console.log('[Migrate] Connected to database.');

  const migrationsDir = path.join(__dirname, '..', 'db', 'migrations');

  const files = fs
    .readdirSync(migrationsDir)
    .filter((f) => f.endsWith('.sql'))
    .sort();

  for (const file of files) {
    const filePath = path.join(migrationsDir, file);
    const sql = fs.readFileSync(filePath, 'utf-8');

    console.log(`[Migrate] Running ${file}…`);
    await client.query(sql);
    console.log(`[Migrate] ✓ ${file}`);
  }

  await client.end();
  console.log('[Migrate] Done.');
}

migrate().catch((err) => {
  console.error('[Migrate] FAILED:', err);
  process.exit(1);
});
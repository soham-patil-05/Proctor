// src/config/index.js — centralised configuration
import 'dotenv/config';

/* ─── env helpers ───────────────────────────────────────────────── */
const env = (key, fallback) => process.env[key] ?? fallback;

export const config = Object.freeze({
  port:        parseInt(env('PORT', '8000'), 10),
  databaseUrl: env('DATABASE_URL', 'postgres://postgres:password@localhost:5432/lab_guardian'),
});

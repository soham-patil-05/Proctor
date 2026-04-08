// src/config/index.js — centralised configuration and Redis client
import 'dotenv/config';
import { createClient } from 'redis';

/* ─── env helpers ───────────────────────────────────────────────── */
const env = (key, fallback) => process.env[key] ?? fallback;

export const config = Object.freeze({
  port:        parseInt(env('PORT', '8000'), 10),
  wsPort:      parseInt(env('WS_PORT', '8001'), 10),
  databaseUrl: env('DATABASE_URL', 'postgres://postgres:password@localhost:5432/lab_monitor'),
  redisUrl:    env('REDIS_URL', 'redis://localhost:6379'),
  jwtSecret:   env('JWT_SECRET', 'replace_with_secure_secret'),
  jwtExpiresIn: env('JWT_EXPIRES_IN', '8h'),
});

/* ─── Redis client (lazy singleton) ─────────────────────────────── */
let _redis = null;

export async function getRedis() {
  if (_redis) return _redis;
  try {
    _redis = createClient({ url: config.redisUrl });
    _redis.on('error', (err) => console.error('[Redis]', err.message));
    await _redis.connect();
    console.log('[Redis] Connected');
    return _redis;
  } catch (err) {
    console.warn('[Redis] Unavailable — falling back to in-memory:', err.message);
    return null;
  }
}

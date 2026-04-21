// src/config/index.js — centralised configuration
import 'dotenv/config';

if (!process.env.DATABASE_URL) {
  throw new Error('DATABASE_URL environment variable is required');
}

export const config = Object.freeze({
  port: process.env.PORT || 8000,
  databaseUrl: process.env.DATABASE_URL,
});

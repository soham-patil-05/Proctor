// src/app.js — Express application setup
// Offline-first Lab Guardian backend
import express from 'express';
import cors from 'cors';
import syncRoutes from './routes/sync.js';
import { errorHandler } from './middleware/errorHandler.js';

const app = express();

/* ─── Security headers ──────────────────────────────────────────── */
app.disable('x-powered-by');

/* ─── CORS configuration ───────────────────────────────────────── */
// Allow all origins for offline-first architecture (agents can be anywhere)
const ALLOWED_ORIGINS = process.env.CORS_ORIGINS
  ? process.env.CORS_ORIGINS.split(',').map(o => o.trim())
  : '*';

app.use(cors({
  origin: ALLOWED_ORIGINS,
  credentials: true,
  maxAge: 86400, // preflight cache 24 h
}));

app.use(express.json({ limit: '10mb' })); // Increased limit for batch uploads

/* ─── Health check ──────────────────────────────────────────────── */
app.get('/api/health', (_req, res) => res.json({ status: 'ok' }));

/* ─── Routes ────────────────────────────────────────────────────── */
// Offline-first sync and dashboard routes (no auth required)
app.use('/api', syncRoutes);

/* ─── 404 fallback ──────────────────────────────────────────────── */
app.use((_req, res) => res.status(404).json({ error: 'Not found' }));

/* ─── Error handler (must be last) ──────────────────────────────── */
app.use(errorHandler);

export default app;

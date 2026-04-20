// src/app.js — Express application setup
import express from 'express';
import cors from 'cors';
import telemetryRoutes from './routes/telemetry.js';
import { errorHandler } from './middleware/errorHandler.js';

const app = express();

/* ─── Security headers ──────────────────────────────────────────── */
app.disable('x-powered-by');

/* ─── CORS configuration ───────────────────────────────────────── */
app.use(cors());
app.options('*', cors());

app.use(express.json({ limit: '1mb' }));

/* ─── Health check ──────────────────────────────────────────────── */
app.get('/api/health', (_req, res) => res.json({ status: 'ok' }));

/* ─── Routes ────────────────────────────────────────────────────── */
app.use('/api/telemetry', telemetryRoutes);

/* ─── 404 fallback ──────────────────────────────────────────────── */
app.use((_req, res) => res.status(404).json({ error: 'Not found' }));

/* ─── Error handler (must be last) ──────────────────────────────── */
app.use(errorHandler);

export default app;

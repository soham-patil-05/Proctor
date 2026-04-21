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

// FIX: Increased from 1mb to 10mb — browser history payloads from active lab
// sessions can easily exceed 1mb (hundreds of URLs × title + metadata).
// A payload over the limit returns a silent 413 that Express converts to a 500
// in some error-handler configurations.
app.use(express.json({ limit: '10mb' }));

/* ─── Health check ──────────────────────────────────────────────── */
app.get('/api/health', (_req, res) => res.json({ status: 'ok' }));

/* ─── Routes ────────────────────────────────────────────────────── */
app.use('/api/telemetry', telemetryRoutes);

/* ─── 404 fallback ──────────────────────────────────────────────── */
app.use((_req, res) => res.status(404).json({ error: 'Not found' }));

/* ─── Error handler (must be last) ──────────────────────────────── */
app.use(errorHandler);

export default app;

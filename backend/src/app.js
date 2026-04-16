// src/app.js — Express application setup
// Updated: Added sync routes for offline-first architecture
import express from 'express';
import cors from 'cors';
import authRoutes from './routes/auth.js';
import subjectRoutes from './routes/subjects.js';
import sessionRoutes from './routes/sessions.js';
import studentRoutes from './routes/students.js';
import dashboardRoutes from './routes/dashboard.js';
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
// Public routes (no auth required)
app.use('/api', syncRoutes);  // Sync and dashboard routes

// Legacy routes (keeping for backward compatibility)
app.use('/api/auth', authRoutes);
app.use('/api/students', studentRoutes);  // public: /join-session
app.use('/api/teacher/subjects', subjectRoutes);
app.use('/api/teacher/sessions', sessionRoutes);
app.use('/api/teacher', studentRoutes);   // mounts /sessions/:id/students/* and /students/*
app.use('/api/teacher/dashboard', dashboardRoutes);

/* ─── 404 fallback ──────────────────────────────────────────────── */
app.use((_req, res) => res.status(404).json({ error: 'Not found' }));

/* ─── Error handler (must be last) ──────────────────────────────── */
app.use(errorHandler);

export default app;

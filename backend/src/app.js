// src/app.js — Express application setup
import express from 'express';
import cors from 'cors';
import authRoutes from './routes/auth.js';
import subjectRoutes from './routes/subjects.js';
import sessionRoutes from './routes/sessions.js';
import studentRoutes from './routes/students.js';
import dashboardRoutes from './routes/dashboard.js';
import { errorHandler } from './middleware/errorHandler.js';

const app = express();

/* ─── Security headers ──────────────────────────────────────────── */
app.disable('x-powered-by');

/* ─── CORS configuration ───────────────────────────────────────── */
const ALLOWED_ORIGINS = process.env.CORS_ORIGINS
  ? process.env.CORS_ORIGINS.split(',').map(o => o.trim())
  : ['http://localhost:5173', 'http://localhost:3000'];

app.use(cors({
  origin(origin, cb) {
    // Allow requests with no origin (curl, agents, server-to-server)
    if (!origin || ALLOWED_ORIGINS.includes(origin)) return cb(null, true);
    cb(new Error('CORS: origin not allowed'));
  },
  credentials: true,
  maxAge: 86400, // preflight cache 24 h
}));

app.use(express.json({ limit: '1mb' }));

/* ─── Health check ──────────────────────────────────────────────── */
app.get('/api/health', (_req, res) => res.json({ status: 'ok' }));

/* ─── Routes ────────────────────────────────────────────────────── */
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

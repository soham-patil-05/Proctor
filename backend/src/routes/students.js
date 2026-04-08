// src/routes/students.js
import { Router } from 'express';
import { authenticate } from '../middleware/auth.js';
import {
    joinSession,
    getSessionStudents,
    getStudentProfile,
    getStudentDevices,
    getStudentNetwork,
    getStudentProcesses,
    getStudentDomainActivity,
} from '../controllers/studentsController.js';
import { asyncHandler } from '../utils/helpers.js';

const router = Router();

// ─── Public (no auth) ─────────────────────────────────────────────
router.post('/join-session', asyncHandler(joinSession));

// ─── Protected (teacher JWT) ──────────────────────────────────────
router.use(authenticate);

// Session-scoped student lists
router.get('/sessions/:sessionId/students', asyncHandler(getSessionStudents));
router.get('/sessions/:sessionId/students/:rollNo/processes', asyncHandler(getStudentProcesses));

// Student profile / devices / network
router.get('/students/:rollNo', asyncHandler(getStudentProfile));
router.get('/students/:rollNo/devices', asyncHandler(getStudentDevices));
router.get('/students/:rollNo/network', asyncHandler(getStudentNetwork));
router.get('/students/:rollNo/domain-activity', asyncHandler(getStudentDomainActivity));

export default router;

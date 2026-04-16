// routes/sync.js - Routes for offline-first log sync and dashboard

import { Router } from 'express';
import {
    receiveLogs,
    getDashboardStudents,
    getStudentDetails,
    endAllSessions
} from '../controllers/syncController.js';

const router = Router();

/**
 * Log receiving endpoint
 * POST /api/logs/receive
 */
router.post('/logs/receive', receiveLogs);

/**
 * Dashboard endpoints (no auth)
 */
router.get('/dashboard/students', getDashboardStudents);
router.get('/dashboard/student/:sessionId', getStudentDetails);

/**
 * Exam management
 */
router.post('/exam/end-all', endAllSessions);

export default router;

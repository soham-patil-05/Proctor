// src/routes/sessions.js
import { Router } from 'express';
import { authenticate } from '../middleware/auth.js';
import {
    createSession,
    getSessions,
    getSession,
    endSession,
} from '../controllers/sessionsController.js';
import { asyncHandler } from '../utils/helpers.js';

const router = Router();

router.use(authenticate);

router.post('/', asyncHandler(createSession));
router.get('/', asyncHandler(getSessions));
router.get('/:sessionId', asyncHandler(getSession));
router.post('/:sessionId/end', asyncHandler(endSession));

export default router;

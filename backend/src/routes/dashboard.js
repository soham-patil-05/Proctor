// src/routes/dashboard.js
import { Router } from 'express';
import { authenticate } from '../middleware/auth.js';
import { getDashboard } from '../controllers/dashboardController.js';
import { asyncHandler } from '../utils/helpers.js';

const router = Router();

router.use(authenticate);

router.get('/', asyncHandler(getDashboard));

export default router;

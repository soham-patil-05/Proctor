// src/routes/subjects.js
import { Router } from 'express';
import { authenticate } from '../middleware/auth.js';
import { getSubjects, createSubject } from '../controllers/subjectsController.js';
import { asyncHandler } from '../utils/helpers.js';

const router = Router();

router.use(authenticate);

router.get('/', asyncHandler(getSubjects));
router.post('/', asyncHandler(createSubject));

export default router;

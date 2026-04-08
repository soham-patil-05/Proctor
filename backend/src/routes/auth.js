// src/routes/auth.js
import { Router } from 'express';
import { login, logout ,register} from '../controllers/authController.js';
import { asyncHandler } from '../utils/helpers.js';

const router = Router();

router.post('/login', asyncHandler(login));
router.post('/register',asyncHandler(register));
router.post('/logout', asyncHandler(logout));

export default router;

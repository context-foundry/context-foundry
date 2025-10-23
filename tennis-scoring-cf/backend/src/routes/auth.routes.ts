import { Router } from 'express';
import * as authController from '../controllers/auth.controller';
import { registerValidation, loginValidation, refreshValidation } from '../validators/auth.validator';
import { validateRequest } from '../middleware/validate.middleware';
import { authMiddleware } from '../middleware/auth.middleware';
import { authLimiter } from '../middleware/rateLimit.middleware';

const router = Router();

// Public routes
router.post('/register', authLimiter, validateRequest(registerValidation), authController.register);
router.post('/login', authLimiter, validateRequest(loginValidation), authController.login);
router.post('/refresh', validateRequest(refreshValidation), authController.refresh);

// Protected routes
router.post('/logout', authMiddleware, authController.logout);
router.get('/me', authMiddleware, authController.me);

export default router;

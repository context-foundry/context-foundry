import { Router } from 'express';
import * as scoreController from '../controllers/score.controller';
import { recordPointValidation, matchActionValidation } from '../validators/score.validator';
import { validateRequest } from '../middleware/validate.middleware';
import { authMiddleware } from '../middleware/auth.middleware';
import { requireCoach } from '../middleware/role.middleware';
import { scoreLimiter } from '../middleware/rateLimit.middleware';

const router = Router();

// All score routes require coach authentication
router.post('/:id/start', authMiddleware, requireCoach, validateRequest(matchActionValidation), scoreController.startMatch);
router.post('/:id/point', authMiddleware, requireCoach, scoreLimiter, validateRequest(recordPointValidation), scoreController.recordPoint);
router.post('/:id/complete', authMiddleware, requireCoach, validateRequest(matchActionValidation), scoreController.completeMatch);

export default router;

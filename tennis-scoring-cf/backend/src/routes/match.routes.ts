import { Router } from 'express';
import * as matchController from '../controllers/match.controller';
import {
  createMatchValidation,
  updateMatchValidation,
  matchIdValidation,
  matchFilterValidation,
} from '../validators/match.validator';
import { validateRequest } from '../middleware/validate.middleware';
import { authMiddleware } from '../middleware/auth.middleware';
import { requireCoach } from '../middleware/role.middleware';

const router = Router();

// Public routes
router.get('/', validateRequest(matchFilterValidation), matchController.getAllMatches);
router.get('/:id', validateRequest(matchIdValidation), matchController.getMatchById);
router.get('/:id/history', validateRequest(matchIdValidation), matchController.getMatchHistory);

// Protected routes (coaches only)
router.post('/', authMiddleware, requireCoach, validateRequest(createMatchValidation), matchController.createMatch);
router.put('/:id', authMiddleware, requireCoach, validateRequest(updateMatchValidation), matchController.updateMatch);
router.delete('/:id', authMiddleware, requireCoach, validateRequest(matchIdValidation), matchController.deleteMatch);

export default router;

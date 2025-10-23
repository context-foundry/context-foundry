import { body, param, query } from 'express-validator';

/**
 * Validation rules for creating a match
 */
export const createMatchValidation = [
  body('player1Name')
    .notEmpty()
    .withMessage('Player 1 name is required')
    .isLength({ max: 255 })
    .withMessage('Player 1 name must not exceed 255 characters'),
  body('player2Name')
    .notEmpty()
    .withMessage('Player 2 name is required')
    .isLength({ max: 255 })
    .withMessage('Player 2 name must not exceed 255 characters'),
  body('player3Name')
    .optional()
    .isLength({ max: 255 })
    .withMessage('Player 3 name must not exceed 255 characters'),
  body('player4Name')
    .optional()
    .isLength({ max: 255 })
    .withMessage('Player 4 name must not exceed 255 characters'),
  body('matchType')
    .isIn(['singles', 'doubles'])
    .withMessage('Match type must be either singles or doubles'),
  body('format')
    .isIn(['best_of_3', 'best_of_5'])
    .withMessage('Format must be either best_of_3 or best_of_5'),
  body('location')
    .optional()
    .isLength({ max: 255 })
    .withMessage('Location must not exceed 255 characters'),
  body('scheduledAt')
    .optional()
    .isISO8601()
    .withMessage('Scheduled time must be a valid date'),
];

/**
 * Validation rules for updating a match
 */
export const updateMatchValidation = [
  param('id')
    .isInt({ min: 1 })
    .withMessage('Match ID must be a positive integer'),
  body('location')
    .optional()
    .isLength({ max: 255 })
    .withMessage('Location must not exceed 255 characters'),
  body('scheduledAt')
    .optional()
    .isISO8601()
    .withMessage('Scheduled time must be a valid date'),
  body('status')
    .optional()
    .isIn(['scheduled', 'in_progress', 'completed', 'cancelled'])
    .withMessage('Status must be scheduled, in_progress, completed, or cancelled'),
];

/**
 * Validation rules for match ID parameter
 */
export const matchIdValidation = [
  param('id')
    .isInt({ min: 1 })
    .withMessage('Match ID must be a positive integer'),
];

/**
 * Validation rules for match filtering
 */
export const matchFilterValidation = [
  query('status')
    .optional()
    .isIn(['scheduled', 'in_progress', 'completed', 'cancelled'])
    .withMessage('Status must be scheduled, in_progress, completed, or cancelled'),
  query('page')
    .optional()
    .isInt({ min: 1 })
    .withMessage('Page must be a positive integer'),
  query('limit')
    .optional()
    .isInt({ min: 1, max: 100 })
    .withMessage('Limit must be between 1 and 100'),
  query('search')
    .optional()
    .isLength({ max: 255 })
    .withMessage('Search term must not exceed 255 characters'),
  query('date')
    .optional()
    .isISO8601()
    .withMessage('Date must be a valid date'),
];

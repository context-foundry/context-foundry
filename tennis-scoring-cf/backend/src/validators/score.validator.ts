import { body, param } from 'express-validator';

/**
 * Validation rules for recording a point
 */
export const recordPointValidation = [
  param('id')
    .isInt({ min: 1 })
    .withMessage('Match ID must be a positive integer'),
  body('winner')
    .isIn([1, 2])
    .withMessage('Winner must be either 1 or 2'),
];

/**
 * Validation rules for match actions (start, complete)
 */
export const matchActionValidation = [
  param('id')
    .isInt({ min: 1 })
    .withMessage('Match ID must be a positive integer'),
];

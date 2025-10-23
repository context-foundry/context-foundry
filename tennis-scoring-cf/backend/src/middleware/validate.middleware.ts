import { Request, Response, NextFunction } from 'express';
import { validationResult, ValidationChain } from 'express-validator';
import { sendError } from '../utils/response.util';

/**
 * Validation middleware - Check express-validator results
 */
export function validate(req: Request, res: Response, next: NextFunction): void {
  const errors = validationResult(req);

  if (!errors.isEmpty()) {
    sendError(
      res,
      'VALIDATION_ERROR',
      'Validation failed',
      400,
      errors.array()
    );
    return;
  }

  next();
}

/**
 * Helper to run validation chains
 */
export function validateRequest(validations: ValidationChain[]) {
  return async (req: Request, res: Response, next: NextFunction) => {
    // Run all validations
    await Promise.all(validations.map(validation => validation.run(req)));

    // Check for errors
    const errors = validationResult(req);
    if (!errors.isEmpty()) {
      sendError(
        res,
        'VALIDATION_ERROR',
        'Validation failed',
        400,
        errors.array()
      );
      return;
    }

    next();
  };
}

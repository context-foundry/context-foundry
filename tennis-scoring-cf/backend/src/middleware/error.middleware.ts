import { Request, Response, NextFunction } from 'express';
import { sendError } from '../utils/response.util';

/**
 * Global error handling middleware
 */
export function errorMiddleware(
  err: any,
  req: Request,
  res: Response,
  next: NextFunction
): void {
  console.error('Error:', err);

  // Default error
  let statusCode = 500;
  let code = 'INTERNAL_SERVER_ERROR';
  let message = 'An unexpected error occurred';

  // Handle specific error types
  if (err.message) {
    message = err.message;
  }

  // Handle known errors
  if (err.statusCode) {
    statusCode = err.statusCode;
  }

  if (err.code) {
    code = err.code;
  }

  // Database errors
  if (err.code === '23505') {
    // Unique violation
    statusCode = 409;
    code = 'DUPLICATE_ENTRY';
    message = 'Resource already exists';
  } else if (err.code === '23503') {
    // Foreign key violation
    statusCode = 400;
    code = 'INVALID_REFERENCE';
    message = 'Referenced resource does not exist';
  } else if (err.code === '23502') {
    // Not null violation
    statusCode = 400;
    code = 'MISSING_REQUIRED_FIELD';
    message = 'Required field is missing';
  }

  sendError(res, code, message, statusCode);
}

/**
 * 404 Not Found handler
 */
export function notFoundMiddleware(req: Request, res: Response): void {
  sendError(res, 'NOT_FOUND', `Route ${req.originalUrl} not found`, 404);
}

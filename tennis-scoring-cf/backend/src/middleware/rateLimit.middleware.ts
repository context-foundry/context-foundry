import rateLimit from 'express-rate-limit';
import { Request, Response, NextFunction } from 'express';

// Bypass rate limiting in development mode
const isDevelopment = process.env.NODE_ENV === 'development';

// No-op middleware for development
const devLimiter = (req: Request, res: Response, next: NextFunction) => next();

/**
 * General API rate limiter
 */
export const generalLimiter = isDevelopment ? devLimiter : rateLimit({
  windowMs: 15 * 60 * 1000, // 15 minutes
  max: 100, // Limit each IP to 100 requests per windowMs
  message: {
    success: false,
    error: {
      code: 'RATE_LIMIT_EXCEEDED',
      message: 'Too many requests, please try again later',
    },
  },
  standardHeaders: true,
  legacyHeaders: false,
});

/**
 * Strict rate limiter for auth endpoints
 */
export const authLimiter = isDevelopment ? devLimiter : rateLimit({
  windowMs: 15 * 60 * 1000, // 15 minutes
  max: 5, // Limit each IP to 5 requests per windowMs
  message: {
    success: false,
    error: {
      code: 'RATE_LIMIT_EXCEEDED',
      message: 'Too many authentication attempts, please try again later',
    },
  },
  standardHeaders: true,
  legacyHeaders: false,
  skipSuccessfulRequests: true, // Don't count successful requests
});

/**
 * Score recording rate limiter
 */
export const scoreLimiter = isDevelopment ? devLimiter : rateLimit({
  windowMs: 60 * 1000, // 1 minute
  max: 60, // Limit each IP to 60 requests per minute (1 per second)
  message: {
    success: false,
    error: {
      code: 'RATE_LIMIT_EXCEEDED',
      message: 'Too many score updates, please slow down',
    },
  },
  standardHeaders: true,
  legacyHeaders: false,
});
